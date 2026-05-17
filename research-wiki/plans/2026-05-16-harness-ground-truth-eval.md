# L2 Harness Ground Truth 评估维度 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 19 维度（自洽性检查）基础上，增加 ground truth 对比维度——Pipeline A 提取结果 vs 附件9 金标准，Pipeline B 审核结论 vs 人类工作底稿。

**Architecture:** 扩展 harness manifest 添加 `ground_truth` 节点声明参考文件路径；在 `api_eval.py` 阶段解析 ground truth 并存入 harness.db 的 `_events` 表；在 `_run_semantic_evaluations` 中为新维度组装 evidence（系统输出 + ground truth）交给 judge 对比评分。

**Tech Stack:** Python 3.11 / xlrd / python-docx / sqlite3 / 现有 HarnessJudge (qwen3.6-plus)

---

## File Structure

| 文件 | 职责 | 操作 |
|------|------|------|
| `govdoc/harness/manifest.py` | 扩展 manifest 模型添加 ground_truth 字段 | MODIFY |
| `govdoc/harness/ground_truth.py` | 解析 ground truth 文件（附件9 + 人类工作底稿） | CREATE |
| `govdoc/harness/api_eval.py` | 在评估流程中加载 ground truth 并存入 events | MODIFY |
| `govdoc/harness/pipeline_eval.py` | 为新维度组装 evidence | MODIFY |
| `scripts/fixtures/harness_manifest.yaml` | 添加 ground_truth 节点 | MODIFY |
| `scripts/rubrics/extract_gold_coverage.md` | 新 rubric | CREATE |
| `scripts/rubrics/extract_gold_alignment.md` | 新 rubric | CREATE |
| `scripts/rubrics/audit_ground_truth.md` | 新 rubric | CREATE |
| `tests/unit/test_ground_truth.py` | 新模块单元测试 | CREATE |

---

### Task 1: 解析 ground truth 文件的工具模块

**Files:**
- Create: `govdoc/harness/ground_truth.py`
- Test: `tests/unit/test_ground_truth.py`

- [ ] **Step 1: Write the failing test — 解析附件9**

```python
"""tests/unit/test_ground_truth.py"""

from __future__ import annotations

from pathlib import Path

from govdoc.harness.ground_truth import parse_gold_checkpoints


def test_parse_gold_checkpoints_returns_52_items() -> None:
    """附件9 应解析出 52 个金标准审核点。"""
    path = Path("real_data/附件9 处理处罚标准.xls")
    if not path.exists():
        import pytest

        pytest.skip("real_data not available")
    items = parse_gold_checkpoints(path)
    assert len(items) == 52
    first = items[0]
    assert "title" in first
    assert "description" in first
    assert "category" in first
    assert first["description"] != ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_ground_truth.py::test_parse_gold_checkpoints_returns_52_items -v`
Expected: FAIL with "ModuleNotFoundError" or "ImportError"

- [ ] **Step 3: Implement parse_gold_checkpoints**

