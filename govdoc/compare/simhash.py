"""SimHash 模糊段落匹配。

使用字符 bigram 作为特征，计算 64-bit SimHash 指纹，
通过汉明距离判断段落相似度。
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from itertools import combinations

MIN_PARAGRAPH_LENGTH = 8


@dataclass(frozen=True)
class SimilarParagraphMatch:
    """一对近似段落的匹配结果。"""

    text_a: str
    text_b: str
    file_index_a: int
    file_index_b: int
    paragraph_index_a: int
    paragraph_index_b: int
    distance: int
    similarity: float


def _token_hash(token: str) -> int:
    """对单个 token 计算 64-bit 哈希。"""
    digest = hashlib.md5(token.encode("utf-8")).digest()
    return struct.unpack("<Q", digest[:8])[0]


def compute_simhash(text: str) -> int:
    """计算文本的 64-bit SimHash 指纹。

    使用字符 bigram 作为特征。
    """
    if len(text) < 2:
        return 0

    weights = [0] * 64
    for i in range(len(text) - 1):
        bigram = text[i : i + 2]
        h = _token_hash(bigram)
        for bit in range(64):
            if h & (1 << bit):
                weights[bit] += 1
            else:
                weights[bit] -= 1

    fingerprint = 0
    for bit in range(64):
        if weights[bit] > 0:
            fingerprint |= 1 << bit
    return fingerprint


def hamming_distance(a: int, b: int) -> int:
    """计算两个 64-bit 整数的汉明距离。"""
    return bin(a ^ b).count("1")


def find_similar_paragraphs(
    all_paragraphs: dict[int, list[str]],
    threshold: int = 10,
    exact_matched_texts: set[str] | None = None,
) -> list[SimilarParagraphMatch]:
    """在 N 个文件间查找近似段落对。

    排除已被精确匹配覆盖的段落和过短段落。
    """
    exact_set = exact_matched_texts or set()

    by_file: dict[int, list[tuple[int, int, str]]] = {}
    for file_index in sorted(all_paragraphs):
        entries: list[tuple[int, int, str]] = []
        for para_index, text in enumerate(all_paragraphs[file_index]):
            if len(text) < MIN_PARAGRAPH_LENGTH:
                continue
            if text in exact_set:
                continue
            fp = compute_simhash(text)
            entries.append((para_index, fp, text))
        by_file[file_index] = entries

    matches: list[SimilarParagraphMatch] = []
    for file_a, file_b in combinations(sorted(by_file), 2):
        for para_idx_a, fp_a, text_a in by_file[file_a]:
            for para_idx_b, fp_b, text_b in by_file[file_b]:
                dist = hamming_distance(fp_a, fp_b)
                if dist <= threshold and text_a != text_b:
                    similarity = 1.0 - dist / 64.0
                    matches.append(
                        SimilarParagraphMatch(
                            text_a=text_a,
                            text_b=text_b,
                            file_index_a=file_a,
                            file_index_b=file_b,
                            paragraph_index_a=para_idx_a,
                            paragraph_index_b=para_idx_b,
                            distance=dist,
                            similarity=similarity,
                        )
                    )

    matches.sort(key=lambda m: (m.distance, m.file_index_a, m.paragraph_index_a))
    return matches
