"""验证 DocumentStore 合并为单一 GLM 实例。"""

from govdoc.runtime import get_document_store
import govdoc.runtime as rt


def test_single_store_uses_glm():
    store = get_document_store()
    assert store._ocr_backend == "glm"


def test_no_compare_store():
    assert not hasattr(rt, "get_compare_document_store")
