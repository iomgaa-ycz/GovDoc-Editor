"""Audit routes — 管道 B 触发 + 状态 + 重试。"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlmodel import Session, select

from govdoc.api.deps import get_db_session
from govdoc.api.middleware import log_activity
from govdoc.api.schemas import AuditRunProgressResponse, CreateAuditRunRequest
from govdoc.db.models import (
    AuditPointRun,
    AuditRun,
    CheckpointFinal,
    CheckpointLibrary,
    CheckpointLibraryItem,
    Document,
    Project,
)

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])
logger = logging.getLogger(__name__)


def _load_supplementary_doc_ids(raw: str | None) -> list[str]:
    """解析 AuditRun.supplementary_doc_ids 的 JSON 字符串为 ID 列表。

    容错处理：空值、JSON 解析失败、非列表值均返回空列表。
    """
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def _resolve_checkpoint_ids_from_library(
    session: "Session",
    library_id: str,
) -> tuple[CheckpointLibrary, list[str], int]:
    """从审核点库解析出有效审核点 ID 列表，跳过已删除的审核点。"""
    library = session.get(CheckpointLibrary, library_id)
    if library is None:
        raise HTTPException(status_code=400, detail=f"审核点库不存在: {library_id}")

    items = session.exec(
        select(CheckpointLibraryItem)
        .where(CheckpointLibraryItem.library_id == library_id)
        .order_by(CheckpointLibraryItem.added_at)
    ).all()
    all_cp_ids = [item.checkpoint_final_id for item in items]
    if not all_cp_ids:
        raise HTTPException(status_code=400, detail="审核点库为空或库内审核点均已删除")

    existing_ids = set(
        session.exec(select(CheckpointFinal.id).where(CheckpointFinal.id.in_(all_cp_ids))).all()
    )

    checkpoint_ids = [cp_id for cp_id in all_cp_ids if cp_id in existing_ids]
    skipped_deleted_count = len(all_cp_ids) - len(checkpoint_ids)

    if not checkpoint_ids:
        raise HTTPException(status_code=400, detail="审核点库为空或库内审核点均已删除")
    return library, checkpoint_ids, skipped_deleted_count


def _resolve_supplementary_doc_ids(
    session: "Session",
    main_document_id: str,
    supplementary_document_ids: list[str],
) -> list[str]:
    """校验附件文档并返回去重后的附件 ID 列表。

    与主文书 ID 冲突或附件 ID 重复时报 400；附件文档不存在时报 400。
    """
    seen = {main_document_id}
    resolved: list[str] = []
    for doc_id in supplementary_document_ids:
        if doc_id in seen:
            raise HTTPException(
                status_code=400,
                detail=f"附件 ID 重复或与主文书冲突: {doc_id}",
            )
        if session.get(Document, doc_id) is None:
            raise HTTPException(status_code=400, detail=f"附件不存在: {doc_id}")
        seen.add(doc_id)
        resolved.append(doc_id)
    return resolved


def _validate_checkpoints_exist(session: "Session", checkpoint_ids: list[str]) -> None:
    """校验所有审核点 ID 均存在，任一不存在则报 400。"""
    for cp_id in checkpoint_ids:
        if session.get(CheckpointFinal, cp_id) is None:
            raise HTTPException(status_code=400, detail=f"CheckpointFinal 不存在: {cp_id}")


@router.post("/runs", status_code=202)
async def create_audit_run(
    payload: CreateAuditRunRequest,
    background_tasks: BackgroundTasks,
):
    with get_db_session() as session:
        main_doc = session.get(Document, payload.main_document_id)
        if main_doc is None:
            raise HTTPException(status_code=400, detail="主文书不存在")

        supplementary_doc_ids = _resolve_supplementary_doc_ids(
            session,
            payload.main_document_id,
            payload.supplementary_document_ids,
        )

        checkpoint_ids = list(payload.checkpoint_ids)
        source_library: CheckpointLibrary | None = None
        skipped_deleted_count = 0
        if payload.checkpoint_library_id:
            if checkpoint_ids:
                raise HTTPException(
                    status_code=400, detail="checkpoint_ids 与 checkpoint_library_id 不能同时传"
                )
            source_library, checkpoint_ids, skipped_deleted_count = (
                _resolve_checkpoint_ids_from_library(
                    session,
                    payload.checkpoint_library_id,
                )
            )
        elif not checkpoint_ids:
            raise HTTPException(status_code=400, detail="至少需要选择一个审核点或审核点库")

        _validate_checkpoints_exist(session, checkpoint_ids)

        audit_run = AuditRun(
            project_id=payload.project_id,
            main_document_id=payload.main_document_id,
            supplementary_doc_ids=json.dumps(supplementary_doc_ids, ensure_ascii=False),
            checkpoint_final_ids=json.dumps(checkpoint_ids, ensure_ascii=False),
            checkpoint_library_id=source_library.id if source_library else None,
            checkpoint_library_name_snapshot=source_library.name if source_library else None,
            total_count=len(checkpoint_ids),
        )
        session.add(audit_run)
        if hasattr(audit_run, "created_by"):
            audit_run.created_by = payload.created_by
        log_activity(
            session,
            actor=payload.created_by,
            action="create_audit_run",
            target_type="AuditRun",
            target_id=audit_run.id,
            after={
                "project_id": payload.project_id,
                "main_document_id": payload.main_document_id,
                "checkpoint_library_id": source_library.id if source_library else None,
            },
        )
        session.commit()
        session.refresh(audit_run)

        for cp_id in checkpoint_ids:
            point_run = AuditPointRun(
                audit_run_id=audit_run.id,
                checkpoint_final_id=cp_id,
            )
            session.add(point_run)
        session.commit()

        result = {
            "audit_run_id": audit_run.id,
            "total_count": audit_run.total_count,
            "status": audit_run.status,
            "checkpoint_library_id": audit_run.checkpoint_library_id,
            "checkpoint_library_name_snapshot": audit_run.checkpoint_library_name_snapshot,
            "skipped_deleted_count": skipped_deleted_count,
        }

    from govdoc.pipelines.audit_tender import run_audit

    async def _run_audit():
        with get_db_session() as s:
            try:
                await run_audit(audit_run.id, s)
            except Exception:
                logger.exception("后台审核执行失败: %s", audit_run.id)
                try:
                    ar = s.get(AuditRun, audit_run.id)
                    if ar is not None and ar.status not in (
                        "draft_ready",
                        "completed",
                        "partial_ready",
                        "failed",
                        "waiting_retry",
                    ):
                        ar.status = "failed"
                        ar.error = "后台任务异常退出"
                        s.add(ar)
                        s.commit()
                except Exception:
                    pass

    background_tasks.add_task(_run_audit)
    return result


@router.get("/runs")
async def list_audit_runs(project_id: str | None = None):
    with get_db_session() as session:
        stmt = select(AuditRun).order_by(AuditRun.created_at.desc())
        if project_id:
            stmt = stmt.where(AuditRun.project_id == project_id)
        runs = session.exec(stmt).all()

        project_ids = {r.project_id for r in runs}
        projects = (
            session.exec(select(Project).where(Project.id.in_(project_ids))).all()
            if project_ids
            else []
        )
        project_names = {p.id: p.name for p in projects}

        return [
            {
                "id": r.id,
                "project_id": r.project_id,
                "project_name": project_names.get(r.project_id, ""),
                "main_document_id": r.main_document_id,
                "tender_doc_id": r.main_document_id,
                "supplementary_doc_ids": _load_supplementary_doc_ids(r.supplementary_doc_ids),
                "checkpoint_library_id": r.checkpoint_library_id,
                "checkpoint_library_name_snapshot": r.checkpoint_library_name_snapshot,
                "status": r.status,
                "processed_count": r.processed_count,
                "total_count": r.total_count,
                "error": r.error,
                "created_at": str(r.created_at),
            }
            for r in runs
        ]


@router.get("/runs/{audit_run_id}")
async def get_audit_run(audit_run_id: str):
    with get_db_session() as session:
        run = session.get(AuditRun, audit_run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="AuditRun 不存在")
        project = session.get(Project, run.project_id)
        return {
            "id": run.id,
            "project_id": run.project_id,
            "project_name": project.name if project else "",
            "main_document_id": run.main_document_id,
            "tender_doc_id": run.main_document_id,
            "supplementary_doc_ids": _load_supplementary_doc_ids(run.supplementary_doc_ids),
            "checkpoint_library_id": run.checkpoint_library_id,
            "checkpoint_library_name_snapshot": run.checkpoint_library_name_snapshot,
            "status": run.status,
            "processed_count": run.processed_count,
            "total_count": run.total_count,
            "error": run.error,
        }


def _filter_orphan_point_runs(
    point_runs: list[AuditPointRun],
    existing_checkpoint_ids: set[str],
) -> list[AuditPointRun]:
    """过滤掉 checkpoint 已被硬删除的孤儿 point_run。

    archived 审核点的 CheckpointFinal 记录仍存在，不会被过滤。

    Args:
        point_runs: 某 audit_run 下的全部 AuditPointRun。
        existing_checkpoint_ids: 当前 CheckpointFinal 表中存在的 id 集合。

    Returns:
        checkpoint 仍存在的 point_run 列表。
    """
    return [pr for pr in point_runs if pr.checkpoint_final_id in existing_checkpoint_ids]


@router.get("/runs/{audit_run_id}/progress")
async def get_audit_run_progress(audit_run_id: str):
    with get_db_session() as session:
        run = session.get(AuditRun, audit_run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="AuditRun 不存在")

        point_runs = [
            pr
            for pr in session.exec(
                select(AuditPointRun).where(AuditPointRun.audit_run_id == audit_run_id)
            ).all()
            if pr.status != "excluded"
        ]

        cp_ids = {pr.checkpoint_final_id for pr in point_runs}
        existing_ids = (
            set(
                session.exec(select(CheckpointFinal.id).where(CheckpointFinal.id.in_(cp_ids))).all()
            )
            if cp_ids
            else set()
        )
        visible_runs = _filter_orphan_point_runs(list(point_runs), existing_ids)
        orphan_count = len(point_runs) - len(visible_runs)

        return AuditRunProgressResponse(
            audit_run_id=run.id,
            status=run.status,
            total_count=max(run.total_count - orphan_count, len(visible_runs)),
            processed_count=max(run.processed_count - orphan_count, 0),
            point_runs=[
                {
                    "id": pr.id,
                    "checkpoint_final_id": pr.checkpoint_final_id,
                    "status": pr.status,
                    "error": pr.error,
                    "finding_json": pr.finding_json,
                    "started_at": str(pr.started_at) if pr.started_at else None,
                    "completed_at": str(pr.completed_at) if pr.completed_at else None,
                    "current_phase": pr.current_phase,
                }
                for pr in visible_runs
            ],
        )


@router.post("/runs/{audit_run_id}/cancel", status_code=200)
async def cancel_audit_run(audit_run_id: str):
    """取消一个正在运行的审核。后台任务会在下一个审核点开始前检查并停止。"""
    with get_db_session() as session:
        run = session.get(AuditRun, audit_run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="AuditRun 不存在")
        if run.status not in ("pending", "running"):
            raise HTTPException(status_code=400, detail=f"状态 {run.status} 不可取消")
        old_status = run.status
        run.status = "cancelled"
        log_activity(
            session,
            actor="system",
            action="cancel_audit_run",
            target_type="AuditRun",
            target_id=run.id,
            before={"status": old_status},
            after={"status": "cancelled"},
        )
        session.add(run)
        session.commit()
        return {"audit_run_id": run.id, "status": "cancelled"}


@router.post("/point-runs/{point_run_id}/retry", status_code=202)
async def retry_point_run(
    point_run_id: str,
    background_tasks: BackgroundTasks,
):
    from govdoc.pipelines.audit_tender import prepare_point_run_retry as _prepare
    from govdoc.pipelines.audit_tender import retry_point_run as _retry

    with get_db_session() as session:
        try:
            _prepare(point_run_id, session)
        except ValueError as exc:
            detail = str(exc)
            if "未找到 AuditPointRun" in detail:
                raise HTTPException(status_code=404, detail="AuditPointRun 不存在") from exc
            raise HTTPException(status_code=400, detail=detail) from exc

    async def _run_retry():
        with get_db_session() as s:
            try:
                await _retry(point_run_id, s, prepared=True)
            except Exception:
                logger.exception("后台重试审核点失败: %s", point_run_id)

    background_tasks.add_task(_run_retry)
    return {"point_run_id": point_run_id, "status": "retrying"}
