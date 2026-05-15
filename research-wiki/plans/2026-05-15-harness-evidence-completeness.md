# Harness 证据完整性修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 L2 评估 11/19 语义维度 FAIL，通过扩展 harness.db 表结构、修复 CRUD 测试污染、补全 agent 轨迹记录，使 L2 成为覆盖 L1 全部能力的唯一评估层。

**Architecture:** harness.db 从"存测试结果摘要"升级为"存完整运行证据"。`record_extract_results` / `record_audit_results` 写入完整业务数据（legal_basis JSON、verdict 详情、evidence 原文）。新增 `agent_trajectories` 表，PES 运行后直接从 workspace 读取 plan.json 和文件列表写入。L2 的 CRUD 测试改为不污染后续审核用的 checkpoint。

**Tech Stack:** Python 3.11 / SQLite / Pydantic v2 / httpx

**前置知识：**
- Conda 环境 `govdoc-auditor-v3`，所有命令用 `source activate govdoc-auditor-v3 && <cmd>`
- harness.db 位于 `results/harness.db`，由 `HarnessLog` 管理
- `schemas.py` 定义表列，`pipeline_eval.py` 定义 record 函数，L1/L2 共用
- workspace 是 scrivai 的 PES 运行沙箱，`workspace.working_dir` 下有 plan.json / findings/ / output.json
- `manager.archive(workspace, success=True)` 会 **删除** workspace 目录，所以必须在 archive 前读取

---

### Task 1: 扩展 extract_results 表结构 + record 函数

**Files:**
- Modify: `govdoc/harness/schemas.py:27-33`
- Modify: `govdoc/harness/pipeline_eval.py:81-97`
- Test: `tests/unit/test_harness_record.py`

- [ ] **Step 1: 写测试 — record_extract_results 应写入完整 legal_basis**

```python
# tests/unit/test_harness_record.py
"""测试 harness record 函数写入完整业务证据。"""

import json
import sqlite3
import tempfile
from pathlib import Path

from govdoc.harness.log import HarnessLog
from govdoc.harness.schemas import create_all_tables
from govdoc.harness.pipeline_eval import record_extract_results


def _make_log(tmp_path: Path) -> HarnessLog:
    """创建临时 HarnessLog。"""
    db_path = str(tmp_path / "test.db")
    log = HarnessLog(db_path=db_path, run_id="test-run")
    create_all_tables(log)
    return log


def test_record_extract_results_stores_full_legal_basis(tmp_path):
    """extract_results 应存完整 legal_basis JSON、description、severity。"""
    log = _make_log(tmp_path)
    checkpoints = [
        {
            "id": "cp_01",
            "title": "测试审核点",
            "category": "围标串标",
            "description": "供应商之间串通投标",
            "severity": "critical",
            "legal_basis": [
                {"law_name": "政府采购法第77条", "article": "第一款", "quote": "供应商有下列情形之一的"},
                {"law_name": "招标投标法第53条", "article": "", "quote": "投标人相互串通投标"},
            ],
        }
    ]
    record_extract_results(log, checkpoints)

    rows = log.query("SELECT * FROM extract_results WHERE run_id=?", ("test-run",))
    assert len(rows) == 1
    row = rows[0]
    assert row["checkpoint_id"] == "cp_01"
    assert row["has_legal_basis"] == 1
    assert row["legal_basis_count"] == 2
    # 新增字段
    assert row["description"] == "供应商之间串通投标"
    assert row["severity"] == "critical"
    basis = json.loads(row["legal_basis_json"])
    assert len(basis) == 2
    assert basis[0]["law_name"] == "政府采购法第77条"
    assert basis[1]["quote"] == "投标人相互串通投标"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_harness_record.py::test_record_extract_results_stores_full_legal_basis -v`
Expected: FAIL — `KeyError: 'description'` 或 `KeyError: 'legal_basis_json'`

- [ ] **Step 3: 修改 schemas.py — extract_results 加 3 列**

`govdoc/harness/schemas.py:27-33` 修改为：

```python
EXTRACT_RESULTS_COLUMNS: dict[str, str] = {
    "checkpoint_id": "TEXT",
    "title": "TEXT",
    "category": "TEXT",
    "description": "TEXT",
    "severity": "TEXT",
    "has_legal_basis": "INTEGER",
    "legal_basis_count": "INTEGER",
    "legal_basis_json": "TEXT",
}
```

