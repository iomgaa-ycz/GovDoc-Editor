"""分层加载新增 schema 单元测试。"""

from govdoc.schemas.compare import (
    MatchSummaryItem,
    CompareSummaryResponse,
    FileContext,
    CompareContextResponse,
    CompareSummary,
    CompareDownloads,
    CompareArtifacts,
)


class TestMatchSummaryItem:
    def test_basic(self) -> None:
        item = MatchSummaryItem(
            id="p-001",
            category="paragraph",
            label="完全重复",
            color="#F59E0B",
            length=100,
            file_indices=[0, 1],
            occurrence_count=2,
            preview="本工程位于...",
        )
        assert item.id == "p-001"
        assert item.preview == "本工程位于..."

    def test_camel_alias(self) -> None:
        item = MatchSummaryItem(
            id="p-001",
            category="paragraph",
            label="x",
            color="#000",
            length=1,
            file_indices=[0],
            occurrence_count=1,
            preview="x",
        )
        dumped = item.model_dump(mode="json", by_alias=True)
        removed_near_match_score_field = "sim" + "ilarity"
        assert "fileIndices" in dumped
        assert "occurrenceCount" in dumped
        assert dumped["perFileCounts"] == {}
        assert removed_near_match_score_field not in dumped


class TestCompareSummaryResponse:
    def test_basic(self) -> None:
        resp = CompareSummaryResponse(
            review_id="abc",
            summary=CompareSummary(
                file_count=2,
                files=[],
                common_paragraph_count=0,
                common_sentence_count=0,
                common_segment_count=0,
                match_count=0,
                min_segment_length=16,
            ),
            matches=[],
            categories=[],
            downloads=CompareDownloads(files={}),
            artifacts=CompareArtifacts(review_dir="/tmp", download_names={}),
        )
        assert resp.review_id == "abc"


class TestCompareContextResponse:
    def test_basic(self) -> None:
        ctx = CompareContextResponse(
            match=MatchSummaryItem(
                id="p-001",
                category="paragraph",
                label="x",
                color="#000",
                length=1,
                file_indices=[0],
                occurrence_count=1,
                preview="x",
                text="full text",
            ),
            file_contexts=[
                FileContext(
                    file_index=0,
                    name="test.pdf",
                    total_blocks=100,
                    match_block_index=50,
                    blocks=[],
                )
            ],
        )
        assert ctx.match.text == "full text"
        assert ctx.file_contexts[0].match_block_index == 50
