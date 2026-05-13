"""SqliteHandler：将 Python logging 记录写入 harness.db _events 表。"""

from __future__ import annotations

import json
import logging
import sqlite3
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteHandler(logging.Handler):
    """将 logging.LogRecord 写入 SQLite _events 表。

    参数:
        db_path: harness.db 文件路径。
        run_id: 当前运行标识，写入每条 event 的 run_id 列。
    """

    def __init__(self, db_path: str, run_id: str) -> None:
        super().__init__()
        self._run_id = run_id
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS _runs (
                run_id TEXT PRIMARY KEY,
                git_sha TEXT,
                started_at TEXT,
                finished_at TEXT,
                config JSON,
                status TEXT DEFAULT 'running'
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS _events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                timestamp TEXT,
                event_type TEXT,
                payload JSON
            )
        """)
        self._conn.commit()

    def emit(self, record: logging.LogRecord) -> None:
        """将一条 LogRecord 写入 _events 表。"""
        try:
            payload: dict[str, Any] = {
                "logger": record.name,
                "message": self.format(record) if self.formatter else record.getMessage(),
                "location": f"{record.pathname}:{record.lineno}",
            }
            if record.exc_info and record.exc_info[1] is not None:
                payload["exception"] = "".join(
                    traceback.format_exception(*record.exc_info)
                )
            self._conn.execute(
                "INSERT INTO _events (run_id, timestamp, event_type, payload) VALUES (?, ?, ?, ?)",
                (
                    self._run_id,
                    _now_iso(),
                    record.levelname,
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            self._conn.commit()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        """关闭数据库连接。"""
        self._conn.close()
        super().close()