- [ ] **Step 4: 修改 record_extract_results — 写入完整数据**

`govdoc/harness/pipeline_eval.py:81-97` 修改为：

```python
def record_extract_results(
    log: HarnessLog,
    checkpoints: list[dict[str, Any]],
) -> None:
    """记录管道 A 提取的审核点到 extract_results 表。"""
    for cp in checkpoints:
        bases = cp.get("legal_basis", [])
        log.insert(
            "extract_results",
            {
                "checkpoint_id": cp["id"],
                "title": cp.get("title", ""),
                "category": cp.get("category", ""),
                "description": cp.get("description", ""),
                "severity": cp.get("severity", ""),
                "has_legal_basis": 1 if bases else 0,
                "legal_basis_count": len(bases),
                "legal_basis_json": json.dumps(bases, ensure_ascii=False),
            },
        )
```

确保 `pipeline_eval.py` 顶部已有 `import json`（已有）。

- [ ] **Step 5: 运行测试确认通过**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_harness_record.py::test_record_extract_results_stores_full_legal_basis -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add govdoc/harness/schemas.py govdoc/harness/pipeline_eval.py tests/unit/test_harness_record.py
git commit -m "feat(harness): extract_results 表扩展 — 存完整 legal_basis/description/severity"
```

---

### Task 2: 扩展 audit_results 表结构 + record 函数

**Files:**
- Modify: `govdoc/harness/schemas.py:35-44`
- Modify: `govdoc/harness/pipeline_eval.py:100-126`
- Modify: `tests/unit/test_harness_record.py`

- [ ] **Step 1: 写测试 — record_audit_results 应写入完整 verdict 和 evidence**

在 `tests/unit/test_harness_record.py` 中追加：

```python
from govdoc.harness.pipeline_eval import record_audit_results


def test_record_audit_results_stores_full_verdict_and_evidence(tmp_path):
    """audit_results 应存完整 verdict JSON 和 evidence JSON。"""
    log = _make_log(tmp_path)
    findings = [
        {
            "point_run_id": "pr_01",
            "checkpoint_id": "cp_01",
            "verdict": {
                "verdict": "不合规",
                "rationale": "文件中设置了地域限制条件",
                "evidence_quotes": [
                    "要求供应商在本市设有分支机构",
                    "具有广州市范围内类似项目经验",
                ],
            },
            "evidence_refs": [
                {"chunk_id": "c1", "text": "供应商须在广州市设立分支机构", "score": 0.92},
            ],
            "case_refs": [{"case_id": "case_01", "similarity": 0.85}],
            "duration_s": 45.3,
            "status": "completed",
        }
    ]
    record_audit_results(log, findings)

    rows = log.query("SELECT * FROM audit_results WHERE run_id=?", ("test-run",))
    assert len(rows) == 1
    row = rows[0]
    assert row["verdict"] == "不合规"
    assert row["has_evidence"] == 1
    assert row["evidence_count"] == 3  # 2 quotes + 1 ref
    # 新增字段
    verdict_detail = json.loads(row["verdict_json"])
    assert verdict_detail["rationale"] == "文件中设置了地域限制条件"
    assert len(verdict_detail["evidence_quotes"]) == 2
    evidence_detail = json.loads(row["evidence_json"])
    assert len(evidence_detail) == 1
    assert evidence_detail[0]["chunk_id"] == "c1"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_harness_record.py::test_record_audit_results_stores_full_verdict_and_evidence -v`
Expected: FAIL — `KeyError: 'verdict_json'`

- [ ] **Step 3: 修改 schemas.py — audit_results 加 2 列**

`govdoc/harness/schemas.py:35-44` 修改为：

```python
AUDIT_RESULTS_COLUMNS: dict[str, str] = {
    "point_run_id": "TEXT",
    "checkpoint_id": "TEXT",
    "verdict": "TEXT",
    "verdict_json": "TEXT",
    "has_evidence": "INTEGER",
    "evidence_count": "INTEGER",
    "evidence_json": "TEXT",
    "has_case_refs": "INTEGER",
    "duration_s": "REAL",
    "status": "TEXT",
}
```

- [ ] **Step 4: 修改 record_audit_results — 写入完整数据**

`govdoc/harness/pipeline_eval.py:100-126` 修改为：

```python
def record_audit_results(
    log: HarnessLog,
    findings: list[dict[str, Any]],
) -> None:
    """记录管道 B 审核发现到 audit_results 表。"""
    for f in findings:
        verdict_obj = f.get("verdict", {})
        if isinstance(verdict_obj, dict):
            verdict_str = verdict_obj.get("verdict", "")
            quotes = verdict_obj.get("evidence_quotes", [])
        else:
            verdict_str = str(verdict_obj)
            quotes = []
        refs = f.get("evidence_refs", [])
        log.insert(
            "audit_results",
            {
                "point_run_id": f.get("point_run_id", ""),
                "checkpoint_id": f.get("checkpoint_id", ""),
                "verdict": verdict_str,
                "verdict_json": json.dumps(verdict_obj, ensure_ascii=False) if isinstance(verdict_obj, dict) else json.dumps({"verdict": verdict_str}, ensure_ascii=False),
                "has_evidence": 1 if (quotes or refs) else 0,
                "evidence_count": len(quotes) + len(refs),
                "evidence_json": json.dumps(refs, ensure_ascii=False),
                "has_case_refs": 1 if f.get("case_refs") else 0,
                "duration_s": f.get("duration_s", 0.0),
                "status": f.get("status", "unknown"),
            },
        )
