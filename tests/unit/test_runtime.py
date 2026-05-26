"""get_compare_document_store 单元测试。"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from govdoc.runtime import get_compare_document_store


class TestGetCompareDocumentStore:
    """验证对比模块 DocumentStore 工厂。"""

    def setup_method(self) -> None:
        get_compare_document_store.cache_clear()

    @patch("govdoc.runtime.get_config")
    def test_returns_store_with_mineru_backend(self, mock_get_config: MagicMock, tmp_path: Path) -> None:
        """get_compare_document_store 返回 ocr_backend=mineru 的 DocumentStore。"""
        cfg = MagicMock()
        cfg.storage_root = tmp_path
        cfg.compare.ocr_backend = "mineru"
        mock_get_config.return_value = cfg

        store = get_compare_document_store()

        assert store._ocr_backend == "mineru"

    @patch("govdoc.runtime.get_config")
    def test_storage_root_is_compare_prepared(self, mock_get_config: MagicMock, tmp_path: Path) -> None:
        """get_compare_document_store 使用 storage_root / compare_prepared 子目录。"""
        cfg = MagicMock()
        cfg.storage_root = tmp_path
        cfg.compare.ocr_backend = "mineru"
        mock_get_config.return_value = cfg

        store = get_compare_document_store()

        assert store._root == tmp_path / "compare_prepared"

    @patch("govdoc.runtime.get_config")
    def test_is_independent_from_main_store(self, mock_get_config: MagicMock, tmp_path: Path) -> None:
        """compare store 与主 store 是不同实例。"""
        from govdoc.runtime import get_document_store

        get_document_store.cache_clear()

        cfg = MagicMock()
        cfg.storage_root = tmp_path
        cfg.app.ocr_backend = "glm"
        cfg.compare.ocr_backend = "mineru"
        mock_get_config.return_value = cfg

        main_store = get_document_store()
        compare_store = get_compare_document_store()

        assert main_store is not compare_store
        assert main_store._ocr_backend == "glm"
        assert compare_store._ocr_backend == "mineru"
        assert main_store._root != compare_store._root
