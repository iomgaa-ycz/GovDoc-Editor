"""DOCX 文本匹配算法。

提供段落级精确匹配和连续公共片段匹配能力，供服务层和单元测试复用。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import combinations

from govdoc.compare.extractor import normalize_text


@dataclass(frozen=True)
class TextSegment:
    """两份全文中的连续公共文本片段。"""

    text: str
    first_start: int
    first_end: int
    second_start: int
    second_end: int
    length: int


@dataclass(frozen=True)
class NFileExactMatch:
    """N 文件场景下的精确文本匹配。"""

    text: str
    file_positions: dict[int, list[int]]


@dataclass(frozen=True)
class TextRange:
    """一段文本在全文中的偏移范围。"""

    start: int
    end: int


@dataclass(frozen=True)
class NFileSegmentMatch:
    """N 文件场景下的连续公共片段匹配。"""

    text: str
    file_ranges: dict[int, list[TextRange]]


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


def trim_match(
    first_text: str,
    second_text: str,
    first_start: int,
    second_start: int,
    size: int,
) -> TextSegment | None:
    """去掉 SequenceMatcher 匹配块两端空白并验证两侧文本一致。"""
    text = first_text[first_start : first_start + size]

    leading = len(text) - len(text.lstrip())
    trailing = len(text) - len(text.rstrip())
    trimmed = text.strip()

    if not trimmed:
        return None

    start_shift = leading
    end_shift = trailing

    new_first_start = first_start + start_shift
    new_second_start = second_start + start_shift
    new_first_end = first_start + size - end_shift
    new_second_end = second_start + size - end_shift

    if first_text[new_first_start:new_first_end] != second_text[new_second_start:new_second_end]:
        return None

    return TextSegment(
        text=trimmed,
        first_start=new_first_start,
        first_end=new_first_end,
        second_start=new_second_start,
        second_end=new_second_end,
        length=len(trimmed),
    )


def find_common_segments(
    first_text: str,
    second_text: str,
    min_length: int = 12,
) -> list[TextSegment]:
    """查找两份全文中长度不小于阈值的连续公共片段。"""
    matcher = SequenceMatcher(a=first_text, b=second_text, autojunk=False)
    segments: list[TextSegment] = []
    seen: set[tuple[str, int, int]] = set()

    for block in matcher.get_matching_blocks():
        if block.size < min_length:
            continue

        segment = trim_match(
            first_text=first_text,
            second_text=second_text,
            first_start=block.a,
            second_start=block.b,
            size=block.size,
        )
        if segment is None or segment.length < min_length:
            continue

        key = (segment.text, segment.first_start, segment.second_start)
        if key in seen:
            continue

        seen.add(key)
        segments.append(segment)

    return segments


def find_nfile_common_segments(
    all_texts: dict[int, str],
    min_length: int = 16,
) -> list[NFileSegmentMatch]:
    """在 N 个文件之间查找连续公共片段。"""
    file_indices = sorted(all_texts)
    segment_map: dict[str, dict[int, set[tuple[int, int]]]] = defaultdict(
        lambda: defaultdict(set)
    )

    for first_index, second_index in combinations(file_indices, 2):
        segments = find_common_segments(
            first_text=all_texts[first_index],
            second_text=all_texts[second_index],
            min_length=min_length,
        )
        for segment in segments:
            segment_map[segment.text][first_index].add((segment.first_start, segment.first_end))
            segment_map[segment.text][second_index].add((segment.second_start, segment.second_end))

    results: list[NFileSegmentMatch] = []
    for text, per_file_ranges in segment_map.items():
        # SequenceMatcher 只负责发现公共片段文本；发现后再扫描所有文件，
        # 补齐同一片段在同一文件或其他文件中的所有出现位置。
        for file_index, full_text in all_texts.items():
            search_start = 0
            while True:
                found = full_text.find(text, search_start)
                if found < 0:
                    break
                per_file_ranges[file_index].add((found, found + len(text)))
                search_start = found + 1

        if len(per_file_ranges) < 2:
            continue
        results.append(
            NFileSegmentMatch(
                text=text,
                file_ranges={
                    file_index: [
                        TextRange(start=start, end=end) for start, end in sorted(ranges)
                    ]
                    for file_index, ranges in sorted(per_file_ranges.items())
                },
            )
        )

    results.sort(key=lambda item: (-len(item.file_ranges), -len(item.text), item.text))
    return results
