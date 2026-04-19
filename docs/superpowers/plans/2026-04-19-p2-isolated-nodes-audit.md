# P2 · 孤立节点审查 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 从 graphify 图谱 `graphify-out/graph.json` 筛出 `file_type=code AND degree≤1` 的节点（估计 ~23 个），人工逐行分类后对"僵尸"代码执行删除。

**Architecture:** 脚本过滤 → CSV 分类 → 按分类执行动作（删除/补边/放过）→ 重跑 graphify 验证下降。

**Tech Stack:** Python 3.11（标准库 + networkx）

**依赖：** **P0/P1a/P1b/P1c 已全部 merge 入 umbrella**（避免误删正在重构的代码）。

---

## Task 0: 建立子分支

- [ ] **Step 1**

```bash
git checkout feat/tech-debt-cleanup
git pull --ff-only 2>/dev/null || true
git checkout -b feat/p2-isolated-nodes-audit
```

- [ ] **Step 2: 验证前 4 项已入 umbrella**

```bash
git log --oneline feat/tech-debt-cleanup | head -20 | grep -E "Merge P[01][abc]*"
```

Expected: 看到 P0、P1b、P1c、P1a 四个 merge commit

---

## Task 1: 编写过滤脚本

**Files:**
- Create: `scripts/audit_isolated_nodes.py`

- [ ] **Step 1: 建立 scripts/ 目录（如未存在）**

```bash
mkdir -p scripts
```

- [ ] **Step 2: 编写脚本**

```python
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
        suspects.append({
            "node_id": nid,
            "label": label,
            "source_file": src_file,
            "degree": degree[nid],
            "classification": "",
            "note": "",
        })

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
```

- [ ] **Step 3: 跑脚本生成 CSV**

```bash
conda run -n govdoc-auditor-v3 python scripts/audit_isolated_nodes.py docs/superpowers/specs/p2-isolated-nodes-audit.csv
wc -l docs/superpowers/specs/p2-isolated-nodes-audit.csv
```

Expected: 约 15-25 行（包含 header）

- [ ] **Step 4: 提交脚本 + 初始 CSV**

```bash
git add scripts/audit_isolated_nodes.py docs/superpowers/specs/p2-isolated-nodes-audit.csv
git commit -m "tooling: 添加孤立节点过滤脚本 + 生成初始 CSV"
```

---

## Task 2: 人工分类

**Files:**
- Modify: `docs/superpowers/specs/p2-isolated-nodes-audit.csv`

- [ ] **Step 1: 打开 CSV 逐行标注**

对每行填入 `classification` 列：

| 值 | 含义 | 下一步动作 |
|---|---|---|
| `zombie` | 确认代码无引用，可安全删除 | Task 3 删除 |
| `missing` | graphify 漏抽边，代码实际被使用 | Task 4 记录，不动代码 |
| `alive` | 低耦合但合理（例如小工具函数） | 不动 |

分类时**必须**对每个嫌疑跑一次引用验证：

```bash
# 对于函数节点
grep -rn "<function_name>" govdoc/ frontend/src/ tests/ --include="*.py" --include="*.ts" --include="*.tsx"

# 对于类节点
grep -rn "<ClassName>" govdoc/ frontend/src/ tests/
```

- 如果 grep 只找到定义本身（1 处）→ `zombie`
- 如果 grep 找到定义 + 至少 1 处使用 → `missing` 或 `alive`
  - 若使用处是 test 文件：`alive`
  - 若使用处是生产代码，说明图谱漏抽边：`missing`

- [ ] **Step 2: CSV 填写完成后统计分布**

```bash
awk -F',' 'NR>1 {print $5}' docs/superpowers/specs/p2-isolated-nodes-audit.csv | sort | uniq -c
```

Expected: 类似
```
  8 alive
  4 missing
  11 zombie
```

- [ ] **Step 3: 提交 CSV 分类结果**

```bash
git add docs/superpowers/specs/p2-isolated-nodes-audit.csv
git commit -m "docs: 完成 P2 孤立节点人工分类（X 僵尸 Y 漏抽 Z 合理）"
```

---

## Task 3: 删除僵尸代码（每个独立 commit）

**Files:**
- Delete / Modify: 按 CSV 里 `classification=zombie` 的行指向的文件

- [ ] **Step 1: 遍历 zombie 行**

对每行执行：

- [ ] **Step 1.1: 再次 grep 验证**

```bash
grep -rn "<symbol_name>" govdoc/ frontend/src/ tests/ --include="*.py" --include="*.ts" --include="*.tsx"
```

