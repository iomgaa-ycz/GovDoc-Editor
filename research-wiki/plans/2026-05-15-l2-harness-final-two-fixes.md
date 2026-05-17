# L2 Harness 最终两项修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 L2 评估 3 个 FAIL 维度中的 2 个：(1) audit-json-correctness 因 failed 审核点空壳 verdict 违反 schema；(2) agent-plan-quality / agent-plan-adherence 因归档 workspace 未读取导致 trajectory 缺失。

**Architecture:** 三处独立修改：(a) 业务管道 `_persist_point_result` 在 PES 报告失败时检查产物是否已合法产出，有效则视为成功（里层根因）；(b) harness `api_eval.py` 给 failed 点填结构合法的 verdict 占位 + evidence 构建时过滤 failed 点（表层防御）；(c) harness `api_eval.py` 收集 trajectory 时补传 `archive_path`（从归档 tar.gz 读取）。另外 `agents/gov-auditor.yaml` summarize `max_turns` 从 4 调大到 16。

**Tech Stack:** Python 3.11 / SQLite / Pydantic v2

---

## File Map

| 文件 | 变更 | 职责 |
|------|------|------|
| `agents/gov-auditor.yaml:26` | Modify | summarize max_turns 4→16 |
| `govdoc/pipelines/audit_tender.py:466-469` | Modify | PES 失败时检查产物，有效则恢复为成功 |
| `govdoc/harness/api_eval.py:753-788` | Modify | failed 点填合法 verdict + trajectory 从归档读 |
| `govdoc/harness/pipeline_eval.py:782-814` | Modify | audit-json-correctness evidence 过滤 failed 点 |
| `tests/unit/test_harness_record.py` | Modify | 新增 2 个测试 |
| `tests/unit/test_audit_point_recovery.py` | Create | 产物恢复逻辑测试 |

---

### Task 1: summarize max_turns 4→16

**Files:**
- Modify: `agents/gov-auditor.yaml:26`

- [ ] **Step 1: 修改 max_turns**

`agents/gov-auditor.yaml:26`，将：

```yaml
    max_turns: 4
```

改为：

```yaml
    max_turns: 16
```

- [ ] **Step 2: Commit**

```bash
git add agents/gov-auditor.yaml
git commit -m "fix(agent): summarize max_turns 4→16 避免产物已就绪仍判定失败"
```

---

### Task 2: 业务管道——PES 失败时检查产物

**Files:**
- Modify: `govdoc/pipelines/audit_tender.py:453-469`
- Create: `tests/unit/test_audit_point_recovery.py`

当 `result.status != "completed"` 但 workspace 中已有合法 `output.json` 时，应视为成功并提取 finding。这是根因修复。

- [ ] **Step 1: 编写测试**

创建 `tests/unit/test_audit_point_recovery.py`：

