import pytest

from govdoc.pipelines.pes_overrides import _validate_govdoc_auditor_payload


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
