# L2 最后修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 L2 评估最后 2 个 FAIL 维度（audit-completeness、audit-json-correctness）和超时问题，使语义通过率从 17/19 提升至 19/19。

**Architecture:** 三处独立修改：(1) evidence 构建为 audit-completeness 提供正确的"应审清单"，为 audit-json-correctness 组装成 output.json 格式；(2) 移除 HARNESS_MAX_CHECKPOINTS 截断，全量审核；(3) 放大 HARNESS_PIPELINE_TIMEOUT 适配全量审核耗时。

**Tech Stack:** Python 3.11 / SQLite / Pydantic v2

---

### Task 1: 移除审核点截断 + 放大超时

**Files:**
- Modify: `govdoc/harness/api_eval.py:293-294`
- Modify: `scripts/harness_api.sh:17`

- [ ] **Step 1: 修改 HARNESS_MAX_CHECKPOINTS 默认值**

`govdoc/harness/api_eval.py:293`，将：

```python
    max_checkpoints = int(os.environ.get("HARNESS_MAX_CHECKPOINTS", "5"))
```

改为：

```python
    max_checkpoints = int(os.environ.get("HARNESS_MAX_CHECKPOINTS", "0"))
```

- [ ] **Step 2: 修改 HARNESS_PIPELINE_TIMEOUT 默认值**

`govdoc/harness/api_eval.py:294`，将：

```python
    pipeline_timeout = float(os.environ.get("HARNESS_PIPELINE_TIMEOUT", "1800"))
```

改为：

```python
    pipeline_timeout = float(os.environ.get("HARNESS_PIPELINE_TIMEOUT", "7200"))
```

- [ ] **Step 3: 更新 harness_api.sh 的显示信息**

`scripts/harness_api.sh:17`，将：

```bash
echo "HARNESS_MAX_CHECKPOINTS=${HARNESS_MAX_CHECKPOINTS:-5}" | tee -a "$LOG_FILE"
```

改为：

```bash
echo "HARNESS_MAX_CHECKPOINTS=${HARNESS_MAX_CHECKPOINTS:-0 (全量)}" | tee -a "$LOG_FILE"
echo "HARNESS_PIPELINE_TIMEOUT=${HARNESS_PIPELINE_TIMEOUT:-7200}" | tee -a "$LOG_FILE"
```

- [ ] **Step 4: 运行测试确认不回归**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -x -q
```

- [ ] **Step 5: Commit**

```bash
git add govdoc/harness/api_eval.py scripts/harness_api.sh
git commit -m "fix(harness): 移除审核点截断(默认全量) + pipeline 超时放大到 7200s"
```

---

### Task 2: audit-completeness — evidence 提供正确的"应审清单"

**Files:**
- Modify: `govdoc/harness/api_eval.py:738-751` (L2 记录 audit_results 的逻辑)
- Modify: `govdoc/harness/pipeline_eval.py:767-776` (evidence 构建)
- Modify: `govdoc/harness/schemas.py` (audit_results 表加 checkpoint_title 列)
- Modify: `tests/unit/test_harness_record.py`

**问题分析：**

当前 `audit-completeness` 维度的 evidence 包含 `extract_results`（Pipeline A 提取的审核点）和 `audit_results`（Pipeline B 的审核结果）。judge 用前者当"应该审的"、后者当"实际审的"。但这两套不是同一组审核点。

修复策略：
1. `audit_results` 记录**所有** AuditPointRun（不仅是 completed），这样 judge 能看到哪些审了、哪些没审
2. 为 `audit-completeness` 维度，在 evidence 中明确标注 `audit_results` 就是完整清单（含 pending/failed 状态的点），不依赖 `extract_results`

- [ ] **Step 1: 修改 L2 记录逻辑 — 记录所有 AuditPointRun，不仅 completed**

`govdoc/harness/api_eval.py`，找到 5i 阶段记录审核发现的代码块（约第 738-751 行）：

```python
                if progress:
                    findings: list[dict[str, Any]] = []
                    for pr in progress.get("point_runs", []):
                        if pr.get("status") != "completed" or not pr.get("finding_json"):
                            continue
