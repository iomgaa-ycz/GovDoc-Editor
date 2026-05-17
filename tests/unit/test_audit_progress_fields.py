"""验证 AuditPointRun 支持 started_at 和 current_phase 字段。"""

from datetime import datetime

from govdoc.db.models import AuditPointRun


def test_audit_point_run_has_started_at():
    """started_at 字段默认 None，可赋值为 datetime。"""
    pr = AuditPointRun(
        audit_run_id="run-1",
        checkpoint_final_id="cp-1",
    )
    assert pr.started_at is None
    pr.started_at = datetime(2026, 5, 17, 14, 30, 0)
    assert pr.started_at == datetime(2026, 5, 17, 14, 30, 0)


def test_audit_point_run_has_current_phase():
    """current_phase 字段默认 None，可赋值为 plan/execute/summarize。"""
    pr = AuditPointRun(
        audit_run_id="run-1",
        checkpoint_final_id="cp-1",
    )
    assert pr.current_phase is None
    pr.current_phase = "plan"
    assert pr.current_phase == "plan"
    pr.current_phase = "execute"
    assert pr.current_phase == "execute"
    pr.current_phase = "summarize"
    assert pr.current_phase == "summarize"
