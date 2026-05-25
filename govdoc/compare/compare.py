"""DOCX 文本匹配算法。

提供段落级精确匹配能力，供服务层和单元测试复用。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from govdoc.compare.extractor import normalize_text


@dataclass(frozen=True)
class NFileExactMatch:
    """N 文件场景下的精确文本匹配。"""

    text: str
    file_positions: dict[int, list[int]]


def find_nfile_exact_matches(all_items: dict[int, list[str]]) -> list[NFileExactMatch]:
    """查找出现在两个或多个文件中的完全相同文本。"""
    text_index: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))
    first_seen: dict[str, tuple[int, int]] = {}

    for file_index in sorted(all_items):
        for position, text in enumerate(all_items[file_index], start=1):
            normalized = normalize_text(text)
            if not normalized:
                continue
            text_index[normalized][file_index].append(position)
            first_seen.setdefault(normalized, (file_index, position))

    matches = [
        NFileExactMatch(text=text, file_positions={idx: positions for idx, positions in files.items()})
        for text, files in text_index.items()
        if len(files) >= 2
    ]
    matches.sort(key=lambda item: (first_seen[item.text][0], first_seen[item.text][1], item.text))
    return matches