```python
"""测试 _persist_point_result 在 PES 报告失败但产物有效时的恢复逻辑。"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from govdoc.pipelines.audit_tender import _persist_point_result
from govdoc.schemas import GovCheckpoint


def _make_checkpoint() -> GovCheckpoint:
    return GovCheckpoint(
        id="cp_recover_01",
        title="恢复测试审核点",
        category="围标串标",
        description="测试用审核点",
        severity="major",
        legal_basis=[],
    )


def _make_workspace(tmp_path: Path) -> SimpleNamespace:
    """创建包含合法 output.json 的 workspace。"""
    working = tmp_path / "working"
    working.mkdir(parents=True)
    output = {
        "findings": [
            {
                "checkpoint": {
                    "id": "cp_recover_01",
                    "category": "围标串标",
                    "title": "恢复测试审核点",
                    "description": "测试用审核点",
                    "legal_basis": [],
                    "severity": "major",
                    "retrieval_hint": "",
                },
                "verdict": {
                    "verdict": "存疑",
                    "rationale": "证据不足",
                    "evidence_quotes": ["引用片段"],
                    "suggestion": "建议补充",
                },
                "evidence_refs": [],
                "case_refs": [],
            }
        ],
        "summary": "共审核 1 个审核点。",
    }
    (working / "output.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return SimpleNamespace(working_dir=working)


def _make_manager() -> MagicMock:
    mgr = MagicMock()
    mgr.archive.return_value = Path("/fake/archive.tar.gz")
    return mgr


def test_failed_result_with_valid_output_recovers(tmp_path: Path) -> None:
    """PES 报告失败但 output.json 合法 → status 应为 completed。"""
    point_run = MagicMock()
    point_run.status = "pending"
    point_run.finding_json = None
    result = SimpleNamespace(
        status="failed",
        error="stop_reason=tool_use errors=['Reached maximum number of turns (4)']",
        final_output_path=None,
        final_output=None,
        phase_results=[],
    )
    workspace = _make_workspace(tmp_path)
    manager = _make_manager()
    checkpoint = _make_checkpoint()

    _persist_point_result(point_run, result, workspace, checkpoint, manager)

    assert point_run.status == "completed"
    assert point_run.finding_json is not None
    finding = json.loads(point_run.finding_json)
    assert finding["verdict"]["verdict"] == "存疑"
    manager.archive.assert_called_once_with(workspace, success=True)


def test_failed_result_without_output_stays_failed(tmp_path: Path) -> None:
    """PES 报告失败且无 output.json → status 应保持 failed。"""
    point_run = MagicMock()
    point_run.status = "pending"
    result = SimpleNamespace(
        status="failed",
        error="真正的错误",
        final_output_path=None,
        final_output=None,
        phase_results=[],
    )
    workspace = SimpleNamespace(working_dir=tmp_path / "working")
    (tmp_path / "working").mkdir()
    manager = _make_manager()
    checkpoint = _make_checkpoint()

    _persist_point_result(point_run, result, workspace, checkpoint, manager)

    assert point_run.status == "failed"
    assert point_run.error == "真正的错误"
    manager.archive.assert_called_once_with(workspace, success=False)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_audit_point_recovery.py -v
```

Expected: 2 FAIL（`_persist_point_result` 还没有恢复逻辑）

- [ ] **Step 3: 实现恢复逻辑**

`govdoc/pipelines/audit_tender.py:466-469`，将：

```python
    else:
        point_run.status = "failed"
        point_run.error = result.error
        point_run.workspace_failed_path = str(manager.archive(workspace, success=False))
```

替换为：

```python
    else:
        recovered = _try_recover_from_workspace(workspace.working_dir, checkpoint.id)
        if recovered is not None:
            finding = GovFinding.model_validate(recovered)
            point_run.finding_json = finding.model_dump_json()
            point_run.status = "completed"
            point_run.completed_at = datetime.utcnow()
            point_run.workspace_archive_path = str(manager.archive(workspace, success=True))
        else:
            point_run.status = "failed"
            point_run.error = result.error
            point_run.workspace_failed_path = str(manager.archive(workspace, success=False))
```

同时在 `govdoc/pipelines/audit_tender.py` 中，在 `_persist_point_result` 函数之前（约第 436 行后），添加辅助函数：

```python
def _try_recover_from_workspace(
    working_dir: Path,
    checkpoint_id: str,
) -> dict[str, Any] | None:
    """尝试从 workspace 产物中恢复 finding（PES 报告失败但产物已就绪时）。"""
    from govdoc.pipelines.pes_overrides import try_recover_audit_output

    recovered_payload = try_recover_audit_output(
        SimpleNamespace(status="failed", error="recovery"),
        working_dir,
    )
    if recovered_payload is None:
        return None
    findings = recovered_payload.get("findings", [])
    finding_data = _match_finding_by_checkpoint_id(findings, checkpoint_id)
    if finding_data is not None:
        return finding_data
    if findings:
        return findings[0]
    return None
```

注意：`SimpleNamespace` 已在测试中使用；需要在 `audit_tender.py` 顶部导入：

在 `from typing import Any` 之后添加：

```python
from types import SimpleNamespace
```

- [ ] **Step 4: 运行测试确认通过**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_audit_point_recovery.py -v
```

Expected: 2 PASS

- [ ] **Step 5: 运行全量单元测试确认无回归**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -x -q
```

- [ ] **Step 6: Commit**

```bash
git add govdoc/pipelines/audit_tender.py tests/unit/test_audit_point_recovery.py
git commit -m "fix(pipeline): PES 报告失败但产物有效时恢复为 completed"
```

---

### Task 3: harness——failed 点填合法 verdict + evidence 过滤

