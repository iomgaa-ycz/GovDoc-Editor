"""DocumentStore 单元测试：验证 scrivai.to_markdown 统一转换路径。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from govdoc.storage.files import DocumentStore


@pytest.fixture()
def store(tmp_path: Path) -> DocumentStore:
    """创建使用临时目录的 DocumentStore。"""
    return DocumentStore(tmp_path)


@pytest.fixture()
def store_with_monkey(tmp_path: Path) -> DocumentStore:
    """创建使用 monkey 后端的 DocumentStore。"""
    return DocumentStore(tmp_path, ocr_backend="monkey")


class TestGetOrConvert:
    """get_or_convert 路由逻辑测试。"""

    def test_md_file_returns_directly(self, store: DocumentStore, tmp_path: Path) -> None:
        """已是 .md 的文件直接返回，不经过转换。"""
        md_file = tmp_path / "raw" / "test.md"
        md_file.parent.mkdir(parents=True, exist_ok=True)
        md_file.write_text("# Hello", encoding="utf-8")
        result = store.get_or_convert(md_file)
        assert result == md_file

    @pytest.mark.parametrize("suffix", [".docx", ".doc", ".pdf"])
    @patch("govdoc.storage.files._scrivai_to_markdown", return_value="# Converted content")
    def test_supported_formats_call_to_markdown(
        self, mock_to_md, suffix: str, store: DocumentStore, tmp_path: Path
    ) -> None:
        """docx/doc/pdf 三种格式均调用 scrivai.to_markdown。"""
        raw_file = tmp_path / "raw" / f"test{suffix}"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_bytes(b"fake content")

        result = store.get_or_convert(raw_file)

        mock_to_md.assert_called_once_with(raw_file, ocr_backend="glm")
        assert result.exists()
        assert result.read_text(encoding="utf-8") == "# Converted content"

    @patch("govdoc.storage.files._scrivai_to_markdown", return_value="# OCR result")
    def test_ocr_backend_passed_through(
        self, mock_to_md, store_with_monkey: DocumentStore, tmp_path: Path
    ) -> None:
        """自定义 ocr_backend 正确传递给 to_markdown。"""
        raw_file = tmp_path / "raw" / "test.pdf"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_bytes(b"fake pdf")

        store_with_monkey.get_or_convert(raw_file)

        mock_to_md.assert_called_once_with(raw_file, ocr_backend="monkey")

    @patch("govdoc.storage.files._scrivai_to_markdown", return_value="")
    def test_empty_result_raises(self, mock_to_md, store: DocumentStore, tmp_path: Path) -> None:
        """to_markdown 返回空字符串时抛 RuntimeError。"""
        raw_file = tmp_path / "raw" / "test.docx"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_bytes(b"fake docx")

        with pytest.raises(RuntimeError, match="返回空内容"):
            store.get_or_convert(raw_file)

    @patch("govdoc.storage.files._scrivai_to_markdown", side_effect=IOError("OCR unreachable"))
    def test_conversion_error_propagates(
        self, mock_to_md, store: DocumentStore, tmp_path: Path
    ) -> None:
        """scrivai 抛出的 IOError 原样上抛，不被吞掉。"""
        raw_file = tmp_path / "raw" / "test.pdf"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_bytes(b"fake pdf")

        with pytest.raises(IOError, match="OCR unreachable"):
            store.get_or_convert(raw_file)

    def test_unsupported_format_fallback_text(self, store: DocumentStore, tmp_path: Path) -> None:
        """非文档格式降级为纯文本提取。"""
        raw_file = tmp_path / "raw" / "data.csv"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_text("a,b,c\n1,2,3", encoding="utf-8")

        warnings_stack: list[str] = []
        result = store.get_or_convert(raw_file, warnings_stack=warnings_stack)

        assert result.exists()
        assert "a,b,c" in result.read_text(encoding="utf-8")
        assert any("不支持" in w for w in warnings_stack)

    def test_file_not_found_raises(self, store: DocumentStore) -> None:
        """原始文件不存在时抛 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError, match="原始文件不存在"):
            store.get_or_convert("/nonexistent/file.docx")


class TestSha256Cache:
    """SHA256 缓存机制测试。"""

    @patch("govdoc.storage.files._scrivai_to_markdown", return_value="# Cached")
    def test_second_call_uses_cache(self, mock_to_md, store: DocumentStore, tmp_path: Path) -> None:
        """相同内容的文件第二次调用不再触发 to_markdown。"""
        raw_file = tmp_path / "raw" / "test.docx"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_bytes(b"same content")

        store.get_or_convert(raw_file)
        store.get_or_convert(raw_file)

        assert mock_to_md.call_count == 1
