"""Harness CLI 公共骨架——DDL 初始化 / 运行状态管理 / 信号处理。"""

from __future__ import annotations

import logging
import signal
import sqlite3
import uuid
from pathlib import Path
from types import FrameType
from typing import NoReturn

logger = logging.getLogger(__name__)

RUNS_DDL = """
CREATE TABLE IF NOT EXISTS _runs (
    run_id TEXT PRIMARY KEY,
    git_sha TEXT,
    started_at TEXT,
    finished_at TEXT,
    heartbeat_at TEXT,
    config JSON,
    status TEXT DEFAULT 'running'
)
"""

EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS _events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    timestamp TEXT,
    event_type TEXT,
    payload JSON
)
"""


def init_run_tables(conn: sqlite3.Connection) -> None:
    """创建 _runs 和 _events 固定表。

    参数:
        conn: SQLite 连接。
    """
    conn.execute(RUNS_DDL)
    conn.execute(EVENTS_DDL)
    conn.commit()


def update_run_status(db_path: str, run_id: str, status: str) -> None:
    """确保运行记录存在，并更新最终状态。

    参数:
        db_path: harness.db 文件路径。
        run_id: 运行标识。
        status: 最终状态。
    """
    from govdoc.harness.log import _now_iso

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        init_run_tables(conn)
        now = _now_iso()
        conn.execute(
            "INSERT OR IGNORE INTO _runs (run_id, started_at, status) VALUES (?, ?, ?)",
            (run_id, now, "running"),
        )
        conn.execute(
            "UPDATE _runs SET finished_at = ?, status = ? WHERE run_id = ?",
            (now, status, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def setup_harness_cli(db_path: str, run_id_prefix: str) -> "tuple[str, SqliteHandler]":
    """配置 harness CLI 公共设施：logging + signal handler + sqlite handler。

    参数:
        db_path: harness.db 文件路径。
        run_id_prefix: 运行 ID 前缀（如 "L1" 或 "L2"）。

    返回:
        (run_id, sqlite_handler) 元组。
    """
    from govdoc.harness.handler import SqliteHandler

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    run_id = f"{run_id_prefix}-{uuid.uuid4().hex[:8]}"
    root_logger = logging.getLogger()
    sqlite_handler = SqliteHandler(db_path=db_path, run_id=run_id)
    root_logger.addHandler(sqlite_handler)

    def _handle_signal(signum: int, frame: FrameType | None) -> NoReturn:
        del frame
        update_run_status(db_path, run_id, "interrupted")
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    return run_id, sqlite_handler