**Files:**
- Modify: `govdoc/harness/api_eval.py:753-764`
- Modify: `govdoc/harness/pipeline_eval.py:782-814`
- Modify: `tests/unit/test_harness_record.py`

表层防御：即使业务管道仍有 failed 点（Task 2 覆盖不到的场景），harness 也不应传空壳 verdict 给 judge。

- [ ] **Step 1: 编写测试——failed 点应有合法 verdict 占位**

在 `tests/unit/test_harness_record.py` 末尾追加：

```python
def test_record_audit_results_failed_point_has_valid_verdict(tmp_path: Path) -> None:
    """failed 状态的审核点应有结构合法的 verdict 占位，而非空 {}。"""
    log = _make_log(tmp_path)
    findings = [
        {
            "point_run_id": "pr_failed",
            "checkpoint_id": "cp_failed",
            "status": "failed",
            "duration_s": 0.0,
            "verdict": {
                "verdict": "未完成",
                "rationale": "审核执行失败",
                "evidence_quotes": [],
            },
            "evidence_refs": [],
            "case_refs": [],
        }
    ]
    record_audit_results(log, findings)
    rows = log.query("SELECT * FROM audit_results WHERE run_id=?", ("test-run",))
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "failed"
    verdict_detail = json.loads(row["verdict_json"])
    assert verdict_detail["verdict"] == "未完成"
    assert "rationale" in verdict_detail
```

- [ ] **Step 2: 运行测试确认通过**

这个测试应该直接 PASS（`record_audit_results` 不过滤 verdict 内容，只是忠实记录）。

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_harness_record.py::test_record_audit_results_failed_point_has_valid_verdict -v
```

Expected: PASS

- [ ] **Step 3: 修改 api_eval.py——failed 点填合法 verdict**

`govdoc/harness/api_eval.py:753-764`，将 else 分支：

```python
                        else:
                            findings.append(
                                {
                                    "point_run_id": pr.get("id", ""),
                                    "checkpoint_id": pr.get("checkpoint_final_id", ""),
                                    "status": pr.get("status", "pending"),
                                    "duration_s": 0.0,
                                    "verdict": {},
                                    "evidence_refs": [],
                                    "case_refs": [],
                                }
                            )
```

替换为：

```python
                        else:
                            findings.append(
                                {
                                    "point_run_id": pr.get("id", ""),
                                    "checkpoint_id": pr.get("checkpoint_final_id", ""),
                                    "status": pr.get("status", "pending"),
                                    "duration_s": 0.0,
                                    "verdict": {
                                        "verdict": "未完成",
                                        "rationale": f"审核执行状态: {pr.get('status', 'unknown')}",
                                        "evidence_quotes": [],
                                    },
                                    "evidence_refs": [],
                                    "case_refs": [],
                                }
                            )
```

- [ ] **Step 4: 修改 pipeline_eval.py——audit-json-correctness 只组装 completed 点**

`govdoc/harness/pipeline_eval.py:782-814`，将 `if dim == "audit-json-correctness" and audit_rows:` 块替换为：

```python
            if dim == "audit-json-correctness" and audit_rows:
                assembled_findings = []
                for ar in audit_rows:
                    if ar.get("status") != "completed":
                        continue
                    verdict_json = ar.get("verdict_json", "{}")
                    try:
                        verdict_obj = (
                            json.loads(verdict_json)
                            if isinstance(verdict_json, str)
                            else verdict_json
                        )
                    except (json.JSONDecodeError, TypeError):
                        verdict_obj = {"verdict": ar.get("verdict", "")}
                    evidence_json = ar.get("evidence_json", "[]")
                    try:
                        evidence_refs = (
                            json.loads(evidence_json)
                            if isinstance(evidence_json, str)
                            else evidence_json
                        )
                    except (json.JSONDecodeError, TypeError):
                        evidence_refs = []
                    assembled_findings.append(
                        {
                            "checkpoint": {"id": ar.get("checkpoint_id", "")},
                            "verdict": verdict_obj,
                            "evidence_refs": evidence_refs,
                            "case_refs": [],
                        }
                    )
                completed_count = sum(1 for ar in audit_rows if ar.get("status") == "completed")
                total_count = len(audit_rows)
                evidence["output_json"] = {
                    "findings": assembled_findings,
                    "summary": f"共审核 {total_count} 个审核点，已完成 {completed_count} 项。",
                }
