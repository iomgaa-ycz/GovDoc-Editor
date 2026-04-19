"""P0 拆分后 helper 函数的单元测试。

与 tests/contract/ 层的集成测试 + golden 对比共同守住 I1（行为不变）。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from govdoc.pipelines.audit_tender import _index_tender_doc


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
