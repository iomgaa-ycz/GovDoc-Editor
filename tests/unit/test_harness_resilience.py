"""Harness 健壮性专项单测。"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from govdoc.harness.log import HarnessLog
from govdoc.harness.pipeline_eval import run_pipeline_eval
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


class TestPipelineTimeout:
    """P6: 管道运行超时应被捕获并记录。"""

    def test_timeout_recorded_in_pipeline_runs(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "timeout.db")
        manifest_path = str(tmp_path / "manifest.yaml")
        (tmp_path / "manifest.yaml").write_text(
            "projects: []\nrules:\n  - name: slow\n    path: fake.doc\ncheckpoints: []\n",
            encoding="utf-8",
        )

        async def slow_extract(**kwargs):
            await asyncio.sleep(9999)

        with patch.dict(os.environ, {"HARNESS_PIPELINE_TIMEOUT": "1"}), \
             patch("govdoc.harness.pipeline_eval._ensure_rule_source", return_value="rs-1"), \
             patch("govdoc.pipelines.extract_rules.run_extract", new=slow_extract), \
             patch("govdoc.db.session.get_session", return_value=iter([MagicMock()])), \
             patch("govdoc.runtime.get_trajectory_store", return_value=MagicMock()):
            asyncio.run(run_pipeline_eval(
                manifest_path=manifest_path, project_root=str(tmp_path),
                rubric_dir=str(tmp_path), db_path=db_path,
            ))

        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT status, error FROM pipeline_runs").fetchall()
        conn.close()
        assert len(rows) >= 1
        assert rows[0][0] == "failed"
        assert "Timeout" in (rows[0][1] or "") or "timeout" in (rows[0][1] or "").lower()
