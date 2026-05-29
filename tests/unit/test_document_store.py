"""DocumentStore 单元测试：验证 MarkdownConverter 集成路径。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from govdoc.storage.files import DocumentStore


@pytest.fixture()
def store(tmp_path: Path) -> DocumentStore:
    """创建使用临时目录的 DocumentStore（mock MarkdownConverter）。"""
    with patch("govdoc.storage.files.MarkdownConverter") as MockConverter:
        MockConverter.return_value = MagicMock()
        s = DocumentStore(tmp_path)
        yield s


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
    def test_supported_formats_call_converter(
        self, suffix: str, store: DocumentStore, tmp_path: Path
    ) -> None:
        """docx/doc/pdf 三种格式均调用 MarkdownConverter.convert。"""
        store._converter.convert.return_value = "# Converted content"

        raw_file = tmp_path / "raw" / f"test{suffix}"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_bytes(b"fake content")

        result = store.get_or_convert(raw_file)

        store._converter.convert.assert_called_once_with(raw_file)
        assert result.exists()
        assert result.read_text(encoding="utf-8") == "# Converted content"

    def test_empty_result_raises(self, store: DocumentStore, tmp_path: Path) -> None:
        """MarkdownConverter.convert 返回空字符串时抛 RuntimeError。"""
        store._converter.convert.return_value = ""

        raw_file = tmp_path / "raw" / "test.docx"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_bytes(b"fake docx")

        with pytest.raises(RuntimeError, match="返回空内容"):
            store.get_or_convert(raw_file)

    def test_conversion_error_propagates(self, store: DocumentStore, tmp_path: Path) -> None:
        """MarkdownConverter 抛出的 OSError 原样上抛，不被吞掉。"""
        store._converter.convert.side_effect = OSError("OCR unreachable")

        raw_file = tmp_path / "raw" / "test.pdf"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_bytes(b"fake pdf")

        with pytest.raises(OSError, match="OCR unreachable"):
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

    def test_second_call_uses_cache(self, store: DocumentStore, tmp_path: Path) -> None:
        """相同内容的文件第二次调用不再触发 converter.convert。"""
        store._converter.convert.return_value = "# Cached"

        raw_file = tmp_path / "raw" / "test.docx"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_bytes(b"same content")

        store.get_or_convert(raw_file)
        store.get_or_convert(raw_file)

        assert store._converter.convert.call_count == 1


class TestConverterIntegration:
    """验证 MarkdownConverter 构造与生命周期。"""

    @patch("govdoc.storage.files.MarkdownConverter")
    def test_converter_receives_config_kwargs(
        self, MockConverter: MagicMock, tmp_path: Path
    ) -> None:
        """converter_kwargs 正确透传给 MarkdownConverter 构造函数。"""
        kwargs = {
            "mode": "api",
            "dispatch": "fallback",
            "monkey_endpoints": ["http://localhost:7866"],
        }
        DocumentStore(tmp_path, converter_kwargs=kwargs)

        MockConverter.assert_called_once_with(**kwargs)

    @patch("govdoc.storage.files.MarkdownConverter")
    def test_default_converter_no_kwargs(self, MockConverter: MagicMock, tmp_path: Path) -> None:
        """不传 converter_kwargs 时 MarkdownConverter 以空参构造。"""
        DocumentStore(tmp_path)

        MockConverter.assert_called_once_with()

    @patch("govdoc.storage.files.MarkdownConverter")
    def test_close_delegates_to_converter(self, MockConverter: MagicMock, tmp_path: Path) -> None:
        """close() 委托给 MarkdownConverter.close()。"""
        store = DocumentStore(tmp_path)
        store.close()

        MockConverter.return_value.close.assert_called_once()
