"""单元测试：exclude_failed_points 软剔除失败点并重出底稿。

覆盖 Task 4：把某 run 下全部 failed 点标记为 excluded，立即重新出（完整）底稿。
"""

import json

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from govdoc.db.models import AuditPointRun, AuditRun, Document, WorkpaperDraft
from govdoc.pipelines.audit_tender import exclude_failed_points

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
        "verdict": {
            "verdict": "合规",
            "rationale": "r",
            "evidence_quotes": [],
            "suggestion": "",
        },
        "evidence_refs": [],
        "case_refs": [],
    },
    ensure_ascii=False,
)


@pytest.mark.asyncio
async def test_exclude_failed_reaches_draft_ready(tmp_path, monkeypatch):
    """剔除唯一失败点后，run 应进入 draft_ready 且生成一份新底稿。"""
    monkeypatch.setattr(
        "govdoc.pipelines.audit_tender.render_workpaper_docx",
        lambda *a, **k: "/tmp/w.docx",
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
            total_count=3,
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
        s.add(
            AuditPointRun(
                audit_run_id=run.id,
                checkpoint_final_id="b",
                status="completed",
                finding_json=FINDING,
            )
        )
        s.add(
            AuditPointRun(
                audit_run_id=run.id,
                checkpoint_final_id="c",
                status="failed",
            )
        )
        s.commit()
        n = await exclude_failed_points(run.id, s)
        s.refresh(run)
        assert n == 1
        assert run.status == "draft_ready"
        assert run.total_count == 2
        drafts = s.exec(select(WorkpaperDraft).where(WorkpaperDraft.audit_run_id == run.id)).all()
        assert len(drafts) == 1


@pytest.mark.asyncio
async def test_exclude_failed_rejects_unfinished_points(tmp_path, monkeypatch):
    """run 内仍有 pending/running 点时，剔除失败点应抛 ValueError 且不改任何状态。"""
    monkeypatch.setattr(
        "govdoc.pipelines.audit_tender.render_workpaper_docx",
        lambda *a, **k: "/tmp/w.docx",
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
            total_count=3,
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
        s.add(
            AuditPointRun(
                audit_run_id=run.id,
                checkpoint_final_id="b",
                status="failed",
            )
        )
        s.add(
            AuditPointRun(
                audit_run_id=run.id,
                checkpoint_final_id="c",
                status="pending",
            )
        )
        s.commit()
        with pytest.raises(ValueError):
            await exclude_failed_points(run.id, s)
        # 守卫触发后不得有任何副作用：失败点仍为 failed，run 状态不变，未生成底稿。
        s.refresh(run)
        assert run.status == "partial_ready"
        failed = s.exec(
            select(AuditPointRun).where(
                AuditPointRun.audit_run_id == run.id,
                AuditPointRun.status == "failed",
            )
        ).all()
        assert len(failed) == 1
        drafts = s.exec(select(WorkpaperDraft).where(WorkpaperDraft.audit_run_id == run.id)).all()
        assert len(drafts) == 0
