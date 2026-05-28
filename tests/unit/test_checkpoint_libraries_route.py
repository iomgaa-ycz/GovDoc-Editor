"""审核点库 API 路由单元测试。"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from govdoc.api.routes.checkpoint_libraries import router
from govdoc.db.models import CheckpointFinal, CheckpointLibraryItem


def _make_memory_engine(db_name: str):
    url = f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true"
    return create_engine(url, connect_args={"check_same_thread": False})


@pytest.fixture()
def engine():
    db_name = f"test_checkpoint_libraries_{uuid.uuid4().hex}"
    eng = _make_memory_engine(db_name)
    SQLModel.metadata.create_all(eng)
    yield eng
    SQLModel.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def client(engine, monkeypatch):
    @contextmanager
    def _fake_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    monkeypatch.setattr("govdoc.api.routes.checkpoint_libraries.get_db_session", _fake_session)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c


def _checkpoint_payload(title: str) -> str:
    return json.dumps(
        {
            "id": uuid.uuid4().hex,
            "category": "其他违法违规",
            "title": title,
            "description": "表现形式",
            "legal_basis": [],
            "severity": "major",
            "retrieval_hint": "表现形式",
        },
        ensure_ascii=False,
    )


def _seed_checkpoint(engine, title: str = "测试审核点") -> str:
    with Session(engine) as session:
        checkpoint = CheckpointFinal(
            payload_json=_checkpoint_payload(title),
            approved_by="tester",
        )
        session.add(checkpoint)
        session.commit()
        session.refresh(checkpoint)
        return checkpoint.id


def test_create_and_list_library(client):
    resp = client.post(
        "/api/v1/checkpoint-libraries",
        json={"name": "政府采购常规库", "created_by": "tester"},
    )
    assert resp.status_code == 200
    created = resp.json()
    assert created["name"] == "政府采购常规库"
    assert created["checkpoint_count"] == 0

    listed = client.get("/api/v1/checkpoint-libraries")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == created["id"]


def test_batch_add_is_idempotent(client, engine):
    checkpoint_id = _seed_checkpoint(engine)
    library_id = client.post(
        "/api/v1/checkpoint-libraries",
        json={"name": "专项库"},
    ).json()["id"]

    first = client.post(
        "/api/v1/checkpoint-libraries/batch-add",
        json={"library_ids": [library_id], "checkpoint_ids": [checkpoint_id]},
    )
    second = client.post(
        "/api/v1/checkpoint-libraries/batch-add",
        json={"library_ids": [library_id], "checkpoint_ids": [checkpoint_id]},
    )

    assert first.status_code == 200
    assert first.json()["added_count"] == 1
    assert second.status_code == 200
    assert second.json()["added_count"] == 0
    with Session(engine) as session:
        items = session.exec(select(CheckpointLibraryItem)).all()
    assert len(items) == 1


def test_library_detail_marks_deleted_checkpoint(client, engine):
    checkpoint_id = _seed_checkpoint(engine)
    library_id = client.post(
        "/api/v1/checkpoint-libraries",
        json={"name": "删除引用库"},
    ).json()["id"]
    client.post(
        "/api/v1/checkpoint-libraries/batch-add",
        json={"library_ids": [library_id], "checkpoint_ids": [checkpoint_id]},
    )

    with Session(engine) as session:
        checkpoint = session.get(CheckpointFinal, checkpoint_id)
        session.delete(checkpoint)
        session.commit()

    detail = client.get(f"/api/v1/checkpoint-libraries/{library_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["checkpoint_count"] == 0
    assert body["deleted_checkpoint_count"] == 1
    assert body["checkpoints"][0]["deleted"] is True
    assert body["checkpoints"][0]["checkpoint"] is None


def test_remove_checkpoints_from_library(client, engine):
    checkpoint_id = _seed_checkpoint(engine)
    library_id = client.post(
        "/api/v1/checkpoint-libraries",
        json={"name": "移出测试库"},
    ).json()["id"]
    client.post(
        "/api/v1/checkpoint-libraries/batch-add",
        json={"library_ids": [library_id], "checkpoint_ids": [checkpoint_id]},
    )

    resp = client.post(
        f"/api/v1/checkpoint-libraries/{library_id}/checkpoints/remove",
        json={"checkpoint_ids": [checkpoint_id]},
    )

    assert resp.status_code == 200
    assert resp.json()["removed_count"] == 1
    detail = client.get(f"/api/v1/checkpoint-libraries/{library_id}")
    assert detail.json()["checkpoints"] == []
