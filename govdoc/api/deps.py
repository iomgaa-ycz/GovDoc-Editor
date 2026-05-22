"""FastAPI 依赖注入。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from govdoc.config import load_config
from govdoc.db.models import User
from govdoc.db.session import get_engine

security = HTTPBearer()


@contextmanager
def get_db_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_db_session),
) -> User:
    """从 Bearer token 解析当前登录用户。"""
    cfg = load_config()
    token = credentials.credentials
    try:
        payload = jwt.decode(token, cfg.app.jwt_secret_key, algorithms=["HS256"])
        user_id: str | None = payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证凭证")

    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证凭证")

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
    return user
