"""L1 管道评估逻辑单测。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from govdoc.harness.judge import Verdict
from govdoc.harness.log import HarnessLog
from govdoc.harness.pipeline_eval import (
    evaluate_dimension,
    load_rubric,
    record_audit_results,
    record_extract_results,
    record_pipeline_run,
    record_quality_score,
)
from govdoc.harness.schemas import create_all_tables


class TestRecordPipelineRun:
    """测试 pipeline_runs 记录。"""

    def test_record_completed_run(self, tmp_path: Path) -> None:
        """记录一次成功的管道运行。"""
        db_path = str(tmp_path / "h.db")
        with HarnessLog(db_path=db_path, run_id="r1") as log:
            create_all_tables(log)
            record_pipeline_run(
                log,
                pipeline="A",
                project_name="测试项目",
                input_file="guide.doc",
                status="completed",
                duration_s=120.5,
                total_tokens=5000,
            )

            rows = log.query("SELECT * FROM pipeline_runs WHERE run_id='r1'")
            assert len(rows) == 1
            assert rows[0]["pipeline"] == "A"
            assert rows[0]["status"] == "completed"
            assert rows[0]["duration_s"] == 120.5

    def test_record_failed_run(self, tmp_path: Path) -> None:
        """记录一次失败的管道运行。"""
        db_path = str(tmp_path / "h.db")
        with HarnessLog(db_path=db_path, run_id="r2") as log:
            create_all_tables(log)
            record_pipeline_run(
                log,
                pipeline="B",
                project_name="p2",
                input_file="tender.docx",
                status="failed",
                duration_s=30.0,
                total_tokens=0,
                error="PES 超时",
            )

            rows = log.query("SELECT * FROM pipeline_runs WHERE run_id='r2'")
            assert rows[0]["error"] == "PES 超时"


class TestRecordExtractResults:
    """测试 extract_results 记录。"""

    def test_record_checkpoints(self, tmp_path: Path) -> None:
        """记录管道 A 提取的审核点。"""
        db_path = str(tmp_path / "h.db")
        with HarnessLog(db_path=db_path, run_id="r3") as log:
            create_all_tables(log)
            checkpoints = [
                {
                    "id": "cp_001",
                    "title": "投标人资质限制",
                    "category": "不合理条件限制或排斥供应商",
                    "legal_basis": [
                        {"law_name": "政府采购法", "article": "第22条", "quote": "..."}
                    ],
                },
                {
                    "id": "cp_002",
                    "title": "围标串标行为",
                    "category": "围标串标",
                    "legal_basis": [],
                },
            ]
            record_extract_results(log, checkpoints)

            rows = log.query(
                "SELECT * FROM extract_results WHERE run_id='r3' ORDER BY checkpoint_id"
            )
            assert len(rows) == 2
            assert rows[0]["checkpoint_id"] == "cp_001"
            assert rows[0]["has_legal_basis"] == 1
            assert rows[0]["legal_basis_count"] == 1
            assert rows[1]["has_legal_basis"] == 0


class TestRecordAuditResults:
    """测试 audit_results 记录。"""

    def test_record_findings(self, tmp_path: Path) -> None:
        """记录管道 B 审核发现。"""
        db_path = str(tmp_path / "h.db")
        with HarnessLog(db_path=db_path, run_id="r4") as log:
            create_all_tables(log)
            findings = [
                {
                    "point_run_id": "pr_001",
                    "checkpoint_id": "cp_001",
                    "verdict": "不合规",
                    "evidence_quotes": ["文书第3页提到..."],
                    "evidence_refs": ["chunk_001"],
                    "case_refs": [],
                    "duration_s": 45.2,
                    "status": "completed",
                },
            ]
            record_audit_results(log, findings)

            rows = log.query("SELECT * FROM audit_results WHERE run_id='r4'")
            assert len(rows) == 1
            assert rows[0]["verdict"] == "不合规"
            assert rows[0]["has_evidence"] == 1
            assert rows[0]["evidence_count"] == 2


class TestEvaluateDimension:
    """测试语义评估 + 记录。"""

    def test_evaluate_and_record(self, tmp_path: Path) -> None:
        """evaluate_dimension 调用 judge 并写入 quality_scores。"""
        db_path = str(tmp_path / "h.db")
        with HarnessLog(db_path=db_path, run_id="r5") as log:
            create_all_tables(log)

            mock_judge = MagicMock()
            mock_judge.evaluate.return_value = Verdict(
                passed=True,
                score=0.85,
                reasoning="法条引用准确",
                suggestions=[],
                raw_response="{}",
            )

            result = evaluate_dimension(
                log=log,
                judge=mock_judge,
                dimension="extract-faithfulness",
                criteria="检查法条引用是否忠实于原文",
                evidence={"checkpoints": [], "source_text": "..."},
            )

            assert result.passed is True
            assert result.score == 0.85

            rows = log.query(
                "SELECT * FROM quality_scores WHERE dimension='extract-faithfulness'"
            )
            assert len(rows) == 1
            assert rows[0]["score"] == 0.85
            assert rows[0]["passed"] == 1


class TestLoadRubric:
    """测试 rubric 文件加载。"""

    def test_load_existing_rubric(self, tmp_path: Path) -> None:
        """加载存在的 rubric 文件返回内容。"""
        rubric = tmp_path / "extract_faithfulness.md"
        rubric.write_text("# 法条引用忠实度\n## 评判标准\n...", encoding="utf-8")

        content = load_rubric(str(tmp_path), "extract-faithfulness")
        assert "法条引用忠实度" in content

    def test_load_missing_rubric_raises(self, tmp_path: Path) -> None:
        """加载不存在的 rubric 文件抛 FileNotFoundError。"""
        import pytest

        with pytest.raises(FileNotFoundError):
            load_rubric(str(tmp_path), "nonexistent-dimension")
