from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import re

from govdoc.compare.extractor import extract_docx_paragraphs, normalize_text


SENTENCE_SPLIT_RE = re.compile(r"(?<=[\u3002\uff01\uff1f!?；;])\s*|(?<=[.])\s+(?=[A-Z0-9\"\'])")


@dataclass(frozen=True)
class ExactMatch:
    text: str
    first_positions: list[int]
    second_positions: list[int]


@dataclass(frozen=True)
class TextSegment:
    text: str
    first_start: int
    first_end: int
    second_start: int
    second_end: int
    length: int


def split_sentences(paragraphs: list[str]) -> list[str]:
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


def compare_docx_files(
    first_path: str | Path,
    second_path: str | Path,
    min_segment_length: int = 12,
) -> dict:
    first_file = Path(first_path)
    second_file = Path(second_path)

    first_paragraphs = extract_docx_paragraphs(first_file)
    second_paragraphs = extract_docx_paragraphs(second_file)

    first_sentences = split_sentences(first_paragraphs)
    second_sentences = split_sentences(second_paragraphs)

    first_text = "\n".join(first_paragraphs)
    second_text = "\n".join(second_paragraphs)

    paragraph_matches = find_exact_matches(first_paragraphs, second_paragraphs)
    sentence_matches = find_exact_matches(first_sentences, second_sentences)
    segment_matches = find_common_segments(
        first_text=first_text,
        second_text=second_text,
        min_length=min_segment_length,
    )

    return {
        "documents": {
            "first": str(first_file),
            "second": str(second_file),
        },
        "summary": {
            "first_paragraph_count": len(first_paragraphs),
            "second_paragraph_count": len(second_paragraphs),
            "first_sentence_count": len(first_sentences),
            "second_sentence_count": len(second_sentences),
            "common_paragraph_count": len(paragraph_matches),
            "common_sentence_count": len(sentence_matches),
            "common_segment_count": len(segment_matches),
            "min_segment_length": min_segment_length,
        },
        "common_paragraphs": [
            {
                "text": match.text,
                "first_positions": match.first_positions,
                "second_positions": match.second_positions,
            }
            for match in paragraph_matches
        ],
        "common_sentences": [
            {
                "text": match.text,
                "first_positions": match.first_positions,
                "second_positions": match.second_positions,
            }
            for match in sentence_matches
        ],
        "common_segments": [
            {
                "text": match.text,
                "first_start": match.first_start,
                "first_end": match.first_end,
                "second_start": match.second_start,
                "second_end": match.second_end,
                "length": match.length,
            }
            for match in segment_matches
        ],
    }
