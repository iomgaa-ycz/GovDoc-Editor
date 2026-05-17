"""Workpaper routes — 草稿/定稿/docx 下载。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import select

from govdoc.api.deps import get_db_session
from govdoc.api.middleware import log_activity
from govdoc.api.schemas import FinalizeWorkpaperRequest, UpdateWorkpaperDraftRequest
from govdoc.db.models import AuditRun, WorkpaperDraft, WorkpaperFinal

router = APIRouter(prefix="/api/v1/audit/runs", tags=["workpapers"])


@router.get("/{audit_run_id}/workpaper/draft")
async def get_workpaper_draft(audit_run_id: str):
    with get_db_session() as session:
        drafts = session.exec(
            select(WorkpaperDraft)
            .where(WorkpaperDraft.audit_run_id == audit_run_id)
            .order_by(WorkpaperDraft.version.desc())
        ).all()
        if not drafts:
            raise HTTPException(status_code=404, detail="未找到 WorkpaperDraft")
        draft = drafts[0]
        return {
            "id": draft.id,
            "version": draft.version,
            "workpaper_json": draft.workpaper_json,
            "docx_path": draft.docx_path,
        }


@router.put("/{audit_run_id}/workpaper/draft")
async def update_workpaper_draft(audit_run_id: str, payload: UpdateWorkpaperDraftRequest):
    with get_db_session() as session:
        current_drafts = session.exec(
            select(WorkpaperDraft)
            .where(WorkpaperDraft.audit_run_id == audit_run_id)
            .order_by(WorkpaperDraft.version.desc())
        ).all()
        next_version = max((d.version for d in current_drafts), default=0) + 1

        from govdoc.workpaper_renderer import render_workpaper_docx

        draft_path = render_workpaper_docx(
            payload.workpaper,
            audit_run_id,
            version=next_version,
        )

        draft = WorkpaperDraft(
            audit_run_id=audit_run_id,
            workpaper_json=payload.workpaper.model_dump_json(),
            docx_path=str(draft_path),
            version=next_version,
        )
        session.add(draft)
        log_activity(
            session,
            actor=payload.modified_by,
            action="update_workpaper_draft",
            target_type="WorkpaperDraft",
            target_id=draft.id,
            after={"version": next_version, "audit_run_id": audit_run_id},
        )
        session.commit()
        session.refresh(draft)
        return {"id": draft.id, "version": draft.version}


@router.post("/{audit_run_id}/workpaper/finalize-partial", status_code=201)
async def finalize_workpaper_partial(
    audit_run_id: str,
    payload: FinalizeWorkpaperRequest,
    background_tasks: BackgroundTasks,
):
    with get_db_session() as session:
        run = session.get(AuditRun, audit_run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="AuditRun 不存在")
        if run.status not in ("partial_ready", "draft_ready"):
            raise HTTPException(status_code=400, detail=f"状态 {run.status} 不支持部分定稿")

    with get_db_session() as log_session:
        log_activity(
            log_session,
            actor=payload.approved_by,
            action="finalize_workpaper",
            target_type="AuditRun",
            target_id=audit_run_id,
            after={"partial": True},
        )
        log_session.commit()

    from govdoc.pipelines.finalize import finalize_workpaper

    async def _run_partial():
        with get_db_session() as s:
            try:
                await finalize_workpaper(
                    audit_run_id,
                    approved_by=payload.approved_by,
                    session=s,
                    partial=True,
                )
            except Exception:
                pass

    background_tasks.add_task(_run_partial)
    return {"audit_run_id": audit_run_id, "status": "finalizing_partial"}


@router.post("/{audit_run_id}/workpaper/finalize", status_code=201)
async def finalize_workpaper_endpoint(
    audit_run_id: str,
    payload: FinalizeWorkpaperRequest,
    background_tasks: BackgroundTasks,
):
    with get_db_session() as session:
        run = session.get(AuditRun, audit_run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="AuditRun 不存在")

    with get_db_session() as log_session:
        log_activity(
            log_session,
            actor=payload.approved_by,
            action="finalize_workpaper",
            target_type="AuditRun",
            target_id=audit_run_id,
            after={"partial": False},
        )
        log_session.commit()

    from govdoc.pipelines.finalize import finalize_workpaper

    async def _run_finalize():
        with get_db_session() as s:
            try:
                await finalize_workpaper(
                    audit_run_id,
                    approved_by=payload.approved_by,
                    session=s,
                )
            except Exception:
                pass

    background_tasks.add_task(_run_finalize)
    return {"audit_run_id": audit_run_id, "status": "finalizing"}


@router.get("/{audit_run_id}/workpaper/final/docx", response_class=StreamingResponse)
async def download_final_workpaper_docx(audit_run_id: str):
    with get_db_session() as session:
        finals = session.exec(
            select(WorkpaperFinal).where(WorkpaperFinal.audit_run_id == audit_run_id)
        ).all()
        if not finals:
            raise HTTPException(status_code=404, detail="未找到 WorkpaperFinal")
        final = finals[-1]
        docx_path = Path(final.docx_path)
        if not docx_path.exists():
            raise HTTPException(status_code=404, detail="docx 文件不存在")
    return StreamingResponse(
        open(docx_path, "rb"),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename=workpaper-final-{audit_run_id}.docx"
        },
    )
