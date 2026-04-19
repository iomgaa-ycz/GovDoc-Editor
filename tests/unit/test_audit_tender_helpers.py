"""P0 拆分后 helper 函数的单元测试。

与 tests/contract/ 层的集成测试 + golden 对比共同守住 I1（行为不变）。
"""
from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlmodel import Session as SQLSession
from sqlmodel import SQLModel, create_engine, select

from govdoc.db.models import (
    AuditPointRun,
    AuditRun,
    CheckpointFinal,
    Project,
    TenderDoc,
    WorkpaperDraft,
)
from govdoc.pipelines.audit_tender import (
    _assemble_workpaper_draft,
    _cleanup_tender_collection,
    _index_tender_doc,
    _persist_point_result,
    _resolve_point_runs,
)


class _FakeTenderDoc:
    """最小化 TenderDoc 替身，只要求 audit_tender 内部拿来做 _ensure_tender_collection 的参数即可。"""

    markdown_path = "/tmp/fake.md"
    qmd_collection = None


def test_index_tender_doc_replay_returns_placeholder():
    """replay 模式返回占位名，不触发 qmd。"""
    audit_run = MagicMock(id="ar_test_123")
    tender_doc = _FakeTenderDoc()

    result = _index_tender_doc(audit_run, tender_doc, replay=True)

    assert result == "run_ar_test_123_tender"


def test_index_tender_doc_non_replay_calls_ensure_collection():
    """非 replay 模式调用 _ensure_tender_collection 并返回其值。"""
    audit_run = MagicMock(id="ar_prod_456")
    tender_doc = _FakeTenderDoc()

    with patch("govdoc.pipelines.audit_tender._ensure_tender_collection") as mock_ensure:
        mock_ensure.return_value = "real_collection_xyz"
        result = _index_tender_doc(audit_run, tender_doc, replay=False)

    assert result == "real_collection_xyz"
    mock_ensure.assert_called_once_with("ar_prod_456", tender_doc)


def test_index_tender_doc_non_replay_exception_returns_none():
    """非 replay 模式下 _ensure_tender_collection 抛异常时返回 None（降级）。"""
    audit_run = MagicMock(id="ar_fail_789")
    tender_doc = _FakeTenderDoc()

    with patch("govdoc.pipelines.audit_tender._ensure_tender_collection") as mock_ensure:
        mock_ensure.side_effect = RuntimeError("qmd unreachable")
        result = _index_tender_doc(audit_run, tender_doc, replay=False)

    assert result is None


def _make_point_run(run_id: str, audit_run_id: str, status: str = "pending"):
    """轻量 point_run 替身，足以让 helper 的集合过滤与 status 检查工作。"""
    pr = MagicMock()
    pr.id = run_id
    pr.audit_run_id = audit_run_id
    pr.status = status
    return pr


def _patched_session(point_runs_list):
    """patch Session.exec 返回给定的 point_runs list。"""
    session = MagicMock()
    exec_result = MagicMock()
    exec_result.all.return_value = point_runs_list
    session.exec.return_value = exec_result
    return session


def test_resolve_point_runs_no_filter_skips_completed():
    """None 过滤时返回所有非 completed 的 point_runs。"""
    audit_run = MagicMock(id="ar_1")
    prs = [
        _make_point_run("pr_0", "ar_1", "pending"),
        _make_point_run("pr_1", "ar_1", "pending"),
        _make_point_run("pr_2", "ar_1", "completed"),
    ]
    session = _patched_session(prs)

    total, to_run = _resolve_point_runs(session, audit_run, None)

    assert total == 3
    assert [pr.id for pr in to_run] == ["pr_0", "pr_1"]


def test_resolve_point_runs_with_whitelist_intersects_with_non_completed():
    """传入 point_run_ids 时只返回 intersect 且非 completed 的。"""
    audit_run = MagicMock(id="ar_1")
    prs = [
        _make_point_run("pr_0", "ar_1", "pending"),
        _make_point_run("pr_1", "ar_1", "pending"),
        _make_point_run("pr_2", "ar_1", "completed"),
    ]
    session = _patched_session(prs)

    total, to_run = _resolve_point_runs(session, audit_run, ["pr_0", "pr_2"])

    # pr_0 在白名单且非 completed → 保留
    # pr_2 在白名单但 completed → 跳过
    assert total == 3
    assert [pr.id for pr in to_run] == ["pr_0"]