```

- [ ] **Step 5: 运行测试确认通过**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_harness_record.py -v`
Expected: 2 PASS

- [ ] **Step 6: Commit**

```bash
git add govdoc/harness/schemas.py govdoc/harness/pipeline_eval.py tests/unit/test_harness_record.py
git commit -m "feat(harness): audit_results 表扩展 — 存完整 verdict_json/evidence_json"
```

---

### Task 3: 新增 agent_trajectories 表 + record 函数

**Files:**
- Modify: `govdoc/harness/schemas.py:70-78` (ALL_TABLES)
- Modify: `govdoc/harness/pipeline_eval.py` (新增 record_agent_trajectory)
- Modify: `tests/unit/test_harness_record.py`

- [ ] **Step 1: 写测试 — record_agent_trajectory 写入 plan 和 workspace 文件列表**

在 `tests/unit/test_harness_record.py` 中追加：

```python
from govdoc.harness.pipeline_eval import record_agent_trajectory


def test_record_agent_trajectory_stores_plan_and_files(tmp_path):
    """agent_trajectories 应存 plan_json、workspace_files、phase_details。"""
    log = _make_log(tmp_path)
    record_agent_trajectory(
        log,
        pipeline="A",
        run_id="extract-run-001",
        plan_json=json.dumps({"items_to_extract": [{"id": "cp_01", "title": "测试"}]}, ensure_ascii=False),
        workspace_files=["plan.json", "plan.md", "findings/cp_01.json"],
        phase_details=[
            {"phase": "plan", "status": "completed", "duration_s": 12.3},
            {"phase": "execute", "status": "completed", "duration_s": 45.0},
            {"phase": "summarize", "status": "completed", "duration_s": 8.1},
        ],
    )

    rows = log.query("SELECT * FROM agent_trajectories WHERE run_id=?", ("test-run",))
    assert len(rows) == 1
    row = rows[0]
    assert row["pipeline"] == "A"
    assert row["source_run_id"] == "extract-run-001"
    plan = json.loads(row["plan_json"])
    assert plan["items_to_extract"][0]["id"] == "cp_01"
    files = json.loads(row["workspace_files_json"])
    assert "findings/cp_01.json" in files
    phases = json.loads(row["phase_details_json"])
    assert len(phases) == 3
    assert phases[0]["phase"] == "plan"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_harness_record.py::test_record_agent_trajectory_stores_plan_and_files -v`
Expected: FAIL — `ImportError: cannot import name 'record_agent_trajectory'`

- [ ] **Step 3: 在 schemas.py 新增 agent_trajectories 表定义**

在 `govdoc/harness/schemas.py` 的 `API_CONTRACTS_COLUMNS` 之后、`ALL_TABLES` 之前添加：

```python
AGENT_TRAJECTORIES_COLUMNS: dict[str, str] = {
    "pipeline": "TEXT",
    "source_run_id": "TEXT",
    "plan_json": "TEXT",
    "workspace_files_json": "TEXT",
    "phase_details_json": "TEXT",
}
```

在 `ALL_TABLES` 字典中添加 `"agent_trajectories": AGENT_TRAJECTORIES_COLUMNS`。

