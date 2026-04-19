"""P0 拆分后 helper 函数的单元测试。

与 tests/contract/ 层的集成测试 + golden 对比共同守住 I1（行为不变）。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from govdoc.pipelines.audit_tender import _index_tender_doc, _resolve_point_runs


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
