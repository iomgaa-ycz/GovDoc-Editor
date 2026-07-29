"""SimHash 模糊段落聚类匹配。

使用字符 bigram 计算 64-bit SimHash 指纹，跨文件以汉明距离阈值查找近似段落，
再用并查集压缩为跨文件聚类，避免保存海量 pair 文本。
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from itertools import combinations

import numpy as np
from numpy.typing import NDArray

# 短于 8 字符的段落（页码、序号等碎片）指纹区分度过低，直接跳过
MIN_PARAGRAPH_LENGTH = 8
# 单块 XOR 矩阵内存 = 4096 × 对侧段落数 × 8B（uint64），万段级文件单块约 300MB，安全可控
SIMHASH_BLOCK_SIZE = 4096
# 候选对仅存整数索引（约 32B/对），5000 万对 ≈ 1.6GB，远超正常规模（真实 9 文件事故数据实测 269 万对）
MAX_CANDIDATE_PAIRS = 50_000_000

_POPCOUNT_TABLE = np.array([int(value).bit_count() for value in range(256)], dtype=np.uint8)


class CompareTooComplexError(Exception):
    """对比规模超出安全上限。

    参数:
        message: 面向律师用户的错误说明。

    关键实现细节:
        当近似候选对数量过大时主动熔断，避免后端进程继续消耗内存。
    """


@dataclass(frozen=True)
class SimilarParagraphCluster:
    """近似段落聚类结果。

    参数:
        members: 组内成员，格式为 ``(file_index, paragraph_index)``，按升序排列。
        representative_file: 代表段落所在文件索引。
        representative_paragraph: 代表段落在文件内的段落索引。

    关键实现细节:
        代表段落选择组内文本最长者；若长度相同，使用成员升序保证稳定输出。
    """

    members: list[tuple[int, int]]
    representative_file: int
    representative_paragraph: int


@dataclass(frozen=True)
class _FingerprintBatch:
    """单文件过滤后的 SimHash 指纹与原段落索引。"""

    fingerprints: NDArray[np.uint64]
    paragraph_indices: NDArray[np.int64]


class _UnionFind:
    """路径压缩并查集，用于把近似候选边聚成连通组。"""

    def __init__(self, size: int) -> None:
        """初始化指定节点数的并查集。

        参数:
            size: 节点总数。
        """
        self._parent = list(range(size))
        self._rank = [0] * size

    def find(self, node: int) -> int:
        """返回节点根节点，并执行路径压缩。

        参数:
            node: 待查询节点。

        返回值:
            节点所属连通分量根节点。
        """
        parent = self._parent[node]
        if parent != node:
            parent = self.find(parent)
            self._parent[node] = parent
        return parent

    def union(self, left: int, right: int) -> None:
        """合并两个节点所在连通分量。

        参数:
            left: 左节点编号。
            right: 右节点编号。
        """
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left == root_right:
            return
        if self._rank[root_left] < self._rank[root_right]:
            self._parent[root_left] = root_right
        elif self._rank[root_left] > self._rank[root_right]:
            self._parent[root_right] = root_left
        else:
            self._parent[root_right] = root_left
            self._rank[root_left] += 1


def _token_hash(token: str) -> int:
    """对单个 token 计算 64-bit 哈希。

    参数:
        token: 字符 bigram。

    返回值:
        小端解释的 64-bit 整数哈希。
    """
    digest = hashlib.md5(token.encode("utf-8")).digest()
    return struct.unpack("<Q", digest[:8])[0]


def compute_simhash(text: str) -> int:
    """计算文本的 64-bit SimHash 指纹。

    参数:
        text: 待计算文本。

    返回值:
        64-bit SimHash 整数；长度小于 2 的文本返回 0。

    关键实现细节:
        沿用字符 bigram 特征，保证与历史算法语义一致。
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
    """计算两个 64-bit 整数的汉明距离。

    参数:
        a: 第一个整数。
        b: 第二个整数。

    返回值:
        ``a ^ b`` 中置位 bit 的数量。
    """
    return (a ^ b).bit_count()