- [ ] **Step 4: 在 pipeline_eval.py 新增 record_agent_trajectory 函数**

在 `record_audit_results` 之后添加：

```python
def record_agent_trajectory(
    log: HarnessLog,
    *,
    pipeline: str,
    run_id: str,
    plan_json: str,
    workspace_files: list[str],
    phase_details: list[dict[str, Any]],
) -> None:
    """记录 PES agent 轨迹到 agent_trajectories 表。"""
    log.insert(
        "agent_trajectories",
        {
            "pipeline": pipeline,
            "source_run_id": run_id,
            "plan_json": plan_json,
            "workspace_files_json": json.dumps(workspace_files, ensure_ascii=False),
            "phase_details_json": json.dumps(phase_details, ensure_ascii=False),
        },
    )
```

- [ ] **Step 5: 运行测试确认通过**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_harness_record.py -v`
Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git add govdoc/harness/schemas.py govdoc/harness/pipeline_eval.py tests/unit/test_harness_record.py
git commit -m "feat(harness): 新增 agent_trajectories 表 — 存 plan/workspace 文件/phase 详情"
```

---

### Task 4: Pipeline A 写入 agent_trajectories — 在 archive 前读取 workspace

**Files:**
- Modify: `govdoc/harness/pipeline_eval.py:285-310` (L1 的 Pipeline A 记录)
- Modify: `govdoc/pipelines/extract_rules.py:97-114` (读 workspace 数据)
- Test: 现有单元测试不回归

这一步的核心是：在 `manager.archive()` 调用之前，从 `workspace.working_dir` 读取 plan.json 和文件列表，传给 `record_agent_trajectory`。

由于 L1 (`pipeline_eval.py`) 和 L2 (`api_eval.py`) 都会调用 `record_extract_results`，但 trajectory 数据只有后端 PES 执行时才有——所以 trajectory 记录应加在**业务管道** (`extract_rules.py` / `audit_tender.py`) 中，在 PES 运行完成后、archive 前调用。

但我们的共识是方案 B：数据写入 harness.db。问题是业务管道不持有 `HarnessLog` 实例。

解决方案：新增一个辅助函数 `collect_workspace_evidence(workspace) -> dict`，在业务管道中调用它收集数据，暂存到 `ExtractRun` / `AuditPointRun` 的一个新字段（如 `trajectory_json`），然后 L1/L2 的 record 逻辑从这个字段读出并写入 harness.db。

但这引入了 DB 模型变更。更简单的路径：直接在 `_run_semantic_evaluations` 中从 trajectory_store 和 workspace archive 读取数据。

**实际最简方案**：`record_agent_trajectory` 在 L1 的 `pipeline_eval.py` 中调用，因为 L1 直接持有 workspace handle；L2 则在 `_run_semantic_evaluations` 中从 `trajectory_store` + DB 中的 `workspace_archive_path` 读取。

但我们的目标是 L2 替代 L1。所以数据链路应该是：

1. 业务管道 (`extract_rules.py`) 在 PES 运行后，将 workspace 证据（plan.json、文件列表、phase 详情）存入 DB（`ExtractRun` / `AuditPointRun` 的新 JSON 字段）
2. L2 的 record 逻辑通过 API 拿到这些数据，写入 harness.db

等等——这又变成了改 DB 模型。让我重新想。

**最终方案**：L2 在 `_run_semantic_evaluations` 时，直接从 `trajectory_store`（SQLite）和 `workspace_archive_path`（tar.gz）读取完整数据。这两个数据源都是本地文件，L2 进程可以直接访问（L2 和后端跑在同一台机器上）。

- [ ] **Step 1: 写辅助函数 — 从 workspace 目录或 archive 读取 plan.json + 文件列表**

在 `govdoc/harness/pipeline_eval.py` 中 `record_agent_trajectory` 之后添加：

