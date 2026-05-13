---
type: plan
node_id: plan:harness-e2e-plan
title: 端到端 Harness 评估基础设施实施计划
date: 2026-05-13
tags: ["harness", "testing", "evaluation"]
---

# 端到端 Harness 评估基础设施实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐 harness-eval skill 的全部前置条件，使项目可以用 `real_data/` 对全部 FastAPI 功能进行端到端 harness 评估。

**Architecture:** 分层架构 — Layer 1 管道直调评估（pipeline_eval.py）+ Layer 2 API 契约验证（api_eval.py），两层共写 `results/harness.db`。Python 逻辑在 `govdoc/harness/` 模块，shell 入口在 `scripts/`。

**Tech Stack:** Python 3.11 / SQLite / HarnessLog / HarnessJudge / httpx / pytest / pydantic v2

**Design doc:** `research-wiki/designs/harness-e2e-design.md`

---

## 文件结构总览

### 新增文件

| 路径 | 职责 |
|------|------|
| `govdoc/harness/manifest.py` | 加载 `harness_manifest.yaml`，提供类型安全的测试数据配置 |
| `govdoc/harness/schemas.py` | 在 HarnessLog 中创建全部 7 张自定义表 |
| `govdoc/harness/pipeline_eval.py` | L1：管道直调 + HarnessJudge 评估 + 记录到 harness.db |
| `govdoc/harness/api_eval.py` | L2：httpx 调全部端点 + 契约验证 + 性能指标 |
| `tests/unit/test_harness_manifest.py` | manifest 加载器单测 |
| `tests/unit/test_harness_schemas.py` | 表创建单测 |
| `tests/unit/test_pipeline_eval.py` | L1 评估逻辑单测（mock PES） |
| `tests/unit/test_api_eval.py` | L2 评估逻辑单测（mock httpx） |
| `scripts/harness_pipeline.sh` | L1 shell 入口 |
| `scripts/harness_api.sh` | L2 shell 入口 |
| `scripts/harness_all.sh` | 总入口 |
| `scripts/fixtures/harness_manifest.yaml` | 测试数据清单 |
| `scripts/rubrics/*.md` | 20 个语义评判 rubric 文件 |
| `research-wiki/schemas/*.md` | 7 个 schema 实体 |
| `research-wiki/metrics/*.md` | 31 个 metric 实体 |
| `results/.gitkeep` | 确保目录被跟踪 |

### 修改文件

| 路径 | 变更 |
|------|------|
| `govdoc/harness/__init__.py` | 追加导出新模块的公共接口 |
| `.gitignore` | 添加 `results/harness.db` |
| `research-wiki/index.md` | 添加 plan 条目 |

---

## Task 1: Manifest 加载器

**Files:**
- Create: `govdoc/harness/manifest.py`
- Create: `scripts/fixtures/harness_manifest.yaml`
- Test: `tests/unit/test_harness_manifest.py`

- [ ] **Step 1: 编写 manifest YAML 文件**

```yaml
# scripts/fixtures/harness_manifest.yaml
projects:
  - name: "从化医院采购"
    tender_doc: "real_data/从化区中医医院手术室设备及附件、病房护理及医院设备采购/从化区中医医院手术室设备及附件、病房护理及医院设备采购.docx"
    supplementary_docs:
      - "real_data/从化区中医医院手术室设备及附件、病房护理及医院设备采购/3、从化区中医医院手术室设备及附件、病房护理及医院设备采购/从化区中医医院手术室设备及附件、病房护理及医院设备采购的合同.pdf"

  - name: "汕头河道项目"
    tender_doc: "real_data/2023年度汕头市潮阳区流域面积50km²以下 河道管理范围划界工作服务项目/2023年度汕头市潮阳区流域面积50km²以下 河道管理范围划界工作服务项目.docx"
    supplementary_docs: []

rules:
  - name: "四类违法违规指引"
    path: "real_data/2025年政府采购领域\"四类\"违法违规行为专项整治工作指引.doc"

checkpoints:
  - name: "处罚标准表"
    path: "real_data/附件9 处理处罚标准.xls"
```

- [ ] **Step 2: 编写失败测试**

```python
# tests/unit/test_harness_manifest.py
"""manifest 加载器单测。"""

import tempfile
from pathlib import Path

import pytest
import yaml

from govdoc.harness.manifest import HarnessManifest, load_manifest


class TestLoadManifest:
    """测试 manifest YAML 加载。"""

    def test_load_valid_manifest(self, tmp_path: Path) -> None:
        """加载合法 manifest，返回 HarnessManifest 对象。"""
        data = {
            "projects": [
                {
                    "name": "测试项目",
                    "tender_doc": "real_data/test.docx",
                    "supplementary_docs": [],
                }
            ],
            "rules": [{"name": "测试法规", "path": "real_data/guide.doc"}],
            "checkpoints": [{"name": "测试表", "path": "real_data/cp.xls"}],
        }
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(yaml.dump(data, allow_unicode=True))

        result = load_manifest(str(manifest_path))

        assert isinstance(result, HarnessManifest)
        assert len(result.projects) == 1
        assert result.projects[0].name == "测试项目"
        assert len(result.rules) == 1
        assert len(result.checkpoints) == 1

    def test_load_resolves_relative_paths(self, tmp_path: Path) -> None:
        """相对路径基于 project_root 解析为绝对路径。"""
        data = {
            "projects": [
                {
                    "name": "p1",
                    "tender_doc": "real_data/a.docx",
                    "supplementary_docs": ["real_data/b.pdf"],
                }
            ],
            "rules": [],
            "checkpoints": [],
        }
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(yaml.dump(data, allow_unicode=True))

        result = load_manifest(str(manifest_path), project_root=str(tmp_path))

        assert result.projects[0].tender_doc == str(tmp_path / "real_data/a.docx")
        assert result.projects[0].supplementary_docs[0] == str(tmp_path / "real_data/b.pdf")

    def test_load_missing_file_raises(self) -> None:
        """加载不存在的文件抛 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            load_manifest("/nonexistent/manifest.yaml")

    def test_load_invalid_yaml_raises(self, tmp_path: Path) -> None:
        """无效 YAML 抛 ValueError。"""
        bad = tmp_path / "bad.yaml"
        bad.write_text("projects: [[[invalid")
        with pytest.raises((yaml.YAMLError, ValueError)):
            load_manifest(str(bad))
```

