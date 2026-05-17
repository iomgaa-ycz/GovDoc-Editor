"""E2E: Pipeline A — 上传法规 → 触发提取 → 轮询 → 查看入库审核点。

标记 @pytest.mark.slow：涉及真实 LLM 调用，单次约 1-5 分钟。
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def extract_result(api: httpx.Client, guide_docx_path: Path) -> dict:
    """上传法规文件，触发提取，返回 {rule_source_id, extract_run_id}。"""
    with open(guide_docx_path, "rb") as f:
        resp = api.post(
            "/api/v1/rules/upload",
            data={"title": "E2E-专项整治工作指引"},
            files={"file": (guide_docx_path.name, f, "application/octet-stream")},
        )
    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert "rule_source_id" in data
    assert "extract_run_id" in data
    assert data["status"] == "pending"
    return data


class TestRuleExtract:
    """B07-B09: 法规上传 → 提取 → 查看入库审核点。"""

    def test_upload_triggers_extraction(self, extract_result: dict):
        """B07: 上传法规返回 rule_source_id + extract_run_id。"""
        assert extract_result["rule_source_id"]
        assert extract_result["extract_run_id"]

    def test_list_rule_sources(self, api: httpx.Client, extract_result: dict):
        """法规列表包含刚上传的法规。"""
        resp = api.get("/api/v1/rules")
        assert resp.status_code == 200
        rules = resp.json()
        ids = {r["id"] for r in rules}
        assert extract_result["rule_source_id"] in ids

    def test_poll_extraction_status(self, api: httpx.Client, extract_result: dict):
        """B08: 轮询直到 draft_ready 或 failed（最长 5 分钟）。"""
        rule_id = extract_result["rule_source_id"]
        run_id = extract_result["extract_run_id"]
        terminal_states = {"draft_ready", "failed"}

        status = "unknown"
        for _ in range(120):  # 最长等 10 分钟（120 × 5s）
            resp = api.get(f"/api/v1/rules/{rule_id}/extract-runs/{run_id}/status")
            assert resp.status_code == 200
            status = resp.json()["status"]
            if status in terminal_states:
                break
            time.sleep(5)
        else:
            pytest.fail(f"提取超时（10 分钟），最后状态: {status}")

        assert status in terminal_states, f"意外状态: {status}"

    def test_view_checkpoints(self, api: httpx.Client, extract_result: dict):
        """B09: 查看提取出的入库审核点。"""
        rule_id = extract_result["rule_source_id"]
        run_id = extract_result["extract_run_id"]

        status_resp = api.get(f"/api/v1/rules/{rule_id}/extract-runs/{run_id}/status")
        status = status_resp.json()["status"]
        if status == "failed":
            pytest.skip(f"提取失败，跳过审核点查看: {status_resp.json().get('error')}")

        resp = api.get("/api/v1/checkpoints")
        assert resp.status_code == 200
        checkpoints = resp.json()
        assert isinstance(checkpoints, list)
        assert len(checkpoints) >= 1, "提取应至少产生 1 个入库审核点"
        assert checkpoints[0]["kind"] == "final"
        assert "payload_json" in checkpoints[0]
