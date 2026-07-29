"""SimHash 模糊段落聚类测试。"""

from __future__ import annotations

import random
from itertools import combinations

import numpy as np
import pytest

from govdoc.compare import simhash
from govdoc.compare.simhash import (
    CompareTooComplexError,
    SimilarParagraphCluster,
    compute_simhash,
    find_similar_paragraphs,
    hamming_distance,
)


def _bruteforce_pairs(
    all_paragraphs: dict[int, list[str]],
    threshold: int,
    exact_texts: set[str],
) -> set[tuple[tuple[int, int], tuple[int, int]]]:
    """用纯 Python 逐对比较生成跨文件近似成员对。"""
    candidates: dict[int, list[tuple[int, int, str]]] = {}
    for file_index, paragraphs in all_paragraphs.items():
        candidates[file_index] = [
            (para_index, compute_simhash(text), text)
            for para_index, text in enumerate(paragraphs)
            if len(text) >= simhash.MIN_PARAGRAPH_LENGTH and text not in exact_texts
        ]

    pairs: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for file_a, file_b in combinations(sorted(candidates), 2):
        for para_a, fp_a, left_text in candidates[file_a]:
            for para_b, fp_b, right_text in candidates[file_b]:
                if left_text != right_text and hamming_distance(fp_a, fp_b) <= threshold:
                    pairs.add(((file_a, para_a), (file_b, para_b)))
    return pairs


def _cluster_pairs(
    clusters: list[SimilarParagraphCluster],
    all_paragraphs: dict[int, list[str]],
    threshold: int,
) -> set[tuple[tuple[int, int], tuple[int, int]]]:
    """把聚类展开为组内真实满足阈值的跨文件成员对。"""
    pairs: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for cluster in clusters:
        for left, right in combinations(cluster.members, 2):
            if left[0] == right[0]:
                continue
            text_left = all_paragraphs[left[0]][left[1]]
            text_right = all_paragraphs[right[0]][right[1]]
            if text_left == text_right:
                continue
            if (
                hamming_distance(compute_simhash(text_left), compute_simhash(text_right))
                <= threshold
            ):
                pairs.add((left, right) if left < right else (right, left))
    return pairs


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


def test_vectorized_clusters_match_bruteforce_pairs() -> None:
    """固定随机小样本上，向量化聚类展开结果应等于暴力逐对结果。"""
    random.seed(20260729)
    all_paragraphs: dict[int, list[str]] = {}
    base = "投标人应具有良好的商业信誉和健全的财务会计制度，且依法缴纳税收。"
    exact = "本项目不接受联合体投标，资格后审。"
    for file_index in range(3):
        paragraphs = [
            f"文件{file_index}随机段落{idx:03d}，采购需求和评分办法内容互不相同。"
            for idx in range(76)
        ]
        paragraphs.extend(
            [
                base.replace("应", "须") if file_index == 1 else base.replace("依法", "按规定"),
                exact,
                f"短{file_index}",
                f"完全独立补充条款{random.randint(1000, 9999)}。",
            ]
        )
        random.shuffle(paragraphs)
        all_paragraphs[file_index] = paragraphs

    exact_texts = {exact}
    clusters = find_similar_paragraphs(
        all_paragraphs, threshold=10, exact_matched_texts=exact_texts
    )

    assert _cluster_pairs(clusters, all_paragraphs, 10) == _bruteforce_pairs(
        all_paragraphs, 10, exact_texts
    )


def test_known_cluster_members_and_representative() -> None:
    """已知三文件近似段落应聚成一组，并以最长文本为代表。"""
    all_paragraphs = {
        0: ["投标人应具有良好的商业信誉和健全的财务会计制度"],
        1: ["投标人须具有良好的商业信誉和健全的财务会计制度"],
        2: ["投标人应具有良好的商业信誉和健全的财务会计制度并提供承诺函"],
    }

    clusters = find_similar_paragraphs(all_paragraphs, threshold=12)

    assert len(clusters) == 1
    assert clusters[0].members == [(0, 0), (1, 0), (2, 0)]
    assert (clusters[0].representative_file, clusters[0].representative_paragraph) == (2, 0)


def test_candidate_pair_circuit_breaker(monkeypatch: pytest.MonkeyPatch) -> None:
    """候选对超过熔断阈值时应抛出面向用户的具名异常。"""
    monkeypatch.setattr(simhash, "MAX_CANDIDATE_PAIRS", 1)
    paragraphs = {
        0: ["投标人应具有良好的商业信誉和健全的财务会计制度"] * 2,
        1: ["投标人须具有良好的商业信誉和健全的财务会计制度"] * 2,
    }

    with pytest.raises(CompareTooComplexError, match="相似内容过多"):
        find_similar_paragraphs(paragraphs, threshold=64)


def test_same_file_only_near_duplicate_is_not_returned() -> None:
    """纯同文件近似段落不应产生跨文件聚类。"""
    paragraphs = {
        0: [
            "投标人应具有良好的商业信誉和健全的财务会计制度",
            "投标人须具有良好的商业信誉和健全的财务会计制度",
        ],
        1: ["本项目采用公开招标方式选择承包商进行施工建设"],
    }

    assert find_similar_paragraphs(paragraphs, threshold=10) == []


def test_exact_matches_are_excluded_from_similar_clusters() -> None:
    """已被精确层覆盖的段落不应进入模糊聚类。"""
    paragraphs = ["完全相同的段落内容用于测试去重逻辑"]
    clusters = find_similar_paragraphs(
        all_paragraphs={0: paragraphs, 1: paragraphs},
        threshold=10,
        exact_matched_texts={"完全相同的段落内容用于测试去重逻辑"},
    )
    assert clusters == []


def test_popcount_lookup_fallback_matches_numpy_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    """numpy 无 bitwise_count 时，uint8 查表回退应与主路径结果一致。"""
    values = np.array([0, 1, 3, 0xFFFFFFFFFFFFFFFF, 0x123456789ABCDEF0], dtype=np.uint64)
    expected = simhash._bitwise_popcount(values)
    monkeypatch.delattr(simhash.np, "bitwise_count", raising=False)

    assert simhash._bitwise_popcount(values).tolist() == expected.tolist()
