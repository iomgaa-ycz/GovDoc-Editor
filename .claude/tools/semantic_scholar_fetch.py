"""Semantic Scholar 搜索命令行工具。"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

try:
    import requests
except ImportError:
    print("警告: 未安装 requests，已跳过 Semantic Scholar CLI。", file=sys.stderr)
    sys.exit(0)


API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
REQUEST_FIELDS = "title,authors,year,venue,citationCount,externalIds,tldr"
REQUEST_INTERVAL_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 30.0
USER_AGENT = "semantic_scholar_fetch.py/1.0"
_LAST_REQUEST_AT: float | None = None


def _normalize_filter_values(values: list[str] | None) -> str | None:
    """将过滤参数整理为 API 需要的逗号分隔字符串。"""
    if not values:
        return None

    items: list[str] = []
    for value in values:
        for item in value.split(","):
            cleaned = item.strip()
            if cleaned:
                items.append(cleaned)

    if not items:
        return None
    return ",".join(items)


def _respect_rate_limit() -> None:
    """确保连续请求之间至少间隔一秒。"""
    global _LAST_REQUEST_AT

    now = time.monotonic()
    if _LAST_REQUEST_AT is not None:
        elapsed = now - _LAST_REQUEST_AT
        if elapsed < REQUEST_INTERVAL_SECONDS:
            time.sleep(REQUEST_INTERVAL_SECONDS - elapsed)

    _LAST_REQUEST_AT = time.monotonic()


def _clean_text(value: Any) -> str:
    """压缩并清理任意文本值。"""
    return " ".join(str(value).split())


def _normalize_authors(authors: Any) -> list[str]:
    """将作者字段统一为作者姓名列表。"""
    normalized_authors: list[str] = []
    if not isinstance(authors, list):
        return normalized_authors

    for author in authors:
        if isinstance(author, dict):
            name = author.get("name")
            if name:
                normalized_authors.append(_clean_text(name))
        elif author:
            normalized_authors.append(_clean_text(author))

    return normalized_authors


def _normalize_external_ids(external_ids: Any) -> dict[str, str]:
    """将 externalIds 统一整理为字符串字典，并保留 arXiv 标识。"""
    normalized: dict[str, str] = {}
    if isinstance(external_ids, dict):
        for key, value in external_ids.items():
            if value is None:
                continue
            cleaned_value = _clean_text(value)
            if cleaned_value:
                normalized[str(key)] = cleaned_value

    arxiv_id = normalized.get("ArXiv") or normalized.get("arXiv") or normalized.get("arxiv")
    if arxiv_id and "ArXiv" not in normalized:
        normalized["ArXiv"] = arxiv_id

    return normalized


def _normalize_tldr(tldr: Any) -> Any:
    """保留 TLDR 字段原始结构，但去除明显的空字符串。"""
    if isinstance(tldr, dict):
        normalized_tldr: dict[str, Any] = {}
        for key, value in tldr.items():
            if isinstance(value, str):
                cleaned = _clean_text(value)
                if cleaned:
                    normalized_tldr[key] = cleaned
            elif value is not None:
                normalized_tldr[key] = value
        return normalized_tldr or None
    return tldr


def _normalize_paper(paper: dict[str, Any]) -> dict[str, Any]:
    """将 API 返回的论文记录压缩成稳定的输出结构。"""
    return {
        "title": _clean_text(paper.get("title", "")),
        "authors": _normalize_authors(paper.get("authors")),
        "year": paper.get("year"),
        "venue": _clean_text(paper.get("venue", "")),
        "citationCount": paper.get("citationCount"),
        "externalIds": _normalize_external_ids(paper.get("externalIds")),
        "tldr": _normalize_tldr(paper.get("tldr")),
    }


def _request_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    """发起受限频率控制的 GET 请求并返回 JSON 对象。"""
    _respect_rate_limit()
    response = requests.get(
        url,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Semantic Scholar 返回了非对象类型的 JSON")
    return payload


def search_papers(
    query: str,
    max_results: int,
    fields_of_study: list[str] | None = None,
    publication_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """搜索 Semantic Scholar 论文并返回标准化结果。"""
    params: dict[str, Any] = {
        "query": query,
        "limit": max_results,
        "fields": REQUEST_FIELDS,
    }

    normalized_fields_of_study = _normalize_filter_values(fields_of_study)
    if normalized_fields_of_study is not None:
        params["fieldsOfStudy"] = normalized_fields_of_study

    normalized_publication_types = _normalize_filter_values(publication_types)
    if normalized_publication_types is not None:
        params["publicationTypes"] = normalized_publication_types

    payload = _request_json(API_URL, params)
    papers = payload.get("data", [])
    if not isinstance(papers, list):
        raise ValueError("Semantic Scholar 响应缺少 data 列表")

    normalized_papers: list[dict[str, Any]] = []
    for paper in papers:
        if isinstance(paper, dict):
            normalized_papers.append(_normalize_paper(paper))
    return normalized_papers


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="Semantic Scholar 搜索工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="搜索论文")
    search_parser.add_argument("query", help="搜索关键词")
    search_parser.add_argument("--max", dest="max_results", type=int, default=10)
    search_parser.add_argument(
        "--fields-of-study",
        nargs="+",
        default=None,
        help="按学科领域过滤",
    )
    search_parser.add_argument(
        "--publication-types",
        nargs="+",
        default=None,
        help="按出版类型过滤",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "search":
            results = search_papers(
                query=args.query,
                max_results=args.max_results,
                fields_of_study=args.fields_of_study,
                publication_types=args.publication_types,
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