- [ ] **Step 3: 运行测试确认失败**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_harness_manifest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'govdoc.harness.manifest'`

- [ ] **Step 4: 实现 manifest 加载器**

```python
# govdoc/harness/manifest.py
"""Harness 测试数据清单加载器。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ProjectFixture:
    """单个测试项目的数据配置。"""

    name: str
    tender_doc: str
    supplementary_docs: list[str] = field(default_factory=list)


@dataclass
class RuleFixture:
    """法规数据配置。"""

    name: str
    path: str


@dataclass
class CheckpointFixture:
    """审核点表格数据配置。"""

    name: str
    path: str


@dataclass
class HarnessManifest:
    """Harness 测试数据清单。"""

    projects: list[ProjectFixture] = field(default_factory=list)
    rules: list[RuleFixture] = field(default_factory=list)
    checkpoints: list[CheckpointFixture] = field(default_factory=list)


def _resolve_path(path: str, project_root: str | None) -> str:
    """将相对路径基于 project_root 解析为绝对路径。"""
    if project_root and not Path(path).is_absolute():
        return str(Path(project_root) / path)
    return path


def load_manifest(
    manifest_path: str,
    project_root: str | None = None,
) -> HarnessManifest:
    """加载 harness_manifest.yaml 并返回类型安全的配置对象。

    参数:
        manifest_path: manifest 文件路径。
        project_root: 项目根目录，用于解析相对路径。

    返回:
        HarnessManifest 实例。

    异常:
        FileNotFoundError: manifest 文件不存在。
        ValueError: YAML 内容不合法。
    """
    p = Path(manifest_path)
    if not p.exists():
        raise FileNotFoundError(f"manifest 文件不存在: {manifest_path}")

    raw: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"manifest 根节点必须是 dict，实际为 {type(raw)}")

    projects = []
    for proj in raw.get("projects", []):
        projects.append(
            ProjectFixture(
                name=proj["name"],
                tender_doc=_resolve_path(proj["tender_doc"], project_root),
                supplementary_docs=[
                    _resolve_path(d, project_root) for d in proj.get("supplementary_docs", [])
                ],
            )
        )

    rules = [
        RuleFixture(name=r["name"], path=_resolve_path(r["path"], project_root))
        for r in raw.get("rules", [])
    ]

    checkpoints = [
        CheckpointFixture(name=c["name"], path=_resolve_path(c["path"], project_root))
        for c in raw.get("checkpoints", [])
    ]

    return HarnessManifest(projects=projects, rules=rules, checkpoints=checkpoints)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_harness_manifest.py -v`
Expected: 4 passed

- [ ] **Step 6: 提交**

```bash
git add govdoc/harness/manifest.py tests/unit/test_harness_manifest.py scripts/fixtures/harness_manifest.yaml
git commit -m "feat: harness manifest 加载器 + 测试数据清单"
```

---

## Task 2: Harness DB Schema 表创建

**Files:**
- Create: `govdoc/harness/schemas.py`
- Test: `tests/unit/test_harness_schemas.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/unit/test_harness_schemas.py
"""harness.db 自定义表创建单测。"""

import sqlite3
import tempfile
from pathlib import Path

from govdoc.harness.log import HarnessLog
from govdoc.harness.schemas import create_all_tables


class TestCreateAllTables:
    """测试 create_all_tables 创建全部 7 张表。"""

    def test_creates_all_seven_tables(self, tmp_path: Path) -> None:
        """创建后应有 7 张自定义表 + 2 张固定表。"""
        db_path = str(tmp_path / "test.db")
        log = HarnessLog(db_path=db_path, run_id="test-001")

        create_all_tables(log)

        conn = sqlite3.connect(db_path)
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        conn.close()
        log.close()

        expected = [
            "_events",
            "_runs",
            "api_calls",
            "api_contracts",
            "audit_results",
            "extract_results",
            "phase_metrics",
            "pipeline_runs",
            "quality_scores",
        ]
        assert sorted(tables) == expected

    def test_tables_have_correct_columns(self, tmp_path: Path) -> None:
        """pipeline_runs 表应包含设计的列。"""
        db_path = str(tmp_path / "test.db")
        log = HarnessLog(db_path=db_path, run_id="test-002")
        create_all_tables(log)

        conn = sqlite3.connect(db_path)
        cols = [row[1] for row in conn.execute("PRAGMA table_info(pipeline_runs)").fetchall()]
        conn.close()
        log.close()

        for expected_col in ["run_id", "pipeline", "project_name", "status", "duration_s"]:
            assert expected_col in cols, f"缺少列: {expected_col}"

    def test_idempotent(self, tmp_path: Path) -> None:
        """重复调用不报错（IF NOT EXISTS）。"""
        db_path = str(tmp_path / "test.db")
        log = HarnessLog(db_path=db_path, run_id="test-003")

        create_all_tables(log)
        create_all_tables(log)

        log.close()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_harness_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'govdoc.harness.schemas'`

- [ ] **Step 3: 实现 schemas.py**

```python
# govdoc/harness/schemas.py
"""Harness DB 自定义表定义与创建。"""

from __future__ import annotations

from govdoc.harness.log import HarnessLog

# -- Layer 1 表 --

PIPELINE_RUNS_COLUMNS = {
    "pipeline": "TEXT",
    "project_name": "TEXT",
    "input_file": "TEXT",
    "status": "TEXT",
    "duration_s": "REAL",
    "total_tokens": "INTEGER",
    "error": "TEXT",
}

PHASE_METRICS_COLUMNS = {
    "pipeline": "TEXT",
    "phase": "TEXT",
    "duration_s": "REAL",
    "tokens_in": "INTEGER",
    "tokens_out": "INTEGER",
    "status": "TEXT",
    "attempt_no": "INTEGER",
}

EXTRACT_RESULTS_COLUMNS = {
    "checkpoint_id": "TEXT",
    "title": "TEXT",
    "category": "TEXT",
    "has_legal_basis": "INTEGER",
    "legal_basis_count": "INTEGER",
}

AUDIT_RESULTS_COLUMNS = {
    "point_run_id": "TEXT",
    "checkpoint_id": "TEXT",
    "verdict": "TEXT",
    "has_evidence": "INTEGER",
    "evidence_count": "INTEGER",
    "has_case_refs": "INTEGER",
    "duration_s": "REAL",
    "status": "TEXT",
}

QUALITY_SCORES_COLUMNS = {
    "dimension": "TEXT",
    "score": "REAL",
    "passed": "INTEGER",
    "judge_reasoning": "TEXT",
}

# -- Layer 2 表 --

API_CALLS_COLUMNS = {
    "method": "TEXT",
    "path": "TEXT",
    "status_code": "INTEGER",
    "duration_ms": "REAL",
    "request_size": "INTEGER",
    "response_size": "INTEGER",
    "error": "TEXT",
}

API_CONTRACTS_COLUMNS = {
    "endpoint": "TEXT",
    "check_name": "TEXT",
    "passed": "INTEGER",
    "detail": "TEXT",
}

ALL_TABLES: dict[str, dict[str, str]] = {
    "pipeline_runs": PIPELINE_RUNS_COLUMNS,
    "phase_metrics": PHASE_METRICS_COLUMNS,
    "extract_results": EXTRACT_RESULTS_COLUMNS,
    "audit_results": AUDIT_RESULTS_COLUMNS,
    "quality_scores": QUALITY_SCORES_COLUMNS,
    "api_calls": API_CALLS_COLUMNS,
    "api_contracts": API_CONTRACTS_COLUMNS,
}


def create_all_tables(log: HarnessLog) -> None:
    """在 harness.db 中创建全部 7 张自定义表。

    参数:
        log: 已初始化的 HarnessLog 实例。
    """
    for table_name, columns in ALL_TABLES.items():
        log.create_table(table_name, columns)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_harness_schemas.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add govdoc/harness/schemas.py tests/unit/test_harness_schemas.py
git commit -m "feat: harness DB 7 张自定义表的 schema 定义与创建"
```

---

## Task 3: L1 管道评估核心 — pipeline_eval.py

**Files:**
- Create: `govdoc/harness/pipeline_eval.py`
- Test: `tests/unit/test_pipeline_eval.py`

- [ ] **Step 1: 编写失败测试 — 记录辅助函数**

```python
# tests/unit/test_pipeline_eval.py
"""L1 管道评估逻辑单测。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from govdoc.harness.log import HarnessLog
from govdoc.harness.pipeline_eval import (
    record_extract_results,
    record_audit_results,
    record_pipeline_run,
    record_phase_metrics,
)
from govdoc.harness.schemas import create_all_tables


