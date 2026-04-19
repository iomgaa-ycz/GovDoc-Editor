"""审查点表格导入解析器。

将 xls/xlsx/csv 格式的审查点表格解析为 GovCheckpoint 列表。
"""

from __future__ import annotations

import csv
import re
import uuid
from pathlib import Path

from govdoc.schemas import (
    CheckpointCategory,
    GovCheckpoint,
    LegalBasis,
    Severity,
)

_HEADER_KEYWORDS = {"违法违规问题", "表现形式", "处理依据"}

# 关键词 → 类别映射，按优先级排列
# 覆盖样本文件中实际出现的4个大类：
#   一、采购文件设置差别歧视条款  → UNREASONABLE_RESTRICTION
#   二、代理机构乱收费            → INTENTIONAL_BIDDING（意向性招标/程序违规）
#   三、供应商提供虚假材料        → INTENTIONAL_BIDDING（意向性欺诈投标）
#   四、供应商围标串标            → COLLUSION
_CATEGORY_MAP: list[tuple[list[str], CheckpointCategory]] = [
    (
        ["围标", "串标", "串通"],
        CheckpointCategory.COLLUSION,
    ),
    (
        ["歧视", "限制", "排斥", "差别"],
        CheckpointCategory.UNREASONABLE_RESTRICTION,
    ),
    (
        ["虚假材料", "虚假", "材料谋取", "意向"],
        CheckpointCategory.INTENTIONAL_BIDDING,
    ),
    (
        ["代理机构", "乱收费", "收费", "保证金", "服务费", "文件费"],
        CheckpointCategory.INTENTIONAL_BIDDING,
    ),
]

_LEGAL_SPLIT_RE = re.compile(r"[，,、;\n]+")


def parse_checkpoint_file(
    path: Path,
) -> tuple[list[GovCheckpoint], list[str]]:
    """解析审查点表格文件。

    支持 .xls / .xlsx / .csv 三种格式。解析过程：
    1. 跳过标题行，找到包含"违法违规问题"等关键词的表头行
    2. 对后续数据行进行前向填充（处理合并单元格）
    3. 跳过表现形式（描述）为空的行
    4. 根据大类关键词映射 CheckpointCategory

    Args:
        path: xls/xlsx/csv 文件路径。

    Returns:
        (checkpoints, skipped_reasons) 二元组：
        - checkpoints: 解析出的 GovCheckpoint 列表
        - skipped_reasons: 跳过行的原因说明列表

    Raises:
        ValueError: 文件格式不支持（非 .xls/.xlsx/.csv）。
    """
    suffix = path.suffix.lower()
    if suffix == ".xls":
        rows = _read_xls(path)
    elif suffix == ".xlsx":
        rows = _read_xlsx(path)
    elif suffix == ".csv":
        rows = _read_csv(path)
    else:
        raise ValueError(f"不支持的文件格式: {suffix}，仅支持 .xls / .xlsx / .csv")

    return _rows_to_checkpoints(rows)


def _read_xls(path: Path) -> list[list[str]]:
    """读取 .xls 文件返回字符串二维列表。"""
    import xlrd

    wb = xlrd.open_workbook(str(path))
    sh = wb.sheet_by_index(0)
    rows: list[list[str]] = []
    for r in range(sh.nrows):
        row = [str(sh.cell_value(r, c)).strip() for c in range(sh.ncols)]
        rows.append(row)
    return rows


def _read_xlsx(path: Path) -> list[list[str]]:
    """读取 .xlsx 文件返回字符串二维列表。"""
    import openpyxl

    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    sh = wb.active
    rows: list[list[str]] = []
    for row in sh.iter_rows(values_only=True):
        rows.append([str(c).strip() if c is not None else "" for c in row])
    wb.close()
    return rows


def _read_csv(path: Path) -> list[list[str]]:
    """读取 .csv 文件返回字符串二维列表。"""
    rows: list[list[str]] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append([c.strip() for c in row])
    return rows


def _is_header_row(row: list[str]) -> bool:
    """判断是否为表头行（包含关键列名）。"""
    text = "".join(row)
    return any(kw in text for kw in _HEADER_KEYWORDS)


def _classify_category(raw: str) -> CheckpointCategory:
    """根据大类文本关键词映射到 CheckpointCategory。

    Args:
        raw: 大类列原始文本（含前向填充后的完整大类标题）。

    Returns:
        最匹配的 CheckpointCategory，无匹配时返回 OTHER。
    """
    for keywords, category in _CATEGORY_MAP:
        if any(kw in raw for kw in keywords):
            return category
    return CheckpointCategory.OTHER


def _parse_legal_basis(text: str) -> list[LegalBasis]:
    """将法条文本拆分为 LegalBasis 列表。

    Args:
        text: 处理依据或处罚依据列的原始文本。

    Returns:
        LegalBasis 列表，text 为空时返回空列表。
    """
    if not text.strip():
        return []
    parts = _LEGAL_SPLIT_RE.split(text.strip())
    return [
        LegalBasis(law_name=p.strip(), article="", quote="")
        for p in parts
        if p.strip()
    ]


def _rows_to_checkpoints(
    rows: list[list[str]],
) -> tuple[list[GovCheckpoint], list[str]]:
    """将二维字符串行列表转换为 GovCheckpoint 列表。

    处理逻辑：
    - 跳过表头行之前的所有行
    - 对每列进行前向填充（处理合并单元格为空的情况）
    - 跳过表现形式（第2列）为空的行，记录到 skipped
    - 为每条记录生成 uuid hex 作为唯一 id

    Args:
        rows: 从文件读取的字符串二维列表。

    Returns:
        (checkpoints, skipped_reasons) 二元组。
    """
    checkpoints: list[GovCheckpoint] = []
    skipped: list[str] = []

    header_found = False
    ncols = max((len(r) for r in rows), default=0)
    # 前向填充状态：记录每列上一个非空值
    prev: list[str] = [""] * ncols

    for row_idx, raw_row in enumerate(rows):
        # 补齐到 ncols 列
        row = raw_row + [""] * (ncols - len(raw_row))

        if not header_found:
            if _is_header_row(row):
                header_found = True
            continue

        # 前向填充：只填充大类（第0列）和违法违规问题（第1列）
        # 其他列（表现形式等）每行独立，不做前向填充
        for i in range(min(2, ncols)):
            if row[i]:
                prev[i] = row[i]
            else:
                row[i] = prev[i]

        description = row[2] if len(row) > 2 else ""
        if not description.strip():
            skipped.append(f"第{row_idx + 1}行：表现形式为空")
            continue

        category_raw = row[0] if len(row) > 0 else ""
        title = row[1] if len(row) > 1 else ""
        legal_text_1 = row[3] if len(row) > 3 else ""
        legal_text_2 = row[4] if len(row) > 4 else ""

        legal_basis = _parse_legal_basis(legal_text_1) + _parse_legal_basis(legal_text_2)

        cp = GovCheckpoint(
            id=uuid.uuid4().hex,
            category=_classify_category(category_raw),
            title=title or description[:40],
            description=description,
            legal_basis=legal_basis,
            severity=Severity.MAJOR,
            retrieval_hint=description[:80],
        )
        checkpoints.append(cp)

    return checkpoints, skipped
