"""E2E: 审核点批量导入（XLS）+ CRUD 操作。"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest


@pytest.fixture(scope="module")
def imported_checkpoints(api: httpx.Client, checkpoint_xls_path: Path) -> list[dict]:
    """导入 XLS，返回写入审核点库的列表。"""
    with open(checkpoint_xls_path, "rb") as f:
        resp = api.post(
            "/api/v1/checkpoints/import",
            files={"file": (checkpoint_xls_path.name, f, "application/octet-stream")},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["imported_count"] >= 1
    return data["checkpoints"]


class TestCheckpointImport:
    """B10: 批量导入审核点。"""

    def test_import_returns_counts(
        self, api: httpx.Client, checkpoint_xls_path: Path,
    ):
        with open(checkpoint_xls_path, "rb") as f:
            resp = api.post(
                "/api/v1/checkpoints/import",
                files={"file": (checkpoint_xls_path.name, f, "application/octet-stream")},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "imported_count" in data
        assert "skipped_count" in data
        assert "skipped_reasons" in data
        assert isinstance(data["skipped_reasons"], list)
        assert data["imported_count"] >= 0

    def test_import_invalid_format(self, api: httpx.Client):
        resp = api.post(
            "/api/v1/checkpoints/import",
            files={"file": ("bad.txt", b"not a spreadsheet", "text/plain")},
        )
        assert resp.status_code == 400
        assert "不支持" in resp.json()["detail"]


class TestCheckpointCRUD:
    """B11-B13: 审核点查看 / 编辑 / 删除。"""

    def test_list_checkpoints(self, api: httpx.Client, imported_checkpoints: list[dict]):
        """B11: 列表应包含导入的审核点。"""
        resp = api.get("/api/v1/checkpoints")
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)
        ids = {item["id"] for item in items}
        assert imported_checkpoints[0]["id"] in ids

    def test_update_checkpoint(self, api: httpx.Client, imported_checkpoints: list[dict]):
        """B12: 编辑审核点 payload。"""
        target_id = imported_checkpoints[0]["id"]
        original_payload = imported_checkpoints[0]["payload_json"]
        parsed = json.loads(original_payload) if original_payload else {}
        parsed["title"] = "E2E 修改后的标题"
        new_payload = json.dumps(parsed, ensure_ascii=False)

        resp = api.put(
            f"/api/v1/checkpoints/{target_id}",
            json={"payload_json": new_payload},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "E2E 修改后的标题" in data["payload_json"]

    def test_delete_checkpoint(self, api: httpx.Client, imported_checkpoints: list[dict]):
        """B13: 删除审核点后 404。"""
        if len(imported_checkpoints) < 2:
            pytest.skip("导入审核点不足 2 个，跳过删除测试")
        target_id = imported_checkpoints[-1]["id"]

        resp = api.delete(f"/api/v1/checkpoints/{target_id}")
        assert resp.status_code == 204

        resp2 = api.get("/api/v1/checkpoints")
        ids = {item["id"] for item in resp2.json()}
        assert target_id not in ids

    def test_delete_nonexistent(self, api: httpx.Client):
        resp = api.delete("/api/v1/checkpoints/nonexistent_999")
        assert resp.status_code == 404
