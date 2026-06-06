"""单测：历史卡死任务残缺底稿回填脚本 ``scripts.backfill_partial_drafts``。"""

import json

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from govdoc.db.models import AuditPointRun, AuditRun, Document, WorkpaperDraft
from scripts.backfill_partial_drafts import backfill

FINDING = json.dumps(
    {
        "checkpoint": {
            "id": "c",
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


@pytest.mark.asyncio
async def test_backfill_generates_draft_for_partial(tmp_path, monkeypatch):
    """partial_ready 且有完成点的任务应被回填出一份 WorkpaperDraft。"""
    monkeypatch.setattr(
        "govdoc.pipelines.audit_tender.render_workpaper_docx", lambda *a, **k: "/tmp/w.docx"
    )
    eng = create_engine(f"sqlite:///{tmp_path}/t.db")
    SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(
            Document(
                id="d",
                filename="t.pdf",
                file_type="pdf",
                file_size=1,
                sha256="x",
                raw_path="/tmp/t.pdf",
                markdown_path="/tmp/t.md",
                status="ready",
            )
        )
        run = AuditRun(
            project_id="p",
            main_document_id="d",
            checkpoint_final_ids="[]",
            status="partial_ready",
            total_count=2,
        )
        s.add(run)
        s.commit()
        s.refresh(run)
        s.add(
            AuditPointRun(
                audit_run_id=run.id,
                checkpoint_final_id="a",
                status="completed",
                finding_json=FINDING,
            )
        )
        s.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id="b", status="failed"))
        s.commit()
        n = await backfill(s)
        assert n == 1
        assert (
            len(s.exec(select(WorkpaperDraft).where(WorkpaperDraft.audit_run_id == run.id)).all())
            == 1
        )