class TestRecordPipelineRun:
    """测试 pipeline_runs 记录。"""

    def test_record_completed_run(self, tmp_path: Path) -> None:
        """记录一次成功的管道运行。"""
        db_path = str(tmp_path / "h.db")
        with HarnessLog(db_path=db_path, run_id="r1") as log:
            create_all_tables(log)
            record_pipeline_run(
                log,
                pipeline="A",
                project_name="测试项目",
                input_file="guide.doc",
                status="completed",
                duration_s=120.5,
                total_tokens=5000,
            )

            rows = log.query("SELECT * FROM pipeline_runs WHERE run_id='r1'")
            assert len(rows) == 1
            assert rows[0]["pipeline"] == "A"
            assert rows[0]["status"] == "completed"
            assert rows[0]["duration_s"] == 120.5

    def test_record_failed_run(self, tmp_path: Path) -> None:
        """记录一次失败的管道运行。"""
        db_path = str(tmp_path / "h.db")
        with HarnessLog(db_path=db_path, run_id="r2") as log:
            create_all_tables(log)
            record_pipeline_run(
                log,
                pipeline="B",
                project_name="p2",
                input_file="tender.docx",
                status="failed",
                duration_s=30.0,
                total_tokens=0,
                error="PES 超时",
            )

            rows = log.query("SELECT * FROM pipeline_runs WHERE run_id='r2'")
            assert rows[0]["error"] == "PES 超时"


class TestRecordExtractResults:
    """测试 extract_results 记录。"""

    def test_record_checkpoints(self, tmp_path: Path) -> None:
        """记录管道 A 提取的审核点。"""
        db_path = str(tmp_path / "h.db")
        with HarnessLog(db_path=db_path, run_id="r3") as log:
            create_all_tables(log)
            checkpoints = [
                {
                    "id": "cp_001",
                    "title": "投标人资质限制",
                    "category": "不合理条件限制或排斥供应商",
                    "legal_basis": [{"law_name": "政府采购法", "article": "第22条", "quote": "..."}],
                },
                {
                    "id": "cp_002",
                    "title": "围标串标行为",
                    "category": "围标串标",
                    "legal_basis": [],
                },
            ]
            record_extract_results(log, checkpoints)

            rows = log.query("SELECT * FROM extract_results WHERE run_id='r3' ORDER BY checkpoint_id")
            assert len(rows) == 2
            assert rows[0]["checkpoint_id"] == "cp_001"
            assert rows[0]["has_legal_basis"] == 1
            assert rows[0]["legal_basis_count"] == 1
            assert rows[1]["has_legal_basis"] == 0


class TestRecordAuditResults:
    """测试 audit_results 记录。"""

    def test_record_findings(self, tmp_path: Path) -> None:
        """记录管道 B 审核发现。"""
        db_path = str(tmp_path / "h.db")
        with HarnessLog(db_path=db_path, run_id="r4") as log:
            create_all_tables(log)
            findings = [
                {
                    "point_run_id": "pr_001",
                    "checkpoint_id": "cp_001",
                    "verdict": "不合规",
                    "evidence_quotes": ["文书第3页提到..."],
                    "evidence_refs": ["chunk_001"],
                    "case_refs": [],
                    "duration_s": 45.2,
                    "status": "completed",
                },
            ]
            record_audit_results(log, findings)

            rows = log.query("SELECT * FROM audit_results WHERE run_id='r4'")
            assert len(rows) == 1
            assert rows[0]["verdict"] == "不合规"
            assert rows[0]["has_evidence"] == 1
            assert rows[0]["evidence_count"] == 2  # quotes + refs
```

- [ ] **Step 2: 运行测试确认失败**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_pipeline_eval.py -v`
Expected: FAIL — `ImportError: cannot import name 'record_extract_results' from 'govdoc.harness.pipeline_eval'`

- [ ] **Step 3: 实现记录辅助函数**

```python
# govdoc/harness/pipeline_eval.py
"""L1 管道评估：直接调用 run_extract / run_audit，记录指标并做语义评估。"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from govdoc.harness.log import HarnessLog
from govdoc.harness.schemas import create_all_tables

logger = logging.getLogger(__name__)


# ── 记录辅助函数 ──


def record_pipeline_run(
    log: HarnessLog,
    *,
    pipeline: str,
    project_name: str,
    input_file: str,
    status: str,
    duration_s: float,
    total_tokens: int,
    error: str | None = None,
) -> None:
    """记录一次管道执行到 pipeline_runs 表。"""
    log.insert(
        "pipeline_runs",
        {
            "pipeline": pipeline,
            "project_name": project_name,
            "input_file": input_file,
            "status": status,
            "duration_s": duration_s,
            "total_tokens": total_tokens,
            "error": error,
        },
    )


def record_phase_metrics(
    log: HarnessLog,
    *,
    pipeline: str,
    phase: str,
    duration_s: float,
    tokens_in: int,
    tokens_out: int,
    status: str,
    attempt_no: int = 0,
) -> None:
    """记录单 phase 指标到 phase_metrics 表。"""
    log.insert(
        "phase_metrics",
        {
            "pipeline": pipeline,
            "phase": phase,
            "duration_s": duration_s,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "status": status,
            "attempt_no": attempt_no,
        },
    )


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
                "has_legal_basis": 1 if bases else 0,
                "legal_basis_count": len(bases),
            },
        )


def record_audit_results(
    log: HarnessLog,
    findings: list[dict[str, Any]],
) -> None:
    """记录管道 B 审核发现到 audit_results 表。"""
    for f in findings:
        quotes = f.get("evidence_quotes", [])
        refs = f.get("evidence_refs", [])
        log.insert(
            "audit_results",
            {
                "point_run_id": f.get("point_run_id", ""),
                "checkpoint_id": f.get("checkpoint_id", ""),
                "verdict": f.get("verdict", ""),
                "has_evidence": 1 if (quotes or refs) else 0,
                "evidence_count": len(quotes) + len(refs),
                "has_case_refs": 1 if f.get("case_refs") else 0,
                "duration_s": f.get("duration_s", 0.0),
                "status": f.get("status", "unknown"),
            },
        )


def record_quality_score(
    log: HarnessLog,
    *,
    dimension: str,
    score: float,
    passed: bool,
    judge_reasoning: str,
) -> None:
    """记录语义评估结果到 quality_scores 表。"""
    log.insert(
        "quality_scores",
        {
            "dimension": dimension,
            "score": score,
            "passed": 1 if passed else 0,
            "judge_reasoning": judge_reasoning,
        },
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_pipeline_eval.py -v`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add govdoc/harness/pipeline_eval.py tests/unit/test_pipeline_eval.py
git commit -m "feat: L1 管道评估记录辅助函数 + 单测"
```

---

## Task 4: L1 管道评估主流程

**Files:**
- Modify: `govdoc/harness/pipeline_eval.py`
- Test: `tests/unit/test_pipeline_eval.py`（追加）

- [ ] **Step 1: 编写失败测试 — 语义评估包装**

在 `tests/unit/test_pipeline_eval.py` 末尾追加：

```python
from govdoc.harness.pipeline_eval import evaluate_dimension
from govdoc.harness.judge import Verdict


class TestEvaluateDimension:
    """测试语义评估 + 记录。"""

    def test_evaluate_and_record(self, tmp_path: Path) -> None:
        """evaluate_dimension 调用 judge 并写入 quality_scores。"""
        db_path = str(tmp_path / "h.db")
        with HarnessLog(db_path=db_path, run_id="r5") as log:
            create_all_tables(log)

            mock_judge = MagicMock()
            mock_judge.evaluate.return_value = Verdict(
                passed=True,
                score=0.85,
                reasoning="法条引用准确",
                suggestions=[],
                raw_response="{}",
            )

            result = evaluate_dimension(
                log=log,
                judge=mock_judge,
                dimension="extract-faithfulness",
                criteria="检查法条引用是否忠实于原文",
                evidence={"checkpoints": [], "source_text": "..."},
            )

            assert result.passed is True
            assert result.score == 0.85

            rows = log.query("SELECT * FROM quality_scores WHERE dimension='extract-faithfulness'")
            assert len(rows) == 1
            assert rows[0]["score"] == 0.85
            assert rows[0]["passed"] == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_pipeline_eval.py::TestEvaluateDimension -v`
Expected: FAIL — `ImportError: cannot import name 'evaluate_dimension'`

- [ ] **Step 3: 实现 evaluate_dimension**

在 `govdoc/harness/pipeline_eval.py` 追加：

```python
from govdoc.harness.judge import HarnessJudge, Verdict


