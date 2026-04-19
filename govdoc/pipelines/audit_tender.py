"""管道 B：审核点 + 招标文书 -> 工作底稿（逐点编排）。

设计基线：docs/design.md §10。
每个 AuditPointRun 对应一个独立 workspace，失败点可单独重试。
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from scrivai import MockPES, WorkspaceSpec
from sqlmodel import Session
from sqlmodel import select

from govdoc.db.models import (
    AuditPointRun,
    AuditRun,
    CheckpointFinal,
    TenderDoc,
    WorkpaperDraft,
)
from govdoc.pipelines.common import attach_workspace_output, dump_phase_usage, load_result_payload
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


def count_processed_points(session: Session, audit_run_id: str) -> int:
    """统计已完成的 AuditPointRun 数量。"""
    runs = session.exec(
        select(AuditPointRun).where(
            AuditPointRun.audit_run_id == audit_run_id,
            AuditPointRun.status == "completed",
        )
    ).all()
    return len(runs)


def generate_summary(findings: list[GovFinding]) -> str:
    """从 findings 生成简短汇总。"""
    if not findings:
        return "无审核结果。"
    total = len(findings)
    compliant = sum(1 for f in findings if f.verdict.verdict == "合规")
    non_compliant = sum(1 for f in findings if f.verdict.verdict == "不合规")
    uncertain = total - compliant - non_compliant
    parts = [f"共审核 {total} 个审核点。"]
    if non_compliant:
        parts.append(f"不合规 {non_compliant} 项。")
    if compliant:
        parts.append(f"合规 {compliant} 项。")
    if uncertain:
        parts.append(f"存疑 {uncertain} 项。")
    return " ".join(parts)


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


def _ensure_tender_collection(
    audit_run_id: str,
    tender_doc: TenderDoc,
    *,
    qmd_client: Any | None = None,
) -> str:
    """创建临时 qmd collection 并索引招标文书 markdown。

    按 design §10 L584-592：创建 run_{id}_tender collection，
    将 tender markdown 加入，使 agent 在 workspace 中可通过 qmd search 检索。
    """
    collection_name = f"run_{audit_run_id}_tender"
    client = qmd_client or get_qmd()
    coll = client.collection(collection_name)
    if coll.get_document(tender_doc.id) is not None:
        return collection_name

    tender_md_path = Path(tender_doc.markdown_path).expanduser().resolve()
    if tender_md_path.exists():
        markdown_text = tender_md_path.read_text(encoding="utf-8")
        coll.add_document(
            tender_doc.id,
            markdown_text,
            metadata={"audit_run": audit_run_id, "source": tender_doc.filename},
        )

    return collection_name


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
    audit_run = session.get(AuditRun, audit_run_id)
    if audit_run is None:
        raise ValueError(f"未找到 AuditRun: {audit_run_id}")

    tender_doc = session.get(TenderDoc, audit_run.tender_doc_id)
    if tender_doc is None:
        raise ValueError(f"未找到 TenderDoc: {audit_run.tender_doc_id}")

    point_runs = session.exec(
        select(AuditPointRun)
        .where(AuditPointRun.audit_run_id == audit_run.id)
        .order_by(AuditPointRun.created_at, AuditPointRun.id)
    ).all()
    selected_point_ids = set(point_run_ids) if point_run_ids is not None else None

    audit_run.status = "running"
    audit_run.total_count = len(point_runs)
    session.add(audit_run)
    session.commit()
    session.refresh(audit_run)

    manager = workspace_manager or get_workspace_manager()
    store = trajectory_store or get_trajectory_store()
    repo_root = Path(project_root).expanduser().resolve() if project_root else get_project_root()
    cfg = get_config()

    # 索引招标文书到 qmd 临时 collection（非 replay 模式下才做）
    tender_collection: str | None = None
    if replay_dir is None:
        try:
            tender_collection = _ensure_tender_collection(audit_run.id, tender_doc)
        except Exception:
            tender_collection = None
    else:
        tender_collection = f"run_{audit_run.id}_tender"

    try:
        # 逐个 AuditPointRun 审核，每个点独立 workspace
        for point_run in point_runs:
            if selected_point_ids is not None and point_run.id not in selected_point_ids:
                continue
            if point_run.status == "completed":
                continue

            checkpoint_row = session.get(CheckpointFinal, point_run.checkpoint_final_id)
            if checkpoint_row is None:
                point_run.status = "failed"
                point_run.error = f"未找到 CheckpointFinal: {point_run.checkpoint_final_id}"
                session.add(point_run)
                session.commit()
                continue

            checkpoint = GovCheckpoint.model_validate_json(checkpoint_row.payload_json)
            point_run.status = "running"
            session.add(point_run)
            session.commit()

            checkpoint_path = write_single_checkpoint_json(audit_run.id, checkpoint)
            workspace = None
            result = None

            try:
                extra_env: dict[str, str] = {
                    "GOVDOC_AUDIT_RUN_ID": audit_run.id,
                }
                if tender_collection:
                    extra_env["GOVDOC_TENDER_COLLECTION"] = tender_collection
                extra_env["GOVDOC_DB_PATH"] = str(cfg.qmd_db_path)

                workspace = manager.create(
                    WorkspaceSpec(
                        run_id=point_run.id,
                        project_root=repo_root,
                        data_inputs={
                            "tender.md": Path(tender_doc.markdown_path).expanduser().resolve(),
                            "checkpoints.json": checkpoint_path,
                        },
                        extra_env=extra_env,
                    )
                )

                runtime_context = {
                    "output_schema": WorkpaperAuditOutput,
                    "verdict_levels": ["合规", "不合规", "存疑"],
                    "evidence_required": True,
                }

                if replay_dir is not None:
                    replay = load_mock_replay(replay_dir)
                    seed_working_tree(replay.working_seed_dir, workspace.working_dir)
                    pes = MockPES(
                        config=get_gov_auditor_config(),
                        workspace=workspace,
                        trajectory_store=store,
                        runtime_context=runtime_context,
                        phase_outcomes=replay.phase_outcomes,
                    )
                else:
                    pes = build_gov_auditor_pes(
                        workspace=workspace, runtime_context=runtime_context
                    )

                result = await pes.run(
                    task_prompt=(
                        "审核 data/tender.md，针对 data/checkpoints.json 中的唯一审核点"
                        f"「{checkpoint.title}」生成一条 GovFinding。"
                    ),
                )
                attach_workspace_output(result, workspace.working_dir)

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
                    point_run.status = "failed"
                    point_run.error = result.error
                    point_run.workspace_failed_path = str(manager.archive(workspace, success=False))

                if result is not None:
                    point_run.usage_json = dump_phase_usage(result.phase_results)

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
            session.commit()

        # 汇总所有 point runs
        all_runs = session.exec(
            select(AuditPointRun).where(AuditPointRun.audit_run_id == audit_run.id)
        ).all()
        completed_runs = [pr for pr in all_runs if pr.status == "completed" and pr.finding_json]
        failed_runs = [pr for pr in all_runs if pr.status == "failed"]

        if not failed_runs and completed_runs:
            findings = [GovFinding.model_validate_json(pr.finding_json) for pr in completed_runs]
            workpaper = Workpaper(
                project_id=audit_run.project_id,
                tender_doc_path=tender_doc.storage_path,
                findings=findings,
                summary=generate_summary(findings),
            )
            current_versions = session.exec(
                select(WorkpaperDraft).where(WorkpaperDraft.audit_run_id == audit_run.id)
            ).all()
            next_version = max((d.version for d in current_versions), default=0) + 1
            draft_path = render_workpaper_docx(
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
            audit_run.status = "draft_ready"
        elif completed_runs:
            audit_run.status = "partial_ready"
        else:
            audit_run.status = "waiting_retry"

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
