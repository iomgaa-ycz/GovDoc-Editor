"""审查点表格导入解析模块单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from govdoc.parsers.checkpoint_import import parse_checkpoint_file
from govdoc.schemas import CheckpointCategory, GovCheckpoint, Severity

SAMPLE_XLS = Path("real_data/附件9 处理处罚标准.xls")


@pytest.fixture
def parsed_xls() -> tuple[list[GovCheckpoint], list[str]]:
    return parse_checkpoint_file(SAMPLE_XLS)


class TestParseCheckpointFile:
    def test_returns_non_empty_list(self, parsed_xls):
        checkpoints, _ = parsed_xls
        assert len(checkpoints) > 40

    def test_every_item_is_gov_checkpoint(self, parsed_xls):
        checkpoints, _ = parsed_xls
        for cp in checkpoints:
            assert isinstance(cp, GovCheckpoint)

    def test_no_empty_description(self, parsed_xls):
        checkpoints, _ = parsed_xls
        for cp in checkpoints:
            assert cp.description.strip()

    def test_no_empty_title(self, parsed_xls):
        checkpoints, _ = parsed_xls
        for cp in checkpoints:
            assert cp.title.strip()

    def test_forward_fill_category(self, parsed_xls):
        """All checkpoints should have a concrete category (not OTHER) for this sample file."""
        checkpoints, _ = parsed_xls
        for cp in checkpoints:
            assert cp.category != CheckpointCategory.OTHER

    def test_category_mapping(self, parsed_xls):
        checkpoints, _ = parsed_xls
        categories = {cp.category for cp in checkpoints}
        assert CheckpointCategory.UNREASONABLE_RESTRICTION in categories

    def test_default_severity(self, parsed_xls):
        checkpoints, _ = parsed_xls
        for cp in checkpoints:
            assert cp.severity == Severity.MAJOR

    def test_retrieval_hint_populated(self, parsed_xls):
        checkpoints, _ = parsed_xls
        for cp in checkpoints:
            assert cp.retrieval_hint
            assert len(cp.retrieval_hint) <= 80

    def test_legal_basis_parsed(self, parsed_xls):
        checkpoints, _ = parsed_xls
        first_with_legal = next((cp for cp in checkpoints if cp.legal_basis), None)
        assert first_with_legal is not None
        assert first_with_legal.legal_basis[0].law_name.strip()

    def test_unique_ids(self, parsed_xls):
        checkpoints, _ = parsed_xls
        ids = [cp.id for cp in checkpoints]
        assert len(ids) == len(set(ids))


class TestParseCSV:
    def test_csv_basic(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "大类,违法违规问题,表现形式,处理依据,处罚依据,处理建议,责任主体\n"
            "一、采购文件设置差别歧视条款,1.直接限制,设置供应商注册地限制,政府采购法第5条,,给予警告,采购人\n"
            ",2.限定行业,将特定行业作为条件,政府采购法第22条,,责令整改,代理机构\n",
            encoding="utf-8",
        )
        checkpoints, skipped = parse_checkpoint_file(csv_file)
        assert len(checkpoints) == 2
        assert checkpoints[0].title == "1.直接限制"
        assert checkpoints[1].category == checkpoints[0].category

    def test_csv_skip_empty_description(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "大类,违法违规问题,表现形式,处理依据,处罚依据,处理建议,责任主体\n"
            "一、限制条款,1.问题,,法条,,建议,主体\n"
            "一、限制条款,2.问题,有效表现形式,法条,,建议,主体\n",
            encoding="utf-8",
        )
        checkpoints, skipped = parse_checkpoint_file(csv_file)
        assert len(checkpoints) == 1
        assert len(skipped) == 1


class TestUnsupportedFormat:
    def test_reject_txt(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("hello")
        with pytest.raises(ValueError, match="不支持"):
            parse_checkpoint_file(txt_file)
