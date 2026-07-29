"""对比结果拆分器：将 CompareResponse 拆分为多个索引文件。"""

from __future__ import annotations

import json
from pathlib import Path

from govdoc.schemas.compare import CompareResponse

PREVIEW_MAX_LENGTH = 100


def split_compare_response(response: CompareResponse, review_dir: Path) -> None:
    """将完整对比响应拆分为 summary.json + blocks_{N}.json + match_index.json。"""
    _write_summary(response, review_dir)
    _write_blocks(response, review_dir)
    _write_match_index(response, review_dir)


def _write_summary(response: CompareResponse, review_dir: Path) -> None:
    """生成 summary.json：摘要 + 匹配列表（仅 preview，无 text）。"""
    match_items = []
    for m in response.matches:
        match_items.append(
            {
                "id": m.id,
                "category": m.category,
                "label": m.label,
                "color": m.color,
                "length": m.length,
                "fileIndices": m.file_indices,
                "occurrenceCount": m.occurrence_count,
                "perFileCounts": m.per_file_counts,
                "preview": m.text[:PREVIEW_MAX_LENGTH] if m.text else "",
            }
        )

    summary_payload = {
        "reviewId": response.review_id,
        "summary": response.summary.model_dump(mode="json", by_alias=True),
        "matches": match_items,
        "categories": [c.model_dump(mode="json", by_alias=True) for c in response.categories],
        "downloads": response.downloads.model_dump(mode="json", by_alias=True),
        "artifacts": response.artifacts.model_dump(mode="json", by_alias=True),
    }
    (review_dir / "summary.json").write_text(
        json.dumps(summary_payload, ensure_ascii=False),
        encoding="utf-8",
    )


def _write_blocks(response: CompareResponse, review_dir: Path) -> None:
    """生成 blocks_{fileIndex}.json：每个文件的段落块独立存储。"""
    for doc in response.documents.files:
        blocks_data = [b.model_dump(mode="json", by_alias=True) for b in doc.blocks]
        (review_dir / f"blocks_{doc.file_index}.json").write_text(
            json.dumps(blocks_data, ensure_ascii=False),
            encoding="utf-8",
        )


def _write_match_index(response: CompareResponse, review_dir: Path) -> None:
    """生成 match_index.json：matchId → 各文件的 blockIndex 映射。"""
    index: dict[str, dict[str, dict]] = {}
    for m in response.matches:
        entry: dict[str, dict] = {}
        for file_idx_str, occurrences in m.occurrences.items():
            block_indices = []
            for occ in occurrences:
                for seg in occ.segments:
                    if seg.block_index not in block_indices:
                        block_indices.append(seg.block_index)
            entry[file_idx_str] = {"blockIndices": sorted(block_indices)}
        index[m.id] = entry

    (review_dir / "match_index.json").write_text(
        json.dumps(index, ensure_ascii=False),
        encoding="utf-8",
    )
