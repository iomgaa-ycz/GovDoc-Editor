"""输出工具：三段结构 preprocess + json5.loads + validate。

设计基线：docs/v2-lessons-design-amendment.md §8 +
docs/superpowers/plans/2026-04-19-p1b-output-utils-json5.md。

P1b 重构要点：
- 用 ``json5.loads`` 取代 ``json.loads`` + 手写 trailing comma 剥离；
  json5 原生支持尾随逗号、单/双引号键、行与块注释等常见 LLM 输出瑕疵。
- ``_preprocess`` 负责 json5 无法处理的中文输出特性：markdown 围栏、
  中文弯引号、字符串内裸引号、中文结构标点（\uff0c/\uff1a/\u3001/\uff1b）。
- ``normalize_output`` / ``validate_*`` 保留原语义，不随 P1b 调整。
"""

from __future__ import annotations

import re
from typing import Any

import json5


def relaxed_json_loads(text: str) -> dict[str, Any]:
    """宽松 JSON 加载：预处理中文瑕疵后交给 ``json5.loads``。"""
    prepared = _preprocess(text)
    try:
        return json5.loads(prepared)
    except ValueError as exc:
        raise ValueError(f"JSON 解析失败（已尝试修复）: {exc}") from exc


def _preprocess(raw: str) -> str:
    """把含中文瑕疵的 LLM 输出整形为 json5 可解析的文本。"""
    text = raw.strip()
    if not text:
        raise ValueError("空字符串无法解析为 JSON")

    # 去除 markdown 代码块围栏（json5 不认识 ```json ... ```）。
    text = re.sub(r"^```(?:json5?)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()

    # 中文弯引号 → ASCII（键与字符串分隔符常被模型替换）。
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")

    # 字符串内裸双引号转义须先于结构标点标准化，避免误动正文。
    text = _escape_intra_string_quotes(text)

    # 字符串外的中文结构标点 → ASCII（json5 不接受 \uff0c 等为分隔符）。
    return _normalize_structural_punctuation(text)


def _normalize_structural_punctuation(text: str) -> str:
    """仅在字符串外标准化 JSON 结构标点（逗号/冒号/顿号/分号）。"""
    mapping = {"\uff0c": ",", "\uff1a": ":", "\u3001": ",", "\uff1b": ";"}
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
        result.append(mapping[ch] if (not in_string and ch in mapping) else ch)
        i += 1
    return "".join(result)


def _escape_intra_string_quotes(text: str) -> str:
    """修复字符串值内部的裸双引号（状态机区分终止符与正文）。"""
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
            elif _looks_like_string_terminator(text, i):
                in_string = False
                result.append(ch)
            else:
                result.append('\\"')
            i += 1
            continue
        result.append(ch)
        i += 1
    return "".join(result)


def _looks_like_string_terminator(text: str, quote_index: int) -> bool:
    """判断当前双引号更像是 JSON 字符串结束符，而非正文内引号。"""
    j = quote_index + 1
    while j < len(text) and text[j].isspace():
        j += 1
    if j >= len(text):
        return True
    next_char = text[j]
    if next_char in ":\uff1a" or next_char in "}]":
        return True
    if next_char not in ",\uff0c":
        return False
    k = j + 1
    while k < len(text) and text[k].isspace():
        k += 1
    if k >= len(text):
        return True
    return text[k] in '"{[-0123456789tfn}]'
