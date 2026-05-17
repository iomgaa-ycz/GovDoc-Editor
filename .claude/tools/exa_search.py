"""Exa 搜索命令行工具。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, is_dataclass
from typing import Any

try:
    import exa
except ImportError:
    print("警告: 未安装 exa-py SDK，已跳过 Exa CLI。", file=sys.stderr)
    sys.exit(0)


def _to_jsonable(value: Any) -> Any:
    """将任意 SDK 返回值递归转换为可序列化对象。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _to_jsonable(model_dump())
    if hasattr(value, "__dict__"):
        data = {
            key: _to_jsonable(item) for key, item in vars(value).items() if not key.startswith("_")
        }
        if data:
            return data
    return str(value)


def _build_contents_option(content_mode: str) -> dict[str, Any]:
    """根据命令行参数构造 Exa contents 配置。"""
    if content_mode == "text":
        return {"text": True}
    return {"highlights": True}


def _extract_results(response: Any) -> list[dict[str, Any]]:
    """从 Exa 响应中提取结果列表并标准化为 JSON 对象。"""
    raw_results: Any
    if isinstance(response, dict):
        raw_results = response.get("results", [])
    else:
        raw_results = getattr(response, "results", [])

    if not isinstance(raw_results, list):
        return []

    normalized_results: list[dict[str, Any]] = []
    for item in raw_results:
        normalized_item = _to_jsonable(item)
        if isinstance(normalized_item, dict):
            normalized_results.append(normalized_item)
        else:
            normalized_results.append({"value": normalized_item})
    return normalized_results


def search_exa(
    query: str,
    max_results: int,
    category: str | None,
    content_mode: str,
) -> list[dict[str, Any]]:
    """执行 Exa 搜索并返回结果列表。"""
    api_key = os.environ.get("EXA_API_KEY", "").strip()
    if not api_key:
        print("警告: 缺少 EXA_API_KEY 环境变量，已跳过 Exa CLI。", file=sys.stderr)
        sys.exit(0)

    client = exa.Exa(api_key=api_key)
    search_kwargs: dict[str, Any] = {
        "num_results": max_results,
        "contents": _build_contents_option(content_mode),
    }
    if category:
        search_kwargs["category"] = category

    response = client.search(query, **search_kwargs)
    return _extract_results(response)


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="Exa 搜索工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="搜索 Exa 索引")
    search_parser.add_argument("query", help="搜索关键词")
    search_parser.add_argument("--max", dest="max_results", type=int, default=10)
    search_parser.add_argument(
        "--category",
        default=None,
        help="数据类别，例如 research paper、news、pdf 等",
    )
    search_parser.add_argument(
        "--content",
        choices=("highlights", "text"),
        default="highlights",
        help="返回的内容类型",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "search":
            results = search_exa(
                query=args.query,
                max_results=args.max_results,
                category=args.category,
                content_mode=args.content,
            )
            json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
            return 0
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    parser.error(f"未知命令: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
