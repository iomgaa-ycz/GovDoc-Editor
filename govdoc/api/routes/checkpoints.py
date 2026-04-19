"""Checkpoints routes — 统一查看/编辑/删除审核点。"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from sqlmodel import select

from govdoc.api.deps import get_db_session
from govdoc.api.schemas import UpdateCheckpointRequest
from govdoc.db.models import CheckpointDraft, CheckpointFinal

router = APIRouter(prefix="/api/v1/checkpoints", tags=["checkpoints"])


def _serialize_draft(draft: CheckpointDraft) -> dict[str, str | None]:
    return {
        "id": draft.id,
        "kind": "draft",
        "status": draft.status,
        "payload_json": draft.payload_json,
        "approved_by": None,
        "rule_source_id": draft.rule_source_id,
    }


def _serialize_final(final: CheckpointFinal) -> dict[str, str | None]:
    return {
        "id": final.id,
        "kind": "final",
        "status": "final",
        "payload_json": final.payload_json,
        "approved_by": final.approved_by,
    }


@router.get("")
async def list_checkpoints():
    with get_db_session() as session:
        drafts = session.exec(
            select(CheckpointDraft).where(CheckpointDraft.status != "promoted")
        ).all()
        finals = session.exec(select(CheckpointFinal)).all()
        payload = [_serialize_final(final) for final in finals]
        payload.extend(_serialize_draft(draft) for draft in drafts)
        payload.sort(key=lambda item: (item["kind"] or "", item["id"] or ""))
        return payload


_ALLOWED_EXTENSIONS = {".xls", ".xlsx", ".csv"}


@router.post("/import")
async def import_checkpoints(file: UploadFile = File(...)):
    """上传审查点表格（xls/xlsx/csv），批量生成 CheckpointDraft。"""
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {suffix}，仅支持 .xls / .xlsx / .csv",
        )

    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        from govdoc.parsers.checkpoint_import import parse_checkpoint_file

        checkpoints, skipped_reasons = parse_checkpoint_file(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    drafts: list[dict[str, str | None]] = []
    with get_db_session() as session:
        for cp in checkpoints:
            draft = CheckpointDraft(
                payload_json=cp.model_dump_json(),
                status="draft",
            )
            session.add(draft)
            session.flush()
            drafts.append(_serialize_draft(draft))
        session.commit()

    return {
        "imported_count": len(checkpoints),
        "skipped_count": len(skipped_reasons),
        "skipped_reasons": skipped_reasons,
        "drafts": drafts,
    }


@router.put("/{checkpoint_id}")
async def update_checkpoint(checkpoint_id: str, payload: UpdateCheckpointRequest):
    with get_db_session() as session:
        final = session.get(CheckpointFinal, checkpoint_id)
        if final is not None:
            final.payload_json = payload.payload_json
            session.add(final)
            session.commit()
            return _serialize_final(final)

        draft = session.get(CheckpointDraft, checkpoint_id)
        if draft is not None:
            draft.payload_json = payload.payload_json
            session.add(draft)
            session.commit()
            return _serialize_draft(draft)

        raise HTTPException(status_code=404, detail="Checkpoint 不存在")


@router.delete("/{checkpoint_id}", status_code=204)
async def delete_checkpoint(checkpoint_id: str) -> Response:
    with get_db_session() as session:
        final = session.get(CheckpointFinal, checkpoint_id)
        if final is not None:
            session.delete(final)
            session.commit()
            return Response(status_code=204)

        draft = session.get(CheckpointDraft, checkpoint_id)
        if draft is not None:
            session.delete(draft)
            session.commit()
            return Response(status_code=204)

        raise HTTPException(status_code=404, detail="Checkpoint 不存在")
