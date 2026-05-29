"""审核点删除归档逻辑单测。"""

from __future__ import annotations

import json

from sqlmodel import Session, SQLModel, create_engine, select

from govdoc.api.routes.checkpoints import _serialize_final
from govdoc.db.models import CheckpointFinal


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