def _bitwise_popcount(values: NDArray[np.uint64]) -> NDArray[np.uint8]:
    """批量计算 uint64 数组每个元素的 bit 数。

    参数:
        values: 任意形状的 ``np.uint64`` 数组。

    返回值:
        与输入同形状的 popcount 数组。

    关键实现细节:
        numpy 2 提供 ``np.bitwise_count``；旧版本使用 uint8 查表回退。
    """
    if hasattr(np, "bitwise_count"):
        return np.bitwise_count(values)

    byte_counts = _POPCOUNT_TABLE[values.view(np.uint8)]
    return byte_counts.reshape(*values.shape, 8).sum(axis=-1).astype(np.uint8)


def _build_fingerprint_batches(
    all_paragraphs: dict[int, list[str]],
    exact_set: set[str],
) -> tuple[dict[int, _FingerprintBatch], dict[tuple[int, int], int]]:
    """按文件构建过滤后的 SimHash 指纹数组。

    参数:
        all_paragraphs: ``file_index -> 段落文本列表``。
        exact_set: 已由精确匹配层覆盖的文本集合。

    返回值:
        文件指纹批次，以及 ``(file_index, paragraph_index) -> 并查集节点`` 映射。
    """
    batches: dict[int, _FingerprintBatch] = {}
    node_ids: dict[tuple[int, int], int] = {}
    next_node_id = 0

    for file_index in sorted(all_paragraphs):
        fingerprints: list[int] = []
        paragraph_indices: list[int] = []
        for paragraph_index, text in enumerate(all_paragraphs[file_index]):
            if len(text) < MIN_PARAGRAPH_LENGTH or text in exact_set:
                continue
            fingerprints.append(compute_simhash(text))
            paragraph_indices.append(paragraph_index)
            node_ids[(file_index, paragraph_index)] = next_node_id
            next_node_id += 1
        batches[file_index] = _FingerprintBatch(
            fingerprints=np.array(fingerprints, dtype=np.uint64),
            paragraph_indices=np.array(paragraph_indices, dtype=np.int64),
        )

    return batches, node_ids


def _raise_too_complex() -> None:
    """抛出统一的对比复杂度熔断异常。"""
    raise CompareTooComplexError("对比文件间相似内容过多，已安全终止，请减少文件数量后重试")


def _union_candidate_pairs(
    all_paragraphs: dict[int, list[str]],
    batches: dict[int, _FingerprintBatch],
    node_ids: dict[tuple[int, int], int],
    threshold: int,
    union_find: _UnionFind,
) -> int:
    """分块查找跨文件候选对，并把候选边合并到并查集。

    参数:
        all_paragraphs: 原始段落文本，候选阶段只在排除等文本时按索引读取。
        batches: 每个文件的指纹数组。
        node_ids: 段落成员到并查集节点的映射。
        threshold: SimHash 汉明距离阈值。
        union_find: 待更新的并查集。

    返回值:
        通过阈值且非等文本的候选对数量。

    关键实现细节:
        内存上界由 ``SIMHASH_BLOCK_SIZE`` 控制：单块 XOR 矩阵峰值约
        ``block_size × len(file_b) × 8`` 字节（uint64），popcount 结果另占
        每元素 1 字节；候选边不保存文本，直接以整数节点合并，
        因此零近似语义与逐对汉明距离判断一致。
    """
    candidate_count = 0
    for file_a, file_b in combinations(sorted(batches), 2):
        batch_a = batches[file_a]
        batch_b = batches[file_b]
        if len(batch_a.fingerprints) == 0 or len(batch_b.fingerprints) == 0:
            continue

        for start in range(0, len(batch_a.fingerprints), SIMHASH_BLOCK_SIZE):
            stop = min(start + SIMHASH_BLOCK_SIZE, len(batch_a.fingerprints))
            xor_values = batch_a.fingerprints[start:stop, None] ^ batch_b.fingerprints[None, :]
            row_indices, col_indices = np.nonzero(_bitwise_popcount(xor_values) <= threshold)
            if candidate_count + len(row_indices) > MAX_CANDIDATE_PAIRS:
                _raise_too_complex()

            for row_offset, col_offset in zip(
                row_indices.tolist(), col_indices.tolist(), strict=True
            ):
                para_a = int(batch_a.paragraph_indices[start + row_offset])
                para_b = int(batch_b.paragraph_indices[col_offset])
                if all_paragraphs[file_a][para_a] == all_paragraphs[file_b][para_b]:
                    continue

                candidate_count += 1
                union_find.union(node_ids[(file_a, para_a)], node_ids[(file_b, para_b)])

    return candidate_count


