"""集成测试：部分失败审核任务 → 残缺底稿 → 跳过失败点 → 完整底稿。

端到端验证 Task 1/4 的核心闭环（用 MockPES replay + 单点失败注入，不调真 LLM）：

1. 构造含 3 个审核点的 AuditRun，其中 2 个点走真实 replay 完成、1 个点稳定失败；
2. ``run_audit(..., replay_dir=...)`` 跑完后 → ``partial_ready`` + 生成 1 份（残缺）底稿；
3. ``exclude_failed_points`` 软剔除失败点 → ``draft_ready`` + total 减少 + 新底稿版本。

失败点制造机制（见文件末 NOTES）：monkeypatch ``_run_single_point``，对指定
checkpoint id 抛 ``RuntimeError`` 模拟“agent 执行失败”，其余点委托原函数走真实 replay。
此路径命中 run_audit 主循环 ``except Exception`` 分支（与线上 agent 失败同构）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from scrivai import FakeTrajectoryStore, TempWorkspaceManager
from sqlmodel import Session, SQLModel, create_engine, select

import govdoc.pipelines.audit_tender as audit_tender
from govdoc.db.models import (
    AuditPointRun,
    AuditRun,
    CheckpointFinal,
    Document,
    WorkpaperDraft,
)
from govdoc.pipelines.audit_tender import exclude_failed_points, run_audit
from govdoc.schemas import GovCheckpoint

# 与 audit_case_01 replay fixture 中 output.json 的 finding checkpoint id 对齐，
# 便于 _persist_point_result 精确匹配（不匹配会 fallback 到 findings[0]，仍 completed）。
_COMPLETED_CP_IDS = ("cp_vendor_scope", "cp_local_service_bonus")
_FAILED_CP_ID = "cp_will_fail"


def _make_checkpoint(cp_id: str, title: str) -> GovCheckpoint:
    """构造一个最小可用的 GovCheckpoint。"""
    return GovCheckpoint(
        id=cp_id,
        category="不合理条件限制或排斥供应商",
        title=title,
        description="集成测试用审核点。",
        legal_basis=[],
        severity="major",
        retrieval_hint="检索关键词",
    )


def _seed_audit_run(session: Session, tender_md: Path) -> AuditRun:
    """落库：1 份招标文书 Document + 1 个 AuditRun + 3 个 AuditPointRun（含其 CheckpointFinal）。"""
    document = Document(
        filename="tender.md",
        file_type="md",
        file_size=tender_md.stat().st_size,
        sha256="integration-partial-failure",
        raw_path=str(tender_md),
        markdown_path=str(tender_md),
        status="ready",
    )
    session.add(document)
    session.flush()

    run = AuditRun(
        project_id="proj-partial",
        main_document_id=document.id,
        checkpoint_final_ids="[]",
        supplementary_doc_ids="[]",
        status="pending",
        total_count=0,
    )
    session.add(run)
    session.flush()

    specs = [
        (_COMPLETED_CP_IDS[0], "不得限定本地业绩"),
        (_COMPLETED_CP_IDS[1], "评分不得对本地服务网点倾向加分"),
        (_FAILED_CP_ID, "会失败的审核点"),
    ]
    for cp_id, title in specs:
        checkpoint = CheckpointFinal(
            payload_json=_make_checkpoint(cp_id, title).model_dump_json(),
            approved_by="tester",
        )
        session.add(checkpoint)
        session.flush()
        session.add(
            AuditPointRun(
                audit_run_id=run.id,
                checkpoint_final_id=checkpoint.id,
                status="pending",
            )
        )
    session.commit()
    session.refresh(run)
    return run


@pytest.mark.asyncio
async def test_partial_failure_then_exclude_reaches_full_draft(tmp_path, monkeypatch):
    """部分失败 → partial_ready + 残缺底稿；剔除失败点 → draft_ready + total 减少 + 新版本。"""
    repo_root = Path(__file__).resolve().parents[2]
    fixtures_root = repo_root / "tests" / "fixtures"
    replay_dir = fixtures_root / "mock_agent_trajectories" / "audit_case_01"
    # GOVDOC_FIXTURES 让 render_workpaper_docx 解析到 workpaper_template.docx。
    monkeypatch.setenv("GOVDOC_FIXTURES", str(fixtures_root))

    # 真实渲染底稿，但落到 tmp_path，避免污染 ./data。
    workpaper_out = tmp_path / "workpapers"

    def _fake_workpaper_dir(audit_run_id: str) -> Path:
        path = workpaper_out / audit_run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr("govdoc.workpaper_renderer.ensure_workpaper_dir", _fake_workpaper_dir)

    # 注入“单点失败”：对 _FAILED_CP_ID 抛异常，其余委托原函数走真实 replay。
    original_run_single_point = audit_tender._run_single_point

    async def _patched_run_single_point(point_run, checkpoint, tender_doc, **kwargs):
        if checkpoint.id == _FAILED_CP_ID:
            raise RuntimeError("模拟 agent 执行失败")
        return await original_run_single_point(point_run, checkpoint, tender_doc, **kwargs)

    monkeypatch.setattr(audit_tender, "_run_single_point", _patched_run_single_point)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        run = _seed_audit_run(session, fixtures_root / "tender_small.md")
        run_id = run.id

        # Phase 1：跑完含失败点的审核 → 应进入 partial_ready 并出残缺底稿。
        await run_audit(
            run_id,
            session,
            workspace_manager=TempWorkspaceManager(tmp_path / "workspaces"),
            trajectory_store=FakeTrajectoryStore(),
            replay_dir=replay_dir,
            project_root=repo_root,
        )
        session.refresh(run)

        assert run.status == "partial_ready"
        assert run.total_count == 3

        completed = session.exec(
            select(AuditPointRun).where(
                AuditPointRun.audit_run_id == run_id,
                AuditPointRun.status == "completed",
            )
        ).all()
        failed = session.exec(
            select(AuditPointRun).where(
                AuditPointRun.audit_run_id == run_id,
                AuditPointRun.status == "failed",
            )
        ).all()
        assert len(completed) == 2
        assert len(failed) == 1

        drafts_v1 = session.exec(
            select(WorkpaperDraft).where(WorkpaperDraft.audit_run_id == run_id)
        ).all()
        assert len(drafts_v1) == 1
        assert Path(drafts_v1[0].docx_path).exists()

        # Phase 2：剔除失败点 → draft_ready + total 减少 + 新底稿版本。
        excluded = await exclude_failed_points(run_id, session)
        session.refresh(run)

        assert excluded == 1
        assert run.status == "draft_ready"
        assert run.total_count == 2

        # 失败点被标记为 excluded（既不计失败也不计总数）。
        still_failed = session.exec(
            select(AuditPointRun).where(
                AuditPointRun.audit_run_id == run_id,
                AuditPointRun.status == "failed",
            )
        ).all()
        assert len(still_failed) == 0

        drafts_v2 = session.exec(
            select(WorkpaperDraft).where(WorkpaperDraft.audit_run_id == run_id)
        ).all()
        assert len(drafts_v2) == 2
        assert max(d.version for d in drafts_v2) == 2
