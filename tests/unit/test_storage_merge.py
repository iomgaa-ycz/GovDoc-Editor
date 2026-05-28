"""验证 DocumentStore 使用 MarkdownConverter 单例。"""

from unittest.mock import patch

from govdoc.runtime import get_document_store
import govdoc.runtime as rt


@patch("govdoc.storage.files.MarkdownConverter")
def test_single_store_has_converter(mock_conv):
    """DocumentStore 持有 MarkdownConverter 实例。"""
    rt.get_document_store.cache_clear()
    try:
        store = get_document_store()
        assert hasattr(store, "_converter")
    finally:
        rt.get_document_store.cache_clear()


def test_no_compare_store():
    assert not hasattr(rt, "get_compare_document_store")
