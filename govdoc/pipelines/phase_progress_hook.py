"""PES before_phase hook——实时回写 current_phase 到 DB。

支持 AuditPointRun 和 ExtractRun（任何含 current_phase 字段的 SQLModel）。
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from scrivai.pes.hooks import hookimpl
from sqlmodel import SQLModel

logger = logging.getLogger(__name__)


class PhaseProgressHook:
    """注册到 PES HookManager，在每个 phase 开始时更新 DB 中的 current_phase。"""

    def __init__(
        self,
        *,
        run_id: str,
        model_class: type[SQLModel],
        session_factory: Callable[..., Any],
    ) -> None:
        self._run_id = run_id
        self._model_class = model_class
        self._session_factory = session_factory

    @hookimpl
    def before_phase(self, context: Any) -> None:
        """PES phase 开始时回写 current_phase。"""
        phase = context.phase
        try:
            with self._session_factory() as session:
                run = session.get(self._model_class, self._run_id)
                if run is None:
                    logger.warning(
                        "PhaseProgressHook: %s %s 不存在",
                        self._model_class.__name__,
                        self._run_id,
                    )
                    return
                run.current_phase = phase
                session.add(run)
                session.commit()
        except Exception:
            logger.exception("PhaseProgressHook: 更新 current_phase 失败")