```python
def collect_workspace_evidence(
    workspace_dir: Path | None = None,
    archive_path: Path | None = None,
) -> dict[str, Any]:
    """从 workspace 目录或归档 tar.gz 中读取 agent 证据。

    优先读活跃 workspace 目录，否则从 archive 解压读取。

    返回:
        {"plan_json": str, "workspace_files": list[str], "findings": dict}
    """
    result: dict[str, Any] = {"plan_json": "", "workspace_files": [], "findings": {}}

    if workspace_dir and workspace_dir.exists():
        working = workspace_dir / "working"
        if not working.exists():
            working = workspace_dir
        plan_path = working / "plan.json"
        if plan_path.exists():
            result["plan_json"] = plan_path.read_text(encoding="utf-8")
        result["workspace_files"] = [
            str(p.relative_to(working)) for p in working.rglob("*") if p.is_file()
        ]
        findings_dir = working / "findings"
        if findings_dir.exists():
            for f in sorted(findings_dir.glob("*.json")):
                result["findings"][f.stem] = f.read_text(encoding="utf-8")
        return result

    if archive_path and Path(archive_path).exists() and str(archive_path).endswith(".tar.gz"):
        import tarfile

        with tarfile.open(archive_path, "r:gz") as tf:
            members = tf.getnames()
            result["workspace_files"] = members
            for m in members:
                if m.endswith("/working/plan.json") or m == "working/plan.json":
                    f = tf.extractfile(m)
                    if f:
                        result["plan_json"] = f.read().decode("utf-8")
                if "/working/findings/" in m and m.endswith(".json"):
                    f = tf.extractfile(m)
                    if f:
                        stem = Path(m).stem
                        result["findings"][stem] = f.read().decode("utf-8")
        return result

    return result
```

- [ ] **Step 2: 写测试 — collect_workspace_evidence 从目录读取**

在 `tests/unit/test_harness_record.py` 中追加：

```python
from govdoc.harness.pipeline_eval import collect_workspace_evidence


def test_collect_workspace_evidence_from_directory(tmp_path):
    """从 workspace 目录结构中读取 plan.json 和 findings。"""
    working = tmp_path / "working"
    working.mkdir()
    plan = {"items_to_extract": [{"id": "cp_01"}]}
    (working / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    (working / "plan.md").write_text("# Plan", encoding="utf-8")
    findings_dir = working / "findings"
    findings_dir.mkdir()
    (findings_dir / "cp_01.json").write_text('{"title":"test"}', encoding="utf-8")

    evidence = collect_workspace_evidence(workspace_dir=tmp_path)
    assert evidence["plan_json"] != ""
    parsed = json.loads(evidence["plan_json"])
    assert parsed["items_to_extract"][0]["id"] == "cp_01"
    assert "plan.json" in evidence["workspace_files"]
    assert "findings/cp_01.json" in evidence["workspace_files"]
    assert "cp_01" in evidence["findings"]
```

- [ ] **Step 3: 运行测试确认通过**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_harness_record.py -v`
Expected: 4 PASS

- [ ] **Step 4: Commit**

```bash
git add govdoc/harness/pipeline_eval.py tests/unit/test_harness_record.py
git commit -m "feat(harness): collect_workspace_evidence — 从 workspace/archive 读取 agent 证据"
```

---

### Task 5: 修改 _run_semantic_evaluations — 用完整数据构建 evidence

**Files:**
- Modify: `govdoc/harness/pipeline_eval.py:627-734`

- [ ] **Step 1: 重写 evidence 构建逻辑**

`govdoc/harness/pipeline_eval.py` 的 `_run_semantic_evaluations` 函数中，652-679 行（数据加载部分）替换为：

```python
    extract_rows = log.query("SELECT * FROM extract_results WHERE run_id=?", (log._run_id,))
    audit_rows = log.query("SELECT * FROM audit_results WHERE run_id=?", (log._run_id,))
    trajectory_rows = log.query("SELECT * FROM agent_trajectories WHERE run_id=?", (log._run_id,))
```

然后 703-711 行（evidence 构建部分）替换为：

```python
    for dim in dimensions:
        try:
            criteria = load_rubric(rubric_dir, dim)
            evidence: dict[str, Any] = {
                "extract_results": extract_rows,
                "audit_results": audit_rows,
                "dimension": dim,
            }
            if dim.startswith("agent-") and trajectory_rows:
                evidence["trajectory"] = trajectory_rows
            evaluate_dimension(
                log=log,
                judge=judge,
                dimension=dim,
                criteria=criteria,
                evidence=evidence,
            )
