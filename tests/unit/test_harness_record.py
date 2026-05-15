"""Harness record helper tests."""

from __future__ import annotations

import json
from pathlib import Path

from govdoc.harness.log import HarnessLog
from govdoc.harness.pipeline_eval import record_audit_results
from govdoc.harness.pipeline_eval import record_extract_results
from govdoc.harness.schemas import create_all_tables


def test_record_extract_results_stores_full_legal_basis(tmp_path: Path) -> None:
    db_path = str(tmp_path / "harness.db")
    with HarnessLog(db_path=db_path, run_id="record-001") as log:
        create_all_tables(log)
        record_extract_results(
            log,
            [
                {
                    "id": "cp_bid_collusion",
                    "title": "不得串通投标",
                    "category": "围标串标",
                    "description": "供应商之间串通投标",
                    "severity": "critical",
                    "legal_basis": [
                        {
                            "law_name": "中华人民共和国政府采购法",
                            "article": "第二十五条",
                            "quote": "供应商不得相互串通投标报价。",
                        },
                        {
                            "law_name": "中华人民共和国招标投标法",
                            "article": "第三十二条",
                            "quote": "投标人不得相互串通投标报价。",
                        },
                    ],
                }
            ],
        )

        rows = log.query("SELECT * FROM extract_results WHERE run_id=?", (log._run_id,))

    assert len(rows) == 1
    row = rows[0]
    assert row["description"] == "供应商之间串通投标"
    assert row["severity"] == "critical"
    assert row["legal_basis_count"] == 2
    assert json.loads(row["legal_basis_json"]) == [
        {
            "law_name": "中华人民共和国政府采购法",
            "article": "第二十五条",
            "quote": "供应商不得相互串通投标报价。",
        },
        {
            "law_name": "中华人民共和国招标投标法",
            "article": "第三十二条",
            "quote": "投标人不得相互串通投标报价。",
        },
    ]


def _make_log(tmp_path: Path) -> HarnessLog:
    log = HarnessLog(db_path=str(tmp_path / "harness.db"), run_id="test-run")
    create_all_tables(log)
    return log


def test_record_audit_results_stores_full_verdict_and_evidence(tmp_path):
    """audit_results 应存完整 verdict JSON 和 evidence JSON。"""
    log = _make_log(tmp_path)
    findings = [
        {
            "point_run_id": "pr_01",
            "checkpoint_id": "cp_01",
            "verdict": {
                "verdict": "不合规",
                "rationale": "文件中设置了地域限制条件",
                "evidence_quotes": [
                    "要求供应商在本市设有分支机构",
                    "具有广州市范围内类似项目经验",
                ],
            },
            "evidence_refs": [
                {"chunk_id": "c1", "text": "供应商须在广州市设立分支机构", "score": 0.92},
            ],
            "case_refs": [{"case_id": "case_01", "similarity": 0.85}],
            "duration_s": 45.3,
            "status": "completed",
        }
    ]
    record_audit_results(log, findings)

    rows = log.query("SELECT * FROM audit_results WHERE run_id=?", ("test-run",))
    assert len(rows) == 1
    row = rows[0]
    assert row["verdict"] == "不合规"
    assert row["has_evidence"] == 1
    assert row["evidence_count"] == 3  # 2 quotes + 1 ref
    # 新增字段
    verdict_detail = json.loads(row["verdict_json"])
    assert verdict_detail["rationale"] == "文件中设置了地域限制条件"
    assert len(verdict_detail["evidence_quotes"]) == 2
    evidence_detail = json.loads(row["evidence_json"])
    assert len(evidence_detail) == 1
    assert evidence_detail[0]["chunk_id"] == "c1"
