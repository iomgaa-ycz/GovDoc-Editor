"""Ground truth 解析模块单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from govdoc.harness.ground_truth import parse_gold_checkpoints, parse_human_workpaper


def test_parse_gold_checkpoints_returns_52_items() -> None:
    """附件9 应解析出 52 个金标准审核点。"""
    path = Path("real_data/附件9 处理处罚标准.xls")
    if not path.exists():
        pytest.skip("real_data not available")
    items = parse_gold_checkpoints(path)
    assert len(items) == 52
    first = items[0]
    assert "title" in first
    assert "description" in first
    assert "category" in first
    assert first["description"] != ""


def test_parse_gold_checkpoints_categories() -> None:
    """金标准审核点应覆盖三个主要分类。"""
    path = Path("real_data/附件9 处理处罚标准.xls")
    if not path.exists():
        pytest.skip("real_data not available")
    items = parse_gold_checkpoints(path)
    categories = {item["category"] for item in items}
    assert "意向性招标" in categories
    assert "围标串标" in categories
    assert "不合理条件限制或排斥供应商" in categories


def test_parse_human_workpaper_extracts_summary() -> None:
    """人类工作底稿应提取出检查情况摘要。"""
    path = Path(
        "real_data/2023年度汕头市潮阳区流域面积50km²以下 "
        "河道管理范围划界工作服务项目/"
        "2023年度汕头市潮阳区流域面积50km²以下 "
        "河道管理范围划界工作服务项目.docx"
    )
    if not path.exists():
        pytest.skip("real_data not available")
    result = parse_human_workpaper(path)
    assert result["checked_unit"] == "广东策成工程咨询服务有限公司"
    assert "资信证书" in result["summary_text"]
    assert len(result["findings_text"]) >= 1


def test_parse_human_workpaper_missing_file() -> None:
    """不存在的文件应抛异常。"""
    with pytest.raises(Exception):
        parse_human_workpaper(Path("/nonexistent/file.docx"))
