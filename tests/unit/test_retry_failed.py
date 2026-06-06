"""批量重试失败点 prepare_failed_points_retry 单元测试。"""

from sqlmodel import Session, SQLModel, create_engine

from govdoc.db.models import AuditPointRun, AuditRun
from govdoc.pipelines.audit_tender import prepare_failed_points_retry


def _session(tmp_path) -> Session:
    """构造独立的内存外 sqlite session。"""
    eng = create_engine(f"sqlite:///{tmp_path}/t.db")
    SQLModel.metadata.create_all(eng)
    return Session(eng)


def test_prepare_failed_resets_all_failed_to_pending(tmp_path):
    """所有 failed 点重置为 pending、清空 error，run 置 running。"""
    s = _session(tmp_path)
    run = AuditRun(
        project_id="p",
        main_document_id="d",
        checkpoint_final_ids="[]",
        status="partial_ready",
    )
    s.add(run)
    s.commit()
    s.refresh(run)
    s.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id="a", status="completed"))
    f1 = AuditPointRun(audit_run_id=run.id, checkpoint_final_id="b", status="failed", error="x")
    f2 = AuditPointRun(audit_run_id=run.id, checkpoint_final_id="c", status="failed", error="y")
    s.add(f1)
    s.add(f2)
    s.commit()
    ids = prepare_failed_points_retry(run.id, s)
    assert set(ids) == {f1.id, f2.id}
    s.refresh(f1)
    s.refresh(run)
    assert f1.status == "pending" and f1.error is None
    assert run.status == "running"
