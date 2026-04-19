"""输出工具：relaxed JSON 修复 + 输出 normalize + 业务级校验。

设计基线：docs/v2-lessons-design-amendment.md §8。
"""

from __future__ import annotations

import json
import re
from typing import Any


def relaxed_json_loads(text: str) -> dict[str, Any]:
    """宽松 JSON 加载：修复常见 LLM 输出问题。"""
    text = text.strip()
    if not text:
        raise ValueError("空字符串无法解析为 JSON")

    # 移除 markdown 代码块包裹
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()

    # 先统一弯引号；逗号/冒号等结构标点只在字符串外替换，避免破坏正文
    text = text.replace("\u201c", '"').replace("\u201d", '"')  # ""
    text = text.replace("\u2018", "'").replace("\u2019", "'")  # ''

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    normalized = _strip_trailing_commas(_normalize_structural_punctuation(text))
    try:
        return json.loads(normalized)
    except json.JSONDecodeError:
        pass

    # 字符串内裸引号修复；修复后再做结构标点标准化，避免正文被误改
    repaired = _escape_intra_string_quotes(text)
    repaired = _strip_trailing_commas(_normalize_structural_punctuation(repaired))
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 解析失败（已尝试修复）: {exc}") from exc


def _normalize_structural_punctuation(text: str) -> str:
    """只在字符串外标准化 JSON 结构标点。"""
    mapping = {
        "\uff0c": ",",  # ，
        "\uff1a": ":",  # ：
        "\u3001": ",",  # 、
        "\uff1b": ";",  # ；
    }

    result: list[str] = []
    i = 0
    in_string = False
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            result.append(ch)
            result.append(text[i + 1])
            i += 2
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            i += 1
            continue
        if not in_string and ch in mapping:
            result.append(mapping[ch])
        else:
            result.append(ch)
        i += 1
    return "".join(result)


def _strip_trailing_commas(text: str) -> str:
    """删除对象/数组末尾的结构逗号，不改字符串正文。"""
    result: list[str] = []
    i = 0
    in_string = False
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            result.append(ch)
            result.append(text[i + 1])
            i += 2
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            i += 1
            continue
        if not in_string and ch == ",":
            j = i + 1
            while j < len(text) and text[j].isspace():
                j += 1
            if j < len(text) and text[j] in "}]":
                i += 1
                continue
        result.append(ch)
        i += 1
    return "".join(result)


def _escape_intra_string_quotes(text: str) -> str:
    """尝试修复字符串值内部的裸双引号。"""
    result: list[str] = []
    i = 0
    in_string = False
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            result.append(ch)
            result.append(text[i + 1])
            i += 2
            continue
        if ch == '"':
            if not in_string:
                in_string = True
                result.append(ch)
            else:
                if _looks_like_string_terminator(text, i):
                    in_string = False
                    result.append(ch)
                else:
                    # 可能是字符串内的裸引号，转义它
                    result.append('\\"')
            i += 1
            continue
        result.append(ch)
        i += 1
    return "".join(result)


def _looks_like_string_terminator(text: str, quote_index: int) -> bool:
    """判断当前位置的双引号更像是 JSON 字符串结束符，而非正文内引号。"""
    j = quote_index + 1
    while j < len(text) and text[j].isspace():
        j += 1
    if j >= len(text):
        return True

    next_char = text[j]
    if next_char in ":\uff1a":
        return True
    if next_char in "}]":
        return True
    if next_char not in ",\uff0c":
        return False

    k = j + 1
    while k < len(text) and text[k].isspace():
        k += 1
    if k >= len(text):
        return True

    return text[k] in '"{[-0123456789tfn}]'


def normalize_output(data: dict[str, Any]) -> dict[str, Any]:
    """输出 normalize：统一字段名和结构。"""
    if "checkpoints" in data and isinstance(data["checkpoints"], list):
        for cp in data["checkpoints"]:
            if isinstance(cp, dict):
                cp.setdefault("id", "")
                cp.setdefault("category", "")
                cp.setdefault("title", "")
                cp.setdefault("description", "")
                cp.setdefault("severity", "minor")
                cp.setdefault("retrieval_hint", "")
                cp.setdefault("legal_basis", [])
    if "findings" in data and isinstance(data["findings"], list):
        for f in data["findings"]:
            if isinstance(f, dict):
                f.setdefault("checkpoint", {})
                f.setdefault("verdict", {})
                f.setdefault("evidence_refs", [])
                f.setdefault("case_refs", [])
    return data


def validate_extractor_output(data: dict[str, Any]) -> list[str]:
    """校验 Pipeline A 输出的业务级完整性。返回错误列表。"""
    errors: list[str] = []
    checkpoints = data.get("checkpoints")
    if not isinstance(checkpoints, list):
        errors.append("缺少 checkpoints 或不是列表")
        return errors
    for i, cp in enumerate(checkpoints):
        if not isinstance(cp, dict):
            errors.append(f"checkpoints[{i}] 不是对象")
            continue
        for field in ("id", "title", "category"):
            if not cp.get(field):
                errors.append(f"checkpoints[{i}] 缺少 {field}")
        legal_basis = cp.get("legal_basis")
        if not isinstance(legal_basis, list):
            errors.append(f"checkpoints[{i}].legal_basis 不是列表")
    return errors


def validate_auditor_output(data: dict[str, Any]) -> list[str]:
    """校验 Pipeline B 输出的业务级完整性。返回错误列表。"""
    errors: list[str] = []
    findings = data.get("findings")
    if not isinstance(findings, list):
        errors.append("缺少 findings 或不是列表")
        return errors
    if not findings:
        errors.append("findings 为空")
    for i, f in enumerate(findings):
        if not isinstance(f, dict):
            errors.append(f"findings[{i}] 不是对象")
            continue
        checkpoint = f.get("checkpoint")
        if not isinstance(checkpoint, dict) or not checkpoint.get("id"):
            errors.append(f"findings[{i}] 缺少 checkpoint.id")
        verdict = f.get("verdict")
        if not isinstance(verdict, dict) or not verdict.get("verdict"):
            errors.append(f"findings[{i}] 缺少 verdict.verdict")
    return errors
