"""Checkpoint library routes — 管理审核点库与库内审核点关联。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
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


def _serialize_checkpoint(final: CheckpointFinal) -> dict[str, str | None]:
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
        return added_count


@router.get("")
async def list_checkpoint_libraries():
    with get_db_session() as session:
        libraries = session.exec(
            select(CheckpointLibrary).order_by(CheckpointLibrary.created_at.desc())
        ).all()
        items = session.exec(select(CheckpointLibraryItem)).all()
        checkpoint_ids = {item.checkpoint_final_id for item in items}
        finals = (
            session.exec(select(CheckpointFinal).where(CheckpointFinal.id.in_(checkpoint_ids))).all()
            if checkpoint_ids
            else []
        )
        existing_checkpoint_ids = {final.id for final in finals}

        counts: dict[str, int] = {}
        deleted_counts: dict[str, int] = {}
        for item in items:
            if item.checkpoint_final_id in existing_checkpoint_ids:
                counts[item.library_id] = counts.get(item.library_id, 0) + 1
            else:
                deleted_counts[item.library_id] = deleted_counts.get(item.library_id, 0) + 1

        return [
            _serialize_library(
                library,
                checkpoint_count=counts.get(library.id, 0),
                deleted_checkpoint_count=deleted_counts.get(library.id, 0),
            )
            for library in libraries
        ]


@router.post("")
async def create_checkpoint_library(payload: CreateCheckpointLibraryRequest):
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
        return _serialize_library(library)


@router.get("/{library_id}")
async def get_checkpoint_library(library_id: str):
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
):
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
        return _serialize_library(library)


@router.delete("/{library_id}", status_code=204)
async def delete_checkpoint_library(library_id: str) -> Response:
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
        return Response(status_code=204)


@router.post("/{library_id}/checkpoints")
async def add_checkpoints_to_library(
    library_id: str,
    payload: LibraryCheckpointIdsRequest,
):
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
):
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
        return {"library_id": library_id, "removed_count": len(items)}


@router.post("/batch-add")
async def batch_add_checkpoints_to_libraries(
    payload: BatchAddCheckpointsToLibrariesRequest,
):
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