```python
"""govdoc/harness/ground_truth.py
Ground truth 解析工具——从附件9和人类工作底稿中提取结构化数据。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def parse_gold_checkpoints(path: Path) -> list[dict[str, str]]:
    """解析附件9（金标准审核点表）为结构化列表。

    复用 checkpoint_import 解析器，输出精简 dict 供 judge 对比。

    Args:
        path: 附件9 xls/xlsx 文件路径。

    Returns:
        每项包含 title, description, category 的 dict 列表。
    """
    from govdoc.parsers.checkpoint_import import parse_checkpoint_file

    checkpoints, _ = parse_checkpoint_file(path)
    return [
        {
            "title": cp.title,
            "description": cp.description,
            "category": cp.category.value,
        }
        for cp in checkpoints
    ]


def parse_human_workpaper(path: Path) -> dict[str, Any]:
    """解析人类撰写的工作底稿 docx 为结构化数据。

    人类工作底稿为固定模板（8行×2列表格），核心内容在 Row5「检查情况摘要」。

    Args:
        path: 人类工作底稿 .docx 文件路径。

    Returns:
        dict 包含：
          - project_name: 检查项目名
          - checked_unit: 被检查单位
          - summary_text: 检查情况摘要全文
          - findings_text: 从摘要中提取的具体发现列表（按分段/编号切分）
    """
    from docx import Document

    doc = Document(str(path))
    if not doc.tables:
        logger.warning("人类工作底稿无表格: %s", path)
        return {"project_name": "", "checked_unit": "", "summary_text": "", "findings_text": []}

    table = doc.tables[0]
    rows = table.rows

    checked_unit = rows[1].cells[1].text.strip() if len(rows) > 1 else ""
    project_name = rows[2].cells[1].text.strip() if len(rows) > 2 else ""
    summary_text = rows[5].cells[1].text.strip() if len(rows) > 5 else ""

    # 从摘要中按编号/换行切分具体发现
    import re

    findings_text = [
        s.strip()
        for s in re.split(r"\n(?=\d+[、.]|招标文件)", summary_text)
        if s.strip() and not s.strip().startswith("根据")
    ]

    return {
        "project_name": project_name,
        "checked_unit": checked_unit,
        "summary_text": summary_text,
        "findings_text": findings_text,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_ground_truth.py::test_parse_gold_checkpoints_returns_52_items -v`
Expected: PASS

- [ ] **Step 5: Write and run the human workpaper test**

在 `tests/unit/test_ground_truth.py` 追加：

```python
from govdoc.harness.ground_truth import parse_human_workpaper


def test_parse_human_workpaper_extracts_summary() -> None:
    """人类工作底稿应提取出检查情况摘要。"""
    path = Path(
        "real_data/2023年度汕头市潮阳区流域面积50km²以下 "
        "河道管理范围划界工作服务项目/"
        "2023年度汕头市潮阳区流域面积50km²以下 "
        "河道管理范围划界工作服务项目.docx"
    )
    if not path.exists():
        import pytest

        pytest.skip("real_data not available")
    result = parse_human_workpaper(path)
    assert result["checked_unit"] == "广东策成工程咨询服务有限公司"
    assert "资信证书" in result["summary_text"]
    assert len(result["findings_text"]) >= 1
```

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_ground_truth.py -v`
Expected: 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add govdoc/harness/ground_truth.py tests/unit/test_ground_truth.py
git commit -m "feat(harness): ground_truth 模块——解析附件9和人类工作底稿"
```

---

### Task 2: 扩展 manifest 支持 ground_truth 声明

**Files:**
- Modify: `govdoc/harness/manifest.py:40-47`
- Modify: `scripts/fixtures/harness_manifest.yaml`
- Test: `tests/unit/test_ground_truth.py`（追加）

- [ ] **Step 1: Write the failing test**

在 `tests/unit/test_ground_truth.py` 追加：

```python
from govdoc.harness.manifest import load_manifest


def test_manifest_loads_ground_truth_section(tmp_path: Path) -> None:
    """manifest 应能加载 ground_truth 节点。"""
    manifest_yaml = tmp_path / "manifest.yaml"
    manifest_yaml.write_text(
        """
projects: []
rules: []
checkpoints: []
ground_truth:
  gold_checkpoints: "real_data/附件9.xls"
  human_workpapers:
    - project_name: "汕头河道项目"
      path: "real_data/汕头.docx"
""",
        encoding="utf-8",
    )
    m = load_manifest(str(manifest_yaml), project_root=str(tmp_path))
    assert m.ground_truth is not None
    assert m.ground_truth.gold_checkpoints == tmp_path / "real_data/附件9.xls"
    assert len(m.ground_truth.human_workpapers) == 1
    assert m.ground_truth.human_workpapers[0].project_name == "汕头河道项目"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_ground_truth.py::test_manifest_loads_ground_truth_section -v`
Expected: FAIL (AttributeError: 'HarnessManifest' has no attribute 'ground_truth')