def _build_clusters(
    all_paragraphs: dict[int, list[str]],
    node_ids: dict[tuple[int, int], int],
    union_find: _UnionFind,
) -> list[SimilarParagraphCluster]:
    """把并查集连通分量转换为稳定排序的近似段落聚类。

    参数:
        all_paragraphs: 原始段落文本。
        node_ids: 段落成员到并查集节点的映射。
        union_find: 已合并候选边的并查集。

    返回值:
        覆盖至少两个不同文件的聚类列表。
    """
    groups_by_root: dict[int, list[tuple[int, int]]] = {}
    for member, node_id in node_ids.items():
        groups_by_root.setdefault(union_find.find(node_id), []).append(member)

    clusters: list[SimilarParagraphCluster] = []
    for members in groups_by_root.values():
        files = {file_index for file_index, _ in members}
        if len(files) < 2:
            continue

        sorted_members = sorted(members)
        representative = max(
            sorted_members,
            key=lambda member: (len(all_paragraphs[member[0]][member[1]]), -member[0], -member[1]),
        )
        clusters.append(
            SimilarParagraphCluster(
                members=sorted_members,
                representative_file=representative[0],
                representative_paragraph=representative[1],
            )
        )

    clusters.sort(
        key=lambda cluster: (
            -len(all_paragraphs[cluster.representative_file][cluster.representative_paragraph]),
            cluster.members[0],
        )
    )
    return clusters


def find_similar_paragraphs(
    all_paragraphs: dict[int, list[str]],
    threshold: int = 10,
    exact_matched_texts: set[str] | None = None,
) -> list[SimilarParagraphCluster]:
    """在 N 个文件间查找近似段落聚类。

    参数:
        all_paragraphs: ``file_index -> 段落文本列表``。
        threshold: 64-bit SimHash 汉明距离阈值，语义与旧逐对算法一致。
        exact_matched_texts: 已由精确匹配层覆盖的文本集合，这些文本不参与模糊匹配。

    返回值:
        覆盖至少两个不同文件的近似段落聚类列表。

    关键实现细节:
        先按文件过滤过短文本和 exact 文本，再使用 numpy 对跨文件指纹做分块全量
        汉明距离比较；候选边只携带文件/段落整数索引，不保存段落文本。该实现没有
        LSH 或采样近似，输出语义与逐对全叉积比较零近似一致；单块内存由
        ``SIMHASH_BLOCK_SIZE`` 限定，候选规模超过 ``MAX_CANDIDATE_PAIRS`` 时熔断。
    """
    exact_set = exact_matched_texts or set()
    batches, node_ids = _build_fingerprint_batches(all_paragraphs, exact_set)
    if not node_ids:
        return []

    union_find = _UnionFind(len(node_ids))
    _union_candidate_pairs(
        all_paragraphs=all_paragraphs,
        batches=batches,
        node_ids=node_ids,
        threshold=threshold,
        union_find=union_find,
    )
    return _build_clusters(all_paragraphs, node_ids, union_find)
