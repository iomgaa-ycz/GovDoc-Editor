"""GovDoc 数据库引擎与 Session 依赖。"""

from __future__ import annotations

from functools import lru_cache
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

from govdoc.config import load_config


@lru_cache
def get_engine():
    config = load_config()
    connect_args = {"check_same_thread": False} if config.app.database_url.startswith("sqlite") else {}
    return create_engine(config.app.database_url, echo=False, connect_args=connect_args)


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session

