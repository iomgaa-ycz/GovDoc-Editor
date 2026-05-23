"""文档对比服务层测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from docx import Document

from govdoc.compare.compare import (
    find_common_segments,
    find_nfile_common_segments,
    find_nfile_exact_matches,
)
from govdoc.compare.service import (
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


def test_match_algorithms_find_nfile_exact_and_segments() -> None:
    """底层算法应识别 N 文件间完全相同文本和连续公共片段。"""
    exact_matches = find_nfile_exact_matches(
        {0: ["甲", "乙", "甲", "丙"], 1: ["乙", "甲", "丁"]},
    )
    segments = find_common_segments(
        "开头这里有连续公共片段 ABCDEFGHIJ 结尾",
        "另一份也有连续公共片段 ABCDEFGHIJ 收尾",
        min_length=12,
    )

    by_text = {match.text: match for match in exact_matches}
    assert "甲" in by_text
    assert "乙" in by_text
    assert by_text["甲"].file_positions == {0: [1, 3], 1: [2]}
    assert by_text["乙"].file_positions == {0: [2], 1: [1]}
    assert any("连续公共片段 ABCDEFGHIJ" in segment.text for segment in segments)


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


def test_nfile_common_segments_preserve_multiple_ranges() -> None:
    """N 文件公共片段应保留同一文件内不同位置的重复出现。"""
    matches = find_nfile_common_segments(
        {
            0: "AAA公共片段XYZ BBB 公共片段XYZ CCC",
            1: "111公共片段XYZ222",
        },
        min_length=6,
    )

    target = next(match for match in matches if "公共片段XYZ" in match.text)
    assert len(target.file_ranges[0]) >= 2
    assert len(target.file_ranges[1]) >= 1


def _create_three_file_bundle(tmp_path: Path) -> tuple[Path, CompareResponse]:
    """构建三文件对比 fixture 并返回 (output_root, payload)。"""
    first_path = tmp_path / "first.docx"
    second_path = tmp_path / "second.docx"
    third_path = tmp_path / "third.docx"
    output_root = tmp_path / "compare"
    common_segment = "具有良好的商业信誉和健全的财务会计制度"
    _write_docx(first_path, ["共同段落。", f"第一份前缀{common_segment}后缀。", "重复段落。", "重复段落。"])
    _write_docx(second_path, ["共同段落。", f"第二份前缀{common_segment}尾部。", "重复段落。"])
    _write_docx(third_path, ["第三份独有。", "重复段落。"])
    payload = create_compare_bundle(
        files=[(first_path, first_path.name), (second_path, second_path.name), (third_path, third_path.name)],
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
    assert payload.summary.common_segment_count >= 1
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