def test_resolve_point_runs_empty_whitelist_returns_empty():
    """空白名单过滤掉所有 point_runs。"""
    audit_run = MagicMock(id="ar_1")
    prs = [
        _make_point_run("pr_0", "ar_1", "pending"),
    ]
    session = _patched_session(prs)

    total, to_run = _resolve_point_runs(session, audit_run, [])

    assert total == 1
    assert to_run == []


def test_resolve_point_runs_all_completed_returns_empty():
    """所有 point_run 都 completed 时，to_run 为空但 total 仍是原始总数。"""
    audit_run = MagicMock(id="ar_done")
    prs = [
        _make_point_run("pr_0", "ar_done", "completed"),
        _make_point_run("pr_1", "ar_done", "completed"),
    ]
    session = _patched_session(prs)

    total, to_run = _resolve_point_runs(session, audit_run, None)

    assert total == 2
    assert to_run == []


def test_resolve_point_runs_whitelist_with_unknown_ids_silently_skips():
    """白名单含不存在的 id 时静默跳过，不报错。"""
    audit_run = MagicMock(id="ar_ghost")
    prs = [
        _make_point_run("pr_real", "ar_ghost", "pending"),
    ]
    session = _patched_session(prs)

    total, to_run = _resolve_point_runs(session, audit_run, ["pr_real", "pr_does_not_exist"])

    assert total == 1
    assert [pr.id for pr in to_run] == ["pr_real"]


def test_run_single_point_is_async_and_has_expected_signature():
    """smoke: 确认 helper 存在、是 async、参数签名正确。

    详细行为由 tests/contract/test_pipeline_b_with_mocks.py + test_audit_golden.py 覆盖。
    """
    from govdoc.pipelines.audit_tender import _run_single_point

    assert inspect.iscoroutinefunction(_run_single_point)
    sig = inspect.signature(_run_single_point)
    assert list(sig.parameters.keys()) == [
        "point_run", "checkpoint", "tender_doc",
        "audit_run", "tender_collection", "manager", "store", "cfg",
        "repo_root", "replay_dir",
    ]


def _make_finding_payload(checkpoint_id: str) -> dict:
    """构造一个能被 GovFinding.model_validate 接受的最小 payload。"""
    return {
        "checkpoint": {
            "id": checkpoint_id,
            "category": "其他违法违规",
            "title": "测试审核点",
            "description": "desc",
            "legal_basis": [],
            "severity": "major",
            "retrieval_hint": "hint",
        },
        "verdict": {
            "verdict": "合规",
            "rationale": "ok",
            "evidence_quotes": [],
            "suggestion": "",
        },
        "evidence_refs": [],
        "case_refs": [],
    }


def test_persist_point_result_completed_with_matching_finding():
    """result.status == 'completed' + finding 匹配 → point_run 完整填充。"""
    point_run = MagicMock()
    point_run.finding_json = None

    finding_payload = _make_finding_payload("cp_test_001")
    result = MagicMock()
    result.status = "completed"
    result.final_output_path = Path("/tmp/nonexistent_govdoc_test.json")  # 不存在 → fallback
    result.final_output = {"findings": [finding_payload]}
    result.phase_results = {}

    workspace = MagicMock()
    checkpoint = MagicMock()
    checkpoint.id = "cp_test_001"
    manager = MagicMock()
    manager.archive.return_value = Path("/tmp/archive/success")

    _persist_point_result(point_run, result, workspace, checkpoint, manager)

    assert point_run.status == "completed"
    assert point_run.finding_json is not None
    assert point_run.workspace_archive_path == "/tmp/archive/success"
    manager.archive.assert_called_once_with(workspace, success=True)
    assert point_run.completed_at is not None


def test_persist_point_result_completed_fallback_to_first_finding():
    """result.status == 'completed' + finding id 不匹配但 findings 非空 → 取 findings[0]。"""
    point_run = MagicMock()
    point_run.finding_json = None

    finding_payload = _make_finding_payload("cp_other")
    result = MagicMock()
    result.status = "completed"
    result.final_output_path = Path("/tmp/nonexistent_govdoc_test.json")
    result.final_output = {"findings": [finding_payload]}
    result.phase_results = {}

    workspace = MagicMock()
    checkpoint = MagicMock()
    checkpoint.id = "cp_target"  # 与 finding 的 cp_other 不匹配
    manager = MagicMock()
    manager.archive.return_value = Path("/tmp/archive")

    _persist_point_result(point_run, result, workspace, checkpoint, manager)

    assert point_run.status == "completed"
    assert point_run.finding_json is not None  # fallback 生效
    # 验证确实取的是 findings[0]（checkpoint id 为 "cp_other"）
    assert '"cp_other"' in point_run.finding_json
    manager.archive.assert_called_once_with(workspace, success=True)


