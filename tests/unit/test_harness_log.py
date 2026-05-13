"""HarnessLog 单元测试。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from govdoc.harness import HarnessLog


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test.db")


class TestHarnessLog:
    """HarnessLog 核心功能测试。"""

    def test_init_creates_tables_and_run(self, db_path: str) -> None:
        """初始化时应创建固定表并插入 _runs 记录。"""
        with HarnessLog(db_path=db_path, run_id="run-001", git_sha="abc123") as log:
            runs = log.query("SELECT * FROM _runs WHERE run_id = ?", ("run-001",))
            assert len(runs) == 1
            assert runs[0]["status"] == "running"
            assert runs[0]["git_sha"] == "abc123"

    def test_close_sets_completed(self, db_path: str) -> None:
        """close() 应将状态设为 completed。"""
        log = HarnessLog(db_path=db_path, run_id="run-002", git_sha="abc")
        log.close(status="completed")

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT status, finished_at FROM _runs WHERE run_id = ?", ("run-002",)
        ).fetchone()
        conn.close()
        assert row[0] == "completed"
        assert row[1] is not None

    def test_context_manager_sets_failed_on_exception(self, db_path: str) -> None:
        """异常退出上下文时状态应为 failed。"""
        with pytest.raises(RuntimeError):
            with HarnessLog(db_path=db_path, run_id="run-003", git_sha="abc"):
                raise RuntimeError("boom")

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT status FROM _runs WHERE run_id = ?", ("run-003",)).fetchone()
        conn.close()
        assert row[0] == "failed"

    def test_log_event(self, db_path: str) -> None:
        """log_event 应写入 _events 表。"""
        with HarnessLog(db_path=db_path, run_id="run-004", git_sha="abc") as log:
            log.log_event("pipeline_start", {"pipeline": "extract_rules"})
            events = log.query("SELECT * FROM _events WHERE run_id = ?", ("run-004",))
            assert len(events) == 1
            assert events[0]["event_type"] == "pipeline_start"
            payload = json.loads(events[0]["payload"])
            assert payload["pipeline"] == "extract_rules"

    def test_create_table_and_insert(self, db_path: str) -> None:
        """create_table + insert 应能写入自定义表。"""
        with HarnessLog(db_path=db_path, run_id="run-005", git_sha="abc") as log:
            log.create_table("audit_metrics", {"accuracy": "REAL", "recall": "REAL"})
            log.insert("audit_metrics", {"accuracy": 0.85, "recall": 0.72})
            rows = log.query("SELECT * FROM audit_metrics WHERE run_id = ?", ("run-005",))
            assert len(rows) == 1
            assert rows[0]["accuracy"] == 0.85
            assert rows[0]["recall"] == 0.72

    def test_insert_many(self, db_path: str) -> None:
        """insert_many 应批量写入。"""
        with HarnessLog(db_path=db_path, run_id="run-006", git_sha="abc") as log:
            log.create_table("steps", {"step": "INTEGER", "loss": "REAL"})
            log.insert_many(
                "steps",
                [
                    {"step": 1, "loss": 0.5},
                    {"step": 2, "loss": 0.3},
                ],
            )
            rows = log.query("SELECT * FROM steps WHERE run_id = ?", ("run-006",))
            assert len(rows) == 2
