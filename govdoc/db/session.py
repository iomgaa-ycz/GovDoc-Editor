"""GovDoc 数据库引擎与 Session 依赖。"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Iterator

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlmodel import Session, SQLModel, create_engine

from govdoc.config import load_config

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@lru_cache
def get_engine():
    config = load_config()
    connect_args = (
        {"check_same_thread": False} if config.app.database_url.startswith("sqlite") else {}
    )
    return create_engine(config.app.database_url, echo=False, connect_args=connect_args)


def init_db() -> None:
    """通过 Alembic 迁移初始化/升级数据库 schema。

    幂等：已是最新版本时直接跳过。
    """
    cfg = AlembicConfig(str(_PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", load_config().app.database_url)
    alembic_command.upgrade(cfg, "head")
    logger.info("数据库迁移完成")


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