- [ ] **Step 3: Extend manifest models**

修改 `govdoc/harness/manifest.py`，在 `CheckpointFixture` 之后添加：

```python
@dataclass(frozen=True)
class HumanWorkpaperFixture:
    """人类工作底稿参考文件。"""

    project_name: str
    path: Path


@dataclass(frozen=True)
class GroundTruthFixture:
    """Ground truth 参考数据配置。"""

    gold_checkpoints: Path | None
    human_workpapers: list[HumanWorkpaperFixture]
```

修改 `HarnessManifest`：

```python
@dataclass(frozen=True)
class HarnessManifest:
    """Harness manifest 的结构化表示。"""

    projects: list[ProjectFixture]
    rules: list[RuleFixture]
    checkpoints: list[CheckpointFixture]
    ground_truth: GroundTruthFixture | None = None
```

修改 `load_manifest` 函数，在 `checkpoints = [...]` 之后添加：

```python
    gt_data = data.get("ground_truth")
    ground_truth = None
    if gt_data:
        gt_cp_path = gt_data.get("gold_checkpoints")
        human_wps = [
            HumanWorkpaperFixture(
                project_name=item["project_name"],
                path=_resolve_path(item["path"], root_path),
            )
            for item in gt_data.get("human_workpapers", [])
        ]
        ground_truth = GroundTruthFixture(
            gold_checkpoints=_resolve_path(gt_cp_path, root_path) if gt_cp_path else None,
            human_workpapers=human_wps,
        )

    manifest = HarnessManifest(
        projects=projects, rules=rules, checkpoints=checkpoints, ground_truth=ground_truth
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_ground_truth.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Update harness_manifest.yaml**

在 `scripts/fixtures/harness_manifest.yaml` 末尾追加：

```yaml
ground_truth:
  gold_checkpoints: "real_data/附件9 处理处罚标准.xls"
  human_workpapers:
    - project_name: "从化医院采购"
      path: "real_data/从化区中医医院手术室设备及附件、病房护理及医院设备采购/从化区中医医院手术室设备及附件、病房护理及医院设备采购.docx"
    - project_name: "汕头河道项目"
      path: "real_data/2023年度汕头市潮阳区流域面积50km²以下 河道管理范围划界工作服务项目/2023年度汕头市潮阳区流域面积50km²以下 河道管理范围划界工作服务项目.docx"
```

- [ ] **Step 6: Commit**

```bash
git add govdoc/harness/manifest.py scripts/fixtures/harness_manifest.yaml
git commit -m "feat(harness): manifest 支持 ground_truth 节点"
```

---

### Task 3: 在 api_eval 阶段存储 ground truth 数据

**Files:**
- Modify: `govdoc/harness/api_eval.py:295-310`（导入区）
- Modify: `govdoc/harness/api_eval.py:950-955`（语义评估前）

- [ ] **Step 1: Write the failing test**

在 `tests/unit/test_ground_truth.py` 追加：

```python
import json

from govdoc.harness.log import HarnessLog
from govdoc.harness.schemas import create_all_tables


def test_store_and_retrieve_ground_truth_events(tmp_path: Path) -> None:
    """ground truth 数据应能存入 _events 表并读回。"""
    db_path = str(tmp_path / "harness.db")
    with HarnessLog(db_path=db_path, run_id="gt-test") as log:
        create_all_tables(log)
        log.log_event(
            "ground_truth_checkpoints",
            {
                "count": 52,
                "items": [{"title": "测试", "description": "描述", "category": "围标串标"}],
            },
        )
        log.log_event(
            "ground_truth_workpaper",
            {
                "project_name": "汕头",
                "summary_text": "经审查存在以下问题...",
                "findings_text": ["招标文件第32页..."],
            },
        )

        rows = log.query(
            "SELECT payload FROM _events WHERE run_id=? AND event_type=?",
            ("gt-test", "ground_truth_checkpoints"),
        )
    assert len(rows) == 1
    data = json.loads(rows[0]["payload"])
    assert data["count"] == 52
