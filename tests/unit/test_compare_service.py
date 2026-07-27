"""文档对比服务层测试。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from docx import Document

from govdoc.compare.compare import find_nfile_exact_matches
from govdoc.compare.service import (
    _extract_pdf_paragraphs,
    create_compare_bundle,
    create_compare_bundle_from_bytes,
    get_compare_download,
)
from govdoc.schemas.compare import CompareResponse


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    """按给定段落写入 DOCX 测试文件。"""
    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    document.save(path)


def test_match_algorithms_find_nfile_exact_matches() -> None:
    """底层算法应识别 N 文件间完全相同文本。"""
    exact_matches = find_nfile_exact_matches(
        {0: ["甲", "乙", "甲", "丙"], 1: ["乙", "甲", "丁"]},
    )

    by_text = {match.text: match for match in exact_matches}
    assert "甲" in by_text
    assert "乙" in by_text
    assert by_text["甲"].file_positions == {0: [1, 3], 1: [2]}
    assert by_text["乙"].file_positions == {0: [2], 1: [1]}


def test_nfile_exact_matches_preserve_subset_and_duplicate_positions() -> None:
    """N 文件精确匹配应保留子集文件和同文件重复位置。"""
    matches = find_nfile_exact_matches(
        {
            0: ["甲", "乙", "甲"],
            1: ["甲", "丙"],
            2: ["乙", "丁"],
        }
    )

    by_text = {match.text: match for match in matches}
    assert by_text["甲"].file_positions == {0: [1, 3], 1: [1]}
    assert by_text["乙"].file_positions == {0: [2], 2: [1]}


def _create_three_file_bundle(tmp_path: Path) -> tuple[Path, CompareResponse]:
    """构建三文件对比 fixture 并返回 (output_root, payload)。"""
    first_path = tmp_path / "first.docx"
    second_path = tmp_path / "second.docx"
    third_path = tmp_path / "third.docx"
    output_root = tmp_path / "compare"
    common_segment = "具有良好的商业信誉和健全的财务会计制度"
    _write_docx(
        first_path, ["共同段落。", f"第一份前缀{common_segment}后缀。", "重复段落。", "重复段落。"]
    )
    _write_docx(second_path, ["共同段落。", f"第二份前缀{common_segment}尾部。", "重复段落。"])
    _write_docx(third_path, ["第三份独有。", "重复段落。"])
    payload = create_compare_bundle(
        files=[
            (first_path, first_path.name),
            (second_path, second_path.name),
            (third_path, third_path.name),
        ],
        output_root=output_root,
        min_segment_length=12,
    )
    return output_root, payload


def test_create_compare_bundle_summary_and_matches(tmp_path: Path) -> None:
    """服务层应正确统计文件数、匹配数和跨文件重复。"""
    _, payload = _create_three_file_bundle(tmp_path)
    repeated = next(match for match in payload.matches if match.text == "重复段落。")

    assert payload.summary.file_count == 3
    assert len(payload.documents.files) == 3
    assert payload.summary.common_paragraph_count == 2
    assert payload.summary.common_segment_count == 0
    assert repeated.file_indices == [0, 1, 2]
    assert repeated.per_file_counts["0"] == 2


def test_create_compare_bundle_writes_review_json_and_downloads(tmp_path: Path) -> None:
    """服务层应生成 review.json 和每份文件的高亮下载文件。"""
    output_root, payload = _create_three_file_bundle(tmp_path)
    review_dir = output_root / payload.review_id
    review_json = review_dir / "review.json"
    first_download = get_compare_download(payload.review_id, 0, output_root=output_root)
    third_download = get_compare_download(payload.review_id, 2, output_root=output_root)
    persisted = json.loads(review_json.read_text(encoding="utf-8"))

    assert review_json.exists()
    assert persisted["documents"]["files"][0]["fileIndex"] == 0
    assert first_download.path.exists()
    assert third_download.path.exists()
    assert first_download.filename == "first_reviewed.docx"
    assert third_download.filename == "third_reviewed.docx"


def test_create_compare_bundle_from_bytes_accepts_uploaded_files(tmp_path: Path) -> None:
    """上传字节入口应接收 files 列表并保留文件顺序。"""
    first_path = tmp_path / "a.docx"
    second_path = tmp_path / "b.docx"
    _write_docx(first_path, ["共同内容。"])
    _write_docx(second_path, ["共同内容。"])

    payload = create_compare_bundle_from_bytes(
        files=[
            (first_path.read_bytes(), "upload_a.docx"),
            (second_path.read_bytes(), "upload_b.docx"),
        ],
        output_root=tmp_path / "compare",
    )

    assert [doc.name for doc in payload.documents.files] == ["upload_a.docx", "upload_b.docx"]
    assert payload.matches[0].file_indices == [0, 1]


def test_compare_pdf_uses_document_store_conversion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PDF 文件应通过 DocumentStore 转换为 Markdown 后参与对比。"""
    pdf_path = tmp_path / "source.pdf"
    docx_path = tmp_path / "source.docx"
    markdown_path = tmp_path / "prepared.md"
    pdf_path.write_bytes(b"%PDF fake")
    markdown_path.write_text("PDF 共同段落。", encoding="utf-8")
    _write_docx(docx_path, ["PDF 共同段落。"])

    class FakeStore:
        def get_or_convert(self, raw_path: Path) -> Path:
            assert raw_path.name.startswith("file_0_")
            return markdown_path

    from govdoc.config import CompareConfig

    class FakeConfig:
        compare = CompareConfig()
        storage_root = tmp_path

    monkeypatch.setattr("govdoc.runtime.get_document_store", lambda: FakeStore())
    monkeypatch.setattr("govdoc.runtime.get_config", lambda: FakeConfig())

    payload = create_compare_bundle(
        files=[
            (pdf_path, "source.pdf"),
            (docx_path, "source.docx"),
        ],
        output_root=tmp_path / "compare",
    )

    assert payload.documents.files[0].suffix == ".pdf"
    assert any(match.text == "PDF 共同段落。" for match in payload.matches)


