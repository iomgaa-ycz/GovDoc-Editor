"""DOCX 文本匹配算法。

提供段落、句子和连续公共片段三类匹配能力，供服务层和单元测试复用。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
import re

from govdoc.compare.extractor import extract_docx_paragraphs, normalize_text


SENTENCE_SPLIT_RE = re.compile(r"(?<=[\u3002\uff01\uff1f!?；;])\s*|(?<=[.])\s+(?=[A-Z0-9\"\'])")


@dataclass(frozen=True)
class ExactMatch:
    """完全相同文本及其在两份文档中的位置。"""

    text: str
    first_positions: list[int]
    second_positions: list[int]


@dataclass(frozen=True)
class TextSegment:
    """两份全文中的连续公共文本片段。"""

    text: str
    first_start: int
    first_end: int
    second_start: int
    second_end: int
    length: int


def split_sentences(paragraphs: list[str]) -> list[str]:
    """按中英文常见句末符号拆分段落为句子。"""
    sentences: list[str] = []

    for paragraph in paragraphs:
        normalized = normalize_text(paragraph)
        if not normalized:
            continue

        for part in SENTENCE_SPLIT_RE.split(normalized):
            sentence = normalize_text(part)
            if sentence:
                sentences.append(sentence)

    return sentences


def find_exact_matches(first_items: list[str], second_items: list[str]) -> list[ExactMatch]:
    """查找两组文本项中完全相同的内容。"""
    first_positions: dict[str, list[int]] = defaultdict(list)
    second_positions: dict[str, list[int]] = defaultdict(list)

    for index, text in enumerate(first_items, start=1):
        first_positions[text].append(index)

    for index, text in enumerate(second_items, start=1):
        second_positions[text].append(index)

    seen: set[str] = set()
    matches: list[ExactMatch] = []

    for text in first_items:
        if text in second_positions and text not in seen:
            seen.add(text)
            matches.append(
                ExactMatch(
                    text=text,
                    first_positions=first_positions[text],
                    second_positions=second_positions[text],
                )
            )

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
