"""DOCX 对比服务层。

该模块负责构建前端展示用 match payload、生成高亮 DOCX，并把 review.json
与下载文件写入运行时目录。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import json
import re
import shutil
import uuid

from docx import Document
from docx.enum.text import WD_COLOR_INDEX

from govdoc.compare.compare import find_common_segments
from govdoc.compare.extractor import extract_docx_paragraphs
from govdoc.schemas.compare import (
    CompareArtifacts,
    CompareBlockSegment,
    CompareCategory,
    CompareCategoryId,
    CompareDocument,
    CompareDocumentBlock,
    CompareDocuments,
    CompareDownloads,
    CompareMatch,
    CompareOccurrence,
    CompareOccurrenceSegment,
    CompareResponse,
    CompareSummary,
)


CategoryId = Literal["paragraph", "sentence", "segment"]

CATEGORY_PRIORITY: dict[CategoryId, int] = {
    "paragraph": 0,
    "sentence": 1,
    "segment": 2,
}

CATEGORY_LABELS: dict[CategoryId, str] = {
    "paragraph": "相同段落",
    "sentence": "相同句子",
    "segment": "连续公共片段",
}

CATEGORY_COLORS: dict[CategoryId, str] = {
    "paragraph": "#f5b700",
    "sentence": "#12b5cb",
    "segment": "#ff7a59",
}

DOCX_HIGHLIGHT_COLORS: dict[CategoryId, WD_COLOR_INDEX] = {
    "paragraph": WD_COLOR_INDEX.YELLOW,
    "sentence": WD_COLOR_INDEX.TURQUOISE,
    "segment": WD_COLOR_INDEX.PINK,
}

SENTENCE_END_CHARS = {
    "。",
    "！",
    "？",
    "!",
    "?",
    "；",
    ";",
}

REVIEW_ID_RE = re.compile(r"^[a-f0-9]{12}$")


@dataclass(frozen=True)
class TextBlock:
    """文档中的一个段落块及其全文偏移范围。"""

    id: str
    index: int
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class SentenceOccurrence:
    """一个句子在全文和段落中的出现位置。"""

    text: str
    start: int
    end: int
    block_id: str
    block_index: int
    start_in_block: int
    end_in_block: int


@dataclass(frozen=True)
class MatchOccurrence:
    """一个匹配项在全文中的出现范围。"""

    start: int
    end: int


@dataclass(frozen=True)
class MatchRecord:
    """服务层内部使用的匹配记录。"""

    id: str
    category: CategoryId
    text: str
    first_occurrences: list[MatchOccurrence]
    second_occurrences: list[MatchOccurrence]


@dataclass(frozen=True)
class DocumentModel:
    """服务层内部使用的文档模型。"""

    side: str
    file_name: str
    blocks: list[TextBlock]
    full_text: str


@dataclass(frozen=True)
class CompareDownload:
    """高亮 DOCX 下载文件信息。"""

    path: Path
    filename: str


def get_compare_root() -> Path:
    """返回文档对比运行时目录。

    对比功能按产品约定固定写入项目根目录下的 data/compare，不单独暴露配置项。
    """
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "data" / "compare"


def _prepare_output_root(output_root: Path | None) -> Path:
    """准备对比输出根目录，测试可通过参数覆盖。"""
    root = output_root or get_compare_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _create_review_dir(output_root: Path) -> tuple[str, Path]:
    """创建唯一 review 目录并返回 review_id。"""
    while True:
        review_id = uuid.uuid4().hex[:12]
        review_dir = output_root / review_id
        if not review_dir.exists():
            review_dir.mkdir(parents=True)
            return review_id, review_dir


def _sanitize_filename(name: str) -> str:
    """清理上传文件名，避免写入危险或不可移植字符。"""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return cleaned.strip("._") or "reviewed_document.docx"


def _build_document_model(side: str, file_name: str, path: Path) -> DocumentModel:
    """把 DOCX 段落转换为带全文偏移的内部文档模型。"""
    paragraphs = extract_docx_paragraphs(path)
    blocks: list[TextBlock] = []
    cursor = 0

    for index, text in enumerate(paragraphs, start=1):
        start = cursor
        end = start + len(text)
        blocks.append(
            TextBlock(
                id=f"{side}-block-{index}",
                index=index,
                text=text,
                start=start,
                end=end,
            )
        )
        cursor = end + 1

    full_text = "\n".join(block.text for block in blocks)
    return DocumentModel(side=side, file_name=file_name, blocks=blocks, full_text=full_text)


def _iter_sentence_occurrences(document: DocumentModel) -> list[SentenceOccurrence]:
    """枚举文档中所有句子的全文位置和段落内位置。"""
    sentences: list[SentenceOccurrence] = []

    for block in document.blocks:
        text = block.text
        start = 0
        index = 0

        while index < len(text):
            current = text[index]
            boundary_end: int | None = None

            if current in SENTENCE_END_CHARS:
                boundary_end = index + 1
            elif current == ".":
                lookahead = index + 1
                while lookahead < len(text) and text[lookahead].isspace():
                    lookahead += 1
                if (
                    lookahead >= len(text)
                    or text[lookahead].isupper()
                    or text[lookahead].isdigit()
                    or text[lookahead] in {'"', "'"}
                ):
                    boundary_end = lookahead

            if boundary_end is not None:
                leading = start
                while leading < boundary_end and text[leading].isspace():
                    leading += 1
                trailing = boundary_end
                while trailing > leading and text[trailing - 1].isspace():
                    trailing -= 1

                if leading < trailing:
                    sentences.append(
                        SentenceOccurrence(
                            text=text[leading:trailing],
                            start=block.start + leading,
                            end=block.start + trailing,
                            block_id=block.id,
                            block_index=block.index,
                            start_in_block=leading,
                            end_in_block=trailing,
                        )
                    )
                start = boundary_end

            index += 1

        leading = start
        while leading < len(text) and text[leading].isspace():
            leading += 1
        trailing = len(text)
        while trailing > leading and text[trailing - 1].isspace():
            trailing -= 1

        if leading < trailing:
            sentences.append(
                SentenceOccurrence(
                    text=text[leading:trailing],
                    start=block.start + leading,
                    end=block.start + trailing,
                    block_id=block.id,
                    block_index=block.index,
                    start_in_block=leading,
                    end_in_block=trailing,
                )
            )

    return sentences


def _build_exact_block_matches(
    first_document: DocumentModel,
    second_document: DocumentModel,
) -> list[MatchRecord]:
    """构建两份文档中完全相同的段落匹配。"""
    first_lookup: dict[str, list[MatchOccurrence]] = defaultdict(list)
    second_lookup: dict[str, list[MatchOccurrence]] = defaultdict(list)

    for block in first_document.blocks:
        first_lookup[block.text].append(MatchOccurrence(start=block.start, end=block.end))
    for block in second_document.blocks:
        second_lookup[block.text].append(MatchOccurrence(start=block.start, end=block.end))

    matches: list[MatchRecord] = []
    seen: set[str] = set()

    for block in first_document.blocks:
        if block.text in second_lookup and block.text not in seen:
            seen.add(block.text)
            matches.append(
                MatchRecord(
                    id=f"paragraph-{len(matches) + 1:03d}",
                    category="paragraph",
                    text=block.text,
                    first_occurrences=first_lookup[block.text],
                    second_occurrences=second_lookup[block.text],
                )
            )

    return matches


def _build_exact_sentence_matches(
    first_document: DocumentModel,
    second_document: DocumentModel,
) -> list[MatchRecord]:
    """构建两份文档中完全相同的句子匹配。"""
    first_sentences = _iter_sentence_occurrences(first_document)
    second_sentences = _iter_sentence_occurrences(second_document)

    first_lookup: dict[str, list[MatchOccurrence]] = defaultdict(list)
    second_lookup: dict[str, list[MatchOccurrence]] = defaultdict(list)

    for sentence in first_sentences:
        first_lookup[sentence.text].append(MatchOccurrence(start=sentence.start, end=sentence.end))
    for sentence in second_sentences:
        second_lookup[sentence.text].append(MatchOccurrence(start=sentence.start, end=sentence.end))

    matches: list[MatchRecord] = []
    seen: set[str] = set()

    for sentence in first_sentences:
        if sentence.text in second_lookup and sentence.text not in seen:
            seen.add(sentence.text)
            matches.append(
                MatchRecord(
                    id=f"sentence-{len(matches) + 1:03d}",
                    category="sentence",
                    text=sentence.text,
                    first_occurrences=first_lookup[sentence.text],
                    second_occurrences=second_lookup[sentence.text],
                )
            )

    return matches


def _build_segment_matches(
    first_document: DocumentModel,
    second_document: DocumentModel,
    min_segment_length: int,
    exact_matches: list[MatchRecord],
) -> list[MatchRecord]:
    """构建两份文档中的连续公共片段匹配。"""
    exact_occurrence_ranges: set[tuple[str, int, int, int, int]] = set()

    for match in exact_matches:
        first_ranges = {(item.start, item.end) for item in match.first_occurrences}
        second_ranges = {(item.start, item.end) for item in match.second_occurrences}
        for first_start, first_end in first_ranges:
            for second_start, second_end in second_ranges:
                exact_occurrence_ranges.add(
                    (match.text, first_start, first_end, second_start, second_end)
                )

    segments = find_common_segments(
        first_text=first_document.full_text,
        second_text=second_document.full_text,
        min_length=min_segment_length,
    )

    matches: list[MatchRecord] = []

    for segment in segments:
        segment_key = (
            segment.text,
            segment.first_start,
            segment.first_end,
            segment.second_start,
            segment.second_end,
        )
        if segment_key in exact_occurrence_ranges:
            continue

        matches.append(
            MatchRecord(
                id=f"segment-{len(matches) + 1:03d}",
                category="segment",
                text=segment.text,
                first_occurrences=[
                    MatchOccurrence(
                        start=segment.first_start,
                        end=segment.first_end,
                    )
                ],
                second_occurrences=[
                    MatchOccurrence(
                        start=segment.second_start,
                        end=segment.second_end,
                    )
                ],
            )
        )

    return matches


def _split_occurrence_by_blocks(
    blocks: list[TextBlock],
    occurrence: MatchOccurrence,
) -> list[CompareOccurrenceSegment]:
    """把全文匹配范围切分到对应段落块内。"""
    pieces: list[CompareOccurrenceSegment] = []

    for block in blocks:
        overlap_start = max(block.start, occurrence.start)
        overlap_end = min(block.end, occurrence.end)
        if overlap_start >= overlap_end:
            continue

        pieces.append(
            CompareOccurrenceSegment(
                block_id=block.id,
                block_index=block.index,
                start=overlap_start - block.start,
                end=overlap_end - block.start,
            )
        )

    return pieces


def _build_annotations(
    document: DocumentModel,
    matches: list[MatchRecord],
    side: Literal["first", "second"],
) -> tuple[dict[str, list[dict]], dict[str, list[CompareOccurrence]]]:
    """生成段落渲染 annotation 和按 match 聚合的位置索引。"""
    block_annotations: dict[str, list[dict]] = defaultdict(list)
    match_segments: dict[str, list[CompareOccurrence]] = defaultdict(list)

    for match in matches:
        occurrences = match.first_occurrences if side == "first" else match.second_occurrences

        for occurrence in occurrences:
            pieces = _split_occurrence_by_blocks(document.blocks, occurrence)
            match_segments[match.id].append(
                CompareOccurrence(
                    start=occurrence.start,
                    end=occurrence.end,
                    segments=pieces,
                )
            )
            for piece in pieces:
                block_annotations[piece.block_id].append(
                    {
                        "match_id": match.id,
                        "category": match.category,
                        "start": piece.start,
                        "end": piece.end,
                    }
                )

    return block_annotations, match_segments


def _pick_primary_match(match_ids: list[str], match_lookup: dict[str, MatchRecord]) -> str:
    """根据类别优先级选择重叠片段的主匹配。"""
    return sorted(
        match_ids,
        key=lambda item: (CATEGORY_PRIORITY[match_lookup[item].category], item),
    )[0]


def _build_block_segments(
    block: TextBlock,
    annotations: list[dict],
    match_lookup: dict[str, MatchRecord],
) -> list[CompareBlockSegment]:
    """按 annotation 边界把段落切成前端可渲染片段。"""
    if not annotations:
        return [
            CompareBlockSegment(
                text=block.text,
                match_ids=[],
                categories=[],
                primary_match_id=None,
            )
        ]

    boundaries = {0, len(block.text)}
    for annotation in annotations:
        boundaries.add(annotation["start"])
        boundaries.add(annotation["end"])

    ordered = sorted(boundaries)
    segments: list[CompareBlockSegment] = []

    for start, end in zip(ordered, ordered[1:]):
        if start == end:
            continue

        text = block.text[start:end]
        active = [
            annotation
            for annotation in annotations
            if annotation["start"] < end and annotation["end"] > start
        ]
        match_ids = sorted({str(annotation["match_id"]) for annotation in active})
        categories: list[CompareCategoryId] = sorted(
            {annotation["category"] for annotation in active},
            key=lambda item: CATEGORY_PRIORITY[item],
        )
        primary_match_id = _pick_primary_match(match_ids, match_lookup) if match_ids else None

        current = CompareBlockSegment(
            text=text,
            match_ids=match_ids,
            categories=categories,
            primary_match_id=primary_match_id,
        )

        if (
            segments
            and segments[-1].match_ids == current.match_ids
            and segments[-1].categories == current.categories
            and segments[-1].primary_match_id == current.primary_match_id
        ):
            segments[-1] = segments[-1].model_copy(update={"text": segments[-1].text + text})
        else:
            segments.append(current)

    return segments


def _serialize_document(
    document: DocumentModel,
    block_annotations: dict[str, list[dict]],
    match_lookup: dict[str, MatchRecord],
) -> CompareDocument:
    """序列化单侧文档为前端展示结构。"""
    return CompareDocument(
        name=document.file_name,
        block_count=len(document.blocks),
        blocks=[
            CompareDocumentBlock(
                id=block.id,
                index=block.index,
                text=block.text,
                segments=_build_block_segments(
                    block=block,
                    annotations=block_annotations.get(block.id, []),
                    match_lookup=match_lookup,
                ),
            )
            for block in document.blocks
        ],
    )


def _serialize_matches(
    matches: list[MatchRecord],
    first_match_segments: dict[str, list[CompareOccurrence]],
    second_match_segments: dict[str, list[CompareOccurrence]],
) -> list[CompareMatch]:
    """序列化匹配记录为前端列表结构。"""
    serialized: list[CompareMatch] = []

    for match in matches:
        serialized.append(
            CompareMatch(
                id=match.id,
                category=match.category,
                label=CATEGORY_LABELS[match.category],
                color=CATEGORY_COLORS[match.category],
                text=match.text,
                length=len(match.text),
                first_occurrences=first_match_segments.get(match.id, []),
                second_occurrences=second_match_segments.get(match.id, []),
                first_count=len(match.first_occurrences),
                second_count=len(match.second_occurrences),
            )
        )

    serialized.sort(
        key=lambda item: (
            CATEGORY_PRIORITY[item.category],
            -item.length,
            item.id,
        )
    )
    return serialized


def _write_highlighted_review_copy(path: Path, document_payload: CompareDocument) -> None:
    """根据前端片段结构写出带高亮的 DOCX 副本。"""
    review_doc = Document()

    for block in document_payload.blocks:
        paragraph = review_doc.add_paragraph()
        for segment in block.segments:
            run = paragraph.add_run(segment.text)
            if segment.categories:
                color = DOCX_HIGHLIGHT_COLORS[segment.categories[0]]
                run.font.highlight_color = color

    review_doc.save(path)


def _build_compare_response(
    review_id: str,
    review_dir: Path,
    first_path: Path,
    second_path: Path,
    first_name: str,
    second_name: str,
    min_segment_length: int,
) -> CompareResponse:
    """构建完整对比响应并落盘 review.json 与下载文件。"""
    first_document = _build_document_model("first", first_name, first_path)
    second_document = _build_document_model("second", second_name, second_path)

    paragraph_matches = _build_exact_block_matches(first_document, second_document)
    sentence_matches = _build_exact_sentence_matches(first_document, second_document)
    segment_matches = _build_segment_matches(
        first_document=first_document,
        second_document=second_document,
        min_segment_length=min_segment_length,
        exact_matches=paragraph_matches + sentence_matches,
    )
    all_matches = paragraph_matches + sentence_matches + segment_matches
    match_lookup = {match.id: match for match in all_matches}

    first_annotations, first_match_segments = _build_annotations(
        document=first_document,
        matches=all_matches,
        side="first",
    )
    second_annotations, second_match_segments = _build_annotations(
        document=second_document,
        matches=all_matches,
        side="second",
    )

    first_payload = _serialize_document(
        document=first_document,
        block_annotations=first_annotations,
        match_lookup=match_lookup,
    )
    second_payload = _serialize_document(
        document=second_document,
        block_annotations=second_annotations,
        match_lookup=match_lookup,
    )
    serialized_matches = _serialize_matches(
        matches=all_matches,
        first_match_segments=first_match_segments,
        second_match_segments=second_match_segments,
    )

    first_download_name = f"{Path(_sanitize_filename(first_name)).stem}_reviewed.docx"
    second_download_name = f"{Path(_sanitize_filename(second_name)).stem}_reviewed.docx"
    first_download_path = review_dir / "first_reviewed.docx"
    second_download_path = review_dir / "second_reviewed.docx"

    _write_highlighted_review_copy(first_download_path, first_payload)
    _write_highlighted_review_copy(second_download_path, second_payload)

    payload = CompareResponse(
        review_id=review_id,
        summary=CompareSummary(
            first_file_name=first_name,
            second_file_name=second_name,
            first_paragraph_count=len(first_document.blocks),
            second_paragraph_count=len(second_document.blocks),
            common_paragraph_count=len(paragraph_matches),
            common_sentence_count=len(sentence_matches),
            common_segment_count=len(segment_matches),
            match_count=len(serialized_matches),
            min_segment_length=min_segment_length,
        ),
        documents=CompareDocuments(first=first_payload, second=second_payload),
        matches=serialized_matches,
        categories=[
            CompareCategory(
                id=category,
                label=CATEGORY_LABELS[category],
                color=CATEGORY_COLORS[category],
            )
            for category in ("paragraph", "sentence", "segment")
        ],
        downloads=CompareDownloads(
            first=f"/api/v1/compare/{review_id}/download/first",
            second=f"/api/v1/compare/{review_id}/download/second",
        ),
        artifacts=CompareArtifacts(
            review_dir=str(review_dir),
            first_download_name=first_download_name,
            second_download_name=second_download_name,
        ),
    )

    (review_dir / "review.json").write_text(
        json.dumps(payload.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def create_compare_bundle(
    first_path: Path,
    second_path: Path,
    output_root: Path | None = None,
    min_segment_length: int = 16,
    first_name: str | None = None,
    second_name: str | None = None,
) -> CompareResponse:
    """从两个本地 DOCX 路径创建对比 review。"""
    root = _prepare_output_root(output_root)
    review_id, review_dir = _create_review_dir(root)

    first_source_name = first_name or first_path.name
    second_source_name = second_name or second_path.name

    uploads_dir = review_dir / "uploads"
    uploads_dir.mkdir(exist_ok=True)

    stored_first = uploads_dir / f"first_{_sanitize_filename(first_source_name)}"
    stored_second = uploads_dir / f"second_{_sanitize_filename(second_source_name)}"
    shutil.copy2(first_path, stored_first)
    shutil.copy2(second_path, stored_second)

    return _build_compare_response(
        review_id=review_id,
        review_dir=review_dir,
        first_path=stored_first,
        second_path=stored_second,
        first_name=first_source_name,
        second_name=second_source_name,
        min_segment_length=min_segment_length,
    )


def create_compare_bundle_from_bytes(
    first_content: bytes,
    second_content: bytes,
    first_name: str,
    second_name: str,
    output_root: Path | None = None,
    min_segment_length: int = 16,
) -> CompareResponse:
    """从上传字节内容创建对比 review。"""
    root = _prepare_output_root(output_root)
    review_id, review_dir = _create_review_dir(root)

    uploads_dir = review_dir / "uploads"
    uploads_dir.mkdir(exist_ok=True)

    stored_first = uploads_dir / f"first_{_sanitize_filename(first_name)}"
    stored_second = uploads_dir / f"second_{_sanitize_filename(second_name)}"
    stored_first.write_bytes(first_content)
    stored_second.write_bytes(second_content)

    return _build_compare_response(
        review_id=review_id,
        review_dir=review_dir,
        first_path=stored_first,
        second_path=stored_second,
        first_name=first_name,
        second_name=second_name,
        min_segment_length=min_segment_length,
    )


def get_compare_download(
    review_id: str,
    side: Literal["first", "second"],
    output_root: Path | None = None,
) -> CompareDownload:
    """读取 review 元数据并返回指定侧的高亮 DOCX 下载信息。"""
    if not REVIEW_ID_RE.fullmatch(review_id):
        raise FileNotFoundError(review_id)

    root = _prepare_output_root(output_root)
    review_dir = root / review_id
    metadata_path = review_dir / "review.json"
    if not metadata_path.exists():
        raise FileNotFoundError(review_id)

    metadata = CompareResponse.model_validate_json(metadata_path.read_text(encoding="utf-8"))
    if side == "first":
        path = review_dir / "first_reviewed.docx"
        filename = metadata.artifacts.first_download_name
    else:
        path = review_dir / "second_reviewed.docx"
        filename = metadata.artifacts.second_download_name

    if not path.exists():
        raise FileNotFoundError(review_id)

    return CompareDownload(path=path, filename=filename)
