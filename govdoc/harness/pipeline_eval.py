"""L1 管道评估：直接调用 run_extract / run_audit，记录指标并做语义评估。"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from types import FrameType
from typing import Any, NoReturn

from sqlmodel import select

from govdoc.harness.handler import SqliteHandler
from govdoc.harness.judge import HarnessJudge, Verdict
from govdoc.harness.log import HarnessLog, _now_iso
from govdoc.harness.schemas import create_all_tables

logger = logging.getLogger(__name__)


def record_pipeline_run(
    log: HarnessLog,
    *,
    pipeline: str,
    project_name: str,
    input_file: str,
    status: str,
    duration_s: float,
    total_tokens: int,
    error: str | None = None,
) -> None:
    """记录一次管道执行到 pipeline_runs 表。"""
    log.insert(
        "pipeline_runs",
        {
            "pipeline": pipeline,
            "project_name": project_name,
            "input_file": str(input_file),
            "status": status,
            "duration_s": duration_s,
            "total_tokens": total_tokens,
            "error": error,
        },
    )


def record_phase_metrics(
    log: HarnessLog,
    *,
    pipeline: str,
    phase: str,
    duration_s: float,
    tokens_in: int,
    tokens_out: int,
    status: str,
    attempt_no: int = 0,
) -> None:
    """记录单 phase 指标到 phase_metrics 表。"""
    log.insert(
        "phase_metrics",
        {
            "pipeline": pipeline,
            "phase": phase,
            "duration_s": duration_s,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "status": status,
            "attempt_no": attempt_no,
        },
    )


def record_extract_results(
    log: HarnessLog,
    checkpoints: list[dict[str, Any]],
) -> None:
    """记录管道 A 提取的审核点到 extract_results 表。"""
    for cp in checkpoints:
        bases = cp.get("legal_basis", [])
        log.insert(
            "extract_results",
            {
                "checkpoint_id": cp["id"],
                "title": cp.get("title", ""),
                "category": cp.get("category", ""),
                "description": cp.get("description", ""),
                "severity": cp.get("severity", ""),
                "has_legal_basis": 1 if bases else 0,
                "legal_basis_count": len(bases),
                "legal_basis_json": json.dumps(bases, ensure_ascii=False),
            },
        )


def record_audit_results(
    log: HarnessLog,
    findings: list[dict[str, Any]],
) -> None:
    """记录管道 B 审核发现到 audit_results 表。"""
    for f in findings:
        verdict_obj = f.get("verdict", {})
        if isinstance(verdict_obj, dict):
            verdict_str = verdict_obj.get("verdict", "")
            quotes = verdict_obj.get("evidence_quotes", [])
        else:
            verdict_str = str(verdict_obj)
            quotes = []
        refs = f.get("evidence_refs", [])
        log.insert(
            "audit_results",
            {
                "point_run_id": f.get("point_run_id", ""),
                "checkpoint_id": f.get("checkpoint_id", ""),
                "verdict": verdict_str,
                "verdict_json": json.dumps(verdict_obj, ensure_ascii=False)
                if isinstance(verdict_obj, dict)
                else json.dumps({"verdict": verdict_str}, ensure_ascii=False),
                "has_evidence": 1 if (quotes or refs) else 0,
                "evidence_count": len(quotes) + len(refs),
                "evidence_json": json.dumps(refs, ensure_ascii=False),
                "has_case_refs": 1 if f.get("case_refs") else 0,
                "duration_s": f.get("duration_s", 0.0),
                "status": f.get("status", "unknown"),
            },
        )


def record_agent_trajectory(
    log: HarnessLog,
    *,
    pipeline: str,
    run_id: str,
    plan_json: str,
    workspace_files: list[str],
    phase_details: list[dict[str, Any]],
) -> None:
    """记录 PES agent 轨迹到 agent_trajectories 表。"""
    log.insert(
        "agent_trajectories",
        {
            "pipeline": pipeline,
            "source_run_id": run_id,
            "plan_json": plan_json,
            "workspace_files_json": json.dumps(workspace_files, ensure_ascii=False),
            "phase_details_json": json.dumps(phase_details, ensure_ascii=False),
        },
    )


def collect_workspace_evidence(
    workspace_dir: Path | None = None,
    archive_path: Path | None = None,
) -> dict[str, Any]:
    """从 workspace 目录或归档 tar.gz 中读取 agent 证据。

    优先读活跃 workspace 目录，否则从 archive 解压读取。

    返回:
        {"plan_json": str, "workspace_files": list[str], "findings": dict}
    """
    result: dict[str, Any] = {"plan_json": "", "workspace_files": [], "findings": {}}

    if workspace_dir and workspace_dir.exists():
        working = workspace_dir / "working"
        if not working.exists():
            working = workspace_dir
        plan_path = working / "plan.json"
        if plan_path.exists():
            result["plan_json"] = plan_path.read_text(encoding="utf-8")
        result["workspace_files"] = [
            str(p.relative_to(working)) for p in working.rglob("*") if p.is_file()
        ]
        findings_dir = working / "findings"
        if findings_dir.exists():
            for f in sorted(findings_dir.glob("*.json")):
                result["findings"][f.stem] = f.read_text(encoding="utf-8")
        return result

    if archive_path and Path(archive_path).exists() and str(archive_path).endswith(".tar.gz"):
        import tarfile

        with tarfile.open(archive_path, "r:gz") as tf:
            members = tf.getnames()
            result["workspace_files"] = members
            for m in members:
                if m.endswith("/working/plan.json") or m == "working/plan.json":
                    f_obj = tf.extractfile(m)
                    if f_obj:
                        result["plan_json"] = f_obj.read().decode("utf-8")
                if ("working/findings/" in m) and m.endswith(".json"):
                    f_obj = tf.extractfile(m)
                    if f_obj:
                        stem = Path(m).stem
                        result["findings"][stem] = f_obj.read().decode("utf-8")
        return result

    return result


def record_quality_score(
    log: HarnessLog,
    *,
    dimension: str,
    score: float,
    passed: bool,
    judge_reasoning: str,
) -> None:
    """记录语义评估结果到 quality_scores 表。"""
    log.insert(
        "quality_scores",
        {
            "dimension": dimension,
            "score": score,
            "passed": 1 if passed else 0,
            "judge_reasoning": judge_reasoning,
        },
    )


def evaluate_dimension(
    *,
    log: HarnessLog,
    judge: HarnessJudge,
    dimension: str,
    criteria: str,
    evidence: dict[str, Any],
    rubric: dict[str, Any] | None = None,
) -> Verdict:
    """调用 HarnessJudge 评估一个语义维度并记录结果。

    参数:
        log: HarnessLog 实例。
        judge: HarnessJudge 实例。
        dimension: 指标 ID（如 'extract-faithfulness'）。
        criteria: 评判标准描述。
        evidence: 证据数据。
        rubric: 可选的评分维度。

    返回:
        Verdict 评估结果。
    """
    verdict = judge.evaluate(criteria, evidence, rubric)
    record_quality_score(
        log,
        dimension=dimension,
        score=verdict.score,
        passed=verdict.passed,
        judge_reasoning=verdict.reasoning,
    )
    log.log_event(
        "semantic_eval",
        {"dimension": dimension, "score": verdict.score, "passed": verdict.passed},
    )
    return verdict


def load_rubric(rubric_dir: str | Path, dimension: str) -> str:
    """从 rubric 文件加载评判标准。

    参数:
        rubric_dir: rubric 目录路径。
        dimension: 指标 ID，映射到文件名（连字符转下划线 + .md）。

    返回:
        rubric 文件内容。
    """
    filename = dimension.replace("-", "_") + ".md"
    path = Path(rubric_dir) / filename
    if not path.exists():
        raise FileNotFoundError(f"rubric 文件不存在: {path}")
    return path.read_text(encoding="utf-8")


async def run_pipeline_eval(
    *,
    manifest_path: str,
    project_root: str,
    rubric_dir: str,
    db_path: str = "results/harness.db",
    run_id: str | None = None,
) -> str:
    """L1 管道评估主入口。

    参数:
        manifest_path: harness_manifest.yaml 路径。
        project_root: 项目根目录。
        rubric_dir: rubric 文件目录。
        db_path: harness.db 输出路径。
        run_id: 可选的运行 ID；为空时自动生成。

    返回:
        本次运行的 run_id。
    """
    import os
    from dotenv import load_dotenv
    from govdoc.harness.manifest import load_manifest

    load_dotenv()
    run_id = run_id or f"L1-{uuid.uuid4().hex[:8]}"

    config_snapshot: dict[str, Any] = {
        "manifest_path": manifest_path,
        "project_root": project_root,
        "rubric_dir": rubric_dir,
        "db_path": db_path,
        "judge_model": os.environ.get("HARNESS_JUDGE_MODEL", ""),
        "judge_base_url": os.environ.get("HARNESS_JUDGE_BASE_URL", ""),
    }

    with HarnessLog(db_path=db_path, run_id=run_id, config_snapshot=config_snapshot) as log:
        create_all_tables(log)

        # 清除上次 harness 残留，确保干净起跑
        from govdoc.db.session import get_session as _get_session

        _sg = _get_session()
        _clean_session = next(_sg)
        try:
            _clean_harness_state(_clean_session)
        finally:
            _sg.close()

        manifest = load_manifest(manifest_path, project_root=project_root)
        config_snapshot["projects"] = [p.name for p in manifest.projects]
        config_snapshot["rules"] = [r.name for r in manifest.rules]
        config_snapshot["checkpoints"] = [c.name for c in manifest.checkpoints]
        log.execute(
            "UPDATE _runs SET config=? WHERE run_id=?",
            (json.dumps(config_snapshot, ensure_ascii=False), run_id),
        )

        log.log_event(
            "pipeline_eval_start",
            {
                "manifest": manifest_path,
                "config": config_snapshot,
            },
        )

        pipeline_timeout = int(os.environ.get("HARNESS_PIPELINE_TIMEOUT", "1800"))

        # Phase 1: 管道 A
        for rule in manifest.rules:
            log.heartbeat("pipeline_A")
            logger.info("管道 A: 处理法规 %s", rule.name)
            t0 = time.time()
            session_gen: Any | None = None
            try:
                from govdoc.pipelines.extract_rules import run_extract
                from govdoc.db.session import get_session
                from govdoc.runtime import get_trajectory_store

                traj_store = get_trajectory_store()
                session_gen = get_session()
                session = next(session_gen)
                extract_run = await asyncio.wait_for(
                    run_extract(
                        rule_source_id=_ensure_rule_source(rule, session),
                        session=session,
                        project_root=project_root,
                        trajectory_store=traj_store,
                    ),
                    timeout=pipeline_timeout,
                )
                duration = time.time() - t0
                usage = json.loads(extract_run.total_usage_json or "{}")
                total_tokens = sum(
                    v
                    for phase in usage.values()
                    if isinstance(phase, dict)
                    for v in phase.values()
                    if isinstance(v, int)
                )

                record_pipeline_run(
                    log,
                    pipeline="A",
                    project_name=rule.name,
                    input_file=rule.path,
                    status=extract_run.status,
                    duration_s=duration,
                    total_tokens=total_tokens,
                    error=getattr(extract_run, "error", None),
                )

                if extract_run.status in ("draft_ready", "completed"):
                    checkpoints = _load_extract_output(extract_run, session)
                    record_extract_results(log, checkpoints)
            except Exception as exc:
                import traceback

                duration = time.time() - t0
                tb = traceback.format_exc()
                record_pipeline_run(
                    log,
                    pipeline="A",
                    project_name=rule.name,
                    input_file=rule.path,
                    status="failed",
                    duration_s=duration,
                    total_tokens=0,
                    error=f"{type(exc).__name__}: {exc}",
                )
                log.log_event(
                    "pipeline_error",
                    {
                        "pipeline": "A",
                        "project_name": rule.name,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                        "traceback": tb,
                    },
                )
                logger.error("管道 A 失败: %s\n%s", rule.name, tb)
            finally:
                if session_gen is not None:
                    try:
                        session_gen.close()
                    except AttributeError:
                        pass

        # Phase 2: 管道 B
        for proj in manifest.projects:
            log.heartbeat("pipeline_B")
            logger.info("管道 B: 处理项目 %s", proj.name)
            t0 = time.time()
            session_gen: Any | None = None
            try:
                from govdoc.pipelines.audit_tender import run_audit
                from govdoc.db.session import get_session
                from govdoc.runtime import get_trajectory_store

                traj_store = get_trajectory_store()

                # 用独立 session 执行数据准备（创建 Project/TenderDoc/AuditRun/AuditPointRun）
                setup_gen = get_session()
                setup_session = next(setup_gen)
                try:
                    audit_run_id = _ensure_audit_run(proj, setup_session, manifest)
                finally:
                    setup_gen.close()

                # 用全新 session 执行 run_audit，避免 identity map 残留导致 StaleDataError
                session_gen = get_session()
                session = next(session_gen)
                audit_run = await asyncio.wait_for(
                    run_audit(
                        audit_run_id=audit_run_id,
                        session=session,
                        project_root=project_root,
                        trajectory_store=traj_store,
                    ),
                    timeout=pipeline_timeout,
                )
                duration = time.time() - t0

                record_pipeline_run(
                    log,
                    pipeline="B",
                    project_name=proj.name,
                    input_file=proj.tender_doc,
                    status=audit_run.status,
                    duration_s=duration,
                    total_tokens=0,
                )

                if audit_run.status in ("draft_ready", "partial_ready", "completed"):
                    findings = _load_audit_findings(audit_run, session)
                    record_audit_results(log, findings)
            except Exception as exc:
                import traceback

                duration = time.time() - t0
                tb = traceback.format_exc()
                record_pipeline_run(
                    log,
                    pipeline="B",
                    project_name=proj.name,
                    input_file=proj.tender_doc,
                    status="failed",
                    duration_s=duration,
                    total_tokens=0,
                    error=f"{type(exc).__name__}: {exc}",
                )
                log.log_event(
                    "pipeline_error",
                    {
                        "pipeline": "B",
                        "project_name": proj.name,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                        "traceback": tb,
                    },
                )
                logger.error("管道 B 失败: %s\n%s", proj.name, tb)
            finally:
                if session_gen is not None:
                    try:
                        session_gen.close()
                    except AttributeError:
                        pass

        # Phase 3: 语义评估
        logger.info("开始语义评估")
        _run_semantic_evaluations(log, rubric_dir, project_root)

    logger.info("L1 评估完成, run_id=%s", run_id)
    return run_id


def _clean_harness_state(session: Any) -> None:
    """清除 app DB 中上次 harness 运行残留的实体，确保干净起跑。"""
    from govdoc.db.models import (
        AuditPointRun,
        AuditRun,
        CheckpointFinal,
        ExtractRun,
        Project,
        RuleSource,
        TenderDoc,
        WorkpaperDraft,
    )

    harness_projects = session.exec(select(Project).where(Project.created_by == "harness")).all()
    for proj in harness_projects:
        audit_runs = session.exec(select(AuditRun).where(AuditRun.project_id == proj.id)).all()
        for ar in audit_runs:
            for apr in session.exec(
                select(AuditPointRun).where(AuditPointRun.audit_run_id == ar.id)
            ).all():
                session.delete(apr)
            for wd in session.exec(
                select(WorkpaperDraft).where(WorkpaperDraft.audit_run_id == ar.id)
            ).all():
                session.delete(wd)
            session.delete(ar)
        for td in session.exec(select(TenderDoc).where(TenderDoc.project_id == proj.id)).all():
            session.delete(td)
        session.delete(proj)

    for rs in session.exec(
        select(RuleSource).where(RuleSource.rule_library_entry_id == "harness-fixture")
    ).all():
        for er in session.exec(select(ExtractRun).where(ExtractRun.rule_source_id == rs.id)).all():
            session.delete(er)
        session.delete(rs)

    for cf in session.exec(
        select(CheckpointFinal).where(
            CheckpointFinal.approved_by.in_(["harness:golden-standard", "system:auto-promote"])
        )
    ).all():
        session.delete(cf)

    session.commit()
    logger.info("已清除上次 harness 残留数据")


def _ensure_rule_source(rule: Any, session: Any) -> str:
    """确保法规已入库，返回 rule_source_id。"""
    from govdoc.db.models import RuleSource

    rs = RuleSource(
        title=rule.name,
        source_path=str(rule.path),
        rule_library_entry_id="harness-fixture",
    )
    session.add(rs)
    session.commit()
    session.refresh(rs)
    return rs.id


def _ensure_audit_run(proj: Any, session: Any, manifest: Any) -> str:
    """确保审核运行已创建（含金标准审核点导入 + AuditPointRun），返回 audit_run_id。"""
    from govdoc.db.models import AuditPointRun, AuditRun, CheckpointFinal, Project, TenderDoc
    from govdoc.parsers.checkpoint_import import parse_checkpoint_file
    from govdoc.storage.files import DocumentStore
    from govdoc.runtime import get_config

    project = Project(name=proj.name, created_by="harness")
    session.add(project)
    session.commit()
    session.refresh(project)

    cfg = get_config()
    store = DocumentStore(cfg.storage_root, ocr_base_url=cfg.app.ocr_base_url)
    tender_path = Path(proj.tender_doc).expanduser().resolve()
    warnings_stack: list[str] = []
    md_path = store.get_or_convert(tender_path, warnings_stack=warnings_stack)
    if warnings_stack:
        logger.warning("文书转换警告: %s", warnings_stack)

    tender_doc = TenderDoc(
        project_id=project.id,
        filename=tender_path.name,
        storage_path=str(tender_path),
        markdown_path=str(md_path),
        qmd_collection="",
    )
    session.add(tender_doc)
    session.commit()
    session.refresh(tender_doc)

    max_checkpoints = int(os.environ.get("HARNESS_MAX_CHECKPOINTS", "0"))

    cp_ids: list[str] = []
    for cp_fixture in manifest.checkpoints:
        cp_path = Path(cp_fixture.path)
        if not cp_path.exists():
            logger.warning("审核点文件不存在: %s", cp_path)
            continue
        checkpoints, skipped = parse_checkpoint_file(cp_path)
        if max_checkpoints > 0:
            checkpoints = checkpoints[:max_checkpoints]
        logger.info(
            "导入审核点: %s → %d 条, 跳过 %d 行",
            cp_fixture.name,
            len(checkpoints),
            len(skipped),
        )
        for gov_cp in checkpoints:
            cf = CheckpointFinal(
                payload_json=gov_cp.model_dump_json(),
                approved_by="harness:golden-standard",
            )
            session.add(cf)
            cp_ids.append(cf.id)
    session.commit()

    audit_run = AuditRun(
        project_id=project.id,
        tender_doc_id=tender_doc.id,
        checkpoint_final_ids=json.dumps(cp_ids),
        total_count=len(cp_ids),
        status="pending",
    )
    session.add(audit_run)
    session.commit()
    session.refresh(audit_run)

    for cp_id in cp_ids:
        session.add(
            AuditPointRun(
                audit_run_id=audit_run.id,
                checkpoint_final_id=cp_id,
            )
        )
    session.commit()

    logger.info(
        "AuditRun %s 创建完成, %d 个审核点, %d 个 AuditPointRun",
        audit_run.id,
        len(cp_ids),
        len(cp_ids),
    )
    return audit_run.id


def _load_extract_output(extract_run: Any, session: Any) -> list[dict[str, Any]]:
    """从 ExtractRun 产出的 CheckpointFinal 加载审核点。

    策略：查询 approved_by='system:auto-promote' 且 approved_at >= extract_run.created_at。
    """
    from govdoc.db.models import CheckpointFinal

    cps = session.exec(
        select(CheckpointFinal).where(
            CheckpointFinal.approved_by == "system:auto-promote",
            CheckpointFinal.approved_at >= extract_run.created_at,
        )
    ).all()
    results = []
    for cp in cps:
        payload = (
            json.loads(cp.payload_json) if isinstance(cp.payload_json, str) else cp.payload_json
        )
        results.append(payload)
    return results


def _load_audit_findings(audit_run: Any, session: Any) -> list[dict[str, Any]]:
    """从 AuditRun 加载审核发现为 dict 列表。"""
    from govdoc.db.models import AuditPointRun

    point_runs = session.exec(
        select(AuditPointRun).where(AuditPointRun.audit_run_id == audit_run.id)
    ).all()
    results = []
    for pr in point_runs:
        if pr.finding_json:
            finding = (
                json.loads(pr.finding_json) if isinstance(pr.finding_json, str) else pr.finding_json
            )
            finding["point_run_id"] = pr.id
            finding["checkpoint_id"] = pr.checkpoint_final_id
            finding["duration_s"] = (
                (pr.completed_at - pr.created_at).total_seconds() if pr.completed_at else 0
            )
            finding["status"] = pr.status
            results.append(finding)
    return results


def _run_semantic_evaluations(log: HarnessLog, rubric_dir: str, project_root: str) -> None:
    """运行全部语义评估维度。"""
    import os
    from dotenv import load_dotenv

    load_dotenv()
    try:
        judge = HarnessJudge(
            provider="openai",
            model=os.environ.get("HARNESS_JUDGE_MODEL", "qwen3.6-plus"),
            base_url=os.environ.get("HARNESS_JUDGE_BASE_URL", "http://110.42.53.85:11098"),
            api_key=os.environ.get("HARNESS_JUDGE_API_KEY", ""),
        )
    except Exception as exc:
        import traceback

        tb = traceback.format_exc()
        log.log_event(
            "semantic_eval_fatal",
            {
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "traceback": tb,
            },
        )
        logger.error("HarnessJudge 初始化失败，跳过全部语义评估:\n%s", tb)
        return

    extract_rows = log.query("SELECT * FROM extract_results WHERE run_id=?", (log._run_id,))
    audit_rows = log.query("SELECT * FROM audit_results WHERE run_id=?", (log._run_id,))
    trajectory_rows = log.query("SELECT * FROM agent_trajectories WHERE run_id=?", (log._run_id,))

    dimensions = [
        "extract-faithfulness",
        "extract-recall",
        "extract-precision",
        "extract-hallucination",
        "extract-json-correctness",
        "extract-category-accuracy",
        "audit-faithfulness",
        "audit-relevancy",
        "audit-verdict-reasoning",
        "audit-hallucination",
        "audit-completeness",
        "audit-json-correctness",
        "agent-plan-quality",
        "agent-plan-adherence",
        "agent-step-efficiency",
        "agent-task-completion",
        "workpaper-summarization",
        "workpaper-finding-coverage",
        "workpaper-format-compliance",
    ]

    for dim in dimensions:
        try:
            criteria = load_rubric(rubric_dir, dim)
            evidence: dict[str, Any] = {
                "extract_results": extract_rows,
                "audit_results": audit_rows,
                "dimension": dim,
            }
            if dim.startswith("agent-") and trajectory_rows:
                evidence["trajectory"] = trajectory_rows
            if dim == "audit-completeness":
                evidence["audit_checkpoint_inventory"] = audit_rows
                evidence["note"] = (
                    "audit_results 包含所有应审审核点（含 pending/failed 状态），以此判断覆盖率"
                )
            if dim == "extract-json-correctness" and extract_rows:
                evidence["output_json"] = {
                    "checkpoints": [
                        {
                            "id": row.get("checkpoint_id", ""),
                            "category": row.get("category", ""),
                            "title": row.get("title", ""),
                            "description": row.get("description", ""),
                            "severity": row.get("severity", ""),
                            "legal_basis": json.loads(row["legal_basis_json"])
                            if row.get("legal_basis_json")
                            else [],
                        }
                        for row in extract_rows
                    ]
                }
            if dim.startswith("workpaper-"):
                wp_events = log.query(
                    "SELECT payload FROM _events WHERE run_id=? AND event_type='workpaper_draft'",
                    (log._run_id,),
                )
                if wp_events:
                    wp_payload = json.loads(wp_events[-1]["payload"])
                    evidence["workpaper_summary"] = wp_payload.get("summary", "")
                    evidence["workpaper_findings_verdicts"] = wp_payload.get(
                        "findings_verdicts", []
                    )
                    evidence["workpaper_findings_count"] = wp_payload.get("findings_count", 0)
            if dim == "audit-json-correctness" and audit_rows:
                assembled_findings = []
                for ar in audit_rows:
                    if ar.get("status") != "completed":
                        continue
                    verdict_json = ar.get("verdict_json", "{}")
                    try:
                        verdict_obj = (
                            json.loads(verdict_json)
                            if isinstance(verdict_json, str)
                            else verdict_json
                        )
                    except (json.JSONDecodeError, TypeError):
                        verdict_obj = {"verdict": ar.get("verdict", "")}
                    evidence_json = ar.get("evidence_json", "[]")
                    try:
                        evidence_refs = (
                            json.loads(evidence_json)
                            if isinstance(evidence_json, str)
                            else evidence_json
                        )
                    except (json.JSONDecodeError, TypeError):
                        evidence_refs = []
                    assembled_findings.append(
                        {
                            "checkpoint": {"id": ar.get("checkpoint_id", "")},
                            "verdict": verdict_obj,
                            "evidence_refs": evidence_refs,
                            "case_refs": [],
                        }
                    )
                completed_count = sum(1 for ar in audit_rows if ar.get("status") == "completed")
                total_count = len(audit_rows)
                evidence["output_json"] = {
                    "findings": assembled_findings,
                    "summary": f"共审核 {total_count} 个审核点，已完成 {completed_count} 项。",
                }
            evaluate_dimension(
                log=log,
                judge=judge,
                dimension=dim,
                criteria=criteria,
                evidence=evidence,
            )
            logger.info("语义评估 %s 完成", dim)
        except FileNotFoundError:
            log.log_event("semantic_eval_skip", {"dimension": dim, "reason": "rubric 文件缺失"})
            logger.warning("跳过 %s: rubric 文件缺失", dim)
        except Exception as exc:
            import traceback

            tb = traceback.format_exc()
            log.log_event(
                "semantic_eval_error",
                {
                    "dimension": dim,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "traceback": tb,
                },
            )
            logger.error("语义评估 %s 失败:\n%s", dim, tb)


def _init_run_tables(conn: sqlite3.Connection) -> None:
    """初始化 CLI 异常处理所需的固定表。"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _runs (
            run_id TEXT PRIMARY KEY,
            git_sha TEXT,
            started_at TEXT,
            finished_at TEXT,
            heartbeat_at TEXT,
            config JSON,
            status TEXT DEFAULT 'running'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            timestamp TEXT,
            event_type TEXT,
            payload JSON
        )
    """)
    conn.commit()


def _update_run_status(db_path: str, run_id: str, status: str) -> None:
    """确保运行记录存在，并更新最终状态。"""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        _init_run_tables(conn)
        now = _now_iso()
        conn.execute(
            "INSERT OR IGNORE INTO _runs (run_id, started_at, status) VALUES (?, ?, ?)",
            (run_id, now, "running"),
        )
        conn.execute(
            "UPDATE _runs SET finished_at = ?, status = ? WHERE run_id = ?",
            (now, status, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def _parse_args() -> argparse.Namespace:
    """解析 L1 管道评估 CLI 参数。"""
    parser = argparse.ArgumentParser(description="L1 管道 harness 评估")
    parser.add_argument("--manifest", default="scripts/fixtures/harness_manifest.yaml")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--rubric-dir", default="scripts/rubrics")
    parser.add_argument("--db-path", default="results/harness.db")
    return parser.parse_args()


def main() -> None:
    """运行 L1 管道评估 CLI，并记录致命异常与中断信号。"""
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    run_id = f"L1-{uuid.uuid4().hex[:8]}"
    root_logger = logging.getLogger()
    sqlite_handler = SqliteHandler(db_path=args.db_path, run_id=run_id)
    root_logger.addHandler(sqlite_handler)

    def _handle_signal(signum: int, frame: FrameType | None) -> NoReturn:
        """将进程中断写入运行记录后退出。"""
        del frame
        _update_run_status(args.db_path, run_id, "interrupted")
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        completed_run_id = asyncio.run(
            run_pipeline_eval(
                manifest_path=args.manifest,
                project_root=args.project_root,
                rubric_dir=args.rubric_dir,
                db_path=args.db_path,
                run_id=run_id,
            )
        )
        logger.info("L1 完成, run_id=%s", completed_run_id)
    except Exception:
        logger.critical("L1 管道评估发生致命异常", exc_info=True)
        _update_run_status(args.db_path, run_id, "crashed")
        sys.exit(1)
    finally:
        root_logger.removeHandler(sqlite_handler)
        sqlite_handler.close()


if __name__ == "__main__":
    main()
