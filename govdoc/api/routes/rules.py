"""Rules routes — 法规上传 + 管道 A 触发。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from sqlmodel import select

from govdoc.api.deps import get_db_session
from govdoc.api.middleware import log_activity
from govdoc.db.models import CheckpointFinal, ExtractRun, RuleSource
from govdoc.runtime import get_document_store, get_libraries

router = APIRouter(prefix="/api/v1/rules", tags=["rules"])
logger = logging.getLogger(__name__)


@router.get("")
async def list_rule_sources():
    with get_db_session() as session:
        sources = session.exec(select(RuleSource).order_by(RuleSource.added_at.desc())).all()
        return [
            {
                "id": s.id,
                "title": s.title,
                "source_path": s.source_path,
                "added_at": str(s.added_at),
            }
            for s in sources
        ]


@router.post("/upload", status_code=202)
async def upload_rule(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    file: UploadFile = File(...),
):
    store = get_document_store()
    content = await file.read()
    raw_path = store.save_raw(file.filename or "rule.md", content, subdir="rules")
    warnings_stack: list[str] = []
    md_path = store.get_or_convert(raw_path, warnings_stack=warnings_stack)

    # 写入 RuleLibrary
    import uuid

    entry_id = f"rules_{uuid.uuid4().hex}"
    rule_library, _, _ = get_libraries()
    rule_entry = rule_library.add(
        entry_id=entry_id,
        markdown=md_path.read_text(encoding="utf-8"),
        metadata={"title": title, "filename": file.filename or ""},
    )

    with get_db_session() as session:
        rule_source = RuleSource(
            title=title,
            source_path=str(md_path),
            rule_library_entry_id=rule_entry.entry_id,
        )
        session.add(rule_source)
        log_activity(
            session,
            actor="system",
            action="upload_rule",
            target_type="RuleSource",
            target_id=rule_source.id,
            after={"title": title, "filename": file.filename or ""},
        )
        session.commit()
        session.refresh(rule_source)

        extract_run = ExtractRun(rule_source_id=rule_source.id, status="pending")
        session.add(extract_run)
        session.commit()
        session.refresh(extract_run)

        result = {
            "rule_source_id": rule_source.id,
            "extract_run_id": extract_run.id,
            "status": "pending",
            "warnings": warnings_stack,
        }

    from govdoc.pipelines.extract_rules import run_extract

    async def _run_extract():
        with get_db_session() as s:
            try:
                await run_extract(rule_source.id, s, extract_run_id=extract_run.id)
            except Exception:
                logger.exception("后台提取执行失败: %s", extract_run.id)
                try:
                    er = s.get(ExtractRun, extract_run.id)
                    if er is not None and er.status not in ("draft_ready", "completed", "failed"):
                        er.status = "failed"
                        er.error = "后台任务异常退出"
                        s.add(er)
                        s.commit()
                except Exception:
                    pass

    background_tasks.add_task(_run_extract)
    return result


@router.get("/{rule_id}/extract-runs/{run_id}/status")
async def get_extract_run_status(rule_id: str, run_id: str):
    with get_db_session() as session:
        run = session.get(ExtractRun, run_id)
        if run is None or run.rule_source_id != rule_id:
            raise HTTPException(status_code=404, detail="ExtractRun 不存在")
        return {
            "run_id": run.id,
            "status": run.status,
            "workspace_archive_path": run.workspace_archive_path,
            "workspace_failed_path": run.workspace_failed_path,
            "error": run.error,
        }


@router.get("/{rule_id}/extract-runs/{run_id}/preview")
async def get_extract_run_preview(rule_id: str, run_id: str):
    """返回提取运行中已提取的审核点数量（提取进行中可轮询）。"""
    with get_db_session() as session:
        run = session.get(ExtractRun, run_id)
        if run is None or run.rule_source_id != rule_id:
            raise HTTPException(status_code=404, detail="ExtractRun 不存在")
        checkpoint_count = len(session.exec(select(CheckpointFinal)).all())
        return {
            "run_id": run.id,
            "status": run.status,
            "extracted_count": checkpoint_count,
        }
