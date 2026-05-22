"""用户认证路由——注册、登录、获取当前用户信息。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from govdoc.api.deps import get_current_user, get_db_session
from govdoc.config import load_config
from govdoc.db.models import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── 请求/响应模型 ──


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6)
    display_name: str = Field(min_length=1, max_length=50)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ── 工具函数 ──


def _create_token(user: User) -> str:
    cfg = load_config()
    expire = datetime.now(timezone.utc) + timedelta(hours=cfg.app.jwt_expire_hours)
    payload = {"sub": user.id, "username": user.username, "exp": expire}
    return jwt.encode(payload, cfg.app.jwt_secret_key, algorithm="HS256")


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )


# ── 路由 ──


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, session: Session = Depends(get_db_session)) -> UserResponse:
    """注册新用户。"""
    existing = session.exec(select(User).where(User.username == payload.username)).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")

    user = User(
        username=payload.username,
        password_hash=pwd_ctx.hash(payload.password),
        display_name=payload.display_name,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return _user_response(user)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, session: Session = Depends(get_db_session)) -> LoginResponse:
    """用户名密码登录，返回 JWT token。"""
    user = session.exec(select(User).where(User.username == payload.username)).first()
    if user is None or not pwd_ctx.verify(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")

    token = _create_token(user)
    return LoginResponse(access_token=token, user=_user_response(user))


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """获取当前登录用户信息。"""
    return _user_response(current_user)
