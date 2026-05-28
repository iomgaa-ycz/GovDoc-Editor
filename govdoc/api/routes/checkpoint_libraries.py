"""Checkpoint library routes — 管理审核点库与库内审核点关联。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import func
from sqlmodel import select

from govdoc.api.deps import get_db_session
from govdoc.api.middleware import log_activity
from govdoc.api.schemas import (
    BatchAddCheckpointsToLibrariesRequest,
    CreateCheckpointLibraryRequest,
    LibraryCheckpointIdsRequest,
    UpdateCheckpointLibraryRequest,
)
from govdoc.db.models import CheckpointFinal, CheckpointLibrary, CheckpointLibraryItem

router = APIRouter(prefix="/api/v1/checkpoint-libraries", tags=["checkpoint-libraries"])
logger = logging.getLogger(__name__)


def _serialize_checkpoint(final: CheckpointFinal) -> dict[str, str | None]:
    """将 CheckpointFinal 实例序列化为 API 响应字典。"""
    return {
        "id": final.id,
        "kind": "final",
        "status": "final",
        "payload_json": final.payload_json,
        "approved_by": final.approved_by,
    }


def _serialize_library(
    library: CheckpointLibrary,
    *,
    checkpoint_count: int = 0,
    deleted_checkpoint_count: int = 0,
) -> dict[str, str | int | None]:
    """将 CheckpointLibrary 实例序列化为 API 响应字典。"""
    return {
        "id": library.id,
        "name": library.name,
        "description": library.description,
        "created_by": library.created_by,
        "created_at": str(library.created_at),
        "checkpoint_count": checkpoint_count,
        "deleted_checkpoint_count": deleted_checkpoint_count,
    }


def _dedupe_ids(ids: list[str]) -> list[str]:
    """对 ID 列表去重，保持原始顺序。"""
    seen: set[str] = set()
    result: list[str] = []
    for item in ids:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def add_checkpoints_to_libraries(
    library_ids: list[str],
    checkpoint_ids: list[str],
    *,
    actor: str = "system",
) -> int:
    """幂等地把多个审核点加入多个审核点库，返回新增关联数。"""
    clean_library_ids = _dedupe_ids([item for item in library_ids if item])
    clean_checkpoint_ids = _dedupe_ids([item for item in checkpoint_ids if item])
    if not clean_library_ids or not clean_checkpoint_ids:
        return 0

    with get_db_session() as session:
        libraries = session.exec(
            select(CheckpointLibrary).where(CheckpointLibrary.id.in_(clean_library_ids))
        ).all()
        found_library_ids = {library.id for library in libraries}
        missing_library_ids = set(clean_library_ids) - found_library_ids
        if missing_library_ids:
            raise ValueError(f"审核点库不存在: {', '.join(sorted(missing_library_ids))}")

        checkpoints = session.exec(
            select(CheckpointFinal).where(CheckpointFinal.id.in_(clean_checkpoint_ids))
        ).all()
        found_checkpoint_ids = {checkpoint.id for checkpoint in checkpoints}
        missing_checkpoint_ids = set(clean_checkpoint_ids) - found_checkpoint_ids
        if missing_checkpoint_ids:
            raise ValueError(f"审核点不存在: {', '.join(sorted(missing_checkpoint_ids))}")

        existing_items = session.exec(
            select(CheckpointLibraryItem).where(
                CheckpointLibraryItem.library_id.in_(clean_library_ids),
                CheckpointLibraryItem.checkpoint_final_id.in_(clean_checkpoint_ids),
            )
        ).all()
        existing_pairs = {
            (item.library_id, item.checkpoint_final_id) for item in existing_items
        }

        added_count = 0
        for library_id in clean_library_ids:
            for checkpoint_id in clean_checkpoint_ids:
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
                added_count += 1

        if added_count:
            log_activity(
                session,
                actor=actor,
                action="add_checkpoints_to_libraries",
                target_type="CheckpointLibrary",
                target_id=",".join(clean_library_ids),
                after={
                    "library_ids": clean_library_ids,
                    "checkpoint_ids": clean_checkpoint_ids,
                    "added_count": added_count,
                },
            )
        session.commit()
        logger.info(
            "批量添加审核点到库: libraries=%s, checkpoints=%s, added=%d",
            clean_library_ids, clean_checkpoint_ids, added_count,
        )
        return added_count


@router.post("/batch-add")
async def batch_add_checkpoints_to_libraries(
    payload: BatchAddCheckpointsToLibrariesRequest,
) -> dict[str, object]:
    """批量将审核点加入多个库。"""
    try:
        added_count = add_checkpoints_to_libraries(
            payload.library_ids,
            payload.checkpoint_ids,
            actor=payload.actor,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {
        "library_ids": _dedupe_ids(payload.library_ids),
        "checkpoint_ids": _dedupe_ids(payload.checkpoint_ids),
        "added_count": added_count,
    }


@router.get("")
async def list_checkpoint_libraries() -> list[dict[str, str | int | None]]:
    """列出所有审核点库（含每个库的审核点计数）。"""
    with get_db_session() as session:
        libraries = session.exec(
            select(CheckpointLibrary).order_by(CheckpointLibrary.created_at.desc())
        ).all()

        # SQL 聚合计数，避免全表扫描
        count_stmt = (
            select(
                CheckpointLibraryItem.library_id,
                func.count().label("total"),
            )
            .group_by(CheckpointLibraryItem.library_id)
        )
        total_counts: dict[str, int] = {
            row[0]: row[1] for row in session.exec(count_stmt).all()
        }

        existing_stmt = (
            select(
                CheckpointLibraryItem.library_id,
                func.count().label("existing"),
            )
            .join(CheckpointFinal, CheckpointLibraryItem.checkpoint_final_id == CheckpointFinal.id)
            .group_by(CheckpointLibraryItem.library_id)
        )
        existing_counts: dict[str, int] = {
            row[0]: row[1] for row in session.exec(existing_stmt).all()
        }

        return [
            _serialize_library(
                library,
                checkpoint_count=existing_counts.get(library.id, 0),
                deleted_checkpoint_count=(
                    total_counts.get(library.id, 0) - existing_counts.get(library.id, 0)
                ),
            )
            for library in libraries
        ]


@router.post("")
async def create_checkpoint_library(payload: CreateCheckpointLibraryRequest) -> dict[str, str | int | None]:
    """创建一个新的审核点库。"""
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="审核点库名称不能为空")
    with get_db_session() as session:
        library = CheckpointLibrary(
            name=name,
            description=payload.description,
            created_by=payload.created_by,
        )
        session.add(library)
        log_activity(
            session,
            actor=payload.created_by,
            action="create_checkpoint_library",
            target_type="CheckpointLibrary",
            target_id=library.id,
            after={"name": name, "description": payload.description},
        )
        session.commit()
        session.refresh(library)
        logger.info("创建审核点库: id=%s, name=%s", library.id, name)
        return _serialize_library(library)


@router.get("/{library_id}")
async def get_checkpoint_library(library_id: str) -> dict[str, object]:
    """获取审核点库详情（含库内审核点列表及软删除标记）。"""
    with get_db_session() as session:
        library = session.get(CheckpointLibrary, library_id)
        if library is None:
            raise HTTPException(status_code=404, detail="审核点库不存在")

        items = session.exec(
            select(CheckpointLibraryItem).where(CheckpointLibraryItem.library_id == library_id)
        ).all()
        checkpoint_ids = [item.checkpoint_final_id for item in items]
        finals = (
            session.exec(select(CheckpointFinal).where(CheckpointFinal.id.in_(checkpoint_ids))).all()
            if checkpoint_ids
            else []
        )
        finals_by_id = {final.id: final for final in finals}

        checkpoints: list[dict[str, object]] = []
        available_count = 0
        deleted_count = 0
        for item in items:
            final = finals_by_id.get(item.checkpoint_final_id)
            deleted = final is None
            if deleted:
                deleted_count += 1
            else:
                available_count += 1
            checkpoints.append(
                {
                    "id": item.id,
                    "library_id": item.library_id,
                    "checkpoint_final_id": item.checkpoint_final_id,
                    "checkpoint": _serialize_checkpoint(final) if final else None,
                    "deleted": deleted,
                    "added_by": item.added_by,
                    "added_at": str(item.added_at),
                }
            )

        return {
            **_serialize_library(
                library,
                checkpoint_count=available_count,
                deleted_checkpoint_count=deleted_count,
            ),
            "checkpoints": checkpoints,
        }


@router.put("/{library_id}")
async def update_checkpoint_library(
    library_id: str,
    payload: UpdateCheckpointLibraryRequest,
) -> dict[str, str | int | None]:
    """编辑审核点库名称和说明。"""
    with get_db_session() as session:
        library = session.get(CheckpointLibrary, library_id)
        if library is None:
            raise HTTPException(status_code=404, detail="审核点库不存在")
        before = {"name": library.name, "description": library.description}
        if payload.name is not None:
            name = payload.name.strip()
            if not name:
                raise HTTPException(status_code=400, detail="审核点库名称不能为空")
            library.name = name
        if payload.description is not None:
            library.description = payload.description
        session.add(library)
        log_activity(
            session,
            actor=payload.modified_by,
            action="update_checkpoint_library",
            target_type="CheckpointLibrary",
            target_id=library.id,
            before=before,
            after={"name": library.name, "description": library.description},
        )
        session.commit()
        session.refresh(library)
        logger.info("更新审核点库: id=%s, name=%s", library.id, library.name)
        return _serialize_library(library)


@router.delete("/{library_id}", status_code=204)
async def delete_checkpoint_library(library_id: str) -> Response:
    """删除审核点库（仅删库和关联，不删审核点本体）。"""
    with get_db_session() as session:
        library = session.get(CheckpointLibrary, library_id)
        if library is None:
            raise HTTPException(status_code=404, detail="审核点库不存在")
        items = session.exec(
            select(CheckpointLibraryItem).where(CheckpointLibraryItem.library_id == library_id)
        ).all()
        for item in items:
            session.delete(item)
        log_activity(
            session,
            actor="system",
            action="delete_checkpoint_library",
            target_type="CheckpointLibrary",
            target_id=library.id,
            before={"name": library.name, "description": library.description},
        )
        session.delete(library)
        session.commit()
        logger.info("删除审核点库: id=%s, name=%s", library_id, library.name)
        return Response(status_code=204)


@router.post("/{library_id}/checkpoints")
async def add_checkpoints_to_library(
    library_id: str,
    payload: LibraryCheckpointIdsRequest,
) -> dict[str, str | int]:
    """向指定库中添加审核点。"""
    try:
        added_count = add_checkpoints_to_libraries(
            [library_id],
            payload.checkpoint_ids,
            actor=payload.actor,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"library_id": library_id, "added_count": added_count}


@router.post("/{library_id}/checkpoints/remove")
async def remove_checkpoints_from_library(
    library_id: str,
    payload: LibraryCheckpointIdsRequest,
) -> dict[str, str | int]:
    """从指定库中移出审核点。"""
    checkpoint_ids = _dedupe_ids(payload.checkpoint_ids)
    with get_db_session() as session:
        library = session.get(CheckpointLibrary, library_id)
        if library is None:
            raise HTTPException(status_code=404, detail="审核点库不存在")
        if not checkpoint_ids:
            return {"library_id": library_id, "removed_count": 0}
        items = session.exec(
            select(CheckpointLibraryItem).where(
                CheckpointLibraryItem.library_id == library_id,
                CheckpointLibraryItem.checkpoint_final_id.in_(checkpoint_ids),
            )
        ).all()
        for item in items:
            session.delete(item)
        if items:
            log_activity(
                session,
                actor=payload.actor,
                action="remove_checkpoints_from_library",
                target_type="CheckpointLibrary",
                target_id=library_id,
                before={"checkpoint_ids": [item.checkpoint_final_id for item in items]},
            )
        session.commit()
        logger.info("移出审核点: library=%s, removed=%d", library_id, len(items))
        return {"library_id": library_id, "removed_count": len(items)}