```

- [ ] **Step 2: Run test to verify it passes** (利用现有基础设施，应该直接 pass)

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_ground_truth.py::test_store_and_retrieve_ground_truth_events -v`
Expected: PASS（log_event 已有此能力）

- [ ] **Step 3: Modify api_eval.py — 在语义评估前加载 ground truth**

在 `govdoc/harness/api_eval.py` 的 `# ── Phase 9: 语义评估 ──` 之前（约 line 950），插入：

```python
            # ── Phase 8.5: 存储 Ground Truth ──
            if manifest.ground_truth:
                from govdoc.harness.ground_truth import (
                    parse_gold_checkpoints,
                    parse_human_workpaper,
                )

                gt = manifest.ground_truth
                if gt.gold_checkpoints and gt.gold_checkpoints.exists():
                    gold_items = parse_gold_checkpoints(gt.gold_checkpoints)
                    log.log_event(
                        "ground_truth_checkpoints",
                        {"count": len(gold_items), "items": gold_items},
                    )
                    logger.info("已加载金标准审核点: %d 项", len(gold_items))

                for wp_fixture in gt.human_workpapers:
                    if wp_fixture.path.exists():
                        wp_data = parse_human_workpaper(wp_fixture.path)
                        wp_data["fixture_project_name"] = wp_fixture.project_name
                        log.log_event("ground_truth_workpaper", wp_data)
                        logger.info(
                            "已加载人类工作底稿: %s (%d 个发现)",
                            wp_fixture.project_name,
                            len(wp_data.get("findings_text", [])),
                        )
```

- [ ] **Step 4: Run all unit tests**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add govdoc/harness/api_eval.py tests/unit/test_ground_truth.py
git commit -m "feat(harness): api_eval 阶段加载 ground truth 并存入 events"
```

---

### Task 4: 编写新维度的 rubric 文件

**Files:**
- Create: `scripts/rubrics/extract_gold_coverage.md`
- Create: `scripts/rubrics/extract_gold_alignment.md`
- Create: `scripts/rubrics/audit_ground_truth.md`

- [ ] **Step 1: Create extract_gold_coverage.md**

```markdown
# 金标准覆盖率 (extract-gold-coverage)

## 评判标准
对比系统提取的审核点（extract_results）与金标准审核点表（附件9，52 子项）：
1. 金标准中的 15 个大类标题是否每个都有对应提取项
2. 每个大类下的子项（表现形式），系统是否覆盖到
3. 子项 description 的语义是否对应（不要求字面完全一致）

## 评分规则
- 1.0：覆盖全部 15 大类且每类子项覆盖率 ≥ 80%
- 0.7-0.9：覆盖全部大类，部分子项有遗漏
- 0.4-0.6：遗漏 1-3 个大类
- 0.0-0.3：遗漏 4 个以上大类或子项覆盖极低

## 判定阈值
score >= 0.7 → passed
```

- [ ] **Step 2: Create extract_gold_alignment.md**

```markdown
# 金标准对齐度 (extract-gold-alignment)

## 评判标准
对于系统提取的审核点中能与金标准匹配的项，检查对齐质量：
1. 系统提取的 description 是否与金标准的「表现形式」语义一致
2. 系统提取的 category 分类是否与金标准对应大类一致
3. 系统是否生成了金标准中不存在的审核点（多余项/幻觉项）

## 评分规则
- 1.0：所有可匹配项的 description 和 category 均一致，无多余幻觉项
- 0.7-0.9：大部分一致，个别描述有差异但不影响审核方向
- 0.4-0.6：约半数项有描述偏差或分类错误
- 0.0-0.3：大量偏差，系统提取内容与金标准严重不对齐

## 判定阈值
score >= 0.7 → passed
```

- [ ] **Step 3: Create audit_ground_truth.md**

```markdown
# 审核结论 Ground Truth 对比 (audit-ground-truth)