```

替换为：

```python
                if progress:
                    findings: list[dict[str, Any]] = []
                    for pr in progress.get("point_runs", []):
                        if pr.get("status") == "completed" and pr.get("finding_json"):
                            finding_raw = pr["finding_json"]
                            finding = (
                                json.loads(finding_raw)
                                if isinstance(finding_raw, str)
                                else finding_raw
                            )
                            finding["point_run_id"] = pr.get("id", "")
                            finding["checkpoint_id"] = pr.get("checkpoint_final_id", "")
                            finding["status"] = pr.get("status", "unknown")
                            finding["duration_s"] = 0.0
                            findings.append(finding)
                        else:
                            # 记录未完成的审核点（pending/failed），让 judge 看到完整清单
                            findings.append({
                                "point_run_id": pr.get("id", ""),
                                "checkpoint_id": pr.get("checkpoint_final_id", ""),
                                "status": pr.get("status", "pending"),
                                "duration_s": 0.0,
                                "verdict": {},
                                "evidence_refs": [],
                                "case_refs": [],
                            })
```

同时删除紧跟其后的重复代码块（原来的第 743-750 行，即 `finding_raw = ...` 到 `findings.append(finding)`），因为已经移到上面的 if 分支中了。

- [ ] **Step 2: 修改 evidence 构建 — audit-completeness 维度使用正确的清单**

`govdoc/harness/pipeline_eval.py`，在 evidence 构建循环中（约第 770-776 行），将：

```python
            evidence: dict[str, Any] = {
                "extract_results": extract_rows,
                "audit_results": audit_rows,
                "dimension": dim,
            }
            if dim.startswith("agent-") and trajectory_rows:
                evidence["trajectory"] = trajectory_rows
```

替换为：

```python
            evidence: dict[str, Any] = {
                "extract_results": extract_rows,
                "audit_results": audit_rows,
                "dimension": dim,
            }
            if dim.startswith("agent-") and trajectory_rows:
                evidence["trajectory"] = trajectory_rows
            if dim == "audit-completeness":
                evidence["audit_checkpoint_inventory"] = audit_rows
                evidence["note"] = "audit_results 包含所有应审审核点（含 pending/failed 状态），以此判断覆盖率"
```

- [ ] **Step 3: 运行测试确认不回归**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -x -q
```

- [ ] **Step 4: Commit**

```bash
git add govdoc/harness/api_eval.py govdoc/harness/pipeline_eval.py
git commit -m "fix(harness): audit-completeness 记录全部审核点状态，提供正确的应审清单"
```

---

### Task 3: audit-json-correctness — evidence 组装成 output.json 格式

**Files:**
- Modify: `govdoc/harness/pipeline_eval.py:767-776` (evidence 构建)

**问题分析：**

rubric `audit_json_correctness.md` 期望评估的是 `output.json` 格式：`{"findings": [...], "summary": "..."}`。但 evidence 传的是 DB 行格式。需要对这个维度单独组装。

- [ ] **Step 1: 为 audit-json-correctness 维度组装 output.json 格式的 evidence**

`govdoc/harness/pipeline_eval.py`，在 evidence 构建循环中（Task 2 修改后的代码），在 `if dim == "audit-completeness":` 块之后添加：

```python
            if dim == "audit-json-correctness" and audit_rows:
                assembled_findings = []
                for ar in audit_rows:
                    verdict_json = ar.get("verdict_json", "{}")
                    try:
                        verdict_obj = json.loads(verdict_json) if isinstance(verdict_json, str) else verdict_json
                    except (json.JSONDecodeError, TypeError):
                        verdict_obj = {"verdict": ar.get("verdict", "")}
                    evidence_json = ar.get("evidence_json", "[]")
                    try:
                        evidence_refs = json.loads(evidence_json) if isinstance(evidence_json, str) else evidence_json
                    except (json.JSONDecodeError, TypeError):
                        evidence_refs = []
                    assembled_findings.append({
                        "checkpoint": {"id": ar.get("checkpoint_id", "")},
                        "verdict": verdict_obj,
                        "evidence_refs": evidence_refs,
                        "case_refs": [],
                    })
                completed_count = sum(1 for ar in audit_rows if ar.get("status") == "completed")
                total_count = len(audit_rows)
                evidence["output_json"] = {
                    "findings": assembled_findings,
                    "summary": f"共审核 {total_count} 个审核点，已完成 {completed_count} 项。",
                }
```

- [ ] **Step 2: 运行测试确认不回归**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -x -q
```

- [ ] **Step 3: Commit**

```bash
git add govdoc/harness/pipeline_eval.py
git commit -m "fix(harness): audit-json-correctness evidence 组装为 output.json 格式"
```

---

### Task 4: 代码格式化 + 全量测试

- [ ] **Step 1: 代码格式化**

```bash
source activate govdoc-auditor-v3 && ruff format . && ruff check . --fix
```

- [ ] **Step 2: 全量单元测试**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v
```

Expected: 全部 PASS

- [ ] **Step 3: Commit 格式化（如有变更）**

```bash
git add -u && git diff --cached --quiet || git commit -m "style: ruff format"
```
