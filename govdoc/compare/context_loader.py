"""按需加载匹配上下文：从拆分文件中读取指定 match 涉及的段落。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_match_context(
    review_dir: Path,
    match_id: str,
    surrounding: int = 3,
) -> dict[str, Any]:
    """加载指定 matchId 的上下文。

    Returns:
        包含 match 信息和各文件上下文 blocks 的字典。
    """
    match_index = json.loads((review_dir / "match_index.json").read_text(encoding="utf-8"))
    summary_data = json.loads((review_dir / "summary.json").read_text(encoding="utf-8"))

    if match_id not in match_index:
        raise KeyError(f"matchId 不存在: {match_id}")

    match_entry = match_index[match_id]
    match_info = _find_match_in_summary(summary_data, match_id)

    file_metas = {f["fileIndex"]: f for f in summary_data["summary"]["files"]}
    file_contexts = []
    for file_idx_str, idx_data in match_entry.items():
        file_idx = int(file_idx_str)
        block_indices = idx_data["blockIndices"]
        if not block_indices:
            continue

        blocks_path = review_dir / f"blocks_{file_idx}.json"
        all_blocks = json.loads(blocks_path.read_text(encoding="utf-8"))
        total = len(all_blocks)

        primary_block = block_indices[0]
        start = max(0, primary_block - surrounding)
        end = min(total, primary_block + surrounding + 1)
        sliced_blocks = all_blocks[start:end]

        meta = file_metas.get(file_idx, {})
        file_contexts.append({
            "fileIndex": file_idx,
            "name": meta.get("name", f"file_{file_idx}"),
            "totalBlocks": total,
            "matchBlockIndex": primary_block,
            "blocks": sliced_blocks,
        })

    return {"match": match_info, "fileContexts": file_contexts}


def _find_match_in_summary(summary_data: dict, match_id: str) -> dict:
    """从 summary 的 matches 列表中找到指定 match。"""
    for m in summary_data.get("matches", []):
        if m["id"] == match_id:
            return m
    return {"id": match_id}
