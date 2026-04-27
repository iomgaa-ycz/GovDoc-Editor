"""E2E: 项目 CRUD + 文书上传（含多文件）。"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import httpx
import pytest


@pytest.fixture(scope="module")
def project_id(api: httpx.Client) -> str:
    """创建一个测试项目，返回 ID。"""
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


class TestProjectCRUD:
    """B02: 项目创建与查询。"""

    def test_create_project(self, api: httpx.Client):
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

    def test_list_projects(self, api: httpx.Client):
        resp = api.get("/api/v1/projects")
        assert resp.status_code == 200
        projects = resp.json()
        assert isinstance(projects, list)
        assert len(projects) >= 1

    def test_get_project(self, api: httpx.Client, project_id: str):
        resp = api.get(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == project_id

    def test_get_nonexistent_project(self, api: httpx.Client):
        resp = api.get("/api/v1/projects/nonexistent_id_999")
        assert resp.status_code == 404


class TestTenderDocUpload:
    """B03-B06: 文书上传（DOCX / PDF / 多文件）。"""

    def test_upload_main_docx(
        self,
        api: httpx.Client,
        project_id: str,
        tender_docx_path: Path,
    ):
        """B03: 上传主文书 DOCX。"""
        with open(tender_docx_path, "rb") as f:
            resp = api.post(
                f"/api/v1/projects/{project_id}/tender-doc",
                files={"file": (tender_docx_path.name, f, "application/octet-stream")},
            )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert "id" in data
        assert data["filename"] == tender_docx_path.name
        assert data["markdown_path"] is not None

    def test_upload_supplementary_pdf(
        self,
        api: httpx.Client,
        project_id: str,
        tender_pdf_path: Path,
    ):
        """B04-B05: 上传 PDF 作为补充文件。"""
        with open(tender_pdf_path, "rb") as f:
            resp = api.post(
                f"/api/v1/projects/{project_id}/tender-doc",
                files={"file": (tender_pdf_path.name, f, "application/octet-stream")},
            )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert "id" in data
        assert isinstance(data.get("warnings", []), list)

    def test_list_tender_docs(self, api: httpx.Client, project_id: str):
        """B06: 查询项目文书列表，应含主文书 + 补充文件。"""
        resp = api.get(f"/api/v1/projects/{project_id}/tender-docs")
        assert resp.status_code == 200
        docs = resp.json()
        assert len(docs) >= 2
        filenames = [d["filename"] for d in docs]
        assert any("docx" in fn.lower() for fn in filenames)

    def test_upload_to_nonexistent_project(self, api: httpx.Client, tender_docx_path: Path):
        """上传文书到不存在的项目 → 404。"""
        with open(tender_docx_path, "rb") as f:
            resp = api.post(
                "/api/v1/projects/nonexistent_999/tender-doc",
                files={"file": (tender_docx_path.name, f, "application/octet-stream")},
            )
        assert resp.status_code == 404
