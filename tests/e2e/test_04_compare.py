"""E2E: DOCX 文档对比 + 高亮下载。"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture(scope="module")
def compare_result(api: httpx.Client, tender_docx_path: Path) -> dict:
    """对比同一文件的两份副本（自对比），返回结果。"""
    with open(tender_docx_path, "rb") as f1, open(tender_docx_path, "rb") as f2:
        resp = api.post(
            "/api/v1/compare",
            files={
                "first_file": (tender_docx_path.name, f1, DOCX_CONTENT_TYPE),
                "second_file": ("copy_" + tender_docx_path.name, f2, DOCX_CONTENT_TYPE),
            },
        )
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestCompare:
    """B19-B21: 文档对比端到端。"""

    def test_compare_returns_matches(self, compare_result: dict):
        """B19: 对比结果包含 review_id 和 matches。"""
        assert "reviewId" in compare_result
        assert "matches" in compare_result
        assert isinstance(compare_result["matches"], list)
        assert len(compare_result["matches"]) > 0

    def test_compare_has_summary(self, compare_result: dict):
        """对比结果包含统计摘要。"""
        summary = compare_result.get("summary", {})
        assert "matchCount" in summary or "commonParagraphCount" in summary

    def test_compare_has_documents(self, compare_result: dict):
        """对比结果包含两侧文档段落。"""
        documents = compare_result.get("documents", {})
        assert "first" in documents
        assert "second" in documents

    def test_download_first_highlighted(self, api: httpx.Client, compare_result: dict):
        """B20: 下载文档 A 高亮 DOCX。"""
        review_id = compare_result["reviewId"]
        resp = api.get(f"/api/v1/compare/{review_id}/download/first")
        assert resp.status_code == 200
        assert DOCX_CONTENT_TYPE in resp.headers.get("content-type", "")
        assert len(resp.content) > 100

    def test_download_second_highlighted(self, api: httpx.Client, compare_result: dict):
        """B21: 下载文档 B 高亮 DOCX。"""
        review_id = compare_result["reviewId"]
        resp = api.get(f"/api/v1/compare/{review_id}/download/second")
        assert resp.status_code == 200
        assert len(resp.content) > 100

    def test_download_nonexistent_review(self, api: httpx.Client):
        resp = api.get("/api/v1/compare/nonexistent_999/download/first")
        assert resp.status_code == 404

    def test_compare_non_docx_rejected(self, api: httpx.Client):
        """上传非 DOCX 文件 → 400。"""
        resp = api.post(
            "/api/v1/compare",
            files={
                "first_file": ("test.txt", b"hello", "text/plain"),
                "second_file": ("test2.txt", b"world", "text/plain"),
            },
        )
        assert resp.status_code == 400
        assert "DOCX" in resp.json()["detail"]
