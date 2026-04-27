"""E2E: Pipeline B — 创建项目 → 上传文书 → 导入审核点 → 启动审核 → 轮询 → 查看结果。

完整端到端流程，自行准备全部数据。
标记 @pytest.mark.slow：涉及真实 LLM 调用，约 3-10 分钟。
"""

from __future__ import annotations

import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

pytestmark = pytest.mark.slow

TENDER_DOCX_FILENAME = "从化区中医医院手术室设备及附件、病房护理及医院设备采购.docx"
TENDER_PDF_FILENAME = (
    "从化区中医医院手术室设备及附件、病房护理及医院设备采购招标文件（2024040902）.pdf.pdf"
)
CHECKPOINT_XLS_FILENAME = "附件9 处理处罚标准.xls"


@pytest.fixture(scope="module")
def data_dir() -> Path:
    return Path(__file__).parent / "data"


@pytest.fixture(scope="module")
def setup_project(api: httpx.Client, data_dir: Path) -> dict:
    """创建项目 + 上传主文书 + 上传补充文件 + 导入审核点，返回所有 ID。"""
    # 1. 创建项目
    resp = api.post(
        "/api/v1/projects",
        json={
            "name": f"E2E审核测试_{uuid4().hex[:8]}",
            "created_by": "e2e-bot",
        },
    )
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    # 2. 上传主文书
    with open(data_dir / TENDER_DOCX_FILENAME, "rb") as f:
        resp = api.post(
            f"/api/v1/projects/{project_id}/tender-doc",
            files={"file": (TENDER_DOCX_FILENAME, f, "application/octet-stream")},
        )
    assert resp.status_code == 201
    main_doc_id = resp.json()["id"]

    # 3. 上传补充文件（PDF）
    with open(data_dir / TENDER_PDF_FILENAME, "rb") as f:
        resp = api.post(
            f"/api/v1/projects/{project_id}/tender-doc",
            files={"file": (TENDER_PDF_FILENAME, f, "application/octet-stream")},
        )
    assert resp.status_code == 201
    supp_doc_id = resp.json()["id"]

    # 4. 导入审核点
    with open(data_dir / CHECKPOINT_XLS_FILENAME, "rb") as f:
        resp = api.post(
            "/api/v1/checkpoints/import",
            files={"file": (CHECKPOINT_XLS_FILENAME, f, "application/octet-stream")},
        )
    assert resp.status_code == 200

    # 5. 获取可用的审核点
    resp = api.get("/api/v1/checkpoints")
    assert resp.status_code == 200
    all_checkpoints = resp.json()

    if not all_checkpoints:
        pytest.skip("无可用审核点，跳过审核测试")

    checkpoint_ids = [cp["id"] for cp in all_checkpoints[:3]]

    return {
        "project_id": project_id,
        "main_doc_id": main_doc_id,
        "supp_doc_id": supp_doc_id,
        "checkpoint_ids": checkpoint_ids,
    }


class TestAuditRun:
    """B14-B18: 创建审核 → 轮询 → 查看结果 → 重试。"""

    def test_create_audit_run(self, api: httpx.Client, setup_project: dict):
        """B14: 创建含补充文件的审核运行。"""
        resp = api.post(
            "/api/v1/audit/runs",
            json={
                "project_id": setup_project["project_id"],
                "tender_doc_id": setup_project["main_doc_id"],
                "supplementary_doc_ids": [setup_project["supp_doc_id"]],
                "checkpoint_ids": setup_project["checkpoint_ids"],
            },
        )
        assert resp.status_code == 202, resp.text
        data = resp.json()
        assert "audit_run_id" in data
        assert data["total_count"] == len(setup_project["checkpoint_ids"])
        setup_project["audit_run_id"] = data["audit_run_id"]

    def test_invalid_supplementary_ids(self, api: httpx.Client, setup_project: dict):
        """B15: 非法补充文件 ID → 400。"""
        resp = api.post(
            "/api/v1/audit/runs",
            json={
                "project_id": setup_project["project_id"],
                "tender_doc_id": setup_project["main_doc_id"],
                "supplementary_doc_ids": ["nonexistent_999"],
                "checkpoint_ids": setup_project["checkpoint_ids"],
            },
        )
        assert resp.status_code == 400

    def test_duplicate_supplementary_id(self, api: httpx.Client, setup_project: dict):
        """补充文件 ID 与主文书重复 → 400。"""
        resp = api.post(
            "/api/v1/audit/runs",
            json={
                "project_id": setup_project["project_id"],
                "tender_doc_id": setup_project["main_doc_id"],
                "supplementary_doc_ids": [setup_project["main_doc_id"]],
                "checkpoint_ids": setup_project["checkpoint_ids"],
            },
        )
        assert resp.status_code == 400
        assert "重复" in resp.json()["detail"]

    def test_list_audit_runs(self, api: httpx.Client, setup_project: dict):
        """列表应包含刚创建的审核运行。"""
        resp = api.get(
            "/api/v1/audit/runs",
            params={"project_id": setup_project["project_id"]},
        )
        assert resp.status_code == 200
        runs = resp.json()
        assert any(r["id"] == setup_project.get("audit_run_id") for r in runs)

    def test_get_audit_run_detail(self, api: httpx.Client, setup_project: dict):
        """B17: 查看审核运行详情。"""
        audit_run_id = setup_project.get("audit_run_id")
        if not audit_run_id:
            pytest.skip("无 audit_run_id")
        resp = api.get(f"/api/v1/audit/runs/{audit_run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == audit_run_id
        assert data["total_count"] >= 1

    def test_poll_audit_progress(self, api: httpx.Client, setup_project: dict):
        """B16: 轮询审核进度直到完成（最长 10 分钟）。"""
        audit_run_id = setup_project.get("audit_run_id")
        if not audit_run_id:
            pytest.skip("无 audit_run_id")

        terminal_states = {"draft_ready", "partial_ready", "failed"}
        last_status = "unknown"

        for _ in range(120):
            resp = api.get(f"/api/v1/audit/runs/{audit_run_id}/progress")
            assert resp.status_code == 200
            progress = resp.json()
            last_status = progress["status"]

            if last_status in terminal_states:
                break

            time.sleep(5)
        else:
            pytest.fail(f"审核超时（10 分钟），最后状态: {last_status}")

        setup_project["final_status"] = last_status
        setup_project["point_runs"] = progress["point_runs"]
        assert last_status in terminal_states

    def test_point_runs_have_findings(self, api: httpx.Client, setup_project: dict):
        """完成的审核点应包含 finding_json。"""
        point_runs = setup_project.get("point_runs", [])
        if not point_runs:
            pytest.skip("无 point_runs 数据")

        completed = [pr for pr in point_runs if pr["status"] == "completed"]
        for pr in completed:
            assert pr["finding_json"] is not None, f"point_run {pr['id']} 缺少 finding_json"

    def test_retry_failed_point_run(self, api: httpx.Client, setup_project: dict):
        """B18: 重试失败的审核点（如果有）。"""
        point_runs = setup_project.get("point_runs", [])
        failed = [pr for pr in point_runs if pr["status"] == "failed"]
        if not failed:
            pytest.skip("无失败的审核点，跳过重试测试")

        pr_id = failed[0]["id"]
        resp = api.post(f"/api/v1/audit/point-runs/{pr_id}/retry")
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "retrying"
