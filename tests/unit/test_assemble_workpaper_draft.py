import json
import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from govdoc.db.models import AuditRun, AuditPointRun, Document, WorkpaperDraft
from govdoc.pipelines.audit_tender import _assemble_workpaper_draft


def _draft_count(session, audit_run_id):
    return len(
        session.exec(
            select(WorkpaperDraft).where(WorkpaperDraft.audit_run_id == audit_run_id)
        ).all()
    )


FINDING = json.dumps(
    {
        "checkpoint": {
            "id": "c1",
            "category": "其他违法违规",
            "title": "t",
            "description": "d",
            "legal_basis": [],
            "severity": "major",
            "retrieval_hint": "h",
        },
        "verdict": {"verdict": "合规", "rationale": "r", "evidence_quotes": [], "suggestion": ""},
        "evidence_refs": [],
        "case_refs": [],
    },
    ensure_ascii=False,
)


def _mk(session, n_completed, n_failed, n_excluded):
    run = AuditRun(
        project_id="p1",
        main_document_id="d1",
        checkpoint_final_ids="[]",
        total_count=n_completed + n_failed + n_excluded,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    for i in range(n_completed):
        session.add(
            AuditPointRun(
                audit_run_id=run.id,
                checkpoint_final_id=f"c{i}",
                status="completed",
                finding_json=FINDING,
            )
        )
    for i in range(n_failed):
        session.add(
            AuditPointRun(audit_run_id=run.id, checkpoint_final_id=f"f{i}", status="failed")
        )
    for i in range(n_excluded):
        session.add(
            AuditPointRun(audit_run_id=run.id, checkpoint_final_id=f"e{i}", status="excluded")
        )
    session.commit()
    session.refresh(run)
    return run


@pytest.fixture
def session(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/t.db")
    SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(
            Document(
                id="d1",
                filename="t.pdf",
                file_type="pdf",
                file_size=1,
                sha256="x",
                raw_path="/tmp/t.pdf",
                markdown_path="/tmp/t.md",
                status="ready",
            )
        )
        s.commit()
        yield s


@pytest.mark.asyncio
async def test_all_completed_no_failed_draft_ready(session, monkeypatch):
    monkeypatch.setattr(
        "govdoc.pipelines.audit_tender.render_workpaper_docx", lambda *a, **k: "/tmp/wp.docx"
    )
    run = _mk(session, 3, 0, 0)
    doc = session.get(Document, "d1")
    await _assemble_workpaper_draft(run, session, doc, None)
    session.commit()
    assert run.status == "draft_ready"
    assert _draft_count(session, run.id) == 1


@pytest.mark.asyncio
async def test_some_failed_generates_partial_draft(session, monkeypatch):
    monkeypatch.setattr(
        "govdoc.pipelines.audit_tender.render_workpaper_docx", lambda *a, **k: "/tmp/wp.docx"
    )
    run = _mk(session, 2, 1, 0)
    doc = session.get(Document, "d1")
    await _assemble_workpaper_draft(run, session, doc, None)
    session.commit()
    assert run.status == "partial_ready"
    assert _draft_count(session, run.id) == 1


@pytest.mark.asyncio
async def test_excluded_not_counted_as_failed(session, monkeypatch):
    monkeypatch.setattr(
        "govdoc.pipelines.audit_tender.render_workpaper_docx", lambda *a, **k: "/tmp/wp.docx"
    )
    run = _mk(session, 2, 0, 2)
    doc = session.get(Document, "d1")
    await _assemble_workpaper_draft(run, session, doc, None)
    session.commit()
    assert run.status == "draft_ready"
    assert run.total_count == 2


@pytest.mark.asyncio
async def test_zero_completed_waiting_retry(session, monkeypatch):
    run = _mk(session, 0, 2, 0)
    doc = session.get(Document, "d1")
    await _assemble_workpaper_draft(run, session, doc, None)
    session.commit()
    assert run.status == "waiting_retry"
    assert _draft_count(session, run.id) == 0
