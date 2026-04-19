"""FastAPI 依赖注入。"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlmodel import Session

from govdoc.config import GovDocConfig, load_config
from govdoc.db.session import get_engine


def get_config() -> GovDocConfig:
    return load_config()


@contextmanager
def get_db_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session

