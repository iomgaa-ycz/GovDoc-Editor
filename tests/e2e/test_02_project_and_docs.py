"""E2E: 项目 CRUD + 文件管理中心文档上传。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest


@pytest.fixture(scope="module")
def project_id(api: httpx.Client) -> str:
    """创建一个测试项目，返回项目 ID。"""
    resp = api.post(
        "/api/v1/projects",
        json={
            "name": f"E2E测试项目_{uuid4().hex[:8]}",
            "created_by": "e2e-bot",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "id" in data
    return data["id"]


@pytest.fixture(scope="module")
def uploaded_pdf_document(
    api: httpx.Client,
    tender_pdf_path: Path,
    wait_for_document_ready: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    """上传单个 PDF，并等待后台转换完成。"""
    with tender_pdf_path.open("rb") as file_obj:
        resp = api.post(
            "/api/v1/documents/upload",
            files=[("files", (tender_pdf_path.name, file_obj, "application/pdf"))],
        )

    assert resp.status_code == 201, resp.text
    payload = resp.json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    document = payload[0]
    assert "id" in document
    assert document["filename"] == tender_pdf_path.name
    assert "status" in document

    return wait_for_document_ready(document["id"])


class TestProjectCRUD:
    """B02: 项目创建与查询。"""

    def test_create_project(self, api: httpx.Client) -> None:
        """创建项目应返回 ID、名称和创建时间。"""
        resp = api.post(
            "/api/v1/projects",
            json={
                "name": f"临时项目_{uuid4().hex[:8]}",
                "created_by": "e2e-bot",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert "name" in data
        assert "created_at" in data

    def test_list_projects(self, api: httpx.Client) -> None:
        """项目列表应至少包含已创建的测试项目。"""
        resp = api.get("/api/v1/projects")
        assert resp.status_code == 200
        projects = resp.json()
        assert isinstance(projects, list)
        assert len(projects) >= 1

    def test_get_project(self, api: httpx.Client, project_id: str) -> None:
        """按 ID 获取项目详情。"""
        resp = api.get(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == project_id

    def test_get_nonexistent_project(self, api: httpx.Client) -> None:
        """不存在项目应返回 404。"""
        resp = api.get("/api/v1/projects/nonexistent_id_999")
        assert resp.status_code == 404


class TestDocumentUpload:
    """B03-B06: 文件管理中心文档上传、去重与筛选。"""

    def test_upload_single_pdf(
        self, uploaded_pdf_document: dict[str, Any], tender_pdf_path: Path
    ) -> None:
        """上传单个 PDF 后应最终进入 ready 状态。"""
        assert uploaded_pdf_document["filename"] == tender_pdf_path.name
        assert uploaded_pdf_document["status"] == "ready"
        assert uploaded_pdf_document["id"]
        assert uploaded_pdf_document["file_type"] == "pdf"

    def test_upload_duplicate_file_deduplicates(
        self,
        api: httpx.Client,
        uploaded_pdf_document: dict[str, Any],
        tender_pdf_path: Path,
    ) -> None:
        """同 sha256 文件重复上传应复用同一个 Document。"""
        with tender_pdf_path.open("rb") as file_obj:
            resp = api.post(
                "/api/v1/documents/upload",
                files=[("files", (tender_pdf_path.name, file_obj, "application/pdf"))],
            )

        assert resp.status_code in (200, 201), resp.text
        payload = resp.json()
        assert isinstance(payload, list)
        assert len(payload) == 1
        duplicate = payload[0]
        assert duplicate["sha256"] == uploaded_pdf_document["sha256"]
        assert (
            duplicate.get("deduplicated") is True
            or resp.status_code == 200
            or duplicate["id"] == uploaded_pdf_document["id"]
        )
        assert duplicate["id"] == uploaded_pdf_document["id"]

    def test_list_documents(self, api: httpx.Client, uploaded_pdf_document: dict[str, Any]) -> None:
        """文档列表应包含刚上传的 PDF。"""
        resp = api.get("/api/v1/documents/")
        assert resp.status_code == 200
        documents = resp.json()
        assert isinstance(documents, list)
        assert any(document["id"] == uploaded_pdf_document["id"] for document in documents)

    def test_filter_ready_documents(
        self,
        api: httpx.Client,
        uploaded_pdf_document: dict[str, Any],
    ) -> None:
        """按 ready 状态筛选文档。"""
        resp = api.get("/api/v1/documents/", params={"status": "ready"})
        assert resp.status_code == 200
        documents = resp.json()
        assert isinstance(documents, list)
        assert all(document["status"] == "ready" for document in documents)
        assert any(document["id"] == uploaded_pdf_document["id"] for document in documents)
