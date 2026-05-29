"""审核点删除归档逻辑单测。"""

from __future__ import annotations

import json

from sqlmodel import Session, SQLModel, create_engine, select

from govdoc.api.routes.checkpoints import (
    _archive_or_delete_checkpoint,
    _filter_listed_finals,
    _serialize_final,
)
from govdoc.db.models import (
    AuditPointRun,
    AuditRun,
    CheckpointFinal,
    CheckpointLibraryItem,
)


def _make_engine():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return engine


def test_serialize_final_marks_archived() -> None:
    """_serialize_final 应根据 status 输出 archived 布尔标志。"""
    active = CheckpointFinal(payload_json="{}", approved_by="t", status="active")
    archived = CheckpointFinal(payload_json="{}", approved_by="t", status="archived")

    assert _serialize_final(active)["archived"] is False
    assert _serialize_final(archived)["archived"] is True


def test_filter_listed_finals_excludes_archived_by_default() -> None:
    """默认只返回 active；include_archived=True 时返回全部。"""
    active = CheckpointFinal(payload_json="{}", approved_by="t", status="active")
    archived = CheckpointFinal(payload_json="{}", approved_by="t", status="archived")
    finals = [active, archived]

    default = _filter_listed_finals(finals, include_archived=False)
    assert default == [active]

    full = _filter_listed_finals(finals, include_archived=True)
    assert full == [active, archived]


def test_archive_when_referenced() -> None:
    """被 AuditPointRun 引用时归档，不删除记录，且解除库关联。"""
    engine = _make_engine()
    with Session(engine) as session:
        final = CheckpointFinal(payload_json="{}", approved_by="t", status="active")
        session.add(final)
        session.commit()
        session.refresh(final)

        session.add(
            CheckpointLibraryItem(library_id="lib1", checkpoint_final_id=final.id)
        )
        session.add(
            AuditPointRun(audit_run_id="run1", checkpoint_final_id=final.id)
        )
        session.commit()

        result = _archive_or_delete_checkpoint(session, final)
        session.commit()

        assert result == {"action": "archived", "referenced_by": 1}
        refreshed = session.get(CheckpointFinal, final.id)
        assert refreshed is not None
        assert refreshed.status == "archived"
        items = session.exec(select(CheckpointLibraryItem)).all()
        assert items == []


def test_hard_delete_when_not_referenced() -> None:
    """无 AuditPointRun 引用时硬删除。"""
    engine = _make_engine()
    with Session(engine) as session:
        final = CheckpointFinal(payload_json="{}", approved_by="t", status="active")
        session.add(final)
        session.commit()
        session.refresh(final)
        fid = final.id

        result = _archive_or_delete_checkpoint(session, final)
        session.commit()

        assert result == {"action": "deleted"}
        assert session.get(CheckpointFinal, fid) is None
