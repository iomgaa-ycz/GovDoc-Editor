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


class TestPipelineTimeout:
    def test_timeout_recorded_in_pipeline_runs(self, tmp_path: Path) -> None:
        import asyncio
        import os
        import sqlite3
        from unittest.mock import MagicMock, patch

        from govdoc.harness.pipeline_eval import run_pipeline_eval

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
            asyncio.run(
                run_pipeline_eval(
                    manifest_path=manifest_path,
                    project_root=str(tmp_path),
                    rubric_dir=str(tmp_path),
                    db_path=db_path,
                )
            )
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT status, error FROM pipeline_runs").fetchall()
        conn.close()
        assert len(rows) >= 1 and rows[0][0] == "failed"
        assert "Timeout" in (rows[0][1] or "") or "timeout" in (rows[0][1] or "").lower()


class TestJudgeInitFailure:
    def test_judge_failure_logged_not_raised(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from govdoc.harness.log import HarnessLog
        from govdoc.harness.pipeline_eval import _run_semantic_evaluations
        from govdoc.harness.schemas import create_all_tables

        db_path = str(tmp_path / "judge.db")
        with HarnessLog(db_path=db_path, run_id="judge-fail") as log:
            create_all_tables(log)
            with patch(
                "govdoc.harness.pipeline_eval.HarnessJudge",
                side_effect=ConnectionError("模拟失败"),
            ):
                _run_semantic_evaluations(log, str(tmp_path), str(tmp_path))
            events = log.query(
                "SELECT event_type FROM _events "
                "WHERE run_id='judge-fail' AND event_type='semantic_eval_fatal'"
            )
            assert len(events) == 1
