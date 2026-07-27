"""context_loader 单元测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from govdoc.compare.context_loader import load_match_context


@pytest.fixture()
def review_dir(tmp_path: Path) -> Path:
    """构造带拆分文件的 review 目录。"""
    blocks_0 = [
        {
            "id": f"b-{i}",
            "index": i,
            "text": f"段落{i}",
            "segments": [{"text": f"段落{i}", "matchIds": [], "categories": []}],
        }
        for i in range(10)
    ]
    blocks_1 = [
        {
            "id": f"b-{i}",
            "index": i,
            "text": f"文件1段落{i}",
            "segments": [{"text": f"文件1段落{i}", "matchIds": [], "categories": []}],
        }
        for i in range(8)
    ]
    (tmp_path / "blocks_0.json").write_text(
        json.dumps(blocks_0, ensure_ascii=False), encoding="utf-8"
    )
    (tmp_path / "blocks_1.json").write_text(
        json.dumps(blocks_1, ensure_ascii=False), encoding="utf-8"
    )

    match_index = {
        "p-001": {
            "0": {"blockIndices": [5]},
            "1": {"blockIndices": [3]},
        },
    }
    (tmp_path / "match_index.json").write_text(json.dumps(match_index), encoding="utf-8")

    summary = {
        "reviewId": "test",
        "summary": {
            "fileCount": 2,
            "files": [
                {
                    "fileIndex": 0,
                    "name": "a.pdf",
                    "suffix": ".pdf",
                    "paragraphCount": 10,
                    "blockCount": 10,
                },
                {
                    "fileIndex": 1,
                    "name": "b.pdf",
                    "suffix": ".pdf",
                    "paragraphCount": 8,
                    "blockCount": 8,
                },
            ],
            "commonParagraphCount": 1,
            "commonSentenceCount": 0,
            "commonSegmentCount": 0,
            "matchCount": 1,
            "minSegmentLength": 16,
        },
        "matches": [
            {
                "id": "p-001",
                "category": "paragraph",
                "label": "完全重复",
                "color": "#F59E0B",
                "length": 50,
                "fileIndices": [0, 1],
                "occurrenceCount": 2,
                "preview": "段落5",
            },
        ],
        "categories": [],
        "downloads": {"files": {}},
        "artifacts": {"reviewDir": str(tmp_path), "downloadNames": {}},
    }
    (tmp_path / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False), encoding="utf-8"
    )
    return tmp_path


class TestLoadMatchContext:
    def test_returns_correct_file_contexts(self, review_dir: Path) -> None:
        result = load_match_context(review_dir, "p-001", surrounding=2)
        assert result["match"]["id"] == "p-001"
        assert len(result["fileContexts"]) == 2

    def test_surrounding_blocks(self, review_dir: Path) -> None:
        result = load_match_context(review_dir, "p-001", surrounding=2)
        ctx0 = result["fileContexts"][0]
        assert ctx0["fileIndex"] == 0
        assert ctx0["matchBlockIndex"] == 5
        indices = [b["index"] for b in ctx0["blocks"]]
        assert indices == [3, 4, 5, 6, 7]

    def test_clamps_at_boundaries(self, review_dir: Path) -> None:
        result = load_match_context(review_dir, "p-001", surrounding=5)
        ctx1 = result["fileContexts"][1]
        indices = [b["index"] for b in ctx1["blocks"]]
        assert indices[0] == 0
        assert indices[-1] == 7

    def test_unknown_match_raises(self, review_dir: Path) -> None:
        with pytest.raises(KeyError):
            load_match_context(review_dir, "nonexistent", surrounding=2)
