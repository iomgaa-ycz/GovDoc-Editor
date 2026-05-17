"""研究 Wiki 的初始化与日志工具。"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen
import xml.etree.ElementTree as ET

ENTITY_TYPES = {
    "paper": "papers",
    "idea": "ideas",
    "experiment": "experiments",
    "claim": "claims",
    "gap": "gaps",
    "design": "designs",
    "finding": "findings",
    "plan": "plans",
    "review": "reviews",
    "schema": "schemas",
    "metric": "metrics",
}

EDGE_TYPES = [
    "extends",
    "contradicts",
    "supersedes",
    "addresses_gap",
    "inspired_by",
    "tested_by",
    "supports",
    "invalidates",
    "implements",
    "reveals",
    "informs",
    "refines",
    "depends_on",
    "measures",
    "evaluates",
]

QUERY_PACK_BUDGET = 8000


def slugify(text: str) -> str:
    """将文本转换为 URL 安全的 slug。"""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = re.sub(r"[^\w\s-]", "", normalized.lower())
    return re.sub(r"[-\s]+", "_", normalized).strip("_")[:60]


def _write_if_missing(path: Path, content: str) -> None:
    """仅在文件不存在时写入内容。

    参数:
        path: 目标文件路径。
        content: 需要写入的文本内容。
    """
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def append_log(wiki_dir: str, message: str) -> None:
    """向 Wiki 变更日志追加一条记录。

    参数:
        wiki_dir: Wiki 根目录。
        message: 需要记录的消息。
    """
    log_path = Path(wiki_dir) / "log.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"- [{timestamp}] {message}\n")


def _render_frontmatter(data: dict[str, Any]) -> str:
    """将字典渲染为 YAML frontmatter。"""
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            rendered_value = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, str) and " " in value:
            rendered_value = f'"{value}"'
        else:
            rendered_value = str(value)
        lines.append(f"{key}: {rendered_value}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _read_frontmatter(filepath: Path) -> dict[str, Any]:
    """从 markdown 文件读取简易 frontmatter。"""
    text = filepath.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}

    lines = text.splitlines()
    result: dict[str, Any] = {}
    for line in lines[1:]:
        if line == "---":
            break
        if ":" not in line:
            continue
        key, _, raw_value = line.partition(":")
        value = raw_value.strip()
        if value.startswith("[") and value.endswith("]"):
            try:
                result[key.strip()] = json.loads(value)
                continue
            except json.JSONDecodeError:
                pass
        if len(value) >= 2 and (
            (value.startswith('"') and value.endswith('"'))
            or (value.startswith("'") and value.endswith("'"))
        ):
            value = value[1:-1]
        result[key.strip()] = value
    return result


def _add_node_to_graph(wiki_dir: str, node_id: str, label: str, entity_type: str) -> None:
    """向关系图中添加节点，若已存在则跳过。"""
    graph_path = Path(wiki_dir) / "graph" / "edges.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = graph.setdefault("nodes", [])
    if not any(node.get("id") == node_id for node in nodes):
        nodes.append({"id": node_id, "label": label, "type": entity_type})
        graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")


def add_edge(
    wiki_dir: str,
    from_id: str,
    to_id: str,
    edge_type: str,
    evidence: str = "",
) -> None:
    """向关系图中添加一条边。"""
    if edge_type not in EDGE_TYPES:
        raise ValueError(f"未知边类型: {edge_type}，合法值: {EDGE_TYPES}")

    graph_path = Path(wiki_dir) / "graph" / "edges.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    links = graph.setdefault("links", [])

    for link in links:
        if (
            link.get("source") == from_id
            and link.get("target") == to_id
            and link.get("relation") == edge_type
        ):
            return

    links.append(
        {
            "source": from_id,
            "target": to_id,
            "relation": edge_type,
            "evidence": evidence,
            "added": datetime.now(timezone.utc).isoformat(),
        }
    )
    graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    append_log(wiki_dir, f"新增边: {from_id} --{edge_type}--> {to_id}")


def add_entity(
    wiki_dir: str,
    entity_type: str,
    entity_id: str,
    title: str,
    extra_frontmatter: dict[str, Any] | None = None,
) -> Path:
    """创建一个实体页面并同步到关系图。"""
    if entity_type not in ENTITY_TYPES:
        raise ValueError(f"未知实体类型: {entity_type}，合法值: {list(ENTITY_TYPES)}")

    root = Path(wiki_dir)
    entity_subdir = root / ENTITY_TYPES[entity_type]
    node_id = f"{entity_type}:{entity_id}"

    for existing_path in entity_subdir.glob("*.md"):
        frontmatter = _read_frontmatter(existing_path)
        if frontmatter.get("node_id") == node_id:
            return existing_path

    filepath = entity_subdir / f"{entity_id}.md"
    frontmatter: dict[str, Any] = {
        "type": entity_type,
        "node_id": node_id,
        "title": title,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    if extra_frontmatter:
        frontmatter.update(extra_frontmatter)

    content = _render_frontmatter(frontmatter) + f"\n# {title}\n\n"
    filepath.write_text(content, encoding="utf-8")

    _add_node_to_graph(wiki_dir, node_id, title, entity_type)
    append_log(wiki_dir, f"新增 {entity_type}: {title} ({node_id})")
    return filepath


def _fetch_arxiv_metadata(arxiv_id: str) -> dict[str, Any] | None:
    """通过 arXiv Atom API 拉取论文元数据。"""
    clean_id = arxiv_id.removeprefix("arxiv:").removeprefix("arXiv:").removeprefix("ARXIV:").strip()
    url = f"http://export.arxiv.org/api/query?id_list={clean_id}"

    try:
        with urlopen(url) as response:
            root = ET.fromstring(response.read())
    except Exception:
        return None

    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    entry = root.find("atom:entry", namespace)
    if entry is None:
        return None

    def _text(path: str) -> str:
        value = entry.findtext(path, default="", namespaces=namespace)
        return " ".join(value.split())

    authors = [
        " ".join(author.findtext("atom:name", default="", namespaces=namespace).split())
        for author in entry.findall("atom:author", namespace)
    ]
    authors = [author for author in authors if author]
    published = _text("atom:published")
    year = published[:4] if len(published) >= 4 else ""

    return {
        "title": _text("atom:title"),
        "authors": authors,
        "year": year,
        "abstract": _text("atom:summary"),
        "arxiv_id": clean_id,
    }


def _last_name(full_name: str) -> str:
    """提取人名最后一个词作为姓氏。"""
    parts = full_name.strip().split()
    return parts[-1].lower() if parts else "unknown"


def _markdown_body(text: str) -> str:
    """提取 markdown 中 frontmatter 之后的正文。"""
    if not text.startswith("---\n"):
        return text

    lines = text.splitlines()
    for index, line in enumerate(lines[1:], start=1):
        if line == "---":
            return "\n".join(lines[index + 1 :])
    return ""


def _iter_entity_pages(wiki_dir: str) -> list[tuple[str, Path, dict[str, Any], str]]:
    """收集 Wiki 中所有实体页面。"""
    root = Path(wiki_dir)
    pages: list[tuple[str, Path, dict[str, Any], str]] = []

    for entity_type, subdir_name in ENTITY_TYPES.items():
        subdir = root / subdir_name
        for path in sorted(subdir.glob("*.md")):
            frontmatter = _read_frontmatter(path)
            body = _markdown_body(path.read_text(encoding="utf-8"))
            resolved_type = str(frontmatter.get("type", entity_type)).strip() or entity_type
            pages.append((resolved_type, path, frontmatter, body))

    return pages


def rebuild_index(wiki_dir: str) -> None:
    """按实体类型重建索引页。"""
    root = Path(wiki_dir)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pages = _iter_entity_pages(wiki_dir)

    grouped: dict[str, list[tuple[Path, dict[str, Any]]]] = {}
    for entity_type, path, frontmatter, _ in pages:
        grouped.setdefault(entity_type, []).append((path, frontmatter))

    lines = [
        "# Research Wiki 索引",
        "",
        f"> 自动生成，更新时间：{timestamp}",
        "",
    ]

    for entity_type in ENTITY_TYPES:
        entries = grouped.get(entity_type, [])
        if not entries:
            continue
        entries = sorted(
            entries,
            key=lambda item: (
                str(item[1].get("title", item[0].stem)).casefold(),
                item[0].name,
            ),
        )
        lines.append(f"## {entity_type} ({len(entries)})")
        for path, frontmatter in entries:
            title = str(frontmatter.get("title", path.stem)).strip() or path.stem
            node_id = str(frontmatter.get("node_id", f"{entity_type}:{path.stem}")).strip()
            relative_path = path.relative_to(root).as_posix()
            lines.append(f"- [{title}]({relative_path}) `{node_id}`")
        lines.append("")

    content = "\n".join(lines).rstrip() + "\n"
    (root / "index.md").write_text(content, encoding="utf-8")
    append_log(wiki_dir, f"重建索引: {len(pages)} 篇页面")


def rebuild_query_pack(wiki_dir: str) -> None:
    """基于 frontmatter 重新生成 Query Pack。"""
    pages = _iter_entity_pages(wiki_dir)

    failed_ideas: list[tuple[str, str]] = []
    open_gaps: list[str] = []
    core_papers: list[tuple[str, str, str]] = []

    for entity_type, path, frontmatter, _ in pages:
        title = str(frontmatter.get("title", path.stem)).strip() or path.stem
        if entity_type == "idea":
            outcome = str(frontmatter.get("outcome", "")).strip().lower()
            if outcome in {"negative", "failed"}:
                failure_reason = str(frontmatter.get("failure_reason", "")).strip()
                failed_ideas.append((title, failure_reason or "未填写"))
        if entity_type == "gap":
            status = str(frontmatter.get("status", "open")).strip().lower()
            if not status or status == "open":
                open_gaps.append(title)
        if entity_type == "paper":
            year = str(frontmatter.get("year", "")).strip()
            venue = str(frontmatter.get("venue", "")).strip()
            core_papers.append(
                (
                    title,
                    year or "未知年份",
                    venue or "未知 venue",
                )
            )

    failed_ideas.sort(key=lambda item: item[0].casefold())
    open_gaps.sort(key=str.casefold)
    core_papers.sort(key=lambda item: (item[1], item[0].casefold(), item[2].casefold()))

    sections: list[tuple[str, list[str]]] = []
    if failed_ideas:
        sections.append(
            (
                "## 失败 Idea（禁区）",
                [f"- ❌ {title}: {reason}" for title, reason in failed_ideas[:10]],
            )
        )
    if open_gaps:
        sections.append(
            (
                "## 未解决空白",
                [f"- {title}" for title in open_gaps[:5]],
            )
        )
    if core_papers:
        sections.append(
            (
                "## 核心论文",
                [f"- [{title}] ({year}) {venue}" for title, year, venue in core_papers[:12]],
            )
        )

    content_parts = [
        "# Query Pack",
        "",
        "> 自动生成，请勿手动编辑。",
        "",
        "",
    ]
    current_content = "\n".join(content_parts)

    for section_title, section_lines in sections:
        section_text = "\n".join([section_title, *section_lines, "", ""])
        candidate = current_content + section_text
        if len(candidate) > QUERY_PACK_BUDGET:
            break
        current_content = candidate

    content = current_content.rstrip() + "\n"
    (Path(wiki_dir) / "query_pack.md").write_text(content, encoding="utf-8")
    append_log(wiki_dir, f"重建 Query Pack: {len(content)} 字符")


def get_stats(wiki_dir: str) -> str:
    """统计 Wiki 规模与图谱信息。"""
    root = Path(wiki_dir)
    lines: list[str] = []

    for entity_type, subdir_name in ENTITY_TYPES.items():
        count = len(list((root / subdir_name).glob("*.md")))
        lines.append(f"{entity_type}: {count}")

    graph_path = root / "graph" / "edges.json"
    if graph_path.exists():
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    else:
        graph = {"nodes": [], "links": []}

    lines.append(f"nodes: {len(graph.get('nodes', []))}")
    lines.append(f"links: {len(graph.get('links', []))}")
    return "\n".join(lines)


def lint_wiki(wiki_dir: str) -> list[str]:
    """检查 Wiki 中的孤立节点与稀疏页面。"""
    root = Path(wiki_dir)
    issues: list[str] = []

    graph_path = root / "graph" / "edges.json"
    if graph_path.exists():
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    else:
        graph = {"nodes": [], "links": []}

    linked_node_ids = {
        str(link.get("source", "")).strip()
        for link in graph.get("links", [])
        if str(link.get("source", "")).strip()
    }
    linked_node_ids.update(
        str(link.get("target", "")).strip()
        for link in graph.get("links", [])
        if str(link.get("target", "")).strip()
    )

    for node in graph.get("nodes", []):
        node_id = str(node.get("id", "")).strip()
        if node_id and node_id not in linked_node_ids:
            label = str(node.get("label", "")).strip()
            issues.append(f"孤立节点: {node_id}" + (f" ({label})" if label else ""))

    for _, path, _, body in _iter_entity_pages(wiki_dir):
        if len(body.strip()) < 50:
            relative_path = path.relative_to(root).as_posix()
            issues.append(f"稀疏页面: {relative_path} (正文 {len(body.strip())} 字符)")

    return issues


def ingest_paper(
    wiki_dir: str,
    arxiv_id: str | None = None,
    title: str | None = None,
    authors: str | None = None,
    year: str | None = None,
    venue: str = "arXiv",
    thesis: str = "",
) -> Path | None:
    """创建 paper 实体并补充标准化正文模板。"""
    abstract = ""
    authors_list: list[str]
    paper_title = title
    paper_year = year
    paper_arxiv_id = None

    if arxiv_id:
        metadata = _fetch_arxiv_metadata(arxiv_id)
        if metadata is None:
            return None
        paper_title = metadata["title"]
        authors_list = metadata["authors"]
        paper_year = metadata["year"]
        abstract = metadata["abstract"]
        paper_arxiv_id = metadata["arxiv_id"]
    else:
        if not (title and authors and year):
            raise ValueError("非 arXiv 论文需提供 --title、--authors、--year")
        authors_list = [author.strip() for author in authors.split(",") if author.strip()]
        if not authors_list:
            raise ValueError("authors 不能为空")

    if not paper_title:
        raise ValueError("论文标题不能为空")
    if not paper_year:
        raise ValueError("论文年份不能为空")
    if not authors_list:
        raise ValueError("论文作者不能为空")

    slug = f"{_last_name(authors_list[0])}{paper_year}_{slugify(paper_title)[:30]}"
    extra_frontmatter: dict[str, Any] = {
        "authors": authors_list,
        "year": paper_year,
        "venue": venue,
    }
    if paper_arxiv_id is not None:
        extra_frontmatter["arxiv_id"] = paper_arxiv_id

    path = add_entity(wiki_dir, "paper", slug, paper_title, extra_frontmatter)

    content = path.read_text(encoding="utf-8")
    if "## 一句话论点" not in content:
        body = f"\n## 一句话论点\n\n{thesis or '待填写'}\n\n"
        if abstract:
            body += f"## 摘要\n\n> {' '.join(abstract.split())}\n\n"
        body += "## 问题/空白\n\n## 方法\n\n## 关键结果\n\n## 局限性\n\n## 与本项目的相关性\n\n"
        path.write_text(content + body, encoding="utf-8")

    return path


def init_wiki(wiki_dir: str) -> None:
    """初始化研究 Wiki 的目录结构与基础文件。

    参数:
        wiki_dir: Wiki 根目录。
    """
    root = Path(wiki_dir)
    root.mkdir(parents=True, exist_ok=True)

    for entity_dir in ENTITY_TYPES.values():
        (root / entity_dir).mkdir(parents=True, exist_ok=True)

    graph_dir = root / "graph"
    graph_dir.mkdir(parents=True, exist_ok=True)

    _write_if_missing(root / "index.md", "# Research Wiki 索引\n\n> 自动生成，请勿手动编辑。\n")
    _write_if_missing(root / "log.md", "# Wiki 变更日志\n\n")
    _write_if_missing(root / "gap_map.md", "# 领域空白汇总\n\n")
    _write_if_missing(
        root / "query_pack.md",
        "# Query Pack\n\n> 尚无数据。运行 research-lit 或 idea-creator 后自动生成。\n",
    )
    _write_if_missing(
        graph_dir / "edges.json",
        json.dumps({"directed": True, "nodes": [], "links": []}, ensure_ascii=False),
    )

    append_log(wiki_dir, "Wiki 初始化完成")


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="研究 Wiki 工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="初始化 Wiki")
    init_parser.add_argument("wiki_dir", help="Wiki 根目录")

    log_parser = subparsers.add_parser("log", help="追加日志")
    log_parser.add_argument("wiki_dir", help="Wiki 根目录")
    log_parser.add_argument("message", nargs="+", help="日志内容")

    entity_parser = subparsers.add_parser("add_entity", help="创建实体")
    entity_parser.add_argument("wiki_dir", help="Wiki 根目录")
    entity_parser.add_argument("--type", required=True, choices=list(ENTITY_TYPES), help="实体类型")
    entity_parser.add_argument("--id", required=True, help="实体 ID")
    entity_parser.add_argument("--title", required=True, help="实体标题")

    edge_parser = subparsers.add_parser("add_edge", help="创建关系边")
    edge_parser.add_argument("wiki_dir", help="Wiki 根目录")
    edge_parser.add_argument("--from", dest="from_id", required=True, help="起点节点 ID")
    edge_parser.add_argument("--to", dest="to_id", required=True, help="终点节点 ID")
    edge_parser.add_argument(
        "--type", required=True, choices=EDGE_TYPES, dest="edge_type", help="边类型"
    )
    edge_parser.add_argument("--evidence", default="", help="证据说明")

    ingest_parser = subparsers.add_parser("ingest_paper", help="导入论文")
    ingest_parser.add_argument("wiki_dir", help="Wiki 根目录")
    ingest_parser.add_argument("--arxiv-id", dest="arxiv_id", help="arXiv ID")
    ingest_parser.add_argument("--title", help="论文标题")
    ingest_parser.add_argument("--authors", help="作者，逗号分隔")
    ingest_parser.add_argument("--year", help="年份")
    ingest_parser.add_argument("--venue", default="arXiv", help="发表 venue")
    ingest_parser.add_argument("--thesis", default="", help="一句话论点")

    rebuild_query_pack_parser = subparsers.add_parser("rebuild_query_pack", help="重建 Query Pack")
    rebuild_query_pack_parser.add_argument("wiki_dir", help="Wiki 根目录")

    rebuild_index_parser = subparsers.add_parser("rebuild_index", help="重建索引")
    rebuild_index_parser.add_argument("wiki_dir", help="Wiki 根目录")

    stats_parser = subparsers.add_parser("stats", help="输出统计信息")
    stats_parser.add_argument("wiki_dir", help="Wiki 根目录")

    lint_parser = subparsers.add_parser("lint", help="检查 Wiki 问题")
    lint_parser.add_argument("wiki_dir", help="Wiki 根目录")

    args = parser.parse_args()

    if args.command == "init":
        init_wiki(args.wiki_dir)
        return

    if args.command == "log":
        append_log(args.wiki_dir, " ".join(args.message))
        return

    if args.command == "add_entity":
        add_entity(args.wiki_dir, args.type, args.id, args.title)
        return

    if args.command == "add_edge":
        add_edge(args.wiki_dir, args.from_id, args.to_id, args.edge_type, args.evidence)
        return

    if args.command == "ingest_paper":
        ingest_paper(
            args.wiki_dir,
            arxiv_id=args.arxiv_id,
            title=args.title,
            authors=args.authors,
            year=args.year,
            venue=args.venue,
            thesis=args.thesis,
        )
        return

    if args.command == "rebuild_query_pack":
        rebuild_query_pack(args.wiki_dir)
        return

    if args.command == "rebuild_index":
        rebuild_index(args.wiki_dir)
        return

    if args.command == "stats":
        print(get_stats(args.wiki_dir))
        return

    if args.command == "lint":
        issues = lint_wiki(args.wiki_dir)
        print("\n".join(issues) if issues else "未发现问题")
        return


if __name__ == "__main__":
    main()