## 评判标准
对比 AI 审核结论与人类工作底稿的检查发现：
1. 人类发现的违规问题，AI 是否也发现了（召回）
2. AI 发现的「不合规」项，是否与人类发现一致或合理（精准）
3. 考虑输入差异：若 AI 的输入文件不包含人类审查的部分，对应的未召回不扣分
4. AI 比人类发现更多合理问题不扣分（更详细不是错误）

## 评分规则
- 1.0：人类发现全部被 AI 覆盖，或可合理解释为输入差异
- 0.7-0.9：人类发现大部分被覆盖，个别遗漏有合理原因
- 0.4-0.6：人类发现约半数未被 AI 覆盖，且非输入差异导致
- 0.0-0.3：AI 结论与人类严重偏离

## 判定阈值
score >= 0.6 → passed

## 特殊说明
AI 输入可能仅为招标公告（不含完整采购文件），而人类可能审查了评审报告、投标文件等完整资料。
judge 应考虑此差异：如果 AI 的输入中确实不包含人类发现问题所在的页面/章节，该项不应扣分。
```

- [ ] **Step 4: Commit**

```bash
git add scripts/rubrics/extract_gold_coverage.md scripts/rubrics/extract_gold_alignment.md scripts/rubrics/audit_ground_truth.md
git commit -m "feat(harness): 新增 3 个 ground truth 对比维度的 rubric"
```

---

### Task 5: 在 _run_semantic_evaluations 中组装新维度 evidence

**Files:**
- Modify: `govdoc/harness/pipeline_eval.py:745-765`（dimensions 列表）
- Modify: `govdoc/harness/pipeline_eval.py:767-820`（evidence 构建循环）

- [ ] **Step 1: 在 dimensions 列表中添加新维度**

在 `govdoc/harness/pipeline_eval.py` 的 `dimensions = [...]` 列表末尾（`"workpaper-format-compliance"` 之后）追加：

```python
        "extract-gold-coverage",
        "extract-gold-alignment",
        "audit-ground-truth",
```

- [ ] **Step 2: 在 evidence 组装逻辑中增加 ground truth 数据**

在 `if dim.startswith("workpaper-"):` 代码块之后、`if dim == "audit-json-correctness" and audit_rows:` 之前，插入：

```python
            if dim.startswith("extract-gold-") and extract_rows:
                gt_cp_events = log.query(
                    "SELECT payload FROM _events WHERE run_id=? AND event_type='ground_truth_checkpoints'",
                    (log._run_id,),
                )
                if gt_cp_events:
                    gt_data = json.loads(gt_cp_events[-1]["payload"])
                    evidence["gold_checkpoints"] = gt_data.get("items", [])
                    evidence["gold_count"] = gt_data.get("count", 0)
            if dim == "audit-ground-truth" and audit_rows:
                gt_wp_events = log.query(
                    "SELECT payload FROM _events WHERE run_id=? AND event_type='ground_truth_workpaper'",
                    (log._run_id,),
                )
                if gt_wp_events:
                    evidence["human_workpapers"] = [
                        json.loads(e["payload"]) for e in gt_wp_events
                    ]
```

- [ ] **Step 3: Run all unit tests**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v`
Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add govdoc/harness/pipeline_eval.py
git commit -m "feat(harness): 新维度 evidence 组装——gold checkpoints + human workpaper"
```

---

### Task 6: 修复已有的 evidence 组装问题

**Files:**
- Modify: `govdoc/harness/pipeline_eval.py`（已在 commit ff99fa0 完成）
- Modify: `govdoc/harness/api_eval.py`（已在 commit ff99fa0 完成）

> 注意：此任务的代码已在本 session 较早时提交（commit ff99fa0）。如果 harness.db 是全新的（即上面的 Task 3-5 合入后重跑 L2），这两个修复已生效。此 task 仅做验证。

- [ ] **Step 1: 验证 extract-json-correctness evidence 转换逻辑存在**

Run: `source activate govdoc-auditor-v3 && grep -A5 'extract-json-correctness.*extract_rows' govdoc/harness/pipeline_eval.py`
Expected: 看到 `output_json` 中有 `"checkpoints"` 根键

- [ ] **Step 2: 验证 workpaper-summarization 的 workpaper_draft event 逻辑存在**

Run: `source activate govdoc-auditor-v3 && grep -A3 'workpaper_draft' govdoc/harness/api_eval.py`
Expected: 看到 `log.log_event("workpaper_draft", ...)` 调用

- [ ] **Step 3: Run all unit tests**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v`
Expected: all PASS

