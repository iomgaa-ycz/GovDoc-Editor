"""管道 B：审核点 + 招标文书 -> 工作底稿（逐点编排）。

设计基线：docs/design.md §10。
每个 AuditPointRun 对应一个独立 workspace，失败点可单独重试。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import sqlite3
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from scrivai import WorkspaceSpec
from sqlmodel import Session
from sqlmodel import select

from govdoc.db.models import (
    AuditPointRun,
    AuditRun,
    CheckpointFinal,
    Document,
    WorkpaperDraft,
)
from govdoc.pipelines.common import attach_workspace_output, dump_phase_usage, load_result_payload
from govdoc.pipelines.pes_overrides import GovDocMockAuditorPES
from govdoc.pipelines.summary import generate_summary
from govdoc.runtime import (
    build_gov_auditor_pes,
    get_config,
    get_gov_auditor_config,
    get_project_root,
    get_qmd,
    get_trajectory_store,
    get_workspace_manager,
)
from govdoc.schemas import GovCheckpoint, GovFinding, Workpaper, WorkpaperAuditOutput
from govdoc.testing_support import load_mock_replay, seed_working_tree
from govdoc.workpaper_renderer import render_workpaper_docx

logger = logging.getLogger(__name__)


def _match_finding_by_checkpoint_id(
    findings: list[dict[str, Any]], checkpoint_id: str
) -> dict[str, Any] | None:
    """从 findings 列表中找到匹配 checkpoint ID 的 finding。"""
    for f in findings:
        cp = f.get("checkpoint", {})
        if isinstance(cp, dict) and cp.get("id") == checkpoint_id:
            return f
    return None


def write_single_checkpoint_json(audit_run_id: str, checkpoint: GovCheckpoint) -> Path:
    """将单个 checkpoint 写为临时 JSON 文件，供 workspace data_inputs 使用。"""
    import tempfile

    tmp = tempfile.mkdtemp(prefix=f"audit_{audit_run_id}_")
    path = Path(tmp) / "checkpoints.json"
    path.write_text(
        json.dumps([checkpoint.model_dump(mode="json")], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def write_documents_manifest_json(
    audit_run_id: str,
    manifest: list[dict[str, str]],
) -> Path:
    """将本次审核输入文档说明写为临时 JSON 文件，供 workspace data_inputs 使用。"""
    import tempfile

    tmp = tempfile.mkdtemp(prefix=f"audit_{audit_run_id}_")
    path = Path(tmp) / "documents.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def count_processed_points(session: Session, audit_run_id: str) -> int:
    """统计已完成的 AuditPointRun 数量。"""
    runs = session.exec(
        select(AuditPointRun).where(
            AuditPointRun.audit_run_id == audit_run_id,
            AuditPointRun.status == "completed",
        )
    ).all()
    return len(runs)


def _update_heartbeat(audit_run: AuditRun, session: Session) -> None:
    """更新 AuditRun 心跳时间。"""
    audit_run.heartbeat_at = datetime.utcnow()
    session.add(audit_run)
    session.commit()


def _delete_trajectory_run(store: Any, run_id: str) -> None:
    """删除指定 run 的 trajectory 数据，供单点重试复用同一 run_id。"""

    delete_run = getattr(store, "delete_run", None)
    if callable(delete_run):
        delete_run(run_id)
        return

    def _work(conn: Any) -> None:
        conn.execute(
            """
            DELETE FROM tool_calls
            WHERE turn_id IN (
                SELECT turn_id
                FROM turns
                WHERE phase_id IN (
                    SELECT phase_id FROM phases WHERE run_id = ?
                )
            )
            """,
            (run_id,),
        )
        conn.execute(
            "DELETE FROM turns WHERE phase_id IN (SELECT phase_id FROM phases WHERE run_id = ?)",
            (run_id,),
        )
        conn.execute("DELETE FROM feedback WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM phases WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))

    execute_with_retry = getattr(store, "_execute_with_retry", None)
    if callable(execute_with_retry):
        execute_with_retry(_work)
        return

    db_path = getattr(store, "db_path", None)
    if db_path in (None, ":memory:"):
        raise RuntimeError("TrajectoryStore 不支持删除内存 run 记录")

    conn = sqlite3.connect(str(Path(db_path).expanduser()))
    try:
        _work(conn)
        conn.commit()
    finally:
        conn.close()


def prepare_point_run_retry(point_run_id: str, session: Session) -> AuditPointRun:
    """预留一个失败点用于重试，防止重复点击并发发起多个后台任务。"""

    point_run = session.get(AuditPointRun, point_run_id)
    if point_run is None:
        raise ValueError(f"未找到 AuditPointRun: {point_run_id}")
    if point_run.status not in ("failed", "waiting_retry"):
        raise ValueError(f"AuditPointRun {point_run_id} 状态为 {point_run.status}，不可重试")

    point_run.status = "pending"
    point_run.error = None
    point_run.usage_json = None
    point_run.finding_json = None
    point_run.completed_at = None
    point_run.workspace_archive_path = None
    point_run.workspace_failed_path = None
    session.add(point_run)

    audit_run = session.get(AuditRun, point_run.audit_run_id)
    if audit_run is not None:
        audit_run.status = "running"
        audit_run.error = None
        session.add(audit_run)

    session.commit()
    session.refresh(point_run)
    return point_run


def prepare_failed_points_retry(audit_run_id: str, session: Session) -> list[str]:
    """把某 run 下所有 failed 点重置为 pending（清产物 + 删旧 workspace），返回其 id 列表。

    复用 prepare_point_run_retry 的字段清理；workspace 删除沿用单点重试的 rmtree 策略。

    Args:
        audit_run_id: 目标审核任务 ID。
        session: 数据库会话。

    Returns:
        被重置为 pending 的 AuditPointRun id 列表（无失败点时为空）。
    """
    failed = session.exec(
        select(AuditPointRun).where(
            AuditPointRun.audit_run_id == audit_run_id,
            AuditPointRun.status == "failed",
        )
    ).all()
    manager = get_workspace_manager()
    store = get_trajectory_store()
    ids: list[str] = []
    for pr in failed:
        old_ws = manager.workspaces_root / pr.id
        if old_ws.exists():
            shutil.rmtree(old_ws)
        _delete_trajectory_run(store, pr.id)
        pr.status = "pending"
        pr.error = None
        pr.usage_json = None
        pr.finding_json = None
        pr.completed_at = None
        pr.workspace_archive_path = None
        pr.workspace_failed_path = None
        session.add(pr)
        ids.append(pr.id)
    audit_run = session.get(AuditRun, audit_run_id)
    if audit_run is not None and ids:
        audit_run.status = "running"
        audit_run.error = None
        session.add(audit_run)
    session.commit()
    return ids


async def exclude_failed_points(
    audit_run_id: str,
    session: Session,
    *,
    template_path: str | Path | None = None,
) -> int:
    """把某 run 下全部 failed 点标记为 excluded，并立即重新出底稿。返回剔除数量。

    excluded 状态的点既不计入失败也不计入有效总数（见 ``_assemble_workpaper_draft``），
    因此剔除后只要仍有 completed 点即可进入 ``draft_ready``（完整底稿）。

    Args:
        audit_run_id: 目标审核任务 ID。
        session: 数据库会话。
        template_path: docxtpl 模板路径（透传给 ``render_workpaper_docx``）。

    Returns:
        被标记为 excluded 的失败点数量（无失败点时为 0）。
    """
    audit_run = session.get(AuditRun, audit_run_id)
    if audit_run is None:
        raise ValueError(f"未找到 AuditRun: {audit_run_id}")
    # 守卫：仍有 pending/running 的点说明审核尚未跑完，此时剔除失败点会把
    # 不完整底稿误判为 draft_ready 并静默丢点，必须拒绝。
    unfinished = session.exec(
        select(AuditPointRun).where(
            AuditPointRun.audit_run_id == audit_run_id,
            AuditPointRun.status.in_(("pending", "running")),  # type: ignore[attr-defined]
        )
    ).all()
    if unfinished:
        raise ValueError(f"AuditRun {audit_run_id} 仍有未完成的审核点，不能跳过失败点")
    failed = session.exec(
        select(AuditPointRun).where(
            AuditPointRun.audit_run_id == audit_run_id,
            AuditPointRun.status == "failed",
        )
    ).all()
    for pr in failed:
        pr.status = "excluded"
        session.add(pr)
    session.commit()
    tender_doc = session.get(Document, audit_run.main_document_id)
    await _assemble_workpaper_draft(audit_run, session, tender_doc, template_path)
    session.add(audit_run)
    session.commit()
    return len(failed)


def _add_doc_to_collection(
    coll: Any,
    audit_run_id: str,
    doc: Document,
    source_type: str,
) -> None:
    """把单个 Document 幂等加入 qmd collection。"""
    if coll.get_document(doc.id) is not None:
        return

    if not doc.markdown_path:
        logger.warning("文书未生成 markdown，跳过 qmd 索引: %s", doc.id)
        return

    md_path = Path(doc.markdown_path).expanduser().resolve()
    if not md_path.exists():
        logger.warning("文书 markdown 不存在，跳过 qmd 索引: %s", md_path)
        return

    coll.add_document(
        doc.id,
        md_path.read_text(encoding="utf-8"),
        metadata={
            "audit_run": audit_run_id,
            "source": doc.filename,
            "filename": doc.filename,
            "source_type": source_type,
        },
    )


def _ensure_tender_collection(
    audit_run_id: str,
    tender_doc: Document,
    supplementary_docs: Sequence[Document] = (),
    *,
    qmd_client: Any | None = None,
) -> str:
    """创建临时 qmd collection 并索引招标文书 markdown 与附件。

    按 design §10 L584-592：创建 run_{id}_tender collection，
    将 tender markdown 加入，使 agent 在 workspace 中可通过 qmd search 检索。
    """
    collection_name = f"run_{audit_run_id}_tender"
    client = qmd_client or get_qmd()
    coll = client.collection(collection_name)

    _add_doc_to_collection(coll, audit_run_id, tender_doc, "main")
    for doc in supplementary_docs:
        _add_doc_to_collection(coll, audit_run_id, doc, "supplementary")

    return collection_name


def _index_tender_doc(
    audit_run: AuditRun,
    tender_doc: Document,
    *,
    supplementary_docs: Sequence[Document] = (),
    replay: bool,
) -> str | None:
    """为本次 audit run 准备 qmd tender collection。

    - replay 模式：返回占位名 f"run_{audit_run.id}_tender"，不触发 qmd
    - 非 replay 模式：调用 _ensure_tender_collection；失败时返回 None（允许降级）

    Args:
        audit_run: 当前 audit run 实例（需要 audit_run.id）
        tender_doc: 招标文书（交给 _ensure_tender_collection）
        replay: 是否 replay 模式

    Returns:
        tender collection 名，或 None（真索引失败时）
    """
    if replay:
        return f"run_{audit_run.id}_tender"
    try:
        return _ensure_tender_collection(
            audit_run.id,
            tender_doc,
            supplementary_docs=supplementary_docs,
        )
    except Exception:
        return None


def _resolve_point_runs(
    session: Session,
    audit_run: AuditRun,
    point_run_ids: Sequence[str] | None,
) -> tuple[int, list[AuditPointRun]]:
    """查找本次 audit run 下所有 point_runs，应用过滤返回 (总数, 待跑列表)。

    Args:
        session: SQLModel session
        audit_run: 当前 audit run 实例
        point_run_ids: 可选的白名单过滤；None 表示不过滤

    Returns:
        (total_count, to_run)
        - total_count: 本 audit run 下 point_runs 的总数，排除 status=='excluded'
        - to_run: 过滤后待跑的 point_runs，按 created_at/id 稳定排序；
                  跳过 status=='completed' 与 status=='excluded'（保证幂等重试且不跑被排除点）；
                  白名单外的也跳过
    """
    point_runs = session.exec(
        select(AuditPointRun)
        .where(AuditPointRun.audit_run_id == audit_run.id)
        .order_by(AuditPointRun.created_at, AuditPointRun.id)
    ).all()
    selected: set[str] | None = set(point_run_ids) if point_run_ids is not None else None
    to_run = [
        pr
        for pr in point_runs
        if (selected is None or pr.id in selected) and pr.status not in ("completed", "excluded")
    ]
    total = sum(1 for pr in point_runs if pr.status != "excluded")
    return total, to_run


async def _run_single_point(
    point_run: AuditPointRun,
    checkpoint: GovCheckpoint,
    tender_doc: Document,
    *,
    supplementary_docs: Sequence[Document] = (),
    audit_run: AuditRun,
    tender_collection: str | None,
    manager: Any,
    store: Any,
    cfg: Any,
    repo_root: Path,
    replay_dir: str | Path | None,
) -> tuple[Any, Any]:
    """搭 workspace、构造 PES（真 or replay）、await pes.run，返回 (workspace, result)。

    抽自 run_audit 主循环（原 L315-366），封装单审核点执行闭环：
    1. 写 checkpoints.json 临时文件
    2. 构造 WorkspaceSpec（data_inputs + extra_env）
    3. 根据 replay_dir 选择 MockPES（replay）或真实 PES（build_gov_auditor_pes）
    4. await pes.run 并 attach_workspace_output

    不做 DB 持久化（留给调用方 / Task 6 的 _persist_point_result），
    不做 cleanup / archive（调用方根据 result 决定）。
    PES 正常返回 PESResult（含 status 字段），不会抛异常；
    异常路径（workspace 创建失败、fixture 读取失败）由调用方 try/except 处理。

    Args:
        point_run: 当前 AuditPointRun（提供 id 作为 workspace run_id）
        checkpoint: 待审核的 GovCheckpoint（用于 task_prompt + 落盘 checkpoints.json）
        tender_doc: 招标文书（提供 markdown_path 作为 data_inputs）
        supplementary_docs: 附件文书列表（作为 supp_*.md 注入 workspace）
        audit_run: 当前 AuditRun（提供 id 给 extra_env / checkpoint 落盘）
        tender_collection: qmd tender collection 名；None 表示不注入该 env
        manager: workspace manager（Scrivai 注入）
        store: trajectory store（replay 分支的 MockPES 需要）
        cfg: config 单例（提供 qmd_db_path）
        repo_root: 项目根路径（WorkspaceSpec.project_root）
        replay_dir: replay fixture 目录；None 表示真跑

    Returns:
        (workspace, result) 元组；result.status 反映 PES 完成情况。
    """
    if not tender_doc.markdown_path:
        raise ValueError(f"文书未生成 markdown: {tender_doc.id}")
    for doc in supplementary_docs:
        if not doc.markdown_path:
            raise ValueError(f"附件文书未生成 markdown: {doc.id}")

    checkpoint_path = write_single_checkpoint_json(audit_run.id, checkpoint)

    extra_env: dict[str, str] = {
        "GOVDOC_AUDIT_RUN_ID": audit_run.id,
    }
    if tender_collection:
        extra_env["GOVDOC_TENDER_COLLECTION"] = tender_collection
    extra_env["GOVDOC_DB_PATH"] = str(cfg.qmd_db_path)

    manifest = [
        {"path": "tender.md", "filename": tender_doc.filename, "source_type": "main"},
        *[
            {
                "path": f"supp_{index}.md",
                "filename": doc.filename,
                "source_type": "supplementary",
            }
            for index, doc in enumerate(supplementary_docs)
        ],
    ]
    manifest_path = write_documents_manifest_json(audit_run.id, manifest)
    data_inputs = {
        "tender.md": Path(tender_doc.markdown_path).expanduser().resolve(),
        "checkpoints.json": checkpoint_path,
        "documents.json": manifest_path,
    }
    for index, doc in enumerate(supplementary_docs):
        data_inputs[f"supp_{index}.md"] = Path(doc.markdown_path).expanduser().resolve()

    workspace = manager.create(
        WorkspaceSpec(
            run_id=point_run.id,
            project_root=repo_root,
            data_inputs=data_inputs,
            extra_env=extra_env,
        )
    )

    runtime_context: dict[str, Any] = {
        "output_schema": WorkpaperAuditOutput,
        "verdict_levels": ["合规", "不合规", "存疑"],
        "evidence_required": True,
    }
    if tender_collection:
        runtime_context["external_cli_tools"] = [
            f"govdoc-cli qmd-search --collection {tender_collection}"
            f" --db {cfg.qmd_db_path} --query",
        ]

    if replay_dir is not None:
        replay = load_mock_replay(replay_dir)
        seed_working_tree(replay.working_seed_dir, workspace.working_dir)
        pes = GovDocMockAuditorPES(
            config=get_gov_auditor_config(),
            workspace=workspace,
            trajectory_store=store,
            runtime_context=runtime_context,
            phase_outcomes=replay.phase_outcomes,
        )
    else:
        from govdoc.pipelines.phase_progress_hook import PhaseProgressHook
        from govdoc.api.deps import get_db_session as _get_progress_session
        from govdoc.db.models import AuditPointRun as _AuditPointRunModel

        progress_hook = PhaseProgressHook(
            run_id=point_run.id,
            model_class=_AuditPointRunModel,
            session_factory=_get_progress_session,
        )
        pes = build_gov_auditor_pes(
            workspace=workspace,
            runtime_context=runtime_context,
            extra_hooks=[progress_hook],
        )

    files_desc = "data/tender.md"
    if supplementary_docs:
        files_desc += "、" + "、".join(
            f"data/supp_{index}.md" for index in range(len(supplementary_docs))
        )

    result = await pes.run(
        task_prompt=(
            f"审核 {files_desc}，参考 data/documents.json 中的文件说明，"
            "针对 data/checkpoints.json 中的唯一审核点"
            f"「{checkpoint.title}」生成一条 GovFinding。"
        ),
    )
    attach_workspace_output(result, workspace.working_dir)
    return workspace, result


def _try_recover_from_workspace(
    working_dir: Path,
    checkpoint_id: str,
) -> dict[str, Any] | None:
    """尝试从 workspace 产物中恢复 finding（PES 报告失败但产物已就绪时）。"""
    from govdoc.pipelines.pes_overrides import try_recover_audit_output

    recovered_payload = try_recover_audit_output(
        SimpleNamespace(status="failed", error="recovery"),
        working_dir,
    )
    if recovered_payload is None:
        return None
    findings = recovered_payload.get("findings", [])
    finding_data = _match_finding_by_checkpoint_id(findings, checkpoint_id)
    if finding_data is not None:
        return finding_data
    if findings:
        return findings[0]
    return None


def _persist_point_result(
    point_run: AuditPointRun,
    result: Any,
    workspace: Any,
    checkpoint: GovCheckpoint,
    manager: Any,
) -> None:
    """把 PES result 落到 point_run 字段。

    - result.status == "completed": 加载 payload、匹配 finding、设 status/completed_at/archive
    - result.status != "completed": 设 failed/error/failed_archive
    - result 非 None: 写 usage_json

    不调用 session.commit/add；异常由调用方接管。
    """
    if result.status == "completed":
        payload = load_result_payload(result.final_output_path, result.final_output)
        findings = payload.get("findings", [])
        finding_data = _match_finding_by_checkpoint_id(findings, checkpoint.id)
        if finding_data is not None:
            finding = GovFinding.model_validate(finding_data)
            point_run.finding_json = finding.model_dump_json()
        elif findings:
            finding = GovFinding.model_validate(findings[0])
            point_run.finding_json = finding.model_dump_json()
        point_run.status = "completed"
        point_run.completed_at = datetime.utcnow()
        point_run.workspace_archive_path = str(manager.archive(workspace, success=True))
    else:
        recovered = _try_recover_from_workspace(workspace.working_dir, checkpoint.id)
        if recovered is not None:
            finding = GovFinding.model_validate(recovered)
            point_run.finding_json = finding.model_dump_json()
            point_run.status = "completed"
            point_run.completed_at = datetime.utcnow()
            point_run.workspace_archive_path = str(manager.archive(workspace, success=True))
        else:
            point_run.status = "failed"
            point_run.error = result.error
            point_run.workspace_failed_path = str(manager.archive(workspace, success=False))

    if result is not None and hasattr(result.phase_results, "items"):
        point_run.usage_json = dump_phase_usage(result.phase_results)


def _cleanup_tender_collection(collection_id: str | None, *, replay: bool) -> None:
    """清理 qmd 临时 tender collection（best-effort）。

    - replay 模式：no-op（测试 fixture 用的是占位名，不接真 qmd）
    - 非 replay 模式：调 ``get_qmd().delete_collection(collection_id)``；
      qmd 对不存在的 collection 静默 no-op，对其他异常则由本函数 try/except
      吞掉（仅 warning log），不向上传播。

    设计：
    - **不抛异常**——调用方通常在 finally 块里调，不希望 cleanup 失败
      覆盖业务异常。
    - 静默 no-op 条件：collection_id is None / 空串 / replay=True。

    Args:
        collection_id: qmd collection 名；None 或空串时 no-op。
        replay: 是否 replay 模式。

    Returns:
        None
    """
    if replay or not collection_id:
        return
    try:
        get_qmd().delete_collection(collection_id)
    except Exception as exc:
        logger.warning(
            "清理 tender collection %r 失败（best-effort，已吞异常）：%s",
            collection_id,
            exc,
        )


async def _assemble_workpaper_draft(
    audit_run: AuditRun,
    session: Session,
    tender_doc: Document,
    template_path: str | Path | None,
) -> None:
    """按 completed point_runs 汇总 findings，生成 WorkpaperDraft，更新 audit_run.status。

    Status 分派规则（残缺也出稿）：
    - 有 completed 且无 failed → ``draft_ready`` + 生成 WorkpaperDraft（新版本）
    - 有 completed 且有 failed → ``partial_ready`` + 生成（残缺）WorkpaperDraft（新版本）
    - 无 completed             → ``waiting_retry``（不生成 WorkpaperDraft）

    其中 ``excluded`` 状态的 point_run 既不计入 failed，也不计入有效总数
    （``audit_run.total_count`` 会被重算为排除 excluded 后的点数）。

    **不**调 ``session.commit``；调用方负责 DB 提交（与 ``_persist_point_result`` 一致）。

    Args:
        audit_run: 当前 audit run 实例（本函数会直接修改其 ``status`` 字段）。
        session: SQLModel session（用于查 point_runs / WorkpaperDraft 版本号）。
        tender_doc: 招标文书（提供 ``raw_path`` 给生成的 Workpaper）。
        template_path: docxtpl 模板路径（透传给 ``render_workpaper_docx``）。

    Returns:
        None
    """
    all_runs = session.exec(
        select(AuditPointRun).where(AuditPointRun.audit_run_id == audit_run.id)
    ).all()
    completed_runs = [pr for pr in all_runs if pr.status == "completed" and pr.finding_json]
    failed_runs = [pr for pr in all_runs if pr.status == "failed"]  # excluded 不计

    # 有效总数：排除 excluded
    audit_run.total_count = sum(1 for pr in all_runs if pr.status != "excluded")

    if completed_runs:
        findings = [GovFinding.model_validate_json(pr.finding_json) for pr in completed_runs]
        workpaper = Workpaper(
            project_id=audit_run.project_id,
            tender_doc_path=tender_doc.raw_path,
            findings=findings,
            summary=generate_summary(findings),
        )
        current_versions = session.exec(
            select(WorkpaperDraft).where(WorkpaperDraft.audit_run_id == audit_run.id)
        ).all()
        next_version = max((d.version for d in current_versions), default=0) + 1
        draft_path = await asyncio.to_thread(
            render_workpaper_docx,
            workpaper,
            audit_run.id,
            template_path=template_path,
            version=next_version,
        )
        session.add(
            WorkpaperDraft(
                audit_run_id=audit_run.id,
                workpaper_json=workpaper.model_dump_json(),
                docx_path=str(draft_path),
                version=next_version,
            )
        )
        audit_run.status = "draft_ready" if not failed_runs else "partial_ready"
    else:
        audit_run.status = "waiting_retry"


async def run_audit(
    audit_run_id: str,
    session: Session,
    *,
    workspace_manager: Any | None = None,
    trajectory_store: Any | None = None,
    replay_dir: str | Path | None = None,
    project_root: str | Path | None = None,
    template_path: str | Path | None = None,
    point_run_ids: Sequence[str] | None = None,
) -> AuditRun:
    """管道 B 入口：审核点 + 招标文书 → 工作底稿。

    薄编排层。所有重活委托给以下 helper：
    - `_resolve_point_runs`: 查点 + 过滤 + total_count
    - `_index_tender_doc`: qmd tender collection 准备
    - `_run_single_point`: 单点 workspace + PES 运行
    - `_persist_point_result`: 结果落 point_run 字段
    - `_assemble_workpaper_draft`: 聚合 findings → WorkpaperDraft
    - `_cleanup_tender_collection`: finally 里清理 qmd collection

    设计基线：docs/design.md §10 +
    docs/superpowers/specs/2026-04-19-govdoc-tech-debt-cleanup-design.md §3.1

    Args:
        audit_run_id: 目标 AuditRun ID
        session: SQLModel session
        workspace_manager: scrivai workspace manager（默认从 runtime 拿）
        trajectory_store: scrivai trajectory store（默认从 runtime 拿）
        replay_dir: replay fixture 目录；None 表示真跑
        project_root: 项目根路径；None 则从 runtime 解析
        template_path: docxtpl 模板路径（给 WorkpaperDraft 用）
        point_run_ids: 白名单过滤；None 表示跑所有未 completed 的点
    """
    audit_run = session.get(AuditRun, audit_run_id)
    if audit_run is None:
        raise ValueError(f"未找到 AuditRun: {audit_run_id}")

    tender_doc = session.get(Document, audit_run.main_document_id)
    if tender_doc is None:
        raise ValueError(f"未找到 Document: {audit_run.main_document_id}")

    try:
        supplementary_doc_ids = json.loads(audit_run.supplementary_doc_ids or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError(f"AuditRun {audit_run.id} 附件 ID JSON 无效") from exc
    if not isinstance(supplementary_doc_ids, list) or not all(
        isinstance(x, str) for x in supplementary_doc_ids
    ):
        raise ValueError(f"AuditRun {audit_run.id} 附件 ID JSON 不是字符串列表")

    supplementary_docs: list[Document] = []
    for doc_id in supplementary_doc_ids:
        doc = session.get(Document, doc_id)
        if doc is None:
            raise ValueError(f"未找到附件 Document: {doc_id}")
        supplementary_docs.append(doc)

    # 解析 point_runs：总数（含 completed）+ 过滤后待跑列表
    audit_run.status = "running"
    audit_run.total_count, point_runs_to_run = _resolve_point_runs(
        session, audit_run, point_run_ids
    )
    session.add(audit_run)
    session.commit()
    session.refresh(audit_run)

    manager = workspace_manager or get_workspace_manager()
    store = trajectory_store or get_trajectory_store()
    repo_root = Path(project_root).expanduser().resolve() if project_root else get_project_root()
    cfg = get_config()

    # 索引招标文书到 qmd 临时 collection（非 replay 模式下才做）
    tender_collection = await asyncio.to_thread(
        _index_tender_doc,
        audit_run,
        tender_doc,
        supplementary_docs=supplementary_docs,
        replay=replay_dir is not None,
    )

    point_timeout_s = int(os.environ.get("GOVDOC_POINT_TIMEOUT", str(cfg.audit.point_timeout_s)))

    try:
        # 逐个 AuditPointRun 审核，每个点独立 workspace
        for point_run in point_runs_to_run:
            session.refresh(audit_run)
            if audit_run.status == "cancelled":
                break

            checkpoint_row = session.get(CheckpointFinal, point_run.checkpoint_final_id)
            if checkpoint_row is None:
                point_run.status = "failed"
                point_run.error = f"未找到 CheckpointFinal: {point_run.checkpoint_final_id}"
                session.add(point_run)
                session.commit()
                continue

            checkpoint = GovCheckpoint.model_validate_json(checkpoint_row.payload_json)
            point_run.status = "running"
            point_run.started_at = datetime.utcnow()
            point_run.current_phase = None
            session.add(point_run)
            session.commit()

            workspace = None
            result = None

            try:
                workspace, result = await asyncio.wait_for(
                    _run_single_point(
                        point_run,
                        checkpoint,
                        tender_doc,
                        supplementary_docs=supplementary_docs,
                        audit_run=audit_run,
                        tender_collection=tender_collection,
                        manager=manager,
                        store=store,
                        cfg=cfg,
                        repo_root=repo_root,
                        replay_dir=replay_dir,
                    ),
                    timeout=point_timeout_s,
                )

                await asyncio.to_thread(
                    _persist_point_result,
                    point_run,
                    result,
                    workspace,
                    checkpoint,
                    manager,
                )

            except asyncio.TimeoutError:
                point_run.status = "failed"
                point_run.error = f"Point audit timeout after {point_timeout_s} seconds"

            except Exception as exc:
                point_run.status = "failed"
                point_run.error = str(exc)
                if (
                    workspace is not None
                    and workspace.root_dir.exists()
                    and point_run.workspace_failed_path is None
                ):
                    try:
                        point_run.workspace_failed_path = str(
                            manager.archive(workspace, success=False)
                        )
                    except Exception:
                        pass

            audit_run.processed_count = count_processed_points(session, audit_run.id)
            session.add(point_run)
            session.add(audit_run)
            _update_heartbeat(audit_run, session)
            session.commit()

        if audit_run.status != "cancelled":
            await _assemble_workpaper_draft(audit_run, session, tender_doc, template_path)

        session.add(audit_run)
        session.commit()
        session.refresh(audit_run)
        return audit_run

    except Exception as exc:
        audit_run.status = "failed"
        audit_run.error = str(exc)
        session.add(audit_run)
        session.commit()
        raise
    finally:
        await asyncio.to_thread(
            _cleanup_tender_collection,
            tender_collection,
            replay=replay_dir is not None,
        )


async def retry_point_run(
    point_run_id: str,
    session: Session,
    *,
    workspace_manager: Any | None = None,
    trajectory_store: Any | None = None,
    replay_dir: str | Path | None = None,
    project_root: str | Path | None = None,
    template_path: str | Path | None = None,
    prepared: bool = False,
) -> AuditPointRun:
    """重试单个失败的 AuditPointRun。"""
    point_run = (
        prepare_point_run_retry(point_run_id, session)
        if not prepared
        else session.get(AuditPointRun, point_run_id)
    )
    if point_run is None:
        raise ValueError(f"未找到 AuditPointRun: {point_run_id}")
    if prepared and point_run.status not in ("pending", "running"):
        raise ValueError(f"AuditPointRun {point_run_id} 状态为 {point_run.status}，不可开始重试")

    manager = workspace_manager or get_workspace_manager()
    store = trajectory_store or get_trajectory_store()
    audit_run_id = point_run.audit_run_id

    try:
        old_ws = manager.workspaces_root / point_run_id
        if old_ws.exists():
            shutil.rmtree(old_ws)

        _delete_trajectory_run(store, point_run_id)

        await run_audit(
            audit_run_id,
            session,
            workspace_manager=workspace_manager,
            trajectory_store=trajectory_store,
            replay_dir=replay_dir,
            project_root=project_root,
            template_path=template_path,
            point_run_ids=[point_run_id],
        )
    except Exception as exc:
        failed_point = session.get(AuditPointRun, point_run_id)
        if failed_point is not None and failed_point.status != "completed":
            failed_point.status = "failed"
            failed_point.error = str(exc)
            session.add(failed_point)

        audit_run = session.get(AuditRun, audit_run_id)
        if audit_run is not None and audit_run.status == "running":
            completed_runs = session.exec(
                select(AuditPointRun).where(
                    AuditPointRun.audit_run_id == audit_run_id,
                    AuditPointRun.status == "completed",
                )
            ).all()
            audit_run.status = "partial_ready" if completed_runs else "waiting_retry"
            session.add(audit_run)

        session.commit()
        logger.exception("重试审核点失败: %s", point_run_id)
        raise

    return session.get(AuditPointRun, point_run_id)