```

关键变化：
- 删除旧的 `trajectory_evidence` 变量（从 trajectory_store 读取的 655-679 行全部删除）
- 改为从 `agent_trajectories` 表读取（表中已有完整 plan_json、workspace_files、phase_details）
- `extract_rows` 和 `audit_rows` 现在包含完整字段（legal_basis_json、verdict_json、evidence_json），judge 自然能拿到

- [ ] **Step 2: 运行全部现有测试确认不回归**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -x -q`
Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add govdoc/harness/pipeline_eval.py
git commit -m "refactor(harness): _run_semantic_evaluations 从 harness.db 读完整证据，不再依赖 trajectory_store"
```

---

### Task 6: 修复 CRUD 测试污染 — Phase 4 改为使用独立 checkpoint

**Files:**
- Modify: `govdoc/harness/api_eval.py:465-511`

- [ ] **Step 1: 重写 Phase 4 CRUD 测试逻辑**

`govdoc/harness/api_eval.py:465-511` 替换为：

```python
            # ── Phase 4: Checkpoint CRUD 测试 ──
            # 用合法数据创建临时 checkpoint，测试 PUT + DELETE，不影响 imported 列表
            if imported_checkpoint_ids:
                # PUT 测试：修改最后一个 checkpoint，但用合法 category 值
                test_cp_id = imported_checkpoint_ids[-1]
                # 先读取原始数据，测试后恢复
                _, original_cp = await call_endpoint(
                    client,
                    EndpointSpec(
                        method="GET",
                        path="/api/v1/checkpoints",
                        expected_status=200,
                        description="读取审核点（CRUD 前备份）",
                    ),
                    log,
                )
                original_payload = None
                if original_cp:
                    for cp in original_cp:
                        if cp.get("id") == test_cp_id:
                            original_payload = cp.get("payload_json")
                            break

                # PUT 用合法枚举值
                await call_endpoint(
                    client,
                    EndpointSpec(
                        method="PUT",
                        path="/api/v1/checkpoints/{checkpoint_id}",
                        expected_status=200,
                        description="更新审核点（CRUD 测试）",
                        path_params={"checkpoint_id": test_cp_id},
                        body={
                            "payload_json": '{"id":"crud-test","category":"其他违法违规","title":"CRUD 测试","description":"临时测试数据","legal_basis":[],"severity":"minor","retrieval_hint":""}'
                        },
                    ),
                    log,
                )

                # 恢复原始数据
                if original_payload:
                    await call_endpoint(
                        client,
                        EndpointSpec(
                            method="PUT",
                            path="/api/v1/checkpoints/{checkpoint_id}",
                            expected_status=200,
                            description="恢复审核点原始数据",
                            path_params={"checkpoint_id": test_cp_id},
                            body={"payload_json": original_payload},
                        ),
                        log,
                    )

                # DELETE 测试：找一个不在 imported 列表中的审核点
                _, extra_resp = await call_endpoint(
                    client,
                    EndpointSpec(
                        method="GET",
                        path="/api/v1/checkpoints",
                        expected_status=200,
                        description="列出审核点（CRUD 后）",
                    ),
                    log,
                )
                if extra_resp:
                    all_ids = {c["id"] for c in extra_resp if c.get("id")}
                    deletable = all_ids - set(imported_checkpoint_ids)
                    if deletable:
                        del_id = next(iter(deletable))
                        await call_endpoint(
                            client,
                            EndpointSpec(
                                method="DELETE",
                                path="/api/v1/checkpoints/{checkpoint_id}",
                                expected_status=204,
                                description="删除审核点",
                                path_params={"checkpoint_id": del_id},
                            ),
                            log,
                        )
```

核心变化：
1. PUT 使用 `"category":"其他违法违规"`（合法枚举值），不再用 `"测试"`
2. PUT 后**恢复原始数据**，确保后续 Pipeline B 使用时数据完整

- [ ] **Step 2: 运行现有测试确认不回归**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -x -q`
Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add govdoc/harness/api_eval.py
git commit -m "fix(harness): CRUD 测试用合法 category + 恢复原始数据，不再污染后续审核"
```

---

### Task 7: L2 Pipeline A/B 执行后写入 agent_trajectories

**Files:**
- Modify: `govdoc/harness/api_eval.py:415-437` (Pipeline A 记录部分)
- Modify: `govdoc/harness/api_eval.py:670-702` (Pipeline B 记录部分)

L2 中，PES 是后端执行的，L2 无法直接读 workspace。但 L2 和后端运行在同一台机器上，所以可以通过以下路径读取数据：
- Pipeline A 完成后，从 `trajectory_store` 读取最近的 run（和 L1 一样）
- workspace 数据：通过 `ExtractRun.workspace_archive_path` 或从 `data/.govdoc/workspaces/{run_id}/` 读取

- [ ] **Step 1: Pipeline A 完成后收集 workspace 证据并写入 agent_trajectories**

在 `govdoc/harness/api_eval.py` 中，`record_extract_results(log, extract_cps)` 之后（约第 437 行），添加：

```python
                        # 收集 agent 轨迹证据
                        from govdoc.harness.pipeline_eval import (
                            collect_workspace_evidence,
                            record_agent_trajectory,
                        )

                        ws_evidence = collect_workspace_evidence(
                            workspace_dir=Path(f"data/.govdoc/workspaces/{extract_run_id}"),
                            archive_path=await _get_extract_archive_path(client, rule_source_id, extract_run_id),
                        )
                        if ws_evidence["plan_json"]:
                            record_agent_trajectory(
                                log,
                                pipeline="A",
                                run_id=extract_run_id,
                                plan_json=ws_evidence["plan_json"],
                                workspace_files=ws_evidence["workspace_files"],
                                phase_details=[],
                            )