def test_compare_bundle_accepts_markdown_files(tmp_path: Path) -> None:
    """已转换的 .md 文件应直接对比，不需要重新解析原始格式。"""
    md_a = tmp_path / "a.md"
    md_b = tmp_path / "b.md"
    md_a.write_text("共同段落。\n\n独有A。", encoding="utf-8")
    md_b.write_text("共同段落。\n\n独有B。", encoding="utf-8")

    payload = create_compare_bundle(
        files=[(md_a, "report_a.doc"), (md_b, "report_b.doc")],
        output_root=tmp_path / "compare",
    )

    assert payload.summary.file_count == 2
    assert payload.summary.common_paragraph_count == 1
    assert payload.documents.files[0].suffix == ".doc"
    assert payload.documents.files[1].suffix == ".doc"


def test_compare_empty_documents_returns_zero_matches(tmp_path: Path) -> None:
    """两个空文档对比应返回 0 匹配而非崩溃。"""
    first_path = tmp_path / "empty_a.docx"
    second_path = tmp_path / "empty_b.docx"
    output_root = tmp_path / "compare"
    _write_docx(first_path, [])
    _write_docx(second_path, [])

    payload = create_compare_bundle(
        files=[
            (first_path, first_path.name),
            (second_path, second_path.name),
        ],
        output_root=output_root,
    )

    assert payload.summary.match_count == 0
    assert payload.summary.files[0].paragraph_count == 0
    assert payload.summary.files[1].paragraph_count == 0
    assert payload.matches == []


def test_sanitize_filename_strips_dangerous_characters() -> None:
    """文件名清理应移除路径分隔符和特殊字符。"""
    from govdoc.compare.service import _sanitize_filename

    assert _sanitize_filename("../../etc/passwd") == "etc_passwd"
    assert _sanitize_filename("hello world (1).docx") == "hello_world_1_.docx"
    assert _sanitize_filename("") == "reviewed_document.docx"
    assert _sanitize_filename("...") == "reviewed_document.docx"


def test_get_compare_download_raises_on_nonexistent_id(tmp_path: Path) -> None:
    """不存在的 review_id 应抛出 FileNotFoundError。"""
    output_root = tmp_path / "compare"
    output_root.mkdir()

    with pytest.raises(FileNotFoundError):
        get_compare_download("aabbccddeeff", 0, output_root=output_root)