def evaluate_dimension(
    *,
    log: HarnessLog,
    judge: HarnessJudge,
    dimension: str,
    criteria: str,
    evidence: dict[str, Any],
    rubric: dict[str, Any] | None = None,
) -> Verdict:
    """调用 HarnessJudge 评估一个语义维度并记录结果。

    参数:
        log: HarnessLog 实例。
        judge: HarnessJudge 实例。
        dimension: 指标 ID（如 'extract-faithfulness'）。
        criteria: 评判标准描述。
        evidence: 证据数据。
        rubric: 可选的评分维度。

    返回:
        Verdict 评估结果。
    """
    verdict = judge.evaluate(criteria, evidence, rubric)
    record_quality_score(
        log,
        dimension=dimension,
        score=verdict.score,
        passed=verdict.passed,
        judge_reasoning=verdict.reasoning,
    )
    log.log_event(
        "semantic_eval",
        {"dimension": dimension, "score": verdict.score, "passed": verdict.passed},
    )
    return verdict


def load_rubric(rubric_dir: str | Path, dimension: str) -> str:
    """从 rubric 文件加载评判标准。

    参数:
        rubric_dir: rubric 目录路径。
        dimension: 指标 ID，映射到文件名（连字符转下划线 + .md）。

    返回:
        rubric 文件内容。
    """
    filename = dimension.replace("-", "_") + ".md"
    path = Path(rubric_dir) / filename
    if not path.exists():
        raise FileNotFoundError(f"rubric 文件不存在: {path}")
    return path.read_text(encoding="utf-8")
```

- [ ] **Step 4: 运行全部测试确认通过**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_pipeline_eval.py -v`
Expected: 5 passed

- [ ] **Step 5: 实现主入口 `run_pipeline_eval`**

在 `govdoc/harness/pipeline_eval.py` 末尾追加：

```python
async def run_pipeline_eval(
    *,
    manifest_path: str,
    project_root: str,
    rubric_dir: str,
    db_path: str = "results/harness.db",
) -> str:
    """L1 管道评估主入口。

    参数:
        manifest_path: harness_manifest.yaml 路径。
        project_root: 项目根目录。
        rubric_dir: rubric 文件目录。
        db_path: harness.db 输出路径。

    返回:
        本次运行的 run_id。
    """
    from govdoc.harness.manifest import load_manifest

    run_id = f"L1-{uuid.uuid4().hex[:8]}"
    manifest = load_manifest(manifest_path, project_root=project_root)

    with HarnessLog(db_path=db_path, run_id=run_id) as log:
        create_all_tables(log)
        log.log_event("pipeline_eval_start", {"manifest": manifest_path})

        # Phase 1: 管道 A — 法规提取
        for rule in manifest.rules:
            logger.info("管道 A: 处理法规 %s", rule.name)
            t0 = time.time()
            try:
                from govdoc.pipelines.extract_rules import run_extract
                from govdoc.db.session import get_session

                with get_session() as session:
                    extract_run = await run_extract(
                        rule_source_id=_ensure_rule_source(rule, session),
                        session=session,
                        project_root=project_root,
                    )
                duration = time.time() - t0
                usage = json.loads(extract_run.total_usage_json or "{}")
                total_tokens = sum(usage.values()) if usage else 0

                record_pipeline_run(
                    log,
                    pipeline="A",
                    project_name=rule.name,
                    input_file=rule.path,
                    status=extract_run.status,
                    duration_s=duration,
                    total_tokens=total_tokens,
                )

                if extract_run.status in ("draft_ready", "completed"):
                    checkpoints = _load_extract_output(extract_run, session)
                    record_extract_results(log, checkpoints)
            except Exception as exc:
                duration = time.time() - t0
                record_pipeline_run(
                    log,
                    pipeline="A",
                    project_name=rule.name,
                    input_file=rule.path,
                    status="failed",
                    duration_s=duration,
                    total_tokens=0,
                    error=str(exc),
                )
                logger.exception("管道 A 失败: %s", rule.name)

        # Phase 2: 管道 B — 招标审核
        for proj in manifest.projects:
            logger.info("管道 B: 处理项目 %s", proj.name)
            t0 = time.time()
            try:
                from govdoc.pipelines.audit_tender import run_audit
                from govdoc.db.session import get_session

                with get_session() as session:
                    audit_run = await run_audit(
                        audit_run_id=_ensure_audit_run(proj, session),
                        session=session,
                        project_root=project_root,
                    )
                duration = time.time() - t0

                record_pipeline_run(
                    log,
                    pipeline="B",
                    project_name=proj.name,
                    input_file=proj.tender_doc,
                    status=audit_run.status,
                    duration_s=duration,
                    total_tokens=0,
                )

                if audit_run.status in ("draft_ready", "partial_ready", "completed"):
                    findings = _load_audit_findings(audit_run, session)
                    record_audit_results(log, findings)
            except Exception as exc:
                duration = time.time() - t0
                record_pipeline_run(
                    log,
                    pipeline="B",
                    project_name=proj.name,
                    input_file=proj.tender_doc,
                    status="failed",
                    duration_s=duration,
                    total_tokens=0,
                    error=str(exc),
                )
                logger.exception("管道 B 失败: %s", proj.name)

        # Phase 3: 语义评估
        logger.info("开始语义评估")
        _run_semantic_evaluations(log, rubric_dir, project_root)

    logger.info("L1 评估完成, run_id=%s", run_id)
    return run_id


def _ensure_rule_source(rule: Any, session: Any) -> str:
    """确保法规已入库，返回 rule_source_id。"""
    from govdoc.db.models import RuleSource

    existing = session.query(RuleSource).filter_by(title=rule.name).first()
    if existing:
        return existing.id

    rs = RuleSource(title=rule.name, source_path=rule.path)
    session.add(rs)
    session.commit()
    session.refresh(rs)
    return rs.id


def _ensure_audit_run(proj: Any, session: Any) -> str:
    """确保审核运行已创建，返回 audit_run_id。"""
    from govdoc.db.models import AuditRun, Project, TenderDoc

    project = session.query(Project).filter_by(name=proj.name).first()
    if not project:
        project = Project(name=proj.name)
        session.add(project)
        session.commit()
        session.refresh(project)

    tender_doc = session.query(TenderDoc).filter_by(project_id=project.id).first()
    if not tender_doc:
        tender_doc = TenderDoc(
            project_id=project.id,
            filename=Path(proj.tender_doc).name,
            storage_path=proj.tender_doc,
        )
        session.add(tender_doc)
        session.commit()
        session.refresh(tender_doc)

    audit_run = AuditRun(
        project_id=project.id,
        tender_doc_id=tender_doc.id,
        status="pending",
    )
    session.add(audit_run)
    session.commit()
    session.refresh(audit_run)
    return audit_run.id


def _load_extract_output(extract_run: Any, session: Any) -> list[dict[str, Any]]:
    """从 ExtractRun 加载审核点结果为 dict 列表。"""
    from govdoc.db.models import CheckpointFinal

    cps = session.query(CheckpointFinal).filter_by(
        rule_source_id=extract_run.rule_source_id
    ).all()
    results = []
    for cp in cps:
        payload = json.loads(cp.payload_json) if isinstance(cp.payload_json, str) else cp.payload_json
        results.append(payload)
    return results


def _load_audit_findings(audit_run: Any, session: Any) -> list[dict[str, Any]]:
    """从 AuditRun 加载审核发现为 dict 列表。"""
    from govdoc.db.models import AuditPointRun

    point_runs = session.query(AuditPointRun).filter_by(audit_run_id=audit_run.id).all()
    results = []
    for pr in point_runs:
        if pr.finding_json:
            finding = json.loads(pr.finding_json) if isinstance(pr.finding_json, str) else pr.finding_json
            finding["point_run_id"] = pr.id
            finding["checkpoint_id"] = pr.checkpoint_final_id
            finding["duration_s"] = (pr.completed_at - pr.created_at).total_seconds() if pr.completed_at else 0
            finding["status"] = pr.status
            results.append(finding)
    return results


def _run_semantic_evaluations(log: HarnessLog, rubric_dir: str, project_root: str) -> None:
    """运行全部语义评估维度。"""
    from govdoc.harness.judge import HarnessJudge
    from govdoc.config import get_config

    config = get_config()
    judge = HarnessJudge(
        provider=config.model.provider,
        model=config.model.model,
        base_url=config.model.base_url,
        api_key=config.model.api_key,
    )

    # 收集证据
    extract_rows = log.query("SELECT * FROM extract_results WHERE run_id=?", (log._run_id,))
    audit_rows = log.query("SELECT * FROM audit_results WHERE run_id=?", (log._run_id,))

    dimensions = [
        "extract-faithfulness",
        "extract-recall",
        "extract-precision",
        "extract-hallucination",
        "extract-json-correctness",
        "extract-category-accuracy",
        "audit-faithfulness",
        "audit-relevancy",
        "audit-verdict-reasoning",
        "audit-hallucination",
        "audit-completeness",
        "audit-json-correctness",
        "agent-plan-quality",
        "agent-plan-adherence",
        "agent-step-efficiency",
        "agent-task-completion",
        "workpaper-summarization",
        "workpaper-finding-coverage",
        "workpaper-format-compliance",
    ]

    for dim in dimensions:
        try:
            criteria = load_rubric(rubric_dir, dim)
            evidence: dict[str, Any] = {
                "extract_results": extract_rows,
                "audit_results": audit_rows,
                "dimension": dim,
            }
            evaluate_dimension(
                log=log,
                judge=judge,
                dimension=dim,
                criteria=criteria,
                evidence=evidence,
            )
            logger.info("语义评估 %s 完成", dim)
        except FileNotFoundError:
            logger.warning("跳过 %s: rubric 文件缺失", dim)
        except Exception:
            logger.exception("语义评估 %s 失败", dim)
```

