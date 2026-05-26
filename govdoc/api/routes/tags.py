"""Tag API 路由：标签列表、创建与删除。"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from fastapi import APIRouter, HTTPException, Response
from sqlmodel import Session, select

from govdoc.db.models import DocumentTag, Tag
from govdoc.db.session import get_session
from govdoc.schemas import GovDocModel

router = APIRouter(prefix="/api/v1/tags", tags=["tags"])


class CreateTagRequest(GovDocModel):
    """创建标签请求。

    参数:
        name: 标签名称，去除首尾空白后不能为空。
        color: 标签颜色值，由前端约定格式。
    """

    name: str
    color: str


@contextmanager
def _session_scope() -> Iterator[Session]:
    """兼容 get_session 的生成器形态，提供上下文管理器。

    返回值:
        当前请求使用的 SQLModel Session。

    关键实现:
        `govdoc.db.session.get_session` 当前返回生成器；若未来改为真正的
        上下文管理器，本函数也能直接透传使用。
    """
    session_source = get_session()
    if hasattr(session_source, "__enter__"):
        with session_source as session:
            yield session
        return

    session = next(session_source)
    try:
        yield session
    finally:
        close = getattr(session_source, "close", None)
        if close is not None:
            close()


def _serialize_tag(tag: Tag) -> dict[str, Any]:
    """序列化标签记录。

    参数:
        tag: Tag 数据库模型。

    返回值:
        API 响应中的标签字典。
    """
    return {
        "id": tag.id,
        "name": tag.name,
        "color": tag.color,
        "created_at": str(tag.created_at),
    }


@router.get("/")
async def list_tags() -> list[dict[str, Any]]:
    """返回所有标签，按创建时间倒序排列。

    返回值:
        标签列表。
    """
    with _session_scope() as session:
        tags = session.exec(select(Tag).order_by(Tag.created_at.desc())).all()
        return [_serialize_tag(tag) for tag in tags]


@router.post("/", status_code=201)
async def create_tag(payload: CreateTagRequest) -> dict[str, Any]:
    """创建标签，重复名称返回 409。

    参数:
        payload: 标签名称和颜色。

    返回值:
        新创建的标签记录。

    异常:
        HTTPException: 名称为空或名称重复。
    """
    tag_name = payload.name.strip()
    if not tag_name:
        raise HTTPException(status_code=400, detail="Tag name 不能为空")

    with _session_scope() as session:
        existing = session.exec(select(Tag).where(Tag.name == tag_name)).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail="Tag name 已存在")

        tag = Tag(name=tag_name, color=payload.color)
        session.add(tag)
        session.commit()
        session.refresh(tag)
        return _serialize_tag(tag)


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(tag_id: str) -> Response:
    """删除标签及其所有 DocumentTag 关联。

    参数:
        tag_id: 待删除的标签 ID。

    返回值:
        204 空响应。

    异常:
        HTTPException: 标签不存在。
    """
    with _session_scope() as session:
        tag = session.get(Tag, tag_id)
        if tag is None:
            raise HTTPException(status_code=404, detail="Tag 不存在")

        links = session.exec(select(DocumentTag).where(DocumentTag.tag_id == tag_id)).all()
        for link in links:
            session.delete(link)
        session.delete(tag)
        session.commit()
        return Response(status_code=204)
