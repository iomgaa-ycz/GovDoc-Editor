"""Document API 路由单元测试。"""
from contextlib import contextmanager
from typing import Iterator
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session, SQLModel, create_engine
from govdoc.api.main import create_app

app = create_app()
client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_document_db(monkeypatch):
    """每个测试使用独立内存数据库，避免污染真实 data/app.sqlite。"""
    db_name = f"test_document_api_{uuid.uuid4().hex}"
    engine = create_engine(
        f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)

    @contextmanager
    def _fake_get_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    monkeypatch.setattr("govdoc.api.routes.documents.get_session", _fake_get_session)
    yield
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


def test_list_documents_empty():
    resp = client.get("/api/v1/documents/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_upload_document():
    with patch("govdoc.api.routes.documents.get_document_store") as ms:
        ms.return_value = MagicMock()
        ms.return_value.save_raw.return_value = "/tmp/raw/test.pdf"
        resp = client.post(
            "/api/v1/documents/upload",
            files=[("files", ("test.pdf", b"%PDF-fake", "application/pdf"))],
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 1
        assert data[0]["filename"] == "test.pdf"
        assert data[0]["status"] in ("converting", "ready")
