"""splitter 单元测试：验证 CompareResponse 拆分为多文件。"""

from __future__ import annotations

import json
from pathlib import Path

from govdoc.compare.splitter import split_compare_response
from govdoc.schemas.compare import (
    CompareArtifacts,
    CompareBlockSegment,
    CompareCategory,
    CompareDocumentBlock,
    CompareDocument,
    CompareDocuments,
    CompareDownloads,
    CompareMatch,
    CompareOccurrence,
    CompareOccurrenceSegment,
    CompareResponse,
    CompareSummary,
    CompareFileMeta,
)


def _make_block(index: int, text: str) -> CompareDocumentBlock:
    return CompareDocumentBlock(
        id=f"b-{index}",
        index=index,
        text=text,
        segments=[CompareBlockSegment(text=text, match_ids=[], categories=[])],
    )


def _make_response() -> CompareResponse:
    blocks_0 = [_make_block(i, f"文件0段落{i}") for i in range(5)]
    blocks_1 = [_make_block(i, f"文件1段落{i}") for i in range(3)]
    return CompareResponse(
        review_id="test-review",
        summary=CompareSummary(
            file_count=2,
            files=[
                CompareFileMeta(
                    file_index=0, name="a.pdf", suffix=".pdf", paragraph_count=5, block_count=5
                ),
                CompareFileMeta(
                    file_index=1, name="b.pdf", suffix=".pdf", paragraph_count=3, block_count=3
                ),
            ],
            common_paragraph_count=1,
            common_sentence_count=0,
            common_segment_count=0,
            match_count=1,
            min_segment_length=16,
        ),
        documents=CompareDocuments(
            files=[
                CompareDocument(
                    file_index=0, name="a.pdf", suffix=".pdf", block_count=5, blocks=blocks_0
                ),
                CompareDocument(
                    file_index=1, name="b.pdf", suffix=".pdf", block_count=3, blocks=blocks_1
                ),
            ]
        ),
        matches=[
            CompareMatch(
                id="p-001",
                category="paragraph",
                label="完全重复",
                color="#F59E0B",
                text="这是一段很长的重复文本内容" * 10,
                length=100,
                file_indices=[0, 1],
                occurrences={
                    "0": [
                        CompareOccurrence(
                            file_index=0,
                            start=0,
                            end=100,
                            segments=[
                                CompareOccurrenceSegment(
                                    file_index=0, block_id="b-2", block_index=2, start=0, end=100
                                ),
                            ],
                        )
                    ],
                    "1": [
                        CompareOccurrence(
                            file_index=1,
                            start=0,
                            end=100,
                            segments=[
                                CompareOccurrenceSegment(
                                    file_index=1, block_id="b-1", block_index=1, start=0, end=100
                                ),
                            ],
                        )
                    ],
                },
                per_file_counts={"0": 1, "1": 1},
                file_count=2,
                occurrence_count=2,
            ),
        ],
        categories=[CompareCategory(id="paragraph", label="完全重复", color="#F59E0B")],
        downloads=CompareDownloads(files={}),
        artifacts=CompareArtifacts(review_dir="/tmp/test", download_names={}),
    )


class TestSplitCompareResponse:
    def test_generates_summary_json(self, tmp_path: Path) -> None:
        resp = _make_response()
        split_compare_response(resp, tmp_path)
        summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
        assert summary["reviewId"] == "test-review"
        assert len(summary["matches"]) == 1
        assert "preview" in summary["matches"][0]
        assert len(summary["matches"][0]["preview"]) <= 150

    def test_generates_blocks_files(self, tmp_path: Path) -> None:
        resp = _make_response()
        split_compare_response(resp, tmp_path)
        b0 = json.loads((tmp_path / "blocks_0.json").read_text(encoding="utf-8"))
        b1 = json.loads((tmp_path / "blocks_1.json").read_text(encoding="utf-8"))
        assert len(b0) == 5
        assert len(b1) == 3

    def test_generates_match_index(self, tmp_path: Path) -> None:
        resp = _make_response()
        split_compare_response(resp, tmp_path)
        idx = json.loads((tmp_path / "match_index.json").read_text(encoding="utf-8"))
        assert "p-001" in idx
        assert idx["p-001"]["0"]["blockIndices"] == [2]
        assert idx["p-001"]["1"]["blockIndices"] == [1]

    def test_summary_matches_no_full_text(self, tmp_path: Path) -> None:
        resp = _make_response()
        split_compare_response(resp, tmp_path)
        summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
        match = summary["matches"][0]
        assert "text" not in match or match.get("text") is None
