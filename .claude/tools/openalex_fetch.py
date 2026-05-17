"""OpenAlex 搜索命令行工具。"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

try:
    import requests
except ImportError:
    print("警告: 未安装 requests，已跳过 OpenAlex CLI。", file=sys.stderr)
    sys.exit(0)


API_URL = "https://api.openalex.org/works"
REQUEST_TIMEOUT_SECONDS = 30.0
USER_AGENT = "openalex_fetch.py/1.0"


def _clean_text(value: Any) -> str:
    """压缩空白并清理文本值。"""
    return " ".join(str(value).split())


def _normalize_year_filter(raw_year: str) -> str:
    """将命令行年份参数转换为 OpenAlex filter 语法。"""
    value = raw_year.strip()
    if not value:
        raise ValueError("年份参数不能为空")

    if value.isdigit() and len(value) == 4:
        return f"publication_year:{value}"

    if value.endswith("-") and value[:-1].strip().isdigit():
        start_year = value[:-1].strip()
        return f"from_publication_date:{start_year}-01-01"

    if value.startswith("-") and value[1:].strip().isdigit():
        end_year = value[1:].strip()
        return f"to_publication_date:{end_year}-12-31"

    if "-" in value:
        start_year, end_year = [part.strip() for part in value.split("-", 1)]
        if start_year.isdigit() and end_year.isdigit():
            return f"publication_year:{start_year}-{end_year}"

    raise ValueError(f"无法识别的年份参数: {raw_year}")


def _normalize_sort_value(sort_value: str) -> str:
    """将用户输入的排序参数转换为 OpenAlex sort 语法。"""
    value = sort_value.strip()
    if not value:
        raise ValueError("排序参数不能为空")
    if value in {"relevance", "relevance_score"}:
        return "relevance_score:desc"
    return value


def _normalize_work(work: dict[str, Any]) -> dict[str, Any]:
    """将 OpenAlex work 记录压缩成稳定输出结构。"""
    authorships = work.get("authorships")
    authors: list[str] = []
    institutions: list[str] = []
    if isinstance(authorships, list):
        for authorship in authorships:
            if not isinstance(authorship, dict):
                continue
            author = authorship.get("author")
            if isinstance(author, dict):
                display_name = author.get("display_name")
                if display_name:
                    cleaned_name = _clean_text(display_name)
                    if cleaned_name not in authors:
                        authors.append(cleaned_name)
            author_institutions = authorship.get("institutions")
            if isinstance(author_institutions, list):
                for institution in author_institutions:
                    if not isinstance(institution, dict):
                        continue
                    display_name = institution.get("display_name")
                    if display_name:
                        cleaned_name = _clean_text(display_name)
                        if cleaned_name not in institutions:
                            institutions.append(cleaned_name)

    return {
        "title": _clean_text(work.get("display_name", "")),
        "authors": authors,
        "year": work.get("publication_year"),
        "cited_by_count": work.get("cited_by_count"),
        "institutions": institutions,
        "doi": work.get("doi"),
    }


def search_openalex(
    query: str,
    max_results: int,
    year: str | None,
    work_type: str | None,
    sort: str,
) -> list[dict[str, Any]]:
    """搜索 OpenAlex 并返回标准化论文结果。"""
    params: dict[str, Any] = {
        "search": query,
        "per-page": max_results,
        "sort": _normalize_sort_value(sort),
    }

    filters: list[str] = []
    if year:
        filters.append(_normalize_year_filter(year))
    if work_type:
        filters.append(f"type:{work_type.strip()}")
    if filters:
        params["filter"] = ",".join(filters)

    response = requests.get(
        API_URL,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("OpenAlex 返回了非对象类型的 JSON")

    works = payload.get("results", [])
    if not isinstance(works, list):
        raise ValueError("OpenAlex 响应缺少 results 列表")

    normalized_results: list[dict[str, Any]] = []
    for work in works:
        if isinstance(work, dict):
            normalized_results.append(_normalize_work(work))
    return normalized_results


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="OpenAlex 搜索工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="搜索 OpenAlex works")
    search_parser.add_argument("query", help="搜索关键词")
    search_parser.add_argument("--max", dest="max_results", type=int, default=10)
    search_parser.add_argument("--year", default=None, help="年份或年份范围")
    search_parser.add_argument("--type", dest="work_type", default=None, help="作品类型")
    search_parser.add_argument(
        "--sort",
        default="relevance",
        help="排序字段，relevance 会映射为 relevance_score:desc",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "search":
            results = search_openalex(
                query=args.query,
                max_results=args.max_results,
                year=args.year,
                work_type=args.work_type,
                sort=args.sort,
            )
            json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
            return 0
    except (requests.RequestException, ValueError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    parser.error(f"未知命令: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
