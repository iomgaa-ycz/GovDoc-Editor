"""按审核点库创建 AuditRun 的快照逻辑测试。"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from govdoc.api.routes.audit import router
from govdoc.db.models import (
    AuditPointRun,
    AuditRun,
    CheckpointFinal,
    CheckpointLibrary,
    CheckpointLibraryItem,
    Project,
    TenderDoc,
)


def _make_memory_engine(db_name: str):
    url = f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true"
    return create_engine(url, connect_args={"check_same_thread": False})


@pytest.fixture()
def engine():
    db_name = f"test_audit_library_snapshot_{uuid.uuid4().hex}"
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

    async def _noop_run_audit(audit_run_id: str, session: Session):
        return session.get(AuditRun, audit_run_id)

    monkeypatch.setattr("govdoc.api.routes.audit.get_db_session", _fake_session)
    monkeypatch.setattr("govdoc.pipelines.audit_tender.run_audit", _noop_run_audit)
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


def _seed_library_case(engine) -> tuple[str, str, str, list[str]]:
    with Session(engine) as session:
        project = Project(name="快照项目", created_by="tester")
        session.add(project)
        session.flush()
        tender = TenderDoc(
            project_id=project.id,
            filename="tender.docx",
            storage_path="/tmp/tender.docx",
            markdown_path="/tmp/tender.md",
            qmd_collection="test_collection",
            uploaded_by="tester",
        )
        session.add(tender)
        library = CheckpointLibrary(name="快照审核库", created_by="tester")
        session.add(library)
        session.flush()
        checkpoint_ids: list[str] = []
        for index in range(2):
            checkpoint = CheckpointFinal(
                payload_json=_checkpoint_payload(f"审核点 {index}"),
                approved_by="tester",
            )
            session.add(checkpoint)
            session.flush()
            checkpoint_ids.append(checkpoint.id)
            session.add(
                CheckpointLibraryItem(
                    library_id=library.id,
                    checkpoint_final_id=checkpoint.id,
                    added_by="tester",
                )
            )
        session.commit()
        return project.id, tender.id, library.id, checkpoint_ids


def test_create_audit_run_from_library_snapshots_checkpoint_ids(client, engine):
    project_id, tender_id, library_id, checkpoint_ids = _seed_library_case(engine)

    resp = client.post(
        "/api/v1/audit/runs",
        json={
            "project_id": project_id,
            "tender_doc_id": tender_id,
            "checkpoint_library_id": library_id,
        },
    )

    assert resp.status_code == 202
    body = resp.json()
    assert body["total_count"] == 2
    assert body["checkpoint_library_id"] == library_id
    assert body["checkpoint_library_name_snapshot"] == "快照审核库"

    with Session(engine) as session:
        audit_run = session.get(AuditRun, body["audit_run_id"])
        point_runs = session.exec(
            select(AuditPointRun).where(AuditPointRun.audit_run_id == body["audit_run_id"])
        ).all()
    assert audit_run is not None
    assert json.loads(audit_run.checkpoint_final_ids) == checkpoint_ids
    assert [point.checkpoint_final_id for point in point_runs] == checkpoint_ids

    with Session(engine) as session:
        extra = CheckpointFinal(
            payload_json=_checkpoint_payload("后来加入的审核点"),
            approved_by="tester",
        )
        session.add(extra)
        session.flush()
        session.add(
            CheckpointLibraryItem(
                library_id=library_id,
                checkpoint_final_id=extra.id,
                added_by="tester",
            )
        )
        session.commit()

    with Session(engine) as session:
        unchanged = session.get(AuditRun, body["audit_run_id"])
    assert json.loads(unchanged.checkpoint_final_ids) == checkpoint_ids


def test_create_audit_run_rejects_empty_library(client, engine):
    with Session(engine) as session:
        project = Project(name="空库项目", created_by="tester")
        session.add(project)
        session.flush()
        tender = TenderDoc(
            project_id=project.id,
            filename="tender.docx",
            storage_path="/tmp/tender.docx",
            markdown_path="/tmp/tender.md",
            qmd_collection="test_collection",
            uploaded_by="tester",
        )
        session.add(tender)
        library = CheckpointLibrary(name="空库", created_by="tester")
        session.add(library)
        session.commit()
        project_id = project.id
        tender_id = tender.id
        library_id = library.id

    resp = client.post(
        "/api/v1/audit/runs",
        json={
            "project_id": project_id,
            "tender_doc_id": tender_id,
            "checkpoint_library_id": library_id,
        },
    )

    assert resp.status_code == 400
    assert "为空" in resp.json()["detail"]
