"""Checkpoints routes — 统一查看/编辑/删除已入库审核点。"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlmodel import select

from govdoc.api.deps import get_current_user, get_db_session
from govdoc.api.middleware import log_activity
from govdoc.api.schemas import UpdateCheckpointRequest
from govdoc.db.models import CheckpointFinal, User

router = APIRouter(prefix="/api/v1/checkpoints", tags=["checkpoints"])


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
        finals = session.exec(select(CheckpointFinal)).all()
        payload = [_serialize_final(final) for final in finals]
        payload.sort(key=lambda item: item["id"] or "")
        return payload


_ALLOWED_EXTENSIONS = {".xls", ".xlsx", ".csv"}


@router.post("/import")
async def import_checkpoints(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """上传审查点表格（xls/xlsx/csv），批量写入审核点库。"""
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
    except ModuleNotFoundError as exc:
        missing = exc.name or "解析依赖"
        raise HTTPException(
            status_code=500,
            detail=f"服务器缺少表格解析依赖: {missing}，请安装项目依赖后重试",
        ) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    imported: list[dict[str, str | None]] = []
    with get_db_session() as session:
        for cp in checkpoints:
            final = CheckpointFinal(
                payload_json=cp.model_dump_json(),
                approved_by="system:import",
            )
            session.add(final)
            session.flush()
            imported.append(_serialize_final(final))
        session.commit()

    return {
        "imported_count": len(checkpoints),
        "skipped_count": len(skipped_reasons),
        "skipped_reasons": skipped_reasons,
        "checkpoints": imported,
    }


@router.put("/{checkpoint_id}")
async def update_checkpoint(
    checkpoint_id: str,
    payload: UpdateCheckpointRequest,
    current_user: User = Depends(get_current_user),
):
    with get_db_session() as session:
        final = session.get(CheckpointFinal, checkpoint_id)
        if final is not None:
            old_payload = final.payload_json
            final.payload_json = payload.payload_json
            log_activity(
                session,
                actor=current_user.username,
                action="update_checkpoint",
                target_type="CheckpointFinal",
                target_id=checkpoint_id,
                before={"payload_json": old_payload},
                after={"payload_json": payload.payload_json},
            )
            session.add(final)
            session.commit()
            return _serialize_final(final)

        raise HTTPException(status_code=404, detail="Checkpoint 不存在")


@router.delete("/{checkpoint_id}", status_code=204)
async def delete_checkpoint(
    checkpoint_id: str,
    current_user: User = Depends(get_current_user),
) -> Response:
    with get_db_session() as session:
        final = session.get(CheckpointFinal, checkpoint_id)
        if final is not None:
            log_activity(
                session,
                actor=current_user.username,
                action="delete_checkpoint",
                target_type="CheckpointFinal",
                target_id=checkpoint_id,
                before={"payload_json": final.payload_json},
            )
            session.delete(final)
            session.commit()
            return Response(status_code=204)

        raise HTTPException(status_code=404, detail="Checkpoint 不存在")
