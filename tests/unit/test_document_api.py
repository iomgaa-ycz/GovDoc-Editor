"""Document API 路由单元测试。"""

from contextlib import contextmanager
import threading
import time
from typing import Iterator
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session, SQLModel, create_engine

from govdoc.api.main import create_app
from govdoc.api.routes import documents as documents_route
from govdoc.db.models import Document

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


def test_upload_document_rejects_file_over_1gb_limit(monkeypatch):
    """超过上传上限的文件应在落盘和 sha256 计算前返回 413。

    参数:
        monkeypatch: pytest 提供的运行期替换工具，用于降低阈值避免构造大文件。
    """
    monkeypatch.setattr(documents_route, "_MAX_UPLOAD_BYTES", 8, raising=False)
    with patch("govdoc.api.routes.documents.get_document_store") as mock_get_store:
        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        resp = client.post(
            "/api/v1/documents/upload",
            files=[("files", ("large.pdf", b"123456789", "application/pdf"))],
        )

    assert resp.status_code == 413
    assert resp.json()["detail"] == "文件 large.pdf 超过 1GB 上传上限，请拆分后重试"
    mock_store.save_raw.assert_not_called()


def test_convert_document_limits_concurrent_conversions() -> None:
    """同一时刻最多允许两个后台文档进入实际转换调用。"""
    documents_by_id = {
        f"doc-{index}": Document(
            id=f"doc-{index}",
            filename=f"test-{index}.pdf",
            file_type="pdf",
            file_size=8,
            sha256=f"sha-{index}",
            raw_path=f"/tmp/raw/test-{index}.pdf",
            status="converting",
        )
        for index in range(3)
    }

    class _FakeSession:
        """供并发测试使用的最小 Session 替身，避免 SQLite 写锁干扰断言。"""

        def get(self, model: type[Document], doc_id: str) -> Document | None:
            """按 ID 返回测试文档。

            参数:
                model: 调用方请求的 SQLModel 类型。
                doc_id: 文档 ID。

            返回值:
                匹配的 Document，未命中时返回 None。
            """
            assert model is Document
            return documents_by_id.get(doc_id)

        def add(self, document: Document) -> None:
            """兼容真实 Session.add，测试中无需执行写入。

            参数:
                document: 被更新的文档对象。
            """

        def commit(self) -> None:
            """兼容真实 Session.commit，测试中无需执行写入。"""

    @contextmanager
    def _fake_session_scope() -> Iterator[_FakeSession]:
        """返回最小 fake session，避免并发测试依赖数据库锁行为。

        返回值:
            fake session 上下文。
        """
        yield _FakeSession()

    entered_paths: list[str] = []
    entered_lock = threading.Lock()
    first_two_entered = threading.Event()
    release_conversion = threading.Event()

    def _blocking_convert(raw_path: str):
        """记录进入转换的调用，并阻塞以暴露信号量并发行为。

        参数:
            raw_path: 待转换原始文件路径。

        返回值:
            模拟的 Markdown 文件路径。
        """
        with entered_lock:
            entered_paths.append(raw_path)
            if len(entered_paths) == 2:
                first_two_entered.set()
        release_conversion.wait(timeout=2)
        return f"{raw_path}.md"

    mock_store = MagicMock()
    mock_store.get_or_convert.side_effect = _blocking_convert
    with (
        patch("govdoc.api.routes.documents._session_scope", _fake_session_scope),
        patch("govdoc.api.routes.documents.get_document_store", return_value=mock_store),
    ):
        threads = [
            threading.Thread(target=documents_route._convert_document, args=(doc_id,))
            for doc_id in documents_by_id
        ]
        try:
            for thread in threads:
                thread.start()

            assert first_two_entered.wait(timeout=2)
            time.sleep(0.1)
            with entered_lock:
                assert len(entered_paths) == 2
        finally:
            release_conversion.set()
            for thread in threads:
                thread.join(timeout=2)
                assert not thread.is_alive()

    assert mock_store.get_or_convert.call_count == 3
