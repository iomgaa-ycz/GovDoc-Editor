"""Harness 健壮性专项单测。"""

from __future__ import annotations

import sqlite3
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
