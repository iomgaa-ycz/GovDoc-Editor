import asyncio
import json
from pathlib import Path

from scrivai import FakeTrajectoryStore, TempWorkspaceManager, TrajectoryStore
from sqlmodel import Session, SQLModel, create_engine, select

from govdoc.db.models import (
    AuditPointRun,
    AuditRun,
    CheckpointFinal,
    Project,
    TenderDoc,
    WorkpaperDraft,
)
from govdoc.pipelines.audit_tender import retry_point_run, run_audit
from govdoc.schemas import GovFinding, VerdictValue


def _write_test_config(path: Path) -> Path:
    config_path = path / "govdoc-test.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                f"  storage_root: {path / 'storage'}",
                f"  database_url: sqlite:///{path / 'app.sqlite'}",
                "model:",
                "  model: mock-model",
                "  base_url: https://example.invalid",
                "  api_key: test-key",
                "  fallback_model: mock-fallback",
                "qmd:",
                f"  db_path: {path / 'qmd.sqlite'}",
                "workspace:",
                f"  workspaces_root: {path / 'govdoc-workspaces'}",
                f"  archives_root: {path / 'govdoc-archives'}",
                "  cleanup_days: 30",
                "evolution:",
                "  enabled: false",
                "  proposer_model: mock-model",
                "  frontier_size: 5",
                f"  eval_dataset_path: {path / 'eval' / 'checkpoints_golden.json'}",
            ]
        ),
        encoding="utf-8",
    )
    return config_path


