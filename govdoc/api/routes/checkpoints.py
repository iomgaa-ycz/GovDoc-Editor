"""Checkpoints routes — 统一查看/编辑/删除已入库审核点。"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from pydantic import ValidationError
from sqlmodel import Session, select

from govdoc.api.deps import get_db_session
from govdoc.api.middleware import log_activity
from govdoc.api.schemas import UpdateCheckpointRequest
from govdoc.db.models import AuditPointRun, AuditRun, CheckpointFinal
from govdoc.schemas import GovCheckpoint

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


class CheckpointDedupError(RuntimeError):
    """审核点去重失败。"""


@dataclass(slots=True)
class DedupStats:
    """审核点去重诊断信息。

    Attributes:
        removed_existing_count: 删除的旧库重复审核点数量。
        rewired_audit_point_runs: 被迁移的 AuditPointRun 数量。
        rewired_audit_runs: 被迁移的 AuditRun 数量。
    """

    removed_existing_count: int = 0
    rewired_audit_point_runs: int = 0
    rewired_audit_runs: int = 0


def _checkpoint_title_key(payload_json: str) -> str | None:
    """从 CheckpointFinal.payload_json 提取 title 去重键。

    Args:
        payload_json: CheckpointFinal.payload_json 原始 JSON 字符串。

    Returns:
        去除首尾空白后的 title；payload 非法或 title 为空时返回 None。
    """
    try:
        checkpoint = GovCheckpoint.model_validate_json(payload_json)
    except ValidationError:
        return None
    title = checkpoint.title.strip()
    return title or None


def _dedupe_ids_preserving_order(ids: list[str]) -> list[str]:
    """对 ID 列表去重并保持第一次出现顺序。"""
    seen: set[str] = set()
    result: list[str] = []
    for item in ids:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _rewire_checkpoint_references(
    session: Session,
    replacement_map: dict[str, str],
) -> tuple[int, int]:
    """把被删除审核点的引用迁移到保留审核点。

    Args:
        session: 当前数据库 session，调用方负责 commit/rollback。
        replacement_map: old_checkpoint_id -> keep_checkpoint_id。

    Returns:
        (rewired_audit_point_runs, rewired_audit_runs)。

    Raises:
        CheckpointDedupError: AuditRun.checkpoint_final_ids 不是合法 JSON list[str]。
    """
    if not replacement_map:
        return 0, 0

    old_ids = list(replacement_map)
    point_runs = session.exec(
        select(AuditPointRun).where(AuditPointRun.checkpoint_final_id.in_(old_ids))
    ).all()
    for point_run in point_runs:
        point_run.checkpoint_final_id = replacement_map[point_run.checkpoint_final_id]
        session.add(point_run)

    rewired_audit_runs = 0
    audit_runs = session.exec(select(AuditRun)).all()
    for audit_run in audit_runs:
        try:
            raw_ids = json.loads(audit_run.checkpoint_final_ids)
        except json.JSONDecodeError as exc:
            raise CheckpointDedupError(
                f"AuditRun {audit_run.id} checkpoint_final_ids 不是合法 JSON"
            ) from exc
        if not isinstance(raw_ids, list) or not all(isinstance(item, str) for item in raw_ids):
            raise CheckpointDedupError(
                f"AuditRun {audit_run.id} checkpoint_final_ids 必须是 list[str]"
            )
        replaced_ids = [replacement_map.get(item, item) for item in raw_ids]
        deduped_ids = _dedupe_ids_preserving_order(replaced_ids)
        if deduped_ids != raw_ids:
            audit_run.checkpoint_final_ids = json.dumps(deduped_ids, ensure_ascii=False)
            session.add(audit_run)
            rewired_audit_runs += 1

    return len(point_runs), rewired_audit_runs


def deduplicate_existing_checkpoints(session: Session) -> DedupStats:
    """清理 CheckpointFinal 旧库中 title 重复的记录。

    同一 title 只保留 approved_at 最新的记录；approved_at 相同时保留 id 字典序较大者。
    删除旧记录前会迁移 AuditPointRun 和 AuditRun 引用。

    Args:
        session: 当前数据库 session，调用方负责 commit/rollback。

    Returns:
        DedupStats 去重诊断。
    """
    finals = session.exec(select(CheckpointFinal)).all()
    groups: dict[str, list[CheckpointFinal]] = {}
    for final in finals:
        title_key = _checkpoint_title_key(final.payload_json)
        if title_key is None:
            continue
        groups.setdefault(title_key, []).append(final)

    replacement_map: dict[str, str] = {}
    delete_targets: list[CheckpointFinal] = []
    for grouped_finals in groups.values():
        if len(grouped_finals) < 2:
            continue
        keep = max(grouped_finals, key=lambda item: (item.approved_at, item.id))
        for final in grouped_finals:
            if final.id == keep.id:
                continue
            replacement_map[final.id] = keep.id
            delete_targets.append(final)

    rewired_point_runs, rewired_audit_runs = _rewire_checkpoint_references(session, replacement_map)
    for final in delete_targets:
        session.delete(final)

    return DedupStats(
        removed_existing_count=len(delete_targets),
        rewired_audit_point_runs=rewired_point_runs,
        rewired_audit_runs=rewired_audit_runs,
    )


@router.post("/import")
async def import_checkpoints(file: UploadFile = File(...)):
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
        deduplicate_existing_checkpoints(session)
        existing_titles = {
            title
            for final in session.exec(select(CheckpointFinal)).all()
            if (title := _checkpoint_title_key(final.payload_json)) is not None
        }

        for cp in checkpoints:
            title_key = cp.title.strip()
            if title_key in existing_titles:
                skipped_reasons.append(f"审核点标题已存在，跳过导入：{title_key}")
                continue

            final = CheckpointFinal(
                payload_json=cp.model_dump_json(),
                approved_by="system:import",
            )
            session.add(final)
            session.flush()
            existing_titles.add(title_key)
            imported.append(_serialize_final(final))
        session.commit()

    return {
        "imported_count": len(imported),
        "skipped_count": len(skipped_reasons),
        "skipped_reasons": skipped_reasons,
        "checkpoints": imported,
    }


@router.put("/{checkpoint_id}")
async def update_checkpoint(checkpoint_id: str, payload: UpdateCheckpointRequest):
    with get_db_session() as session:
        final = session.get(CheckpointFinal, checkpoint_id)
        if final is not None:
            old_payload = final.payload_json
            final.payload_json = payload.payload_json
            log_activity(
                session,
                actor=payload.modified_by,
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
async def delete_checkpoint(checkpoint_id: str) -> Response:
    with get_db_session() as session:
        final = session.get(CheckpointFinal, checkpoint_id)
        if final is not None:
            log_activity(
                session,
                actor="system",
                action="delete_checkpoint",
                target_type="CheckpointFinal",
                target_id=checkpoint_id,
                before={"payload_json": final.payload_json},
            )
            session.delete(final)
            session.commit()
            return Response(status_code=204)

        raise HTTPException(status_code=404, detail="Checkpoint 不存在")
