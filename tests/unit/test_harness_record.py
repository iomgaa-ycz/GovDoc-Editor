"""Harness record helper tests."""

from __future__ import annotations

import json
from pathlib import Path

from govdoc.harness.log import HarnessLog
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
