"""审核点删除归档逻辑单测。"""

from __future__ import annotations

import json

from sqlmodel import Session, SQLModel, create_engine, select

from govdoc.api.routes.checkpoints import (
    _archive_or_delete_checkpoint,
    _filter_listed_finals,
    _serialize_final,
    deduplicate_existing_checkpoints,
)
from govdoc.api.routes.audit import _filter_orphan_point_runs
from govdoc.schemas import GovCheckpoint
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

        session.add(CheckpointLibraryItem(library_id="lib1", checkpoint_final_id=final.id))
        session.add(AuditPointRun(audit_run_id="run1", checkpoint_final_id=final.id))
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


def _cp_payload(title: str) -> str:
    return GovCheckpoint(
        id="x",
        category="意向性招标",
        title=title,
        description="d",
        severity="major",
        retrieval_hint="h",
    ).model_dump_json()


def test_dedup_migrates_archived_to_active() -> None:
    """同名 archived 旧记录的历史引用迁移到新导入的 active 记录后删除。"""
    engine = _make_engine()
    with Session(engine) as session:
        # 旧的归档记录
        archived = CheckpointFinal(
            payload_json=_cp_payload("逾期退还保证金"),
            approved_by="t",
            status="archived",
        )
        # 新导入的 active 记录（同 title）
        active = CheckpointFinal(
            payload_json=_cp_payload("逾期退还保证金"),
            approved_by="t",
            status="active",
        )
        session.add(archived)
        session.add(active)
        session.commit()
        session.refresh(archived)
        session.refresh(active)

        # 历史审查任务引用了 archived 记录
        session.add(
            AuditRun(
                id="run1",
                project_id="p1",
                main_document_id="d1",
                checkpoint_final_ids=json.dumps([archived.id]),
            )
        )
        session.add(AuditPointRun(audit_run_id="run1", checkpoint_final_id=archived.id))
        session.commit()

        stats = deduplicate_existing_checkpoints(session)
        session.commit()

        assert stats.removed_existing_count == 1
        assert session.get(CheckpointFinal, archived.id) is None
        kept = session.get(CheckpointFinal, active.id)
        assert kept is not None and kept.status == "active"
        # point_run 已迁移到 active 记录
        prs = session.exec(select(AuditPointRun)).all()
        assert all(pr.checkpoint_final_id == active.id for pr in prs)


def test_filter_orphan_point_runs() -> None:
    """checkpoint 不存在的 point_run 被过滤，存在的保留。"""
    existing_ids = {"cp-alive"}
    point_runs = [
        AuditPointRun(audit_run_id="r", checkpoint_final_id="cp-alive"),
        AuditPointRun(audit_run_id="r", checkpoint_final_id="cp-gone"),
    ]
    kept = _filter_orphan_point_runs(point_runs, existing_ids)
    assert len(kept) == 1
    assert kept[0].checkpoint_final_id == "cp-alive"
