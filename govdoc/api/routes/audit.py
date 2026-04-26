"""Audit routes — 管道 B 触发 + 状态 + 重试。"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlmodel import select

from govdoc.api.deps import get_db_session
from govdoc.api.schemas import AuditRunProgressResponse, CreateAuditRunRequest
from govdoc.db.models import AuditPointRun, AuditRun, CheckpointFinal, TenderDoc

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])
logger = logging.getLogger(__name__)


def _load_supplementary_doc_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


@router.post("/runs", status_code=202)
async def create_audit_run(
    payload: CreateAuditRunRequest,
    background_tasks: BackgroundTasks,
):
    with get_db_session() as session:
        main_doc = session.get(TenderDoc, payload.tender_doc_id)
        if main_doc is None or main_doc.project_id != payload.project_id:
            raise HTTPException(status_code=400, detail="主文书不存在或不属于该项目")

        seen = {payload.tender_doc_id}
        supplementary_doc_ids: list[str] = []
        for doc_id in payload.supplementary_doc_ids:
            if doc_id in seen:
                raise HTTPException(
                    status_code=400,
                    detail=f"附件 ID 重复或与主文书冲突: {doc_id}",
                )
            doc = session.get(TenderDoc, doc_id)
            if doc is None or doc.project_id != payload.project_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"附件不存在或不属于该项目: {doc_id}",
                )
            seen.add(doc_id)
            supplementary_doc_ids.append(doc_id)

        for cp_id in payload.checkpoint_ids:
            cp = session.get(CheckpointFinal, cp_id)
            if cp is None:
                raise HTTPException(status_code=400, detail=f"CheckpointFinal 不存在: {cp_id}")

        audit_run = AuditRun(
            project_id=payload.project_id,
            tender_doc_id=payload.tender_doc_id,
            supplementary_doc_ids=json.dumps(supplementary_doc_ids, ensure_ascii=False),
            checkpoint_final_ids=json.dumps(payload.checkpoint_ids, ensure_ascii=False),
            total_count=len(payload.checkpoint_ids),
        )
        session.add(audit_run)
        session.commit()
        session.refresh(audit_run)

        for cp_id in payload.checkpoint_ids:
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
        }

    from govdoc.pipelines.audit_tender import run_audit

    async def _run_audit():
        with get_db_session() as s:
            try:
                await run_audit(audit_run.id, s)
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
        return [
            {
                "id": r.id,
                "project_id": r.project_id,
                "tender_doc_id": r.tender_doc_id,
                "supplementary_doc_ids": _load_supplementary_doc_ids(r.supplementary_doc_ids),
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
        return {
            "id": run.id,
            "project_id": run.project_id,
            "tender_doc_id": run.tender_doc_id,
            "supplementary_doc_ids": _load_supplementary_doc_ids(run.supplementary_doc_ids),
            "status": run.status,
            "processed_count": run.processed_count,
            "total_count": run.total_count,
            "error": run.error,
        }


@router.get("/runs/{audit_run_id}/progress")
async def get_audit_run_progress(audit_run_id: str):
    with get_db_session() as session:
        run = session.get(AuditRun, audit_run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="AuditRun 不存在")

        point_runs = session.exec(
            select(AuditPointRun).where(AuditPointRun.audit_run_id == audit_run_id)
        ).all()

        return AuditRunProgressResponse(
            audit_run_id=run.id,
            status=run.status,
            total_count=run.total_count,
            processed_count=run.processed_count,
            point_runs=[
                {
                    "id": pr.id,
                    "checkpoint_final_id": pr.checkpoint_final_id,
                    "status": pr.status,
                    "error": pr.error,
                    "finding_json": pr.finding_json,
                }
                for pr in point_runs
            ],
        )


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