```

同时在文件顶部附近添加一个辅助函数来获取 archive 路径：

```python
async def _get_extract_archive_path(
    client: httpx.AsyncClient,
    rule_source_id: str,
    extract_run_id: str,
) -> Path | None:
    """从 extract-run status 中获取 workspace_archive_path。"""
    resp = await client.get(f"/api/v1/rules/{rule_source_id}/extract-runs/{extract_run_id}/status")
    if resp.status_code == 200:
        data = resp.json()
        path = data.get("workspace_archive_path")
        if path:
            return Path(path)
    return None
```

- [ ] **Step 2: Pipeline B 完成后收集 workspace 证据并写入 agent_trajectories**

在 `govdoc/harness/api_eval.py` 中 `record_audit_results(log, findings)` 之后（约第 702 行），添加类似逻辑。但 Pipeline B 的每个 AuditPointRun 都有自己的 workspace，需要逐个收集：

```python
                    if findings:
                        record_audit_results(log, findings)
                        # 收集各 point_run 的 workspace 证据
                        from govdoc.harness.pipeline_eval import (
                            collect_workspace_evidence,
                            record_agent_trajectory,
                        )

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

- [ ] **Step 3: 运行现有测试确认不回归**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -x -q`
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add govdoc/harness/api_eval.py
git commit -m "feat(harness): L2 Pipeline A/B 完成后写入 agent_trajectories"
```

---

### Task 8: 更新设计文档 + Wiki schema

**Files:**
- Modify: `research-wiki/designs/harness-e2e-design.md`
- Modify: `research-wiki/schemas/harness-extract-results.md`
- Modify: `research-wiki/schemas/harness-audit-results.md`
- Create: `research-wiki/schemas/harness-agent-trajectories.md`

- [ ] **Step 1: 更新设计文档 — L2 替代 L1 路线 + harness 定位修正**

`research-wiki/designs/harness-e2e-design.md` 做以下修改：

**§2.2** 在"选定方案：C（分层架构）"之后添加：

```markdown
> **演进方向（2026-05-15 更新）：** L2 将逐步覆盖 L1 全部能力（完整业务证据记录 + 语义评估），成为唯一评估层。L1 保留为过渡期兼容，最终废弃。
```

**§3.1 extract_results 表** 添加 3 列：

```markdown
| description | TEXT | 审核点描述 |
| severity | TEXT | 严重程度（critical/major/minor） |
| legal_basis_json | TEXT | 完整法条引用 JSON 数组 |
```

**§3.1 audit_results 表** 添加 2 列：

```markdown
| verdict_json | TEXT | 完整判定 JSON（含 rationale + evidence_quotes） |
| evidence_json | TEXT | 证据引用 JSON 数组（chunk_id + text + score） |
```

**§3.1 新增 agent_trajectories 表：**

```markdown
#### `agent_trajectories` — PES agent 运行轨迹

| 列 | 类型 | 说明 |
|----|------|------|
| run_id | TEXT | FK → _runs.run_id |
| pipeline | TEXT | "A" 或 "B" |
| source_run_id | TEXT | ExtractRun.id 或 AuditPointRun.id |
| plan_json | TEXT | PES plan 阶段产出的完整 JSON |
| workspace_files_json | TEXT | workspace 中所有文件路径的 JSON 数组 |
| phase_details_json | TEXT | 各 phase 的详细状态 JSON 数组 |
```