def test_pipeline_b_with_mock_pes_replay(monkeypatch, tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    fixtures_root = repo_root / "tests" / "fixtures"
    monkeypatch.setenv("GOVDOC_FIXTURES", str(fixtures_root))
    monkeypatch.setenv("GOVDOC_CONFIG_PATH", str(_write_test_config(tmp_path)))

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    checkpoints_payload = json.loads(
        (fixtures_root / "checkpoints_golden.json").read_text(encoding="utf-8")
    )["checkpoints"]
    expected_workpaper = json.loads(
        (fixtures_root / "workpaper_expected.json").read_text(encoding="utf-8")
    )

    with Session(engine) as session:
        project = Project(name="示例项目", created_by="tester")
        session.add(project)
        session.commit()
        session.refresh(project)

        tender_doc = TenderDoc(
            project_id=project.id,
            filename="tender_small.docx",
            storage_path="tests/fixtures/tender_small.docx",
            markdown_path=str(fixtures_root / "tender_small.md"),
            qmd_collection="test-tender-collection",
        )
        session.add(tender_doc)
        session.commit()
        session.refresh(tender_doc)

        final_ids: list[str] = []
        for payload in checkpoints_payload:
            checkpoint_final = CheckpointFinal(
                payload_json=json.dumps(payload, ensure_ascii=False),
                approved_by="tester",
            )
            session.add(checkpoint_final)
            session.commit()
            session.refresh(checkpoint_final)
            final_ids.append(checkpoint_final.id)

        audit_run = AuditRun(
            project_id=project.id,
            tender_doc_id=tender_doc.id,
            checkpoint_final_ids=json.dumps(final_ids, ensure_ascii=False),
            total_count=len(final_ids),
        )
        session.add(audit_run)
        session.commit()
        session.refresh(audit_run)

        # 预创建 AuditPointRun（与 API POST /audit/runs 行为一致）
        for cp_id in final_ids:
            point_run = AuditPointRun(
                audit_run_id=audit_run.id,
                checkpoint_final_id=cp_id,
            )
            session.add(point_run)
        session.commit()

        result = asyncio.run(
            run_audit(
                audit_run.id,
                session,
                workspace_manager=TempWorkspaceManager(tmp_path / "workspaces"),
                trajectory_store=FakeTrajectoryStore(),
                replay_dir=fixtures_root / "mock_agent_trajectories" / "audit_case_01",
                project_root=repo_root,
                template_path=fixtures_root / "workpaper_template.docx",
            )
        )

        drafts = session.exec(
            select(WorkpaperDraft).where(WorkpaperDraft.audit_run_id == audit_run.id)
        ).all()

        point_runs = session.exec(
            select(AuditPointRun).where(AuditPointRun.audit_run_id == audit_run.id)
        ).all()

    assert result.status == "draft_ready"
    assert result.total_count == len(final_ids)
    assert result.processed_count == len(final_ids)
    assert len(drafts) == 1
    assert Path(drafts[0].docx_path).is_file()

    # 验证 AuditPointRun 逐点完成
    assert all(pr.status == "completed" for pr in point_runs)
    assert all(pr.finding_json is not None for pr in point_runs)
    assert all(pr.workspace_archive_path is not None for pr in point_runs)

    workpaper = json.loads(drafts[0].workpaper_json)
    assert workpaper["tender_doc_path"] == expected_workpaper["tender_doc_path"]
    assert workpaper["summary"]  # summary is non-empty
    assert [item["checkpoint"]["id"] for item in workpaper["findings"]] == [
        item["checkpoint"]["id"] for item in expected_workpaper["findings"]
    ]

    # === Guardrail assertions for P0 run_audit refactor ===
    # I1: behavior-preservation checks. Any helper extraction must preserve these.

    # 1. AuditRun 最终 status 在合法集合内
    assert result.status in {"draft_ready", "partial_ready", "waiting_retry", "failed"}, (
        f"unexpected audit_run.status: {result.status}"
    )

    # 2. run_audit 返回后每个 point_run 必在终态（run_audit 保证 pending/running 不会遗留）
    for pr in point_runs:
        assert pr.status in {"completed", "failed"}, f"point_run {pr.id} 停留在非终态: {pr.status}"

    # 3. 每个 completed point_run 的 finding_json 可解析为 GovFinding，且 verdict 合法
    for pr in point_runs:
        if pr.status == "completed":
            assert pr.finding_json and pr.finding_json.strip(), (
                f"completed point_run {pr.id} has empty finding_json"
            )
            finding = GovFinding.model_validate_json(pr.finding_json)
            assert finding.verdict.verdict in {v.value for v in VerdictValue}, (
                f"point_run {pr.id} verdict 不在合法集合: {finding.verdict.verdict!r}"
            )

    # 4. draft_ready 时 WorkpaperDraft 的 docx 文件必须实际存在
    if result.status == "draft_ready":
        assert len(drafts) >= 1, "draft_ready but no WorkpaperDraft"
        for d in drafts:
            assert d.docx_path and Path(d.docx_path).is_file(), (
                f"WorkpaperDraft.docx_path 文件不存在: {d.docx_path}"
            )

    # 5. trajectory 落盘：FakeTrajectoryStore 接口可能没有 list/get，
    #    L144 原断言 pr.workspace_archive_path is not None 已提供等价保证，本条留注释不强断言

    # 6. tender_collection 清理：语义由拆分出的 helper 单测 (test_cleanup_tender_collection) 保证，此处不重复


def test_retry_point_run_reuses_same_run_id_after_cleanup(monkeypatch, tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    fixtures_root = repo_root / "tests" / "fixtures"
    monkeypatch.setenv("GOVDOC_FIXTURES", str(fixtures_root))
    monkeypatch.setenv("GOVDOC_CONFIG_PATH", str(_write_test_config(tmp_path)))

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    checkpoints_payload = json.loads(
        (fixtures_root / "checkpoints_golden.json").read_text(encoding="utf-8")
    )["checkpoints"]

    workspace_manager = TempWorkspaceManager(tmp_path / "retry")
    trajectory_store = TrajectoryStore(tmp_path / "retry-trajectories.sqlite")

    with Session(engine) as session:
        project = Project(name="重试项目", created_by="tester")
        session.add(project)
        session.commit()
        session.refresh(project)

        tender_doc = TenderDoc(
            project_id=project.id,
            filename="tender_small.docx",
            storage_path="tests/fixtures/tender_small.docx",
            markdown_path=str(fixtures_root / "tender_small.md"),
            qmd_collection="test-tender-collection",
        )
        session.add(tender_doc)
        session.commit()
        session.refresh(tender_doc)

        final_ids: list[str] = []
        for payload in checkpoints_payload[:2]:
            checkpoint_final = CheckpointFinal(
                payload_json=json.dumps(payload, ensure_ascii=False),
                approved_by="tester",
            )
            session.add(checkpoint_final)
            session.commit()
            session.refresh(checkpoint_final)
            final_ids.append(checkpoint_final.id)

        audit_run = AuditRun(
            project_id=project.id,
            tender_doc_id=tender_doc.id,
            checkpoint_final_ids=json.dumps(final_ids, ensure_ascii=False),
            total_count=len(final_ids),
            status="waiting_retry",
        )
        session.add(audit_run)
        session.commit()
        session.refresh(audit_run)

        for cp_id in final_ids:
            point_run = AuditPointRun(
                audit_run_id=audit_run.id,
                checkpoint_final_id=cp_id,
                status="failed",
                error="上一次执行失败",
                workspace_failed_path="stale-failed-workspace",
            )
            session.add(point_run)
        session.commit()

        point_runs = session.exec(
            select(AuditPointRun)
            .where(AuditPointRun.audit_run_id == audit_run.id)
            .order_by(AuditPointRun.created_at, AuditPointRun.id)
        ).all()
        retry_target, untouched_target = point_runs

        stale_workspace = workspace_manager.workspaces_root / retry_target.id
        (stale_workspace / "working").mkdir(parents=True, exist_ok=True)
        (stale_workspace / ".failed").touch()

        trajectory_store.start_run(
            run_id=retry_target.id,
            pes_name="gov-auditor",
            model_name="mock-model",
            provider="mock",
            sdk_version="test",
            skills_git_hash=None,
            agents_git_hash=None,
            skills_is_dirty=False,
            task_prompt="previous failed attempt",
            runtime_context={"source": "retry-test"},
        )
        phase_id = trajectory_store.record_phase_start(
            retry_target.id,
            phase_name="plan",
            phase_order=0,
            attempt_no=0,
        )
        trajectory_store.record_phase_end(
            phase_id,
            prompt="old prompt",
            response_text="old response",
            produced_files=["plan.md"],
            usage={"input_tokens": 1, "output_tokens": 1},
            error="old error",
            error_type="sdk_other",
            is_retryable=False,
        )
        trajectory_store.finalize_run(
            retry_target.id,
            status="failed",
            final_output=None,
            workspace_archive_path=None,
            error="old error",
            error_type="sdk_other",
        )

        result = asyncio.run(
            retry_point_run(
                retry_target.id,
                session,
                workspace_manager=workspace_manager,
                trajectory_store=trajectory_store,
                replay_dir=fixtures_root / "mock_agent_trajectories" / "audit_case_01",
                project_root=repo_root,
                template_path=fixtures_root / "workpaper_template.docx",
            )
        )

        session.refresh(audit_run)
        session.refresh(untouched_target)

    assert result is not None
    assert result.status == "completed"
    assert result.error is None
    assert result.finding_json is not None
    assert result.workspace_archive_path is not None
    assert result.workspace_failed_path is None
    assert not stale_workspace.exists()

    assert trajectory_store.get_run(retry_target.id) is None
    trajectory_store.start_run(
        run_id=retry_target.id,
        pes_name="gov-auditor",
        model_name="mock-model",
        provider="mock",
        sdk_version="test",
        skills_git_hash=None,
        agents_git_hash=None,
        skills_is_dirty=False,
        task_prompt="fresh retry attempt",
        runtime_context={"source": "post-retry-check"},
    )
    assert trajectory_store.get_run(retry_target.id) is not None

    assert audit_run.status == "partial_ready"
    assert audit_run.processed_count == 1
    assert untouched_target.status == "failed"
    assert untouched_target.error == "上一次执行失败"
