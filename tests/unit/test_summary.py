"""generate_summary 公共函数单测。"""

from govdoc.pipelines.summary import generate_summary
from govdoc.schemas import GovCheckpoint, GovFinding, GovFindingVerdict


def _make_finding(verdict_value: str) -> GovFinding:
    return GovFinding(
        checkpoint=GovCheckpoint(
            id="cp_01",
            category="其他违法违规",
            title="test",
            description="desc",
            severity="minor",
            retrieval_hint="hint",
        ),
        verdict=GovFindingVerdict(verdict=verdict_value, rationale="r"),
    )


def test_generate_summary_empty():
    assert generate_summary([]) == "无审核结果。"


def test_generate_summary_mixed():
    findings = [_make_finding("合规"), _make_finding("不合规"), _make_finding("存疑")]
    result = generate_summary(findings)
    assert "共审核 3 个审核点" in result
    assert "不合规 1 项" in result
    assert "合规 1 项" in result
    assert "存疑 1 项" in result
