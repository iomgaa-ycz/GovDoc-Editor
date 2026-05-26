"""E2E: Pipeline B — 上传 Document → 创建项目 → 导入审核点 → 启动审核 → 轮询结果。

完整端到端流程，自行准备全部数据。
标记 @pytest.mark.slow：涉及真实 LLM 调用，约 3-10 分钟。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def setup_project(
    api: httpx.Client,
    upload_document: Callable[[Path, bool], dict[str, Any]],
    tender_docx_path: Path,
    tender_pdf_path: Path,
    checkpoint_xls_path: Path,
) -> dict[str, Any]:
    """创建项目、上传 Document、导入审核点，返回端到端流程所需 ID。"""
    resp = api.post(
        "/api/v1/projects",
        json={
            "name": f"E2E审核测试_{uuid4().hex[:8]}",
            "created_by": "e2e-bot",
        },
    )
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["id"]

    main_document = upload_document(tender_docx_path, True)
    supplementary_document = upload_document(tender_pdf_path, True)
    assert main_document["status"] == "ready"
    assert supplementary_document["status"] == "ready"

    with checkpoint_xls_path.open("rb") as file_obj:
        resp = api.post(
            "/api/v1/checkpoints/import",
            files={"file": (checkpoint_xls_path.name, file_obj, "application/octet-stream")},
        )
    assert resp.status_code == 200, resp.text

    resp = api.get("/api/v1/checkpoints")
    assert resp.status_code == 200, resp.text
    all_checkpoints = resp.json()
    if not all_checkpoints:
        pytest.skip("无可用审核点，跳过审核测试")

    return {
        "project_id": project_id,
        "main_document_id": main_document["id"],
        "supplementary_document_id": supplementary_document["id"],
        "checkpoint_ids": [checkpoint["id"] for checkpoint in all_checkpoints[:2]],
    }


@pytest.fixture(scope="module")
def audit_run(api: httpx.Client, setup_project: dict[str, Any]) -> dict[str, Any]:
    """创建审核运行，并返回创建结果。"""
    resp = api.post(
        "/api/v1/audit/runs",
        json={
            "project_id": setup_project["project_id"],
            "main_document_id": setup_project["main_document_id"],
            "supplementary_document_ids": [setup_project["supplementary_document_id"]],
            "checkpoint_ids": setup_project["checkpoint_ids"],
            "created_by": "e2e-bot",
        },
    )
    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert "audit_run_id" in data
    assert data["total_count"] == len(setup_project["checkpoint_ids"])

    return {
        **setup_project,
        "audit_run_id": data["audit_run_id"],
        "created": data,
    }


@pytest.fixture(scope="module")
def audit_progress(api_long: httpx.Client, audit_run: dict[str, Any]) -> dict[str, Any]:
    """轮询审核进度直到终态。"""
    terminal_states = {"draft_ready", "partial_ready", "completed", "failed", "waiting_retry"}
    audit_run_id = audit_run["audit_run_id"]
    last_progress: dict[str, Any] = {}

    for _ in range(120):
        resp = api_long.get(f"/api/v1/audit/runs/{audit_run_id}/progress")
        assert resp.status_code == 200, resp.text
        last_progress = resp.json()
        status = last_progress["status"]

        if status in terminal_states:
            return last_progress

        time.sleep(5)

    pytest.fail(f"审核超时（10 分钟），最后进度: {last_progress}")


class TestAuditRun:
    """B14-B18: 创建审核 → 轮询 → 查看结果 → 重试。"""

    def test_create_audit_run(self, audit_run: dict[str, Any]) -> None:
        """B14: 使用 main_document_id 创建含附件的审核运行。"""
        created = audit_run["created"]
        assert created["audit_run_id"] == audit_run["audit_run_id"]
        assert created["total_count"] == len(audit_run["checkpoint_ids"])
        assert created["status"] in {"pending", "running"}

    def test_invalid_supplementary_ids(
        self,
        api: httpx.Client,
        setup_project: dict[str, Any],
    ) -> None:
        """B15: 非法附件 Document ID 应返回 400。"""
        resp = api.post(
            "/api/v1/audit/runs",
            json={
                "project_id": setup_project["project_id"],
                "main_document_id": setup_project["main_document_id"],
                "supplementary_document_ids": ["nonexistent_999"],
                "checkpoint_ids": setup_project["checkpoint_ids"],
            },
        )
        assert resp.status_code == 400

    def test_duplicate_supplementary_id(
        self,
        api: httpx.Client,
        setup_project: dict[str, Any],
    ) -> None:
        """附件 Document ID 与主文档重复应返回 400。"""
        resp = api.post(
            "/api/v1/audit/runs",
            json={
                "project_id": setup_project["project_id"],
                "main_document_id": setup_project["main_document_id"],
                "supplementary_document_ids": [setup_project["main_document_id"]],
                "checkpoint_ids": setup_project["checkpoint_ids"],
            },
        )
        assert resp.status_code == 400
        assert "重复" in resp.json()["detail"] or "冲突" in resp.json()["detail"]

    def test_list_audit_runs(self, api: httpx.Client, audit_run: dict[str, Any]) -> None:
        """列表应包含刚创建的审核运行。"""
        resp = api.get(
            "/api/v1/audit/runs",
            params={"project_id": audit_run["project_id"]},
        )
        assert resp.status_code == 200
        runs = resp.json()
        assert any(run["id"] == audit_run["audit_run_id"] for run in runs)
        assert any(run["main_document_id"] == audit_run["main_document_id"] for run in runs)

    def test_get_audit_run_detail(self, api: httpx.Client, audit_run: dict[str, Any]) -> None:
        """B17: 查看审核运行详情。"""
        resp = api.get(f"/api/v1/audit/runs/{audit_run['audit_run_id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == audit_run["audit_run_id"]
        assert data["main_document_id"] == audit_run["main_document_id"]
        assert data["total_count"] >= 1

    def test_poll_audit_progress(self, audit_progress: dict[str, Any]) -> None:
        """B16: 轮询审核进度直到完成或失败终态。"""
        assert audit_progress["status"] in {
            "draft_ready",
            "partial_ready",
            "completed",
            "failed",
            "waiting_retry",
        }
        assert "point_runs" in audit_progress

    def test_point_runs_have_findings(self, audit_progress: dict[str, Any]) -> None:
        """完成的审核点应包含 finding_json。"""
        point_runs = audit_progress.get("point_runs", [])
        if not point_runs:
            pytest.skip("无 point_runs 数据")

        completed = [point_run for point_run in point_runs if point_run["status"] == "completed"]
        if not completed:
            pytest.skip("无已完成的审核点，跳过 finding_json 校验")

        for point_run in completed:
            assert point_run["finding_json"] is not None, (
                f"point_run {point_run['id']} 缺少 finding_json"
            )

    def test_retry_failed_point_run(
        self, api: httpx.Client, audit_progress: dict[str, Any]
    ) -> None:
        """B18: 重试失败的审核点（如果有）。"""
        failed = [
            point_run
            for point_run in audit_progress.get("point_runs", [])
            if point_run["status"] == "failed"
        ]
        if not failed:
            pytest.skip("无失败的审核点，跳过重试测试")

        point_run_id = failed[0]["id"]
        resp = api.post(f"/api/v1/audit/point-runs/{point_run_id}/retry")
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "retrying"
