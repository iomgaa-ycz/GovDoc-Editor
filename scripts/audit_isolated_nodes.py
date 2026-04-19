#!/usr/bin/env python3
"""从 graphify-out/graph.json 筛出真代码嫌疑孤立节点，输出 CSV 供人工分类。

用法：
    python scripts/audit_isolated_nodes.py > docs/superpowers/specs/p2-isolated-nodes-audit.csv

筛选规则：
    - node 必须有 source_file 字段
    - source_file 后缀必须是代码类型（.py / .ts / .tsx / .js / .jsx 等）
    - 节点度数（入度+出度）≤ 1
    - 排除明显是 module docstring 的节点（label 过长或以句号结尾）

输出 CSV 列：
    node_id, label, source_file, degree, classification, note
    classification 初始为空，需人工填入：
        zombie   - 确认无引用，可删
        missing  - 图谱漏抽边，真实代码有被使用
        alive    - 低耦合但合理，放过
        gone     - 符号已在代码中消失（被前置 P0/P1 重构删除），无动作
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

CODE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx"}


def is_module_docstring(label: str) -> bool:
    """启发式：模块 docstring 通常较长或以句号结尾。"""
    if not label:
        return False
    if len(label) > 60:
        return True
    if label.rstrip().endswith(("。", ".")):
        return True
    return False


def main(graph_path: Path, out_path: Path | None = None) -> None:
    data = json.loads(graph_path.read_text())
    nodes = {n["id"]: n for n in data["nodes"]}

    # 建立度数索引
    degree: dict[str, int] = {nid: 0 for nid in nodes}
    # NetworkX JSON 导出用 "links" 或 "edges"
    edge_list = data.get("links") or data.get("edges") or []
    for edge in edge_list:
        src = edge.get("source")
        tgt = edge.get("target")
        if src in degree:
            degree[src] += 1
        if tgt in degree:
            degree[tgt] += 1

    # 筛选：code + degree ≤ 1 + 非 docstring
    suspects = []
    for nid, n in nodes.items():
        src_file = n.get("source_file") or ""
        if not src_file:
            continue
        ext = Path(src_file).suffix.lower()
        if ext not in CODE_EXTS:
            continue
        if degree[nid] > 1:
            continue
        label = n.get("label", "")
        if is_module_docstring(label):
            continue
        suspects.append(
            {
                "node_id": nid,
                "label": label,
                "source_file": src_file,
                "degree": degree[nid],
                "classification": "",
                "note": "",
            }
        )

    suspects.sort(key=lambda x: (x["source_file"], x["label"]))

    # 写 CSV
    out = sys.stdout if out_path is None else out_path.open("w", encoding="utf-8")
    writer = csv.DictWriter(
        out, fieldnames=["node_id", "label", "source_file", "degree", "classification", "note"]
    )
    writer.writeheader()
    for row in suspects:
        writer.writerow(row)
    if out_path is not None:
        out.close()

    print(f"# 共 {len(suspects)} 个真代码嫌疑孤立节点", file=sys.stderr)


if __name__ == "__main__":
    graph_path = Path("graphify-out/graph.json")
    if len(sys.argv) >= 2:
        out_path = Path(sys.argv[1])
    else:
        out_path = None
    main(graph_path, out_path)