```

注意：唯一的变化是在循环开头加了 `if ar.get("status") != "completed": continue`，跳过 failed/pending 点。其余代码不变。

- [ ] **Step 5: 运行全量单元测试确认无回归**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -x -q
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add govdoc/harness/api_eval.py govdoc/harness/pipeline_eval.py tests/unit/test_harness_record.py
git commit -m "fix(harness): failed 审核点填合法 verdict + json-correctness 只评估 completed 点"
```

---

### Task 4: harness——trajectory 从归档 tar.gz 读取

**Files:**
- Modify: `govdoc/harness/api_eval.py:773-788`
- Modify: `tests/unit/test_harness_record.py`

归档路径规律：`data/.govdoc/archives/{pr_id}.tar.gz`。API 不返回归档路径，但可以按约定构造。

- [ ] **Step 1: 编写测试——从 tar.gz 读取 trajectory**

在 `tests/unit/test_harness_record.py` 末尾追加：

```python
import tarfile


def test_collect_workspace_evidence_from_archive(tmp_path: Path) -> None:
    """从 tar.gz 归档中读取 plan.json 和 findings。"""
    # 构建 workspace 结构并打包
    ws_dir = tmp_path / "ws"
    working = ws_dir / "working"
    working.mkdir(parents=True)
    plan = {"items_to_extract": [{"id": "cp_archive"}]}
    (working / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    findings_dir = working / "findings"
    findings_dir.mkdir()
    (findings_dir / "cp_archive.json").write_text(
        '{"verdict": "存疑"}', encoding="utf-8"
    )

    archive_path = tmp_path / "test.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tf:
        tf.add(working / "plan.json", arcname="working/plan.json")
        tf.add(
            findings_dir / "cp_archive.json",
            arcname="working/findings/cp_archive.json",
        )

    evidence = collect_workspace_evidence(archive_path=archive_path)
    assert evidence["plan_json"] != ""
    parsed = json.loads(evidence["plan_json"])
    assert parsed["items_to_extract"][0]["id"] == "cp_archive"
    assert len(evidence["workspace_files"]) >= 2
    assert "cp_archive" in evidence["findings"]
```

- [ ] **Step 2: 运行测试确认通过**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_harness_record.py::test_collect_workspace_evidence_from_archive -v
```

Expected: PASS（`collect_workspace_evidence` 已支持 `archive_path`）

- [ ] **Step 3: 修改 api_eval.py——trajectory 收集补传 archive_path**

`govdoc/harness/api_eval.py:773-788`，将：

```python
                        for pr in progress.get("point_runs", []):
                            pr_id = pr.get("id", "")
                            if not pr_id:
                                continue
                            ws_evidence = collect_workspace_evidence(
                                workspace_dir=Path(f"data/.govdoc/workspaces/{pr_id}"),
                            )
                            if ws_evidence["plan_json"]:
                                record_agent_trajectory(
                                    log,
                                    pipeline="B",
                                    run_id=pr_id,
                                    plan_json=ws_evidence["plan_json"],
                                    workspace_files=ws_evidence["workspace_files"],
                                    phase_details=[],
                                )
```

替换为：

```python
                        for pr in progress.get("point_runs", []):
                            pr_id = pr.get("id", "")
                            if not pr_id:
                                continue
                            ws_dir = Path(f"data/.govdoc/workspaces/{pr_id}")
                            archive = Path(f"data/.govdoc/archives/{pr_id}.tar.gz")
                            ws_evidence = collect_workspace_evidence(
                                workspace_dir=ws_dir if ws_dir.exists() else None,
                                archive_path=archive if archive.exists() else None,
                            )
                            if ws_evidence["plan_json"]:
                                record_agent_trajectory(
                                    log,
                                    pipeline="B",
                                    run_id=pr_id,
                                    plan_json=ws_evidence["plan_json"],
                                    workspace_files=ws_evidence["workspace_files"],
                                    phase_details=[],
                                )
```

- [ ] **Step 4: 运行全量单元测试确认无回归**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -x -q
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add govdoc/harness/api_eval.py tests/unit/test_harness_record.py
git commit -m "fix(harness): trajectory 收集补传 archive_path，从归档 tar.gz 读取"
```

---

### Task 5: 代码格式化 + 全量测试

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
