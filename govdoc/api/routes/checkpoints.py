"""Checkpoints routes — 统一查看/编辑/删除已入库审核点。"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from pydantic import ValidationError
from sqlmodel import Session, select

from govdoc.api.deps import get_db_session
from govdoc.api.middleware import log_activity
from govdoc.api.schemas import UpdateCheckpointRequest
from govdoc.db.models import (
    AuditPointRun,
    AuditRun,
    CheckpointFinal,
    CheckpointLibrary,
    CheckpointLibraryItem,
)
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
    rewired_library_items: int = 0


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
) -> tuple[int, int, int]:
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
        return 0, 0, 0

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

    library_items = session.exec(
        select(CheckpointLibraryItem).where(
            CheckpointLibraryItem.checkpoint_final_id.in_(old_ids)
        )
    ).all()
    rewired_library_items = 0
    for item in library_items:
        keep_id = replacement_map[item.checkpoint_final_id]
        duplicate = session.exec(
            select(CheckpointLibraryItem).where(
                CheckpointLibraryItem.library_id == item.library_id,
                CheckpointLibraryItem.checkpoint_final_id == keep_id,
            )
        ).first()
        if duplicate is not None:
            session.delete(item)
        else:
            item.checkpoint_final_id = keep_id
            session.add(item)
        rewired_library_items += 1

    return len(point_runs), rewired_audit_runs, rewired_library_items


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

    rewired_point_runs, rewired_audit_runs, rewired_library_items = (
        _rewire_checkpoint_references(session, replacement_map)
    )
    for final in delete_targets:
        session.delete(final)

    return DedupStats(
        removed_existing_count=len(delete_targets),
        rewired_audit_point_runs=rewired_point_runs,
        rewired_audit_runs=rewired_audit_runs,
        rewired_library_items=rewired_library_items,
    )


def _validate_checkpoint_upload(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {suffix}，仅支持 .xls / .xlsx / .csv",
        )
    return suffix


def _parse_library_ids(raw: str | None) -> list[str]:
    if raw is None or not raw.strip():
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="library_ids 必须是 JSON 字符串数组") from exc
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise HTTPException(status_code=400, detail="library_ids 必须是 JSON 字符串数组")
    return _dedupe_ids_preserving_order([item for item in value if item])


def _parse_checkpoint_upload(
    *,
    filename: str,
    content: bytes,
) -> tuple[list[GovCheckpoint], list[str]]:
    suffix = _validate_checkpoint_upload(filename)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        from govdoc.parsers.checkpoint_import import parse_checkpoint_file

        return parse_checkpoint_file(tmp_path)
    except ModuleNotFoundError as exc:
        missing = exc.name or "解析依赖"
        raise HTTPException(
            status_code=500,
            detail=f"服务器缺少表格解析依赖: {missing}，请安装项目依赖后重试",
        ) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


def _title_to_final(session: Session) -> dict[str, CheckpointFinal]:
    result: dict[str, CheckpointFinal] = {}
    for final in session.exec(select(CheckpointFinal)).all():
        title = _checkpoint_title_key(final.payload_json)
        if title is None:
            continue
        result[title] = final
    return result


def _validate_libraries(session: Session, library_ids: list[str]) -> list[CheckpointLibrary]:
    if not library_ids:
        return []
    libraries = session.exec(
        select(CheckpointLibrary).where(CheckpointLibrary.id.in_(library_ids))
    ).all()
    found_ids = {library.id for library in libraries}
    missing_ids = set(library_ids) - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"审核点库不存在: {', '.join(sorted(missing_ids))}",
        )
    return libraries


def _add_library_items_in_session(
    session: Session,
    *,
    library_ids: list[str],
    checkpoint_ids: list[str],
    actor: str = "system:import",
) -> int:
    if not library_ids or not checkpoint_ids:
        return 0
    existing_items = session.exec(
        select(CheckpointLibraryItem).where(
            CheckpointLibraryItem.library_id.in_(library_ids),
            CheckpointLibraryItem.checkpoint_final_id.in_(checkpoint_ids),
        )
    ).all()
    existing_pairs = {
        (item.library_id, item.checkpoint_final_id) for item in existing_items
    }
    linked_count = 0
    for library_id in library_ids:
        for checkpoint_id in checkpoint_ids:
            pair = (library_id, checkpoint_id)
            if pair in existing_pairs:
                continue
            session.add(
                CheckpointLibraryItem(
                    library_id=library_id,
                    checkpoint_final_id=checkpoint_id,
                    added_by=actor,
                )
            )
            existing_pairs.add(pair)
            linked_count += 1
    return linked_count


@router.post("/import/preview")
async def preview_import_checkpoints(
    file: UploadFile = File(...),
    library_ids: str | None = Form(None),
):
    """解析审查点表格并返回新增/复用预估，不写入数据库。"""
    filename = file.filename or ""
    checkpoints, skipped_reasons = _parse_checkpoint_upload(
        filename=filename,
        content=await file.read(),
    )
    parsed_library_ids = _parse_library_ids(library_ids)

    with get_db_session() as session:
        _validate_libraries(session, parsed_library_ids)
        existing_titles = set(_title_to_final(session))

    seen_titles: set[str] = set()
    created_count = 0
    reused_count = 0
    duplicate_count = 0
    for cp in checkpoints:
        title_key = cp.title.strip()
        if not title_key:
            skipped_reasons.append("审核点标题为空")
            continue
        if title_key in seen_titles:
            duplicate_count += 1
            skipped_reasons.append(f"审核点标题已存在，跳过导入：{title_key}")
            continue
        seen_titles.add(title_key)
        if title_key in existing_titles and parsed_library_ids:
            reused_count += 1
        elif title_key in existing_titles:
            duplicate_count += 1
            skipped_reasons.append(f"审核点标题已存在，跳过导入：{title_key}")
        else:
            created_count += 1

    return {
        "parsed_count": len(checkpoints),
        "created_count": created_count,
        "reused_count": reused_count,
        "duplicate_count": duplicate_count,
        "skipped_count": len(skipped_reasons),
        "skipped_reasons": skipped_reasons,
    }


@router.post("/import")
async def import_checkpoints(
    file: UploadFile = File(...),
    library_ids: str | None = Form(None),
):
    """上传审查点表格（xls/xlsx/csv），批量写入审核点库。"""
    filename = file.filename or ""
    checkpoints, skipped_reasons = _parse_checkpoint_upload(
        filename=filename,
        content=await file.read(),
    )
    parsed_library_ids = _parse_library_ids(library_ids)

    imported: list[dict[str, str | None]] = []
    reused: list[dict[str, str | None]] = []
    target_checkpoint_ids: list[str] = []
    linked_count = 0
    with get_db_session() as session:
        _validate_libraries(session, parsed_library_ids)
        deduplicate_existing_checkpoints(session)
        existing_by_title = _title_to_final(session)
        seen_upload_titles: set[str] = set()

        for cp in checkpoints:
            title_key = cp.title.strip()
            if not title_key:
                skipped_reasons.append("审核点标题为空")
                continue
            if title_key in seen_upload_titles:
                skipped_reasons.append(f"审核点标题已存在，跳过导入：{title_key}")
                continue
            seen_upload_titles.add(title_key)

            existing_final = existing_by_title.get(title_key)
            if existing_final is not None:
                if parsed_library_ids:
                    reused.append(_serialize_final(existing_final))
                    target_checkpoint_ids.append(existing_final.id)
                else:
                    skipped_reasons.append(f"审核点标题已存在，跳过导入：{title_key}")
                continue

            final = CheckpointFinal(
                payload_json=cp.model_dump_json(),
                approved_by="system:import",
            )
            session.add(final)
            session.flush()
            existing_by_title[title_key] = final
            target_checkpoint_ids.append(final.id)
            imported.append(_serialize_final(final))
        linked_count = _add_library_items_in_session(
            session,
            library_ids=parsed_library_ids,
            checkpoint_ids=target_checkpoint_ids,
        )
        session.commit()

    return {
        "imported_count": len(imported),
        "created_count": len(imported),
        "reused_count": len(reused),
        "linked_count": linked_count,
        "skipped_count": len(skipped_reasons),
        "skipped_reasons": skipped_reasons,
        "checkpoints": imported + reused,
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
