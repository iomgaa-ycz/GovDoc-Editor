"""文档对比响应 schema。"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict

from govdoc.schemas.common import GovDocModel


def _to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


CompareCategoryId = Literal["paragraph", "sentence", "similar"]


class CompareModel(GovDocModel):
    """文档对比 schema 基类，自动转换 snake_case → camelCase 别名。"""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )


class CompareCategory(CompareModel):
    """文档对比匹配类别。"""

    id: CompareCategoryId
    label: str
    color: str


class CompareFileMeta(CompareModel):
    """单个参与对比文件的元信息。"""

    file_index: int
    name: str
    suffix: str
    paragraph_count: int
    block_count: int


class CompareSummary(CompareModel):
    """N 文件对比摘要统计。"""

    file_count: int
    files: list[CompareFileMeta]
    common_paragraph_count: int
    common_sentence_count: int
    common_segment_count: int
    common_similar_count: int = 0
    match_count: int
    min_segment_length: int


class CompareBlockSegment(CompareModel):
    """前端渲染段落时的一段连续文本。"""

    text: str
    match_ids: list[str]
    categories: list[CompareCategoryId]
    primary_match_id: str | None = None


class CompareDocumentBlock(CompareModel):
    """前端渲染的单个段落块。"""

    id: str
    index: int
    text: str
    segments: list[CompareBlockSegment]


class CompareDocument(CompareModel):
    """前端渲染单个文件所需的段落块结构。"""

    file_index: int
    name: str
    suffix: str
    block_count: int
    blocks: list[CompareDocumentBlock]


class CompareDocuments(CompareModel):
    """所有参与对比的文件。"""

    files: list[CompareDocument]


class CompareOccurrenceSegment(CompareModel):
    """匹配范围落在某个段落块内的一段。"""

    file_index: int
    block_id: str
    block_index: int
    start: int
    end: int


class CompareOccurrence(CompareModel):
    """某个匹配在某个文件中的一次出现。"""

    file_index: int
    start: int
    end: int
    segments: list[CompareOccurrenceSegment]


class CompareMatch(CompareModel):
    """一条跨文件匹配记录。"""

    id: str
    category: CompareCategoryId
    label: str
    color: str
    text: str
    length: int
    file_indices: list[int]
    occurrences: dict[str, list[CompareOccurrence]]
    per_file_counts: dict[str, int]
    file_count: int
    occurrence_count: int
    similarity: float | None = None
    text_b: str | None = None


class CompareDownloads(CompareModel):
    """每个文件的高亮 DOCX 下载链接。"""

    files: dict[str, str]


class CompareArtifacts(CompareModel):
    """服务端生成物信息。"""

    review_dir: str
    download_names: dict[str, str]


class CompareResponse(CompareModel):
    """文档对比完整响应。"""

    review_id: str
    summary: CompareSummary
    documents: CompareDocuments
    matches: list[CompareMatch]
    categories: list[CompareCategory]
    downloads: CompareDownloads
    artifacts: CompareArtifacts


class CompareRunStatus(CompareModel):
    """对比任务状态响应。"""

    review_id: str
    status: str
    file_count: int
    file_names: list[str]
    progress: dict | None = None
    error: str | None = None
    created_at: str
    completed_at: str | None = None


class MatchSummaryItem(CompareModel):
    """摘要中的匹配项（无完整 text，只有 preview）。"""

    id: str
    category: CompareCategoryId
    label: str
    color: str
    length: int
    file_indices: list[int]
    occurrence_count: int
    preview: str
    text: str | None = None
    similarity: float | None = None


class CompareSummaryResponse(CompareModel):
    """分层加载摘要响应（不含 documents）。"""

    review_id: str
    summary: CompareSummary
    matches: list[MatchSummaryItem]
    categories: list[CompareCategory]
    downloads: CompareDownloads
    artifacts: CompareArtifacts


class FileContext(CompareModel):
    """单个文件的匹配上下文。"""

    file_index: int
    name: str
    total_blocks: int
    match_block_index: int
    blocks: list[CompareDocumentBlock]


class CompareContextResponse(CompareModel):
    """按需加载的匹配上下文响应。"""

    match: MatchSummaryItem
    file_contexts: list[FileContext]
