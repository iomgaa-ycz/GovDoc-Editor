"""harness.db 自定义表创建单测。"""

import sqlite3
from pathlib import Path

from govdoc.harness.log import HarnessLog
from govdoc.harness.schemas import create_all_tables


class TestCreateAllTables:
    """测试 create_all_tables 创建全部 8 张表。"""

    def test_creates_all_eight_tables(self, tmp_path: Path) -> None:
        """创建后应有 8 张自定义表 + 2 张固定表。"""
        db_path = str(tmp_path / "test.db")
        log = HarnessLog(db_path=db_path, run_id="test-001")
        create_all_tables(log)

        conn = sqlite3.connect(db_path)
        tables = sorted(
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        )
        conn.close()
        log.close()

        expected = [
            "_events",
            "_runs",
            "agent_trajectories",
            "api_calls",
            "api_contracts",
            "audit_results",
            "extract_results",
            "phase_metrics",
            "pipeline_runs",
            "quality_scores",
        ]
        assert tables == expected

    def test_tables_have_correct_columns(self, tmp_path: Path) -> None:
        """pipeline_runs 表应包含设计的列。"""
        db_path = str(tmp_path / "test.db")
        log = HarnessLog(db_path=db_path, run_id="test-002")
        create_all_tables(log)

        conn = sqlite3.connect(db_path)
        cols = [row[1] for row in conn.execute("PRAGMA table_info(pipeline_runs)").fetchall()]
        conn.close()
        log.close()

        for expected_col in ["run_id", "pipeline", "project_name", "status", "duration_s"]:
            assert expected_col in cols, f"缺少列: {expected_col}"

    def test_idempotent(self, tmp_path: Path) -> None:
        """重复调用不报错（IF NOT EXISTS）。"""
        db_path = str(tmp_path / "test.db")
        log = HarnessLog(db_path=db_path, run_id="test-003")
        create_all_tables(log)
        create_all_tables(log)
        log.close()