- [ ] **Step 6: 添加 `__main__` 入口**

在 `govdoc/harness/pipeline_eval.py` 末尾追加：

```python
if __name__ == "__main__":
    import asyncio
    import argparse

    parser = argparse.ArgumentParser(description="L1 管道 harness 评估")
    parser.add_argument("--manifest", default="scripts/fixtures/harness_manifest.yaml")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--rubric-dir", default="scripts/rubrics")
    parser.add_argument("--db-path", default="results/harness.db")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    run_id = asyncio.run(
        run_pipeline_eval(
            manifest_path=args.manifest,
            project_root=args.project_root,
            rubric_dir=args.rubric_dir,
            db_path=args.db_path,
        )
    )
    print(f"L1 完成, run_id={run_id}")
```

- [ ] **Step 7: 提交**

```bash
git add govdoc/harness/pipeline_eval.py tests/unit/test_pipeline_eval.py
git commit -m "feat: L1 管道评估主流程 + 语义评估集成"
```

---

## Task 5: L2 API 评估 — api_eval.py

**Files:**
- Create: `govdoc/harness/api_eval.py`
- Test: `tests/unit/test_api_eval.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/unit/test_api_eval.py
"""L2 API 评估逻辑单测。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from govdoc.harness.api_eval import (
    record_api_call,
    record_api_contract,
    check_response_schema,
    EndpointSpec,
)
from govdoc.harness.log import HarnessLog
from govdoc.harness.schemas import create_all_tables


class TestRecordApiCall:
    """测试 api_calls 记录。"""

    def test_record_success(self, tmp_path: Path) -> None:
        """记录一次成功的 API 调用。"""
        db_path = str(tmp_path / "h.db")
        with HarnessLog(db_path=db_path, run_id="api-1") as log:
            create_all_tables(log)
            record_api_call(
                log,
                method="GET",
                path="/healthz",
                status_code=200,
                duration_ms=15.3,
                request_size=0,
                response_size=28,
            )

            rows = log.query("SELECT * FROM api_calls WHERE run_id='api-1'")
            assert len(rows) == 1
            assert rows[0]["status_code"] == 200
            assert rows[0]["duration_ms"] == 15.3


class TestCheckResponseSchema:
    """测试响应 schema 校验。"""

    def test_valid_response(self) -> None:
        """合法响应返回 (True, '')。"""
        from pydantic import BaseModel

        class HealthResponse(BaseModel):
            status: str

        passed, detail = check_response_schema({"status": "ok"}, HealthResponse)
        assert passed is True

    def test_invalid_response(self) -> None:
        """不合法响应返回 (False, error_msg)。"""
        from pydantic import BaseModel

        class HealthResponse(BaseModel):
            status: str
            version: int

        passed, detail = check_response_schema({"status": "ok"}, HealthResponse)
        assert passed is False
        assert "version" in detail


class TestEndpointSpec:
    """测试端点规格定义。"""

    def test_spec_fields(self) -> None:
        """EndpointSpec 包含必要字段。"""
        spec = EndpointSpec(
            method="POST",
            path="/api/v1/projects",
            expected_status=201,
            description="创建项目",
        )
        assert spec.method == "POST"
        assert spec.expected_status == 201
```

- [ ] **Step 2: 运行测试确认失败**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_api_eval.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 api_eval.py**

