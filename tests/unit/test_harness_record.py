"""Harness record helper tests."""

from __future__ import annotations

import json
from pathlib import Path

from govdoc.harness.log import HarnessLog
from govdoc.harness.pipeline_eval import collect_workspace_evidence
from govdoc.harness.pipeline_eval import record_agent_trajectory
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


def test_record_agent_trajectory_stores_plan_and_files(tmp_path):
    """agent_trajectories 应存 plan_json、workspace_files、phase_details。"""
    log = _make_log(tmp_path)
    record_agent_trajectory(
        log,
        pipeline="A",
        run_id="extract-run-001",
        plan_json=json.dumps(
            {"items_to_extract": [{"id": "cp_01", "title": "测试"}]}, ensure_ascii=False
        ),
        workspace_files=["plan.json", "plan.md", "findings/cp_01.json"],
        phase_details=[
            {"phase": "plan", "status": "completed", "duration_s": 12.3},
            {"phase": "execute", "status": "completed", "duration_s": 45.0},
            {"phase": "summarize", "status": "completed", "duration_s": 8.1},
        ],
    )

    rows = log.query("SELECT * FROM agent_trajectories WHERE run_id=?", ("test-run",))
    assert len(rows) == 1
    row = rows[0]
    assert row["pipeline"] == "A"
    assert row["source_run_id"] == "extract-run-001"
    plan = json.loads(row["plan_json"])
    assert plan["items_to_extract"][0]["id"] == "cp_01"
    files = json.loads(row["workspace_files_json"])
    assert "findings/cp_01.json" in files
    phases = json.loads(row["phase_details_json"])
    assert len(phases) == 3
    assert phases[0]["phase"] == "plan"


def test_collect_workspace_evidence_from_directory(tmp_path):
    """从 workspace 目录结构中读取 plan.json 和 findings。"""
    working = tmp_path / "working"
    working.mkdir()
    plan = {"items_to_extract": [{"id": "cp_01"}]}
    (working / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    (working / "plan.md").write_text("# Plan", encoding="utf-8")
    findings_dir = working / "findings"
    findings_dir.mkdir()
    (findings_dir / "cp_01.json").write_text('{"title":"test"}', encoding="utf-8")

    evidence = collect_workspace_evidence(workspace_dir=tmp_path)
    assert evidence["plan_json"] != ""
    parsed = json.loads(evidence["plan_json"])
    assert parsed["items_to_extract"][0]["id"] == "cp_01"
    assert "plan.json" in evidence["workspace_files"]
    assert "findings/cp_01.json" in evidence["workspace_files"]
    assert "cp_01" in evidence["findings"]


def test_record_audit_results_failed_point_has_valid_verdict(tmp_path: Path) -> None:
    """failed 状态的审核点应有结构合法的 verdict 占位，而非空 {}。"""
    log = _make_log(tmp_path)
    findings = [
        {
            "point_run_id": "pr_failed",
            "checkpoint_id": "cp_failed",
            "status": "failed",
            "duration_s": 0.0,
            "verdict": {
                "verdict": "未完成",
                "rationale": "审核执行失败",
                "evidence_quotes": [],
            },
            "evidence_refs": [],
            "case_refs": [],
        }
    ]
    record_audit_results(log, findings)
    rows = log.query("SELECT * FROM audit_results WHERE run_id=?", ("test-run",))
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "failed"
    verdict_detail = json.loads(row["verdict_json"])
    assert verdict_detail["verdict"] == "未完成"
    assert "rationale" in verdict_detail


def test_collect_workspace_evidence_from_archive(tmp_path: Path) -> None:
    """从 tar.gz 归档中读取 plan.json 和 findings。"""
    import tarfile

    ws_dir = tmp_path / "ws"
    working = ws_dir / "working"
    working.mkdir(parents=True)
    plan = {"items_to_extract": [{"id": "cp_archive"}]}
    (working / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    findings_dir = working / "findings"
    findings_dir.mkdir()
    (findings_dir / "cp_archive.json").write_text('{"verdict": "存疑"}', encoding="utf-8")

    archive_path = tmp_path / "test.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tf:
        tf.add(working / "plan.json", arcname="working/plan.json")
        tf.add(
            findings_dir / "cp_archive.json",
            arcname="working/findings/cp_archive.json",
        )

    evidence = collect_workspace_evidence(archive_path=archive_path)
    assert evidence["plan_json"] != ""
    parsed = json.loads(evidence["plan_json"])
    assert parsed["items_to_extract"][0]["id"] == "cp_archive"
    assert len(evidence["workspace_files"]) >= 2
    assert "cp_archive" in evidence["findings"]