**§6.2 关键设计决策** 修改这一行：

原：`| 真实 LLM 调用 | L1 用真 LLM，L2 不涉及 LLM | L1 评估输出质量必须真跑；L2 只验 API 契约 |`

改为：`| 评估分层 | L2 全栈评估（API 契约 + 完整业务证据 + 语义评估） | L2 覆盖 L1 全部能力，L1 保留为过渡兼容 |`

新增一行：`| harness.db 数据粒度 | 存完整运行证据（legal_basis 明细、verdict 详情、plan.json 内容） | judge 需要完整数据才能做深度语义评估 |`

- [ ] **Step 2: 更新 Wiki schema — extract_results**

`research-wiki/schemas/harness-extract-results.md` 表格添加 3 行：

```markdown
| description | TEXT | 审核点描述 |
| severity | TEXT | 严重程度 |
| legal_basis_json | TEXT | 完整法条引用 JSON 数组（含 law_name/article/quote） |
```

- [ ] **Step 3: 更新 Wiki schema — audit_results**

`research-wiki/schemas/harness-audit-results.md` 表格添加 2 行：

```markdown
| verdict_json | TEXT | 完整判定 JSON（含 verdict/rationale/evidence_quotes） |
| evidence_json | TEXT | 证据引用 JSON 数组（含 chunk_id/text/score） |
```

- [ ] **Step 4: 创建 Wiki schema — agent_trajectories**

```markdown
---
type: schema
node_id: schema:harness-agent-trajectories
title: "表结构: agent_trajectories"
date: 2026-05-15
tags: ["harness"]
---

# agent_trajectories

PES agent 运行轨迹表。每次 PES 执行记录一行，存储完整的 plan、workspace 文件列表和 phase 详情。

| 列 | 类型 | 说明 |
|----|------|------|
| run_id | TEXT | 关联 _runs.run_id |
| pipeline | TEXT | "A" 或 "B" |
| source_run_id | TEXT | ExtractRun.id 或 AuditPointRun.id |
| plan_json | TEXT | PES plan 阶段产出的完整 JSON |
| workspace_files_json | TEXT | workspace 中所有文件路径的 JSON 数组 |
| phase_details_json | TEXT | 各 phase 的详细状态 JSON 数组 |
```

- [ ] **Step 5: Commit**

```bash
git add research-wiki/designs/harness-e2e-design.md research-wiki/schemas/
git commit -m "docs: 更新 harness 设计文档 — L2 全栈定位 + 表结构扩展 + agent_trajectories"
```

---

### Task 9: 运行完整测试 + 删除旧 harness.db + 重跑 L2

- [ ] **Step 1: 运行全部单元测试**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v
```

Expected: 全部 PASS

- [ ] **Step 2: 代码格式化**

```bash
source activate govdoc-auditor-v3 && ruff format . && ruff check . --fix
```

- [ ] **Step 3: 删除旧 harness.db 并重跑 L2**

```bash
rm -f results/harness.db results/harness.db-shm results/harness.db-wal
# 确保 FastAPI 在运行
curl -sf http://localhost:8000/healthz || echo "需要先启动 FastAPI"
# 运行 L2
bash scripts/harness_api.sh
```

- [ ] **Step 4: 检查结果**

```bash
source activate govdoc-auditor-v3 && python3 -c "
import sqlite3
conn = sqlite3.connect('results/harness.db')
# Pipeline B 应该 5/5 不再 4/5
for r in conn.execute('SELECT pipeline, project_name, status FROM pipeline_runs').fetchall():
    print(f'{r[0]} | {r[1]} | {r[2]}')
print()
# 语义评估通过率
rows = conn.execute('SELECT dimension, score, passed FROM quality_scores ORDER BY dimension').fetchall()
passed = sum(1 for r in rows if r[2])
print(f'通过率: {passed}/{len(rows)}')
for r in rows:
    s = 'PASS' if r[2] else 'FAIL'
    print(f'  {s} {r[0]:40s} {r[1]:.1f}')
"
```

Expected:
- Pipeline B 两个项目都应该 `draft_ready` 或 `completed`（不再是 `failed`）
- `audit_results` 表不再是 0 行
- 语义评估通过率显著提升（预期 16/19+）

- [ ] **Step 5: Commit 最终结果**

```bash
git add -A
git commit -m "test: L2 重跑验证 — 语义评估通过率提升"
```
