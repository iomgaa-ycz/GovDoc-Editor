from sqlmodel import Session, SQLModel, create_engine
from govdoc.db.models import AuditRun, AuditPointRun
from govdoc.pipelines.audit_tender import _resolve_point_runs


def _session(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/t.db")
    SQLModel.metadata.create_all(eng)
    return Session(eng)


def test_resolve_skips_completed_and_excluded(tmp_path):
    s = _session(tmp_path)
    run = AuditRun(project_id="p", main_document_id="d", checkpoint_final_ids="[]")
    s.add(run)
    s.commit()
    s.refresh(run)
    s.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id="a", status="completed"))
    s.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id="b", status="excluded"))
    s.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id="c", status="failed"))
    s.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id="e", status="pending"))
    s.commit()
    total, to_run = _resolve_point_runs(s, run, None)
    assert total == 3  # 4 - 1 excluded
    assert {pr.status for pr in to_run} == {"failed", "pending"}  # 跳过 completed+excluded
