"""测试 _persist_point_result 在 PES 报告失败但产物有效时的恢复逻辑。"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from govdoc.pipelines.audit_tender import _persist_point_result
from govdoc.schemas import GovCheckpoint


def _make_checkpoint() -> GovCheckpoint:
    return GovCheckpoint(
        id="cp_recover_01",
        title="恢复测试审核点",
        category="围标串标",
        description="测试用审核点",
        severity="major",
        legal_basis=[],
        retrieval_hint="",
    )


def _make_workspace(tmp_path: Path) -> SimpleNamespace:
    """创建包含合法 output.json 的 workspace。"""
    working = tmp_path / "working"
    working.mkdir(parents=True)
    output = {
        "findings": [
            {
                "checkpoint": {
                    "id": "cp_recover_01",
                    "category": "围标串标",
                    "title": "恢复测试审核点",
                    "description": "测试用审核点",
                    "legal_basis": [],
                    "severity": "major",
                    "retrieval_hint": "",
                },
                "verdict": {
                    "verdict": "存疑",
                    "rationale": "证据不足",
                    "evidence_quotes": ["引用片段"],
                    "suggestion": "建议补充",
                },
                "evidence_refs": [],
                "case_refs": [],
            }
        ],
        "summary": "共审核 1 个审核点。",
    }
    (working / "output.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return SimpleNamespace(working_dir=working)


def _make_manager() -> MagicMock:
    mgr = MagicMock()
    mgr.archive.return_value = Path("/fake/archive.tar.gz")
    return mgr


def test_failed_result_with_valid_output_recovers(tmp_path: Path) -> None:
    """PES 报告失败但 output.json 合法 → status 应为 completed。"""
    point_run = MagicMock()
    point_run.status = "pending"
    point_run.finding_json = None
    result = SimpleNamespace(
        status="failed",
        error="stop_reason=tool_use errors=['Reached maximum number of turns (4)']",
        final_output_path=None,
        final_output=None,
        phase_results=[],
    )
    workspace = _make_workspace(tmp_path)
    manager = _make_manager()
    checkpoint = _make_checkpoint()

    _persist_point_result(point_run, result, workspace, checkpoint, manager)

    assert point_run.status == "completed"
    assert point_run.finding_json is not None
    finding = json.loads(point_run.finding_json)
    assert finding["verdict"]["verdict"] == "存疑"
    manager.archive.assert_called_once_with(workspace, success=True)


def test_failed_result_without_output_stays_failed(tmp_path: Path) -> None:
    """PES 报告失败且无 output.json → status 应保持 failed。"""
    point_run = MagicMock()
    point_run.status = "pending"
    result = SimpleNamespace(
        status="failed",
        error="真正的错误",
        final_output_path=None,
        final_output=None,
        phase_results=[],
    )
    workspace = SimpleNamespace(working_dir=tmp_path / "working")
    (tmp_path / "working").mkdir()
    manager = _make_manager()
    checkpoint = _make_checkpoint()

    _persist_point_result(point_run, result, workspace, checkpoint, manager)

    assert point_run.status == "failed"
    assert point_run.error == "真正的错误"
    manager.archive.assert_called_once_with(workspace, success=False)
