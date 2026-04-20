"""test_pes_overrides.py — pes_overrides 层单元测试。"""

from unittest.mock import MagicMock

import pytest

from govdoc.pipelines.pes_overrides import (
    _validate_govdoc_auditor_payload,
    try_recover_audit_output,
)


# ── Validator 测试 ──


def test_validate_govdoc_auditor_payload_accepts_nested_verdict_object():
    payload = {
        "findings": [
            {
                "checkpoint": {"id": "cp_02"},
                "verdict": {
                    "verdict": "合规",
                    "rationale": "收费条款披露完整。",
                    "evidence_quotes": ["售价：免费"],
                    "suggestion": "",
                },
                "evidence_refs": [],
                "case_refs": [],
            }
        ],
        "summary": "未发现违规收费。",
    }

    _validate_govdoc_auditor_payload(
        payload,
        verdict_levels=["合规", "不合规", "存疑"],
        evidence_required=True,
    )


def test_validate_govdoc_auditor_payload_rejects_unknown_verdict_value():
    payload = {
        "findings": [
            {
                "checkpoint": {"id": "cp_02"},
                "verdict": {
                    "verdict": "通过",
                    "rationale": "不符合约定枚举。",
                    "evidence_quotes": ["售价：免费"],
                    "suggestion": "",
                },
                "evidence_refs": [],
                "case_refs": [],
            }
        ],
        "summary": "结果异常。",
    }

    with pytest.raises(ValueError, match="不在 verdict_levels"):
        _validate_govdoc_auditor_payload(
            payload,
            verdict_levels=["合规", "不合规", "存疑"],
            evidence_required=True,
        )


# ── Recovery 测试 ──


@pytest.fixture
def workspace_tree(tmp_path):
    """模拟 workspace 目录结构。"""
    working = tmp_path / "working"
    working.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    findings = working / "findings"
    findings.mkdir()
    return working


def test_recover_from_standard_path(workspace_tree):
    (workspace_tree / "output.json").write_text(
        '{"findings": [{"verdict": {"verdict": "合规"}}], "summary": "ok"}',
        encoding="utf-8",
    )
    result = MagicMock()
    recovered = try_recover_audit_output(result, workspace_tree)
    assert recovered is not None
    assert recovered["findings"][0]["verdict"]["verdict"] == "合规"


def test_recover_from_misplaced_output(workspace_tree):
    output_dir = workspace_tree.parent / "output"
    (output_dir / "output.json").write_text(
        '{"findings": [{"verdict": {"verdict": "不合规"}}], "summary": "bad"}',
        encoding="utf-8",
    )
    result = MagicMock()
    recovered = try_recover_audit_output(result, workspace_tree)
    assert recovered is not None
    assert recovered["findings"][0]["verdict"]["verdict"] == "不合规"


def test_recover_from_findings_dir(workspace_tree):
    findings_dir = workspace_tree / "findings"
    (findings_dir / "cp_01.json").write_text(
        '{"checkpoint": {}, "verdict": {"verdict": "存疑"}}',
        encoding="utf-8",
    )
    result = MagicMock()
    recovered = try_recover_audit_output(result, workspace_tree)
    assert recovered is not None
    assert len(recovered["findings"]) == 1


def test_recover_returns_none_when_empty(workspace_tree):
    result = MagicMock()
    recovered = try_recover_audit_output(result, workspace_tree)
    assert recovered is None