- [ ] **Step 4: Commit (only if any fix was needed)**

```bash
git add -A && git commit -m "fix(harness): 确认 evidence 组装修复已就位"
```

---

### Task 7: 集成测试——本地跑完整语义评估验证新维度

- [ ] **Step 1: 清理旧 harness.db 并重启 FastAPI**

```bash
rm -f results/harness.db
tmux kill-session -t govdoc-api 2>/dev/null
tmux new-session -d -s govdoc-api 'eval "$(conda shell.bash hook)" && conda activate govdoc-auditor-v3 && export no_proxy="110.42.53.85,100.81.95.44,localhost,127.0.0.1" && export NO_PROXY="110.42.53.85,100.81.95.44,localhost,127.0.0.1" && python -c "from govdoc.api.main import app; import uvicorn; uvicorn.run(app, host=\"0.0.0.0\", port=8000, log_level=\"info\")" 2>&1; echo "=== EXITED ==="; sleep 86400'
```

- [ ] **Step 2: 启动 L2 harness**

```bash
tmux kill-session -t l2-eval 2>/dev/null
tmux new-session -d -s l2-eval "export HARNESS_PIPELINE_TIMEOUT=43200 && bash scripts/harness_api.sh 2>&1; echo '=== L2 FINISHED ==='; sleep 86400"
```

- [ ] **Step 3: 等待完成后检查新维度分数**

```bash
source activate govdoc-auditor-v3 && python3 -c "
import sqlite3, json
conn = sqlite3.connect('results/harness.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT dimension, score, passed, judge_reasoning FROM quality_scores ORDER BY dimension').fetchall()
print(f'总维度: {len(rows)}')
for r in rows:
    status = 'PASS' if r[\"passed\"] else 'FAIL'
    print(f'  {r[\"dimension\"]:<35} {r[\"score\"]:>5.2f} {status}')
    if 'gold' in r['dimension'] or 'ground' in r['dimension']:
        print(f'    reasoning: {r[\"judge_reasoning\"][:150]}')
conn.close()
"
```

Expected: 22 维度（19 原有 + 3 新增），新维度有分数输出

- [ ] **Step 4: Commit test results to research-wiki (如有需要)**

记录评测结果到 `research-wiki/findings/` 便于后续对比。

---

## Acceptance Criteria

1. `parse_gold_checkpoints` 正确解析附件9 为 52 项结构化数据
2. `parse_human_workpaper` 正确提取人类工作底稿的检查情况摘要
3. manifest 新增 `ground_truth` 节点不影响旧字段解析
4. L2 运行时能加载 ground truth 并存入 events
5. 3 个新维度在 `_run_semantic_evaluations` 中正确组装 evidence 并由 judge 评分
6. 之前的 2 个 evidence 修复（extract-json-correctness / workpaper-summarization）仍然生效
7. 最终 L2 输出 22 维度评分（19 + 3）

## Risks

- **Judge 对 ground truth 对比的评分可能不稳定**：qwen3.6-plus 模型对复杂对比任务的一致性有限。mitigation: rubric 写清楚评分档位，减少模糊地带
- **输入差异导致 audit-ground-truth 天然偏低**：AI 只有公告，人类有全套文件。mitigation: rubric 明确说明"输入差异不扣分"，阈值设 0.6
- **附件9 解析器依赖 xlrd**：已有且测试通过，风险低