⚠️ **必须**确认只有定义本身被 grep 到，否则跳过此条（改分类为 `missing` 或 `alive`）

- [ ] **Step 1.2: 删除对应代码块**

- 函数/类：在源文件里删除定义 + 相关 import
- 整个文件：`git rm <path>`

- [ ] **Step 1.3: 跑测试确认无回归**

```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/ -v
cd frontend && npm test && cd ..
```

Expected: 全绿

- [ ] **Step 1.4: 提交该单项删除**

```bash
git add -A
git commit -m "chore: 删除僵尸代码 <symbol_name>（P2）"
```

- [ ] **Step 2: 对 CSV 里每个 zombie 重复上述 Step 1.1-1.4**

每个删除独立 commit，保留 revert 粒度。

---

## Task 4: 记录 missing 节点（不动代码）

**Files:**
- Create: `docs/superpowers/specs/p2-graphify-missing-edges.md`

- [ ] **Step 1: 写报告**

```markdown
# P2 副产物：graphify 漏抽的边

本次 P2 审查过程中发现以下节点度数 ≤1 但实际有使用，属 graphify 抽取工具的漏抽。

| 节点 | 文件 | 实际使用点 | 建议 |
|---|---|---|---|
| <symbol> | <file> | <用方> | 下次 /graphify 重跑后复核 |

（填入 CSV 里所有 classification=missing 的行）

---

下次跑 `/graphify <path> --update` 后再跑 `scripts/audit_isolated_nodes.py`，这部分节点应进入正常连通分量。
```

- [ ] **Step 2: 提交**

```bash
git add docs/superpowers/specs/p2-graphify-missing-edges.md
git commit -m "docs: 记录 P2 发现的 graphify 漏抽边"
```

---

## Task 5: 重跑 graphify 验证孤立节点下降

**Files:** 无代码改动；仅验证产物

- [ ] **Step 1: 重跑 graphify**

Run: `/graphify . --update`

Expected: 看到"Cache: X files hit, Y files need extraction"与之前类似

- [ ] **Step 2: 重跑过滤脚本**

```bash
conda run -n govdoc-auditor-v3 python scripts/audit_isolated_nodes.py /tmp/p2-verify.csv
wc -l /tmp/p2-verify.csv
```

Expected: 孤立节点数 **严格小于** Task 1 Step 3 的结果（因为 Task 3 删了 zombie）

- [ ] **Step 3: 如果数字没下降**

说明 Task 3 的删除没有真正减少代码节点 —— 可能是：
- 删除不彻底（导入语句残留）
- graphify 缓存未刷新（尝试删 `graphify-out/cache/` 再重跑）

排查后补 commit。

---

## Task 6: 推 PR + 合入 umbrella

- [ ] **Step 1**

```bash
git push -u origin feat/p2-isolated-nodes-audit
```

- [ ] **Step 2: PR 描述**

```
## 目的
P2 · 图谱 158 个孤立节点里真代码嫌疑的审查与清理

## 过程
1. scripts/audit_isolated_nodes.py 过滤出 ~23 个真嫌疑
2. 人工逐行分类：X 僵尸 / Y 漏抽 / Z 合理
3. 删除僵尸代码（每个独立 commit）
4. 记录漏抽边供下次 graphify 复核
5. 重跑 graphify 验证孤立节点数下降

## 产物
- scripts/audit_isolated_nodes.py
- docs/superpowers/specs/p2-isolated-nodes-audit.csv (分类表)
- docs/superpowers/specs/p2-graphify-missing-edges.md (漏抽记录)
- 删除的僵尸代码：见 commit history

## DoD
- [x] 过滤脚本产出 CSV
- [x] 人工分类完整
- [x] 僵尸代码删除
- [x] graphify 重跑后孤立节点数下降
```

- [ ] **Step 3: Merge 到 umbrella**

```bash
git checkout feat/tech-debt-cleanup
git merge --no-ff feat/p2-isolated-nodes-audit -m "Merge P2 · 孤立节点审查"
```

- [ ] **Step 4: 回滚演练**

---

## P2 DoD 汇总

- [ ] `scripts/audit_isolated_nodes.py` 就位并产 CSV
- [ ] CSV 每行 `classification` 已填
- [ ] 标为 `zombie` 的代码已删除（每项独立 commit）
- [ ] `docs/superpowers/specs/p2-graphify-missing-edges.md` 记录漏抽节点
- [ ] `graphify --update` 重跑后孤立节点数下降
- [ ] 全部测试 + ruff + tsc 通过
- [ ] 回滚演练通过
