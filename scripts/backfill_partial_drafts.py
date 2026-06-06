"""一次性回填：给历史卡死的 partial_ready/waiting_retry 任务补生成（残缺）底稿。

用法（4090 服务器, govdoc-auditor-v3 环境，须先 export NO_PROXY + HF_HUB_OFFLINE=1）::

    python scripts/backfill_partial_drafts.py

对所有处于 ``partial_ready`` / ``waiting_retry`` 状态且至少有 1 个 completed 审核点的
``AuditRun`` 复用 ``_assemble_workpaper_draft`` 重新出稿（残缺也出稿），修正历史上因缺少
"有完成点即出稿"逻辑而卡死、无底稿的任务。
"""

from __future__ import annotations

import asyncio
import logging

from sqlmodel import Session, select

from govdoc.api.deps import get_db_session
from govdoc.db.models import AuditPointRun, AuditRun, Document
from govdoc.pipelines.audit_tender import _assemble_workpaper_draft

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill")


async def backfill(session: Session) -> int:
    """对所有 partial_ready/waiting_retry 且有 ≥1 完成点的任务重出底稿。

    Args:
        session: SQLModel session（用于查询与提交）。

    Returns:
        实际处理（重新出稿）的任务数量。
    """
    runs = session.exec(
        select(AuditRun).where(AuditRun.status.in_(["partial_ready", "waiting_retry"]))
    ).all()
    done = 0
    for run in runs:
        has_completed = session.exec(
            select(AuditPointRun).where(
                AuditPointRun.audit_run_id == run.id,
                AuditPointRun.status == "completed",
            )
        ).first()
        if not has_completed:
            logger.info("跳过（无完成点）: %s", run.id)
            continue
        tender = session.get(Document, run.main_document_id)
        await _assemble_workpaper_draft(run, session, tender, None)
        session.add(run)
        session.commit()
        logger.info("已回填 %s -> %s", run.id, run.status)
        done += 1
    return done


async def main() -> None:
    """入口：对生产库执行回填。"""
    with get_db_session() as s:
        s.connection().exec_driver_sql("PRAGMA busy_timeout=30000")
        n = await backfill(s)
        logger.info("回填完成，共处理 %d 个任务", n)


if __name__ == "__main__":
    asyncio.run(main())
