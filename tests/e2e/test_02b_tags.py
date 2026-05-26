"""E2E: 标签 CRUD + 文档批量打标签。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest


@pytest.fixture(scope="module")
def created_tag(api: httpx.Client) -> dict[str, Any]:
    """创建一个唯一测试标签，并在模块结束时尽力清理。"""
    resp = api.post(
        "/api/v1/tags/",
        json={"name": f"测试标签_{uuid4().hex[:8]}", "color": "#DBEAFE:#1D4ED8"},
    )
    assert resp.status_code == 201, resp.text
    tag = resp.json()
    assert "id" in tag
    assert tag["name"].startswith("测试标签_")
    assert tag["color"] == "#DBEAFE:#1D4ED8"

    yield tag

    cleanup_resp = api.delete(f"/api/v1/tags/{tag['id']}")
    assert cleanup_resp.status_code in (204, 404)


@pytest.fixture(scope="module")
def document_for_tag(
    upload_document: Callable[[Path, bool], dict[str, Any]],
    tender_pdf_path: Path,
) -> dict[str, Any]:
    """上传一个可打标签的 ready 文档。"""
    document = upload_document(tender_pdf_path, True)
    assert document["status"] == "ready"
    return document


@pytest.fixture(scope="module")
def tagged_document(
    api: httpx.Client,
    created_tag: dict[str, Any],
    document_for_tag: dict[str, Any],
) -> dict[str, Any]:
    """给测试文档批量打上测试标签。"""
    resp = api.post(
        "/api/v1/documents/batch-tag",
        json={
            "document_ids": [document_for_tag["id"]],
            "tag_ids": [created_tag["id"]],
        },
    )
    assert resp.status_code in (200, 201), resp.text
    result = resp.json()
    assert result["created_count"] + result["skipped_count"] >= 1
    return document_for_tag


class TestTagCRUD:
    """B06b: 标签 CRUD 与文档标签筛选。"""

    def test_create_tag(self, created_tag: dict[str, Any]) -> None:
        """创建标签应返回 ID、名称、颜色和创建时间。"""
        assert created_tag["id"]
        assert created_tag["name"].startswith("测试标签_")
        assert created_tag["color"] == "#DBEAFE:#1D4ED8"
        assert "created_at" in created_tag

    def test_list_tags(self, api: httpx.Client, created_tag: dict[str, Any]) -> None:
        """标签列表应包含刚创建的标签。"""
        resp = api.get("/api/v1/tags/")
        assert resp.status_code == 200
        tags = resp.json()
        assert isinstance(tags, list)
        assert any(tag["id"] == created_tag["id"] for tag in tags)

    def test_batch_tag_document(
        self,
        tagged_document: dict[str, Any],
        created_tag: dict[str, Any],
    ) -> None:
        """批量打标签接口应成功建立 DocumentTag 关联。"""
        assert tagged_document["id"]
        assert created_tag["id"]

    def test_filter_documents_by_tag(
        self,
        api: httpx.Client,
        tagged_document: dict[str, Any],
        created_tag: dict[str, Any],
    ) -> None:
        """按标签筛选文档时只返回已打该标签的文档。"""
        resp = api.get("/api/v1/documents/", params={"tag_id": created_tag["id"]})
        assert resp.status_code == 200
        documents = resp.json()
        assert isinstance(documents, list)
        assert {document["id"] for document in documents} == {tagged_document["id"]}
        assert all(
            any(tag["id"] == created_tag["id"] for tag in document["tags"])
            for document in documents
        )

    def test_delete_tag_cleans_document_links(
        self,
        api: httpx.Client,
        tagged_document: dict[str, Any],
        created_tag: dict[str, Any],
    ) -> None:
        """删除标签后，标签筛选结果和文档详情中的关联应清空。"""
        resp = api.delete(f"/api/v1/tags/{created_tag['id']}")
        assert resp.status_code == 204

        filter_resp = api.get("/api/v1/documents/", params={"tag_id": created_tag["id"]})
        assert filter_resp.status_code in (200, 404)
        if filter_resp.status_code == 200:
            assert filter_resp.json() == []

        detail_resp = api.get(f"/api/v1/documents/{tagged_document['id']}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert all(tag["id"] != created_tag["id"] for tag in detail["tags"])