def test_get_compare_download_raises_on_invalid_id_or_index(tmp_path: Path) -> None:
    """非法 review_id 或 file_index 应抛出 FileNotFoundError。"""
    output_root = tmp_path / "compare"
    output_root.mkdir()

    with pytest.raises(FileNotFoundError):
        get_compare_download("../../../etc", 0, output_root=output_root)

    with pytest.raises(FileNotFoundError):
        get_compare_download("too-short", 0, output_root=output_root)

    with pytest.raises(FileNotFoundError):
        get_compare_download("aabbccddeeff", -1, output_root=output_root)


def test_compare_single_paragraph_documents(tmp_path: Path) -> None:
    """单段落相同文档应产生段落级匹配。"""
    first_path = tmp_path / "single_a.docx"
    second_path = tmp_path / "single_b.docx"
    output_root = tmp_path / "compare"
    _write_docx(first_path, ["唯一段落内容。"])
    _write_docx(second_path, ["唯一段落内容。"])

    payload = create_compare_bundle(
        files=[
            (first_path, first_path.name),
            (second_path, second_path.name),
        ],
        output_root=output_root,
    )

    assert payload.summary.common_paragraph_count == 1
    assert any(m.category == "paragraph" for m in payload.matches)


def test_compare_requires_at_least_two_files(tmp_path: Path) -> None:
    """服务层应拒绝少于两份文件的对比请求。"""
    only_path = tmp_path / "only.docx"
    _write_docx(only_path, ["内容"])

    with pytest.raises(ValueError, match="至少上传 2 份文件"):
        create_compare_bundle(files=[(only_path, only_path.name)], output_root=tmp_path / "compare")


def test_sentence_inside_matched_paragraph_is_deduplicated(tmp_path: Path) -> None:
    """段落内的单句子不应被重复计入 sentenceCount。"""
    first_path = tmp_path / "a.docx"
    second_path = tmp_path / "b.docx"
    output_root = tmp_path / "compare"
    _write_docx(first_path, ["唯一共同段落。", "独有A段落。"])
    _write_docx(second_path, ["唯一共同段落。", "独有B段落。"])

    payload = create_compare_bundle(
        files=[(first_path, first_path.name), (second_path, second_path.name)],
        output_root=output_root,
    )

    assert payload.summary.common_paragraph_count == 1
    assert payload.summary.common_sentence_count == 0
    assert not any(m.category == "sentence" for m in payload.matches)


def test_sentence_dedup_preserves_cross_paragraph_sentences(tmp_path: Path) -> None:
    """跨段落的相同句子（不在段落匹配中）应保留。"""
    first_path = tmp_path / "a.docx"
    second_path = tmp_path / "b.docx"
    output_root = tmp_path / "compare"
    _write_docx(first_path, ["第一句共享。第二句不同A。"])
    _write_docx(second_path, ["第一句共享。第二句不同B。"])

    payload = create_compare_bundle(
        files=[(first_path, first_path.name), (second_path, second_path.name)],
        output_root=output_root,
    )

    assert payload.summary.common_paragraph_count == 0
    assert payload.summary.common_sentence_count == 1
    assert any(m.text == "第一句共享。" and m.category == "sentence" for m in payload.matches)


class TestExtractPdfUsesCompareStore:
    """验证 _extract_pdf_paragraphs 使用 get_document_store。"""

    @patch("govdoc.runtime.get_document_store")
    @patch("govdoc.runtime.get_config")
    def test_calls_compare_store_not_main(
        self,
        mock_config: MagicMock,
        mock_store_fn: MagicMock,
        tmp_path: Path,
    ) -> None:
        """_extract_pdf_paragraphs 调用 get_document_store。"""
        mock_config.return_value.compare.pdf_timeout_s = 60

        md_path = tmp_path / "result.md"
        md_path.write_text("段落一\n\n段落二", encoding="utf-8")
        mock_store = MagicMock()
        mock_store.get_or_convert.return_value = md_path
        mock_store_fn.return_value = mock_store

        result = _extract_pdf_paragraphs(tmp_path / "test.pdf")

        mock_store_fn.assert_called_once()
        mock_store.get_or_convert.assert_called_once()
        assert len(result) >= 1
