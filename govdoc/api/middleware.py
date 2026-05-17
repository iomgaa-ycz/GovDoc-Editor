# govdoc/api/middleware.py
"""审计日志工具函数——所有 API 写操作通过此模块记录。"""

from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session

from govdoc.db.models import ActivityLog


def log_activity(
    session: Session,
    *,
    actor: str,
    action: str,
    target_type: str,
    target_id: str,
    before: Any = None,
    after: Any = None,
    request_id: str | None = None,
) -> None:
    """记录一条操作审计日志。

    参数:
        session: DB session（调用方负责 commit）。
        actor: 操作人标识。
        action: 操作类型（如 upload_tender_doc / update_checkpoint）。
        target_type: 目标实体类型名。
        target_id: 目标实体 ID。
        before: 修改前的状态快照（dict 或 None）。
        after: 修改后的状态快照（dict 或 None）。
        request_id: 可选的请求追踪 ID。
    """
    session.add(
        ActivityLog(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before_json=json.dumps(before, ensure_ascii=False) if before else None,
            after_json=json.dumps(after, ensure_ascii=False) if after else None,
            request_id=request_id,
        )
    )
