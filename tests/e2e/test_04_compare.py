"""E2E: 文件管理中心文档对比 + 高亮下载。"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _wait_for_compare_completed(
    api: httpx.Client,
    review_id: str,
    timeout_seconds: int = 300,
    interval_seconds: int = 5,
) -> dict[str, Any]:
    """轮询对比任务状态，直到 completed 或 failed。"""
    deadline = time.monotonic() + timeout_seconds
    last_status: dict[str, Any] = {}

    while time.monotonic() < deadline:
        resp = api.get(f"/api/v1/compare/{review_id}/status")
        assert resp.status_code == 200, resp.text
        last_status = resp.json()
        status = last_status.get("status")

        if status == "completed":
            return last_status
        if status == "failed":
            pytest.fail(f"文档对比失败: {review_id}, error={last_status.get('error')}")

        time.sleep(interval_seconds)

    pytest.fail(f"等待文档对比完成超时: {review_id}, last={last_status}")


@pytest.fixture(scope="module")
def compare_documents(
    upload_document: Callable[[Path, bool], dict[str, Any]],
    tender_docx_path: Path,
    tender_pdf_path: Path,
) -> list[dict[str, Any]]:
    """上传两个参与对比的文档，并等待转换完成。"""
    first = upload_document(tender_docx_path, True)
    second = upload_document(tender_pdf_path, True)
    assert first["status"] == "ready"
    assert second["status"] == "ready"
    assert first["id"] != second["id"]
    return [first, second]


@pytest.fixture(scope="module")
def compare_result(api: httpx.Client, compare_documents: list[dict[str, Any]]) -> dict[str, Any]:
    """创建异步对比任务，等待完成后返回状态与结果。"""
    document_ids = [document["id"] for document in compare_documents]
    resp = api.post("/api/v1/compare", json={"document_ids": document_ids})
    assert resp.status_code == 202, resp.text
    created = resp.json()
    review_id = created["reviewId"]

    completed_status = _wait_for_compare_completed(api, review_id)

    result_resp = api.get(f"/api/v1/compare/{review_id}/result")
    assert result_resp.status_code == 200, result_resp.text

    return {
        "review_id": review_id,
        "document_ids": document_ids,
        "created": created,
        "status": completed_status,
        "result": result_resp.json(),
    }


class TestCompare:
    """B19-B21: 基于 document_ids 的文档对比端到端。"""

    def test_create_compare_run_returns_pending(self, compare_result: dict[str, Any]) -> None:
        """创建对比任务应立即返回 reviewId 和 pending 状态。"""
        created = compare_result["created"]
        assert created["reviewId"] == compare_result["review_id"]
        assert created["status"] == "pending"

    def test_compare_status_completed(self, compare_result: dict[str, Any]) -> None:
        """对比状态最终应进入 completed。"""
        status = compare_result["status"]
        assert status["status"] == "completed"
        assert status["fileCount"] == 2
        assert len(status["fileNames"]) == 2

    def test_compare_result_contains_matches(self, compare_result: dict[str, Any]) -> None:
        """对比结果应包含 summary、documents 和 match 数据。"""
        result = compare_result["result"]
        assert result["reviewId"] == compare_result["review_id"]
        assert "summary" in result
        assert "documents" in result
        assert "matches" in result
        assert isinstance(result["matches"], list)
        assert result["summary"]["matchCount"] == len(result["matches"])
        assert len(result["matches"]) > 0

    def test_compare_result_has_documents(self, compare_result: dict[str, Any]) -> None:
        """对比结果应包含两个文件的段落结构。"""
        documents = compare_result["result"]["documents"]
        assert "files" in documents
        assert len(documents["files"]) == 2
        assert [document["fileIndex"] for document in documents["files"]] == [0, 1]

    def test_download_first_highlighted(
        self, api: httpx.Client, compare_result: dict[str, Any]
    ) -> None:
        """下载第一个文件的高亮 DOCX。"""
        review_id = compare_result["review_id"]
        resp = api.get(f"/api/v1/compare/{review_id}/download/0")
        assert resp.status_code == 200
        assert DOCX_CONTENT_TYPE in resp.headers.get("content-type", "")
        assert len(resp.content) > 100

    def test_download_second_highlighted(
        self, api: httpx.Client, compare_result: dict[str, Any]
    ) -> None:
        """下载第二个文件的高亮 DOCX。"""
        review_id = compare_result["review_id"]
        resp = api.get(f"/api/v1/compare/{review_id}/download/1")
        assert resp.status_code == 200
        assert DOCX_CONTENT_TYPE in resp.headers.get("content-type", "")
        assert len(resp.content) > 100

    def test_download_nonexistent_review(self, api: httpx.Client) -> None:
        """不存在的对比任务下载应返回 404。"""
        resp = api.get("/api/v1/compare/nonexistent_999/download/0")
        assert resp.status_code == 404

    def test_compare_requires_two_documents(
        self,
        api: httpx.Client,
        compare_documents: list[dict[str, Any]],
    ) -> None:
        """创建对比任务至少需要两个文档 ID。"""
        resp = api.post(
            "/api/v1/compare",
            json={"document_ids": [compare_documents[0]["id"]]},
        )
        assert resp.status_code == 400
