"""arXiv 搜索与 PDF 下载的独立命令行工具。"""

from __future__ import annotations

import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen


ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_API_URL = "http://export.arxiv.org/api/query?search_query=all:{query}&max_results={max}"
ARXIV_PDF_URL = "https://arxiv.org/pdf/{arxiv_id}.pdf"
USER_AGENT = "arxiv_fetch.py/1.0"
MIN_PDF_SIZE = 10 * 1024
DOWNLOAD_DELAY_SECONDS = 1.0


def _clean_text(value: str) -> str:
    """压缩空白并清理文本内容。"""
    return " ".join(value.split())


def _normalize_arxiv_id(raw_id: str) -> str:
    """将 arXiv 标识归一化为不带版本号的论文 ID。"""
    value = raw_id.strip()
    if value.startswith("http://") or value.startswith("https://"):
        value = value.rsplit("/", 1)[-1]
    if value.startswith("abs/") or value.startswith("pdf/"):
        value = value.split("/", 1)[1]
    if value.endswith(".pdf"):
        value = value[:-4]
    if value.startswith("arXiv:") or value.startswith("arxiv:"):
        value = value.split(":", 1)[1]
    if "v" in value:
        head, tail = value.rsplit("v", 1)
        if tail.isdigit():
            value = head
    return value


def _request_text(url: str) -> bytes:
    """发起 HTTP 请求并返回原始字节内容。"""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request) as response:
        return response.read()


def _parse_arxiv_feed(xml_bytes: bytes) -> list[dict[str, Any]]:
    """解析 arXiv Atom Feed 并提取论文条目。"""
    root = ET.fromstring(xml_bytes)
    namespace = {"atom": ATOM_NS}
    results: list[dict[str, Any]] = []

    for entry in root.findall("atom:entry", namespace):
        title = _clean_text(entry.findtext("atom:title", default="", namespaces=namespace))
        abstract = _clean_text(entry.findtext("atom:summary", default="", namespaces=namespace))
        published = _clean_text(entry.findtext("atom:published", default="", namespaces=namespace))
        if "T" in published:
            published = published.split("T", 1)[0]

        authors: list[str] = []
        for author in entry.findall("atom:author", namespace):
            name = _clean_text(author.findtext("atom:name", default="", namespaces=namespace))
            if name:
                authors.append(name)

        categories: list[str] = []
        for category in entry.findall("atom:category", namespace):
            term = category.get("term", "").strip()
            if term and term not in categories:
                categories.append(term)

        raw_id = entry.findtext("atom:id", default="", namespaces=namespace)
        arxiv_id = _normalize_arxiv_id(raw_id.rsplit("/", 1)[-1] if raw_id else "")

        results.append(
            {
                "title": title,
                "authors": authors,
                "arxiv_id": arxiv_id,
                "abstract": abstract,
                "categories": categories,
                "published": published,
            }
        )

    return results


def search_arxiv(query: str, max_results: int) -> list[dict[str, Any]]:
    """搜索 arXiv 并返回结构化论文结果。"""
    encoded_query = quote(query, safe="")
    url = ARXIV_API_URL.format(query=encoded_query, max=max_results)
    feed_bytes = _request_text(url)
    return _parse_arxiv_feed(feed_bytes)


def download_arxiv_pdf(arxiv_id: str, target_dir: Path) -> Path:
    """下载指定 arXiv 论文的 PDF 并校验文件大小。"""
    normalized_id = _normalize_arxiv_id(arxiv_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / f"{normalized_id}.pdf"
    pdf_url = ARXIV_PDF_URL.format(arxiv_id=normalized_id)

    request = Request(pdf_url, headers={"User-Agent": USER_AGENT})
    time.sleep(DOWNLOAD_DELAY_SECONDS)
    try:
        with urlopen(request) as response, output_path.open("wb") as handle:
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                handle.write(chunk)
    except Exception:
        if output_path.exists():
            output_path.unlink()
        raise

    if output_path.stat().st_size <= MIN_PDF_SIZE:
        output_path.unlink(missing_ok=True)
        raise ValueError(f"下载文件过小，疑似失败: {output_path}")

    return output_path


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="arXiv 搜索与 PDF 下载工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="搜索 arXiv 论文")
    search_parser.add_argument("query", help="搜索关键词")
    search_parser.add_argument("--max", type=int, default=10, help="最大返回数量")

    download_parser = subparsers.add_parser("download", help="下载 arXiv PDF")
    download_parser.add_argument("arxiv_id", help="arXiv 论文 ID")
    download_parser.add_argument("--dir", dest="target_dir", default=".", help="保存目录")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "search":
            results = search_arxiv(args.query, args.max)
            json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
            return 0

        if args.command == "download":
            output_path = download_arxiv_pdf(args.arxiv_id, Path(args.target_dir))
            sys.stdout.write(f"{output_path}\n")
            return 0
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    parser.error(f"未知命令: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