```python
# govdoc/harness/api_eval.py
"""L2 API 评估：httpx 调全部端点 + 契约验证 + 性能指标。"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Type

from pydantic import BaseModel, ValidationError

from govdoc.harness.log import HarnessLog
from govdoc.harness.schemas import create_all_tables

logger = logging.getLogger(__name__)


@dataclass
class EndpointSpec:
    """单个 API 端点的测试规格。"""

    method: str
    path: str
    expected_status: int
    description: str
    body: dict[str, Any] | None = None
    files: dict[str, str] | None = None
    response_model: Type[BaseModel] | None = None
    is_async: bool = False
    path_params: dict[str, str] = field(default_factory=dict)


def record_api_call(
    log: HarnessLog,
    *,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    request_size: int = 0,
    response_size: int = 0,
    error: str | None = None,
) -> None:
    """记录一次 HTTP 调用到 api_calls 表。"""
    log.insert(
        "api_calls",
        {
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "request_size": request_size,
            "response_size": response_size,
            "error": error,
        },
    )


def record_api_contract(
    log: HarnessLog,
    *,
    endpoint: str,
    check_name: str,
    passed: bool,
    detail: str = "",
) -> None:
    """记录一次契约检查到 api_contracts 表。"""
    log.insert(
        "api_contracts",
        {
            "endpoint": endpoint,
            "check_name": check_name,
            "passed": 1 if passed else 0,
            "detail": detail,
        },
    )


def check_response_schema(
    data: dict[str, Any],
    model: Type[BaseModel],
) -> tuple[bool, str]:
    """校验响应 body 是否符合 Pydantic model。

    返回:
        (passed, detail) 元组。
    """
    try:
        model.model_validate(data)
        return True, ""
    except ValidationError as e:
        return False, str(e)


async def call_endpoint(
    client: Any,
    spec: EndpointSpec,
    log: HarnessLog,
) -> tuple[int, dict[str, Any] | None]:
    """调用单个端点并记录。

    返回:
        (status_code, response_json)。
    """
    path = spec.path
    for key, val in spec.path_params.items():
        path = path.replace(f"{{{key}}}", val)

    t0 = time.time()
    try:
        if spec.method == "GET":
            resp = await client.get(path)
        elif spec.method == "POST":
            if spec.files:
                resp = await client.post(path, files=spec.files)
            else:
                resp = await client.post(path, json=spec.body)
        elif spec.method == "PUT":
            resp = await client.put(path, json=spec.body)
        elif spec.method == "DELETE":
            resp = await client.delete(path)
        else:
            raise ValueError(f"不支持的 HTTP 方法: {spec.method}")

        duration_ms = (time.time() - t0) * 1000
        response_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else None

        record_api_call(
            log,
            method=spec.method,
            path=path,
            status_code=resp.status_code,
            duration_ms=duration_ms,
            request_size=len(json.dumps(spec.body).encode()) if spec.body else 0,
            response_size=len(resp.content),
        )

        # 状态码契约检查
        record_api_contract(
            log,
            endpoint=f"{spec.method} {spec.path}",
            check_name="status_code",
            passed=resp.status_code == spec.expected_status,
            detail=f"expected={spec.expected_status}, actual={resp.status_code}",
        )

        # Schema 契约检查
        if spec.response_model and response_data:
            passed, detail = check_response_schema(response_data, spec.response_model)
            record_api_contract(
                log,
                endpoint=f"{spec.method} {spec.path}",
                check_name="response_schema",
                passed=passed,
                detail=detail,
            )

        return resp.status_code, response_data

    except Exception as exc:
        duration_ms = (time.time() - t0) * 1000
        record_api_call(
            log,
            method=spec.method,
            path=path,
            status_code=0,
            duration_ms=duration_ms,
            error=str(exc),
        )
        logger.exception("调用 %s %s 失败", spec.method, path)
        return 0, None


async def run_api_eval(
    *,
    base_url: str = "http://localhost:8000",
    manifest_path: str,
    project_root: str,
    db_path: str = "results/harness.db",
) -> str:
    """L2 API 评估主入口。

    参数:
        base_url: FastAPI 服务地址。
        manifest_path: harness_manifest.yaml 路径。
        project_root: 项目根目录。
        db_path: harness.db 路径。

    返回:
        本次运行的 run_id。
    """
    import httpx

    from govdoc.harness.manifest import load_manifest

    run_id = f"L2-{uuid.uuid4().hex[:8]}"
    manifest = load_manifest(manifest_path, project_root=project_root)

    async with httpx.AsyncClient(base_url=base_url, timeout=60.0) as client:
        with HarnessLog(db_path=db_path, run_id=run_id) as log:
            create_all_tables(log)
            log.log_event("api_eval_start", {"base_url": base_url})

            # Phase 1: 健康检查
            await call_endpoint(
                client,
                EndpointSpec(method="GET", path="/healthz", expected_status=200, description="健康检查"),
                log,
            )

            # Phase 2: 项目 CRUD
            status, proj_data = await call_endpoint(
                client,
                EndpointSpec(
                    method="POST",
                    path="/api/v1/projects",
                    expected_status=201,
                    description="创建项目",
                    body={"name": f"harness-test-{run_id}"},
                ),
                log,
            )
            project_id = proj_data["id"] if proj_data else "unknown"

            await call_endpoint(
                client,
                EndpointSpec(method="GET", path="/api/v1/projects", expected_status=200, description="列出项目"),
                log,
            )

            await call_endpoint(
                client,
                EndpointSpec(
                    method="GET",
                    path="/api/v1/projects/{project_id}",
                    expected_status=200,
                    description="获取项目",
                    path_params={"project_id": project_id},
                ),
                log,
            )

            # Phase 3: 文书上传
            for proj in manifest.projects:
                tender_path = Path(proj.tender_doc)
                if tender_path.exists():
                    await call_endpoint(
                        client,
                        EndpointSpec(
                            method="POST",
                            path="/api/v1/projects/{project_id}/tender-doc",
                            expected_status=201,
                            description=f"上传文书: {proj.name}",
                            path_params={"project_id": project_id},
                            files={"file": (tender_path.name, tender_path.read_bytes())},
                        ),
                        log,
                    )

            # Phase 4: 规则上传
            for rule in manifest.rules:
                rule_path = Path(rule.path)
                if rule_path.exists():
                    await call_endpoint(
                        client,
                        EndpointSpec(
                            method="POST",
                            path="/api/v1/rules/upload",
                            expected_status=202,
                            description=f"上传法规: {rule.name}",
                            files={"file": (rule_path.name, rule_path.read_bytes())},
                            is_async=True,
                        ),
                        log,
                    )

            # Phase 5: 审核点导入
            for cp in manifest.checkpoints:
                cp_path = Path(cp.path)
                if cp_path.exists():
                    await call_endpoint(
                        client,
                        EndpointSpec(
                            method="POST",
                            path="/api/v1/checkpoints/import",
                            expected_status=200,
                            description=f"导入审核点: {cp.name}",
                            files={"file": (cp_path.name, cp_path.read_bytes())},
                        ),
                        log,
                    )

            # Phase 6: 列出端点
            await call_endpoint(
                client,
                EndpointSpec(method="GET", path="/api/v1/rules", expected_status=200, description="列出法规"),
                log,
            )
            await call_endpoint(
                client,
                EndpointSpec(method="GET", path="/api/v1/checkpoints", expected_status=200, description="列出审核点"),
                log,
            )

            # Phase 7: P95 延迟计算
            sync_calls = log.query(
                "SELECT duration_ms FROM api_calls WHERE run_id=? AND status_code > 0 ORDER BY duration_ms",
                (run_id,),
            )
            if sync_calls:
                durations = [row["duration_ms"] for row in sync_calls]
                p95_idx = int(len(durations) * 0.95)
                p95 = durations[min(p95_idx, len(durations) - 1)]
                log.log_event("api_latency_p95", {"p95_ms": p95})

            log.log_event("api_eval_complete", {"total_calls": len(sync_calls) if sync_calls else 0})

    logger.info("L2 评估完成, run_id=%s", run_id)
    return run_id


if __name__ == "__main__":
    import asyncio
    import argparse

    parser = argparse.ArgumentParser(description="L2 API harness 评估")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--manifest", default="scripts/fixtures/harness_manifest.yaml")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--db-path", default="results/harness.db")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    run_id = asyncio.run(
        run_api_eval(
            base_url=args.base_url,
            manifest_path=args.manifest,
            project_root=args.project_root,
            db_path=args.db_path,
        )
    )
    print(f"L2 完成, run_id={run_id}")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_api_eval.py -v`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add govdoc/harness/api_eval.py tests/unit/test_api_eval.py
git commit -m "feat: L2 API 评估 — 全端点冒烟 + 契约验证 + 性能指标"
```

---

## Task 6: Shell 脚本入口

**Files:**
- Create: `scripts/harness_pipeline.sh`
- Create: `scripts/harness_api.sh`
- Create: `scripts/harness_all.sh`

- [ ] **Step 1: 创建 scripts 目录结构**

```bash
mkdir -p scripts/fixtures scripts/rubrics results
```

- [ ] **Step 2: 编写 harness_pipeline.sh**

```bash
#!/usr/bin/env bash
# L1 管道 harness 评估 — 直接调用 run_extract / run_audit + HarnessJudge
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== L1 Pipeline Eval ==="
echo "开始时间: $(date)"

conda run -n govdoc-auditor-v3 python -m govdoc.harness.pipeline_eval \
    --manifest scripts/fixtures/harness_manifest.yaml \
    --project-root . \
    --rubric-dir scripts/rubrics \
    --db-path results/harness.db

