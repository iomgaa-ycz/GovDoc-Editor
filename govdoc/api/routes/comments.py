"""Comments routes — 批注/评论 CRUD。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import select

from govdoc.api.deps import get_current_user, get_db_session
from govdoc.api.middleware import log_activity
from govdoc.db.models import Comment, User
from govdoc.schemas.common import GovDocModel

router = APIRouter(prefix="/api/v1/comments", tags=["comments"])


class CreateCommentRequest(GovDocModel):
    """创建评论请求。"""

    target_type: str
    target_id: str
    author: str
    text: str


@router.post("", status_code=201)
async def create_comment(
    payload: CreateCommentRequest,
    current_user: User = Depends(get_current_user),
):
    """创建一条评论/批注。"""
    with get_db_session() as session:
        comment = Comment(
            target_type=payload.target_type,
            target_id=payload.target_id,
            author=current_user.username,
            text=payload.text,
        )
        session.add(comment)
        log_activity(
            session,
            actor=current_user.username,
            action="create_comment",
            target_type=payload.target_type,
            target_id=payload.target_id,
            after={"text": payload.text},
        )
        session.commit()
        session.refresh(comment)
        return {
            "id": comment.id,
            "target_type": comment.target_type,
            "target_id": comment.target_id,
            "author": comment.author,
            "text": comment.text,
            "created_at": str(comment.created_at),
        }


@router.get("")
async def list_comments(target_type: str | None = None, target_id: str | None = None):
    """列出评论，可按 target_type 和 target_id 过滤。"""
    with get_db_session() as session:
        stmt = select(Comment).order_by(Comment.created_at.desc())
        if target_type:
            stmt = stmt.where(Comment.target_type == target_type)
        if target_id:
            stmt = stmt.where(Comment.target_id == target_id)
        comments = session.exec(stmt).all()
        return [
            {
                "id": c.id,
                "target_type": c.target_type,
                "target_id": c.target_id,
                "author": c.author,
                "text": c.text,
                "created_at": str(c.created_at),
            }
            for c in comments
        ]


@router.delete("/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: str,
    current_user: User = Depends(get_current_user),
) -> Response:
    """删除一条评论。"""
    with get_db_session() as session:
        comment = session.get(Comment, comment_id)
        if comment is None:
            raise HTTPException(status_code=404, detail="Comment 不存在")
        log_activity(
            session,
            actor=current_user.username,
            action="delete_comment",
            target_type=comment.target_type,
            target_id=comment.target_id,
            before={"text": comment.text},
        )
        session.delete(comment)
        session.commit()
        return Response(status_code=204)
