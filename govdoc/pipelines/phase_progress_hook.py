"""PES before_phase hook——实时回写 AuditPointRun.current_phase 到 DB。"""

from __future__ import annotations

import logging
from typing import Any, Callable

from scrivai.pes.hooks import hookimpl

from govdoc.db.models import AuditPointRun

logger = logging.getLogger(__name__)


class PhaseProgressHook:
    """注册到 PES HookManager，在每个 phase 开始时更新 DB 中的 current_phase。"""

    def __init__(self, *, point_run_id: str, session_factory: Callable[..., Any]) -> None:
        self._point_run_id = point_run_id
        self._session_factory = session_factory

    @hookimpl
    def before_phase(self, context: Any) -> None:
        """PES phase 开始时回写 current_phase。"""
        phase = context.phase
        try:
            with self._session_factory() as session:
                point_run = session.get(AuditPointRun, self._point_run_id)
                if point_run is None:
                    logger.warning("PhaseProgressHook: AuditPointRun %s 不存在", self._point_run_id)
                    return
                point_run.current_phase = phase
                session.add(point_run)
                session.commit()
        except Exception:
            logger.exception("PhaseProgressHook: 更新 current_phase 失败")
