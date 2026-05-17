"""验证 PhaseProgressHook 在 before_phase 时回写 current_phase 到 DB。"""

from unittest.mock import MagicMock

from govdoc.pipelines.phase_progress_hook import PhaseProgressHook


def _make_phase_context(phase: str) -> MagicMock:
    """构造 PhaseHookContext mock。"""
    ctx = MagicMock()
    ctx.phase = phase
    return ctx


def test_before_phase_updates_current_phase():
    """before_phase 应更新 AuditPointRun.current_phase。"""
    mock_session_factory = MagicMock()
    mock_session = MagicMock()
    mock_session_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_session_factory.return_value.__exit__ = MagicMock(return_value=False)
    mock_point_run = MagicMock()
    mock_point_run.current_phase = None
    mock_session.get.return_value = mock_point_run

    hook = PhaseProgressHook(point_run_id="pr-123", session_factory=mock_session_factory)
    hook.before_phase(context=_make_phase_context("execute"))

    assert mock_point_run.current_phase == "execute"
    mock_session.add.assert_called_once_with(mock_point_run)
    mock_session.commit.assert_called_once()


def test_before_phase_skips_when_not_found():
    """point_run 不存在时不报错（容错）。"""
    mock_session_factory = MagicMock()
    mock_session = MagicMock()
    mock_session_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_session_factory.return_value.__exit__ = MagicMock(return_value=False)
    mock_session.get.return_value = None

    hook = PhaseProgressHook(point_run_id="pr-x", session_factory=mock_session_factory)
    hook.before_phase(context=_make_phase_context("plan"))
    mock_session.add.assert_not_called()
