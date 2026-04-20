"""FastAPI 依赖注入。"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlmodel import Session

from govdoc.db.session import get_engine


@contextmanager
def get_db_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
