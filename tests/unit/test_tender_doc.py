from govdoc.parsers.tender_doc import locate_section, parse


def test_parse_tender_splits_known_sections():
    md = """# 资格要求
供应商应具备相关资质。

# 评分办法
采用综合评分法。

# 合同条款
合同签订后 30 日内履约。
"""
    structure = parse(md)
    assert [item.name for item in structure.sections] == ["资格要求", "评分办法", "合同条款"]


def test_locate_section_returns_none_when_missing():
    assert locate_section("无明确章节", "评分办法") is None