echo "=== L1 完成 ==="
echo "结束时间: $(date)"
```

- [ ] **Step 3: 编写 harness_api.sh**

```bash
#!/usr/bin/env bash
# L2 API harness 评估 — httpx 全端点冒烟 + 契约验证
set -euo pipefail
cd "$(dirname "$0")/.."

BASE_URL="${HARNESS_API_URL:-http://localhost:8000}"

echo "=== L2 API Eval ==="
echo "目标: $BASE_URL"
echo "开始时间: $(date)"

# 检查服务是否可达
if ! curl -sf "${BASE_URL}/healthz" > /dev/null 2>&1; then
    echo "错误: FastAPI 服务不可达 ($BASE_URL/healthz)"
    echo "请先启动: conda run -n govdoc-auditor-v3 uvicorn govdoc.api.main:app --port 8000"
    exit 1
fi

conda run -n govdoc-auditor-v3 python -m govdoc.harness.api_eval \
    --base-url "$BASE_URL" \
    --manifest scripts/fixtures/harness_manifest.yaml \
    --project-root . \
    --db-path results/harness.db

echo "=== L2 完成 ==="
echo "结束时间: $(date)"
```

- [ ] **Step 4: 编写 harness_all.sh**

```bash
#!/usr/bin/env bash
# Harness 总入口：串行执行 L1 + L2
set -euo pipefail
cd "$(dirname "$0")/.."

echo "========================================="
echo "  GovDoc Harness 端到端评估"
echo "  $(date)"
echo "========================================="

echo ""
echo "[1/2] L1 管道评估..."
bash scripts/harness_pipeline.sh

echo ""
echo "[2/2] L2 API 评估..."
bash scripts/harness_api.sh