def test_persist_point_result_failed():
    """result.status != 'completed' → failed 分支。"""
    point_run = MagicMock()
    result = MagicMock()
    result.status = "failed"
    result.error = "something broke"
    result.phase_results = {}

    workspace = MagicMock()
    checkpoint = MagicMock()
    manager = MagicMock()
    manager.archive.return_value = Path("/tmp/archive/failed")

    _persist_point_result(point_run, result, workspace, checkpoint, manager)

    assert point_run.status == "failed"
    assert point_run.error == "something broke"
    assert point_run.workspace_failed_path == "/tmp/archive/failed"
    manager.archive.assert_called_once_with(workspace, success=False)


def test_persist_point_result_usage_json_set():
    """result 非 None → usage_json 被 dump_phase_usage 填充。"""
    point_run = MagicMock()
    result = MagicMock()
    result.status = "failed"
    result.error = "err"
    result.phase_results = {}  # 空 dict：dump_phase_usage({}) → "{}"

    workspace = MagicMock()
    checkpoint = MagicMock()
    manager = MagicMock()
    manager.archive.return_value = Path("/tmp/x")

    _persist_point_result(point_run, result, workspace, checkpoint, manager)

    # dump_phase_usage({}) 返回字符串 "{}"（证实"result 非 None 时无条件调用"的副作用路径）
    assert point_run.usage_json == "{}"


# --- Task 7: _cleanup_tender_collection ----------------------------------


def test_cleanup_tender_collection_replay_mode_noop():
    """replay=True 时不调 get_qmd，直接返回。"""
    with patch("govdoc.pipelines.audit_tender.get_qmd") as mock_get_qmd:
        _cleanup_tender_collection("run_abc_tender", replay=True)
    mock_get_qmd.assert_not_called()


def test_cleanup_tender_collection_none_id_noop():
    """collection_id=None 时直接返回，不调 get_qmd。"""
    with patch("govdoc.pipelines.audit_tender.get_qmd") as mock_get_qmd:
        _cleanup_tender_collection(None, replay=False)
    mock_get_qmd.assert_not_called()


def test_cleanup_tender_collection_empty_id_noop():
    """collection_id='' 时直接返回，不调 get_qmd。"""
    with patch("govdoc.pipelines.audit_tender.get_qmd") as mock_get_qmd:
        _cleanup_tender_collection("", replay=False)
    mock_get_qmd.assert_not_called()


def test_cleanup_tender_collection_production_mode_calls_delete():
    """非 replay + 有效 id → 调 get_qmd().delete_collection。"""
    mock_client = MagicMock()
    with patch("govdoc.pipelines.audit_tender.get_qmd", return_value=mock_client):
        _cleanup_tender_collection("run_abc_tender", replay=False)
    mock_client.delete_collection.assert_called_once_with("run_abc_tender")


def test_cleanup_tender_collection_swallows_exceptions():
    """delete_collection 抛异常时本函数静默吞掉，不向上传播。"""
    mock_client = MagicMock()
    mock_client.delete_collection.side_effect = RuntimeError("qmd down")
    with patch("govdoc.pipelines.audit_tender.get_qmd", return_value=mock_client):
        # 不应抛异常
        _cleanup_tender_collection("run_abc_tender", replay=False)
    mock_client.delete_collection.assert_called_once_with("run_abc_tender")


# --- Task 8: _assemble_workpaper_draft -----------------------------------


def _seed_audit(session: SQLSession) -> tuple[AuditRun, TenderDoc, CheckpointFinal]:
    """为 _assemble_workpaper_draft 测试 seed 最小数据。"""
    project = Project(name="test", created_by="tester")
    session.add(project)
    session.commit()
    session.refresh(project)

    tender_doc = TenderDoc(
        project_id=project.id,
        filename="t.docx",
        storage_path="/tmp/t.docx",
        markdown_path="/tmp/t.md",
        qmd_collection="c",
    )
    session.add(tender_doc)
    session.commit()
    session.refresh(tender_doc)

    cf = CheckpointFinal(
        payload_json=(
            '{"id":"cp_1","category":"其他违法违规","title":"t","description":"d",'
            '"legal_basis":[],"severity":"major","retrieval_hint":"h"}'
        ),
        approved_by="tester",
    )
    session.add(cf)
    session.commit()
    session.refresh(cf)

    audit_run = AuditRun(
        project_id=project.id,
        tender_doc_id=tender_doc.id,
        checkpoint_final_ids=f'["{cf.id}"]',
        total_count=1,
    )
    session.add(audit_run)
    session.commit()
    session.refresh(audit_run)

    return audit_run, tender_doc, cf


