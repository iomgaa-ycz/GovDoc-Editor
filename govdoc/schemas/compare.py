"""DOCX comparison response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict

from govdoc.schemas.common import GovDocModel


def _to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


CompareCategoryId = Literal["paragraph", "sentence", "segment"]


class CompareModel(GovDocModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        extra="forbid",
        populate_by_name=True,
    )


class CompareCategory(CompareModel):
    id: CompareCategoryId
    label: str
    color: str


class CompareSummary(CompareModel):
    first_file_name: str
    second_file_name: str
    first_paragraph_count: int
    second_paragraph_count: int
    common_paragraph_count: int
    common_sentence_count: int
    common_segment_count: int
    match_count: int
    min_segment_length: int


class CompareBlockSegment(CompareModel):
    text: str
    match_ids: list[str]
    categories: list[CompareCategoryId]
    primary_match_id: str | None = None


class CompareDocumentBlock(CompareModel):
    id: str
    index: int
    text: str
    segments: list[CompareBlockSegment]


class CompareDocument(CompareModel):
    name: str
    block_count: int
    blocks: list[CompareDocumentBlock]


class CompareDocuments(CompareModel):
    first: CompareDocument
    second: CompareDocument


class CompareOccurrenceSegment(CompareModel):
    block_id: str
    block_index: int
    start: int
    end: int


class CompareOccurrence(CompareModel):
    start: int
    end: int
    segments: list[CompareOccurrenceSegment]


class CompareMatch(CompareModel):
    id: str
    category: CompareCategoryId
    label: str
    color: str
    text: str
    length: int
    first_occurrences: list[CompareOccurrence]
    second_occurrences: list[CompareOccurrence]
    first_count: int
    second_count: int


class CompareDownloads(CompareModel):
    first: str
    second: str


class CompareArtifacts(CompareModel):
    review_dir: str
    first_download_name: str
    second_download_name: str


class CompareResponse(CompareModel):
    review_id: str
    summary: CompareSummary
    documents: CompareDocuments
    matches: list[CompareMatch]
    categories: list[CompareCategory]
    downloads: CompareDownloads
    artifacts: CompareArtifacts
