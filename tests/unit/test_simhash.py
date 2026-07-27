"""SimHash 模糊段落匹配测试。"""

from __future__ import annotations

from govdoc.compare.simhash import (
    compute_simhash,
    find_similar_paragraphs,
    hamming_distance,
)


def test_identical_text_produces_same_hash() -> None:
    """完全相同的文本应产生相同的 SimHash。"""
    text = "具有良好的商业信誉和健全的财务会计制度"
    assert compute_simhash(text) == compute_simhash(text)


def test_similar_text_has_small_hamming_distance() -> None:
    """高度相似文本的汉明距离应远小于不同文本。"""
    a = "投标人应具有良好的商业信誉和健全的财务会计制度"
    b = "投标人须具有良好的商业信誉和健全的财务会计制度"
    dist = hamming_distance(compute_simhash(a), compute_simhash(b))
    assert dist <= 10


def test_different_text_has_large_hamming_distance() -> None:
    """完全不同文本的汉明距离应较大。"""
    a = "投标人应具有良好的商业信誉和健全的财务会计制度"
    b = "本项目采用公开招标方式选择承包商进行施工建设"
    dist = hamming_distance(compute_simhash(a), compute_simhash(b))
    assert dist > 10


def test_hamming_distance_zero_for_same_value() -> None:
    """相同值的汉明距离为 0。"""
    assert hamming_distance(0xABCD, 0xABCD) == 0


def test_hamming_distance_counts_differing_bits() -> None:
    """汉明距离应正确计算不同位数。"""
    assert hamming_distance(0b1111, 0b0000) == 4
    assert hamming_distance(0b1010, 0b0101) == 4


def test_find_similar_paragraphs_detects_near_duplicates() -> None:
    """应检测出高度相似但非完全相同的段落对。"""
    paragraphs_a = [
        "投标人应具有良好的商业信誉和健全的财务会计制度",
        "本项目不接受联合体投标",
        "完全不同的独有段落内容放在这里用来测试",
    ]
    paragraphs_b = [
        "投标人须具有良好的商业信誉和健全的财务会计制度",
        "本项目不接受联合体投标",
        "另一段完全无关的文字内容放在这里用来测试",
    ]
    exact_texts = {"本项目不接受联合体投标"}

    matches = find_similar_paragraphs(
        all_paragraphs={0: paragraphs_a, 1: paragraphs_b},
        threshold=10,
        exact_matched_texts=exact_texts,
    )

    assert len(matches) >= 1
    assert any("商业信誉" in m.text_a and "商业信誉" in m.text_b for m in matches)


def test_find_similar_paragraphs_excludes_exact_matches() -> None:
    """已被精确匹配覆盖的段落不应出现在模糊结果中。"""
    paragraphs = ["完全相同的段落内容用于测试去重逻辑"]
    matches = find_similar_paragraphs(
        all_paragraphs={0: paragraphs, 1: paragraphs},
        threshold=10,
        exact_matched_texts={"完全相同的段落内容用于测试去重逻辑"},
    )
    assert matches == []


def test_short_paragraphs_are_skipped() -> None:
    """过短的段落（< 8 字符）不参与模糊匹配。"""
    matches = find_similar_paragraphs(
        all_paragraphs={0: ["短文本"], 1: ["短文本"]},
        threshold=10,
        exact_matched_texts=set(),
    )
    assert matches == []