def _make_finding_json(checkpoint_id: str = "cp_1", verdict: str = "合规") -> str:
    """生成一份合法 GovFinding JSON。"""
    import json

    return json.dumps(
        {
            "checkpoint": {
                "id": checkpoint_id,
                "category": "其他违法违规",
                "title": "t",
                "description": "d",
                "legal_basis": [],
                "severity": "major",
                "retrieval_hint": "h",
            },
            "verdict": {
                "verdict": verdict,
                "rationale": "ok",
                "evidence_quotes": [],
                "suggestion": "",
            },
            "evidence_refs": [],
            "case_refs": [],
        },
        ensure_ascii=False,
    )


def test_assemble_workpaper_draft_all_completed_sets_draft_ready(tmp_path, monkeypatch):
    """所有 point_runs completed 且 finding_json 非空 → draft_ready + WorkpaperDraft 被 add。"""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with SQLSession(engine) as session:
        audit_run, tender_doc, cf = _seed_audit(session)
        pr = AuditPointRun(
            audit_run_id=audit_run.id,
            checkpoint_final_id=cf.id,
            status="completed",
            finding_json=_make_finding_json(),
        )
        session.add(pr)
        session.commit()

        # Mock render_workpaper_docx 避免真写 docx
        fake_path = tmp_path / "draft.docx"
        fake_path.touch()
        monkeypatch.setattr(
            "govdoc.pipelines.audit_tender.render_workpaper_docx",
            lambda *a, **kw: fake_path,
        )

        _assemble_workpaper_draft(audit_run, session, tender_doc, template_path=None)

        assert audit_run.status == "draft_ready"
        # WorkpaperDraft 未 commit 但已 add；帮 helper 提交（helper 不负责）
        session.commit()
        drafts = session.exec(
            select(WorkpaperDraft).where(WorkpaperDraft.audit_run_id == audit_run.id)
        ).all()
        assert len(drafts) == 1
        assert drafts[0].version == 1


def test_assemble_workpaper_draft_partial_completed_sets_partial_ready():
    """有 completed 和 failed → partial_ready，不生成 WorkpaperDraft。"""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with SQLSession(engine) as session:
        audit_run, tender_doc, cf = _seed_audit(session)
        # 1 个 completed + 1 个 failed
        pr1 = AuditPointRun(
            audit_run_id=audit_run.id,
            checkpoint_final_id=cf.id,
            status="completed",
            finding_json=_make_finding_json(),
        )
        pr2 = AuditPointRun(
            audit_run_id=audit_run.id,
            checkpoint_final_id=cf.id,
            status="failed",
            error="err",
        )
        session.add_all([pr1, pr2])
        session.commit()

        _assemble_workpaper_draft(audit_run, session, tender_doc, template_path=None)

        assert audit_run.status == "partial_ready"
        session.commit()
        drafts = session.exec(
            select(WorkpaperDraft).where(WorkpaperDraft.audit_run_id == audit_run.id)
        ).all()
        assert len(drafts) == 0


def test_assemble_workpaper_draft_no_completed_sets_waiting_retry():
    """无 completed 的 point_runs → waiting_retry。"""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with SQLSession(engine) as session:
        audit_run, tender_doc, cf = _seed_audit(session)
        # 全 failed 或全 pending（这里用 pending）
        pr = AuditPointRun(
            audit_run_id=audit_run.id,
            checkpoint_final_id=cf.id,
            status="pending",
        )
        session.add(pr)
        session.commit()

        _assemble_workpaper_draft(audit_run, session, tender_doc, template_path=None)

        assert audit_run.status == "waiting_retry"
        session.commit()
        drafts = session.exec(
            select(WorkpaperDraft).where(WorkpaperDraft.audit_run_id == audit_run.id)
        ).all()
        assert len(drafts) == 0
