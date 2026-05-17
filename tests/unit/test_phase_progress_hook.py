"""验证 PhaseProgressHook 在 before_phase 时回写 current_phase 到 DB。

泛化后支持任意含 current_phase 字段的 SQLModel（AuditPointRun / ExtractRun）。
"""

from unittest.mock import MagicMock

from govdoc.db.models import AuditPointRun, ExtractRun
from govdoc.pipelines.phase_progress_hook import PhaseProgressHook


def _make_phase_context(phase: str) -> MagicMock:
    """构造 PhaseHookContext mock。"""
    ctx = MagicMock()
    ctx.phase = phase
    return ctx


def _make_session_factory(mock_run: MagicMock | None) -> MagicMock:
    """构造 session_factory mock，get() 返回指定对象。"""
    factory = MagicMock()
    session = MagicMock()
    factory.return_value.__enter__ = MagicMock(return_value=session)
    factory.return_value.__exit__ = MagicMock(return_value=False)
    session.get.return_value = mock_run
    return factory, session


def test_before_phase_updates_audit_point_run():
    """before_phase 应更新 AuditPointRun.current_phase。"""
    mock_run = MagicMock()
    mock_run.current_phase = None
    factory, session = _make_session_factory(mock_run)

    hook = PhaseProgressHook(run_id="pr-123", model_class=AuditPointRun, session_factory=factory)
    hook.before_phase(context=_make_phase_context("execute"))

    assert mock_run.current_phase == "execute"
    session.add.assert_called_once_with(mock_run)
    session.commit.assert_called_once()


def test_before_phase_updates_extract_run():
    """before_phase 同样适用于 ExtractRun。"""
    mock_run = MagicMock()
    mock_run.current_phase = None
    factory, session = _make_session_factory(mock_run)

    hook = PhaseProgressHook(run_id="er-456", model_class=ExtractRun, session_factory=factory)
    hook.before_phase(context=_make_phase_context("plan"))

    assert mock_run.current_phase == "plan"
    session.add.assert_called_once_with(mock_run)
    session.commit.assert_called_once()


def test_before_phase_skips_when_not_found():
    """run 不存在时不报错（容错）。"""
    factory, session = _make_session_factory(None)

    hook = PhaseProgressHook(run_id="pr-x", model_class=AuditPointRun, session_factory=factory)
    hook.before_phase(context=_make_phase_context("plan"))
    session.add.assert_not_called()