echo ""
echo "========================================="
echo "  全部完成！结果: results/harness.db"
echo "  $(date)"
echo "========================================="
```

- [ ] **Step 5: 设置可执行权限**

```bash
chmod +x scripts/harness_pipeline.sh scripts/harness_api.sh scripts/harness_all.sh
```

- [ ] **Step 6: 添加 .gitignore 条目**

在项目根 `.gitignore` 追加：

```
# Harness 运行结果（每次重新生成）
results/harness.db
results/harness.db-wal
results/harness.db-shm
```

- [ ] **Step 7: 创建 results/.gitkeep**

```bash
touch results/.gitkeep
```

- [ ] **Step 8: 提交**

```bash
git add scripts/harness_pipeline.sh scripts/harness_api.sh scripts/harness_all.sh results/.gitkeep .gitignore
git commit -m "feat: harness shell 脚本入口 + results 目录"
```

---

## Task 7: Rubric 文件

**Files:**
- Create: `scripts/rubrics/*.md`（20 个文件）

- [ ] **Step 1: 创建管道 A rubric 文件（6 个）**

```markdown
<!-- scripts/rubrics/extract_faithfulness.md -->
# 法条引用忠实度 (extract-faithfulness)

## 评判标准
逐个检查每个审核点的 `legal_basis[]` 字段：
1. 每条法条引用的 `law_name`（法律名称）是否在法规原文中出现
2. `article`（条款号）是否与原文中实际条款对应
3. `quote`（原文引用）是否能在法规原文中找到相似段落

## 评分规则
- 1.0：全部法条引用可在原文中找到精确或近似匹配
- 0.7-0.9：大部分引用准确，少量有偏差但不影响判断
- 0.4-0.6：约半数引用准确
- 0.0-0.3：大量引用无法在原文中找到，存在编造

## 判定阈值
score >= 0.7 → passed
```

```markdown
<!-- scripts/rubrics/extract_recall.md -->
# 审核点召回率 (extract-recall)

## 评判标准
对照法规原文，检查是否覆盖了以下四类违法违规行为的所有可审核维度：
1. 意向性招标
2. 围标串标
3. 不合理条件限制或排斥供应商
4. 其他违法违规

## 评分规则
- 1.0：每类至少有 1 个审核点，且覆盖了法规中明确列出的所有判断标准
- 0.7-0.9：覆盖了主要维度，缺少个别细分点
- 0.4-0.6：仅覆盖部分类别
- 0.0-0.3：严重遗漏

## 判定阈值
score >= 0.7 → passed
```

```markdown
<!-- scripts/rubrics/extract_precision.md -->
# 审核点精准率 (extract-precision)

## 评判标准
逐个检查每个审核点是否都有明确的法规依据：
1. 审核点描述的行为是否在法规中有对应条款
2. 是否存在凭空推测的审核点（法规中无相关描述）
3. 审核点之间是否存在重复（同一行为拆成多个点）

## 评分规则
- 1.0：全部审核点都有法规依据，无重复
- 0.7-0.9：个别审核点的法规依据较弱但合理
- 0.4-0.6：存在明显无依据的审核点
- 0.0-0.3：大量虚构审核点

## 判定阈值
score >= 0.7 → passed
```

```markdown
<!-- scripts/rubrics/extract_hallucination.md -->
# 幻觉检测 (extract-hallucination)

## 评判标准
检查审核点的描述、标题、法条引用中是否包含法规原文未提及的内容：
1. 描述中是否引入了法规未提及的概念或要求
2. 法条引用是否指向不存在的法律或条款
3. 是否歪曲了法规原意（断章取义、过度推断）

## 评分规则
- 1.0：无幻觉，全部内容可追溯至法规原文
- 0.7-0.9：极少量推断，但不影响审核判断
- 0.4-0.6：存在明显的幻觉内容
- 0.0-0.3：大量幻觉，严重偏离法规原文

## 判定阈值
score >= 0.7 → passed
```

```markdown
<!-- scripts/rubrics/extract_json_correctness.md -->
# 输出 Schema 合规 (extract-json-correctness)

## 评判标准
检查 output.json 是否严格符合 CheckpointListOutput schema：
1. 根节点有 `checkpoints` 数组
2. 每个元素有 `id`, `category`, `title`, `description`, `severity` 必填字段
3. `category` 值为枚举之一：意向性招标|围标串标|不合理条件限制或排斥供应商|其他违法违规
4. `severity` 值为枚举之一：critical|major|minor
5. `legal_basis` 若存在，每项有 `law_name`, `article`, `quote`

## 评分规则
- 1.0：完全符合 schema，所有字段类型和枚举值正确
- 0.5：结构基本正确但有字段缺失或类型错误
- 0.0：无法解析或结构完全不匹配

## 判定阈值
score >= 0.9 → passed
```

```markdown
<!-- scripts/rubrics/extract_category_accuracy.md -->
# 分类准确性 (extract-category-accuracy)

## 评判标准
逐个检查每个审核点的 `category` 是否与其内容匹配：
1. "意向性招标" → 审核点描述的是否为倾向特定供应商的行为
2. "围标串标" → 是否为投标人之间的串通行为
3. "不合理条件限制或排斥供应商" → 是否为设置不合理门槛
4. "其他违法违规" → 上述三类无法涵盖的行为

## 评分规则
- 1.0：全部分类准确
- 0.7-0.9：个别分类可商榷但不明显错误
- 0.4-0.6：约半数分类有误
- 0.0-0.3：大量分类错误

## 判定阈值
score >= 0.7 → passed
```

- [ ] **Step 2: 创建管道 B rubric 文件（6 个）**

以同样格式创建：
- `scripts/rubrics/audit_faithfulness.md` — 证据引用忠实度
- `scripts/rubrics/audit_relevancy.md` — 发现与审核点相关性
- `scripts/rubrics/audit_verdict_reasoning.md` — 判定推理自洽性
- `scripts/rubrics/audit_hallucination.md` — 幻觉检测
- `scripts/rubrics/audit_completeness.md` — 审核覆盖完整性
- `scripts/rubrics/audit_json_correctness.md` — 输出 Schema 合规

每个文件结构与 Step 1 一致：评判标准 → 评分规则 → 判定阈值。

- [ ] **Step 3: 创建 Agent 行为 rubric 文件（4 个）**

- `scripts/rubrics/agent_plan_quality.md`
- `scripts/rubrics/agent_plan_adherence.md`
- `scripts/rubrics/agent_step_efficiency.md`
- `scripts/rubrics/agent_task_completion.md`

- [ ] **Step 4: 创建工作底稿 + 导入 rubric 文件（4 个）**

- `scripts/rubrics/workpaper_summarization.md`
- `scripts/rubrics/workpaper_finding_coverage.md`
- `scripts/rubrics/workpaper_format_compliance.md`
- `scripts/rubrics/checkpoint_import_fidelity.md`

- [ ] **Step 5: 验证 rubric 文件数量**

```bash
ls scripts/rubrics/*.md | wc -l
```
Expected: 20

- [ ] **Step 6: 提交**

```bash
git add scripts/rubrics/
git commit -m "feat: 20 个语义评估 rubric 文件"
```

---

## Task 8: research-wiki Schema 实体

**Files:**
- Create: `research-wiki/schemas/` 目录及 7 个 .md 文件

- [ ] **Step 1: 创建 schemas 目录和 7 个 schema 实体**

每个文件格式：

```markdown
---
type: schema
node_id: schema:harness-pipeline-runs
title: "表结构: pipeline_runs"
date: 2026-05-13
tags: ["harness"]
---

# pipeline_runs

Layer 1 管道执行汇总表。每次 run_extract() / run_audit() 调用记录一行。

| 列 | 类型 | 说明 |
|----|------|------|
| run_id | TEXT | HarnessLog 运行 ID |
| timestamp | TEXT | 自动填充 |
| pipeline | TEXT | "A" 或 "B" |
| project_name | TEXT | 测试项目名 |
| input_file | TEXT | 输入文件路径 |
| status | TEXT | completed / failed |
| duration_s | REAL | 执行耗时（秒） |
| total_tokens | INTEGER | 总 token 用量 |
| error | TEXT | 失败时的错误信息 |
```

创建 7 个文件：
- `research-wiki/schemas/harness-pipeline-runs.md`
- `research-wiki/schemas/harness-phase-metrics.md`
- `research-wiki/schemas/harness-extract-results.md`
- `research-wiki/schemas/harness-audit-results.md`
- `research-wiki/schemas/harness-quality-scores.md`
- `research-wiki/schemas/harness-api-calls.md`
- `research-wiki/schemas/harness-api-contracts.md`

- [ ] **Step 2: 提交**

```bash
git add research-wiki/schemas/
git commit -m "docs: 7 个 harness DB schema 实体"
```

---

## Task 9: research-wiki Metric 实体

**Files:**
- Create: `research-wiki/metrics/` 目录及 31 个 .md 文件

- [ ] **Step 1: 创建 metrics 目录和硬性指标实体（14 个）**

每个文件格式：

```markdown
---
type: metric
node_id: metric:pipeline-a-success
title: "管道 A 成功率"
date: 2026-05-13
tags: ["harness", "hard-metric", "L1"]
---

# 管道 A 成功率 (pipeline-a-success)

- **类型**: 硬性指标
- **层**: L1（管道层）
- **计算**: `COUNT(status='completed') / COUNT(*)` from `pipeline_runs WHERE pipeline='A'`
- **阈值**: ≥ 80%
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-pipeline-runs]]
```

创建 14 个硬性指标文件：`pipeline-a-success`, `pipeline-b-success`, `phase-no-crash`, `extract-yield`, `audit-completion`, `e2e-duration`, `checkpoint-import-success`, `tender-parse-success`, `workpaper-render`, `docx-download`, `compare-success`, `api-all-endpoints`, `api-contract-pass`, `api-latency-p95`

- [ ] **Step 2: 创建语义指标实体（17 个）**

格式与硬性指标类似，`type` 标记为 `semantic-metric`：

创建 17 个语义指标文件：`extract-faithfulness`, `extract-recall`, `extract-precision`, `extract-hallucination`, `extract-json-correctness`, `extract-category-accuracy`, `audit-faithfulness`, `audit-relevancy`, `audit-verdict-reasoning`, `audit-hallucination`, `audit-completeness`, `audit-json-correctness`, `agent-plan-quality`, `agent-plan-adherence`, `agent-step-efficiency`, `agent-task-completion`, `workpaper-summarization`, `workpaper-finding-coverage`, `workpaper-format-compliance`, `checkpoint-import-fidelity`

- [ ] **Step 3: 验证文件数量**

```bash
ls research-wiki/metrics/*.md | wc -l
```
Expected: 31

- [ ] **Step 4: 提交**

```bash
git add research-wiki/metrics/
git commit -m "docs: 31 个 harness 评估指标实体（14 硬性 + 17 语义）"
```

---

## Task 10: 更新 __init__.py 和 index.md

**Files:**
- Modify: `govdoc/harness/__init__.py`
- Modify: `research-wiki/index.md`

- [ ] **Step 1: 更新 harness __init__.py**

```python
# govdoc/harness/__init__.py
"""Harness 评估系统：日志基础设施与 LLM 评估。"""

from govdoc.harness.judge import Diagnosis, HarnessJudge, Verdict
from govdoc.harness.log import HarnessLog
from govdoc.harness.manifest import HarnessManifest, load_manifest
from govdoc.harness.schemas import ALL_TABLES, create_all_tables

__all__ = [
    "HarnessLog",
    "HarnessJudge",
    "Verdict",
    "Diagnosis",
    "HarnessManifest",
    "load_manifest",
    "ALL_TABLES",
    "create_all_tables",
]
```

- [ ] **Step 2: 更新 research-wiki/index.md**

在 `## plan` 区块添加：
```markdown
- [端到端 Harness 评估基础设施实施计划](plans/harness-e2e-plan.md) `plan:harness-e2e-plan`
```

新增两个区块：
```markdown
## schema (7)
- [pipeline_runs](schemas/harness-pipeline-runs.md) `schema:harness-pipeline-runs`
- [phase_metrics](schemas/harness-phase-metrics.md) `schema:harness-phase-metrics`
- [extract_results](schemas/harness-extract-results.md) `schema:harness-extract-results`
- [audit_results](schemas/harness-audit-results.md) `schema:harness-audit-results`
- [quality_scores](schemas/harness-quality-scores.md) `schema:harness-quality-scores`
- [api_calls](schemas/harness-api-calls.md) `schema:harness-api-calls`
- [api_contracts](schemas/harness-api-contracts.md) `schema:harness-api-contracts`

## metric (31)
- [管道 A 成功率](metrics/pipeline-a-success.md) `metric:pipeline-a-success`
... (全部 31 个)
```

- [ ] **Step 3: 提交**

```bash
git add govdoc/harness/__init__.py research-wiki/index.md
git commit -m "refactor: 更新 harness 模块导出 + wiki 索引"
```

---

## Task 11: 运行全部单测验证

**Files:** 无新增

- [ ] **Step 1: 运行全部 harness 相关单测**

```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_harness_*.py -v
```

Expected: 全部 passed（约 15+ 个测试）

- [ ] **Step 2: 运行 ruff 格式化和检查**

```bash
conda run -n govdoc-auditor-v3 ruff format govdoc/harness/ tests/unit/test_harness_*.py scripts/
conda run -n govdoc-auditor-v3 ruff check govdoc/harness/ tests/unit/test_harness_*.py --fix
```

Expected: 无错误

- [ ] **Step 3: 如有格式修复，提交**

```bash
git add -u
git commit -m "style: ruff 格式化 harness 模块"
```
