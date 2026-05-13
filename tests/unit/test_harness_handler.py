"""SqliteHandler 单元测试。"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

import pytest

from govdoc.harness.handler import SqliteHandler


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test_handler.db")


@pytest.fixture
def handler(db_path: str) -> SqliteHandler:
    h = SqliteHandler(db_path=db_path, run_id="test-run-001")
    yield h
    h.close()


class TestSqliteHandler:
    """SqliteHandler 基本功能测试。"""

    def test_emit_writes_event(self, handler: SqliteHandler, db_path: str) -> None:
        """logger 调用应写入 _events 表。"""
        logger = logging.getLogger("test.emit")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        logger.warning("测试警告消息")

        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT * FROM _events").fetchall()
        conn.close()

        assert len(rows) == 1
        row = rows[0]
        assert row[1] == "test-run-001"
        assert row[3] == "WARNING"
        payload = json.loads(row[4])
        assert "测试警告消息" in payload["message"]

        logger.removeHandler(handler)

    def test_emit_captures_exception(self, handler: SqliteHandler, db_path: str) -> None:
        """logger.exception 应捕获异常信息。"""
        logger = logging.getLogger("test.exc")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            raise ValueError("模拟错误")
        except ValueError:
            logger.exception("处理失败")

        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT payload FROM _events").fetchall()
        conn.close()

        payload = json.loads(rows[0][0])
        assert "exception" in payload
        assert "ValueError" in payload["exception"]

        logger.removeHandler(handler)

    def test_creates_fixed_tables(self, db_path: str) -> None:
        """初始化时应自动创建 _runs 和 _events 表。"""
        h = SqliteHandler(db_path=db_path, run_id="init-test")
        conn = sqlite3.connect(db_path)
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        conn.close()
        h.close()

        assert "_runs" in tables
        assert "_events" in tables
