"""Harness 健壮性专项单测。"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from govdoc.harness.log import HarnessLog
from govdoc.harness.schemas import create_all_tables


class TestExitDoesNotMaskException:
    """P5: __exit__ 中 close() 失败不应覆盖原始异常。"""

    def test_original_exception_propagates(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "h.db")
        with pytest.raises(RuntimeError, match="原始错误"):
            with HarnessLog(db_path=db_path, run_id="mask-test") as log:
                log._conn.close()
                raise RuntimeError("原始错误")


class TestHeartbeat:
    """P11: heartbeat 更新时间戳。"""

    def test_heartbeat_updates_column(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "h.db")
        with HarnessLog(db_path=db_path, run_id="hb-test") as log:
            log.heartbeat("pipeline_A")
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT heartbeat_at FROM _runs WHERE run_id='hb-test'").fetchone()
            conn.close()
            assert row is not None
            assert row[0] is not None


class TestMainCatchesFatalException:
    """验证 CLI 主入口会记录致命异常。"""

    def test_crash_recorded_in_db(self, tmp_path: Path) -> None:
        """不存在的 manifest 应记录崩溃状态和 CRITICAL 事件。"""
        db_path = str(tmp_path / "crash.db")
        result = subprocess.run(
            [sys.executable, "-m", "govdoc.harness.pipeline_eval",
             "--manifest", str(tmp_path / "nonexistent_12345.yaml"),
             "--db-path", db_path],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode != 0
        conn = sqlite3.connect(db_path)
        runs = conn.execute("SELECT status FROM _runs").fetchall()
        events = conn.execute(
            "SELECT event_type, payload FROM _events WHERE event_type='CRITICAL'"
        ).fetchall()
        conn.close()
        assert len(runs) >= 1
        assert any(r[0] in ("crashed", "failed") for r in runs)
        assert len(events) >= 1
