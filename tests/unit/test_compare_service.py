"""文档对比服务层测试。"""

from __future__ import annotations

import json
from pathlib import Path

from docx import Document

from govdoc.compare.compare import find_common_segments, find_exact_matches
from govdoc.compare.service import create_compare_bundle, get_compare_download


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    """按给定段落写入 DOCX 测试文件。"""
    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    document.save(path)


def test_match_algorithms_find_exact_items_and_segments() -> None:
    """底层算法应识别完全相同文本和连续公共片段。"""
    exact_matches = find_exact_matches(
        ["甲", "乙", "甲", "丙"],
        ["乙", "甲", "丁"],
    )
    segments = find_common_segments(
        "开头这里有连续公共片段 ABCDEFGHIJ 结尾",
        "另一份也有连续公共片段 ABCDEFGHIJ 收尾",
        min_length=12,
    )

    assert [match.text for match in exact_matches] == ["甲", "乙"]
    assert exact_matches[0].first_positions == [1, 3]
    assert exact_matches[0].second_positions == [2]
    assert any("连续公共片段 ABCDEFGHIJ" in segment.text for segment in segments)


def test_create_compare_bundle_writes_payload_and_downloads(tmp_path: Path) -> None:
    """服务层应生成 review.json、上传副本和两份高亮下载文件。"""
    first_path = tmp_path / "first.docx"
    second_path = tmp_path / "second.docx"
    output_root = tmp_path / "compare"
    _write_docx(
        first_path,
        [
            "共同段落。",
            "第一份独有句子。这里有连续公共片段 ABCDEFGHIJ。",
            "重复段落。",
            "重复段落。",
        ],
    )
    _write_docx(
        second_path,
        [
            "共同段落。",
            "第二份独有句子。这里有连续公共片段 ABCDEFGHIJ。",
            "重复段落。",
        ],
    )

    payload = create_compare_bundle(
        first_path=first_path,
        second_path=second_path,
        output_root=output_root,
        min_segment_length=12,
    )

    review_dir = output_root / payload.review_id
    review_json = review_dir / "review.json"
    first_download = get_compare_download(payload.review_id, "first", output_root=output_root)
    second_download = get_compare_download(payload.review_id, "second", output_root=output_root)
    persisted = json.loads(review_json.read_text(encoding="utf-8"))

    assert payload.summary.first_paragraph_count == 4
    assert payload.summary.second_paragraph_count == 3
    assert payload.summary.common_paragraph_count == 2
    assert payload.summary.common_segment_count >= 1
    assert {match.category for match in payload.matches} >= {"paragraph", "segment"}
    assert review_json.exists()
    assert persisted["reviewId"] == payload.review_id
    assert first_download.path.exists()
    assert second_download.path.exists()
    assert first_download.filename == "first_reviewed.docx"
    assert second_download.filename == "second_reviewed.docx"
