# P0 · run_audit 拆分 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `govdoc/pipelines/audit_tender.py::run_audit`（214 行，L204-418）拆成一个薄编排层（≤70 行）+ 5 个职责清晰的 helper，行为不变。

**Architecture:**
- 先扩充集成测试断言终态（护栏 B），再写 golden 采集脚本（护栏 A），提交护栏 commit
- 逐个抽 helper，每次抽完跑全测试确认绿
- 最后 `run_audit` 只做编排：调用 helper + 汇总

**Tech Stack:** Python 3.11, SQLModel, pytest, `govdoc-auditor-v3` conda env

**依赖：** Umbrella 分支已建立

---

## 拆分目标

原 `run_audit(audit_run_id, session, *, workspace_manager, trajectory_store, replay_dir, project_root, template_path, point_run_ids) -> AuditRun` 约 214 行，拆为：

```python
def _index_tender_doc(audit_run: AuditRun, tender_doc: TenderDoc, *, replay: bool) -> str | None:
    """为本次 audit run 准备 qmd tender collection。replay 模式下返回占位名。"""
    # 搬原 L241-249

def _resolve_point_runs(
    session: Session, audit_run: AuditRun, point_run_ids: Sequence[str] | None
) -> list[AuditPointRun]:
    """按 audit_run_id 查 point_runs，可按 point_run_ids 过滤，status=completed 的跳过。"""
    # 搬原 L223-227 + L253-257（selected_point_ids 过滤）

async def _run_single_point(
    point_run: AuditPointRun,
    checkpoint: GovCheckpoint,
    *,
    audit_run: AuditRun,
    tender_doc: TenderDoc,
    tender_collection: str | None,
    manager: Any,
    store: Any,
    cfg: Any,
    repo_root: Path,
    replay_dir: str | Path | None,
) -> tuple[Any, Any]:  # (workspace, pes_result)
    """搭建单点 workspace，运行 PES（真或 mock），返回 workspace 与 result。"""
    # 搬原 L276-323（WorkspaceSpec 构建 + PES 创建 + await pes.run）

def _persist_point_result(
    point_run: AuditPointRun,
    result: Any,
    workspace: Any,
    checkpoint: GovCheckpoint,
    *,
    manager: Any,
) -> None:
    """把 PES result 落到 point_run（status/finding_json/archive_path/usage_json）。"""
    # 搬原 L325-344

def _cleanup_tender_collection(collection_id: str | None) -> None:
    """清理 qmd 临时 tender collection。允许失败静默（best-effort）。"""
    # 当前原代码里没有显式清理，本次拆分需新增清理逻辑（见 spec §3.1）

def _assemble_workpaper_draft(
    audit_run: AuditRun, session: Session, tender_doc: TenderDoc, template_path: str | Path | None
) -> None:
    """从 completed point_runs 汇总 findings，生成 WorkpaperDraft。更新 audit_run.status。"""
    # 搬原 L367-403
```

原 `run_audit` 只剩：参数校验 + 调用上述 helper + try/except 顶层包装，≤70 行。

---

## Task 0: 建立子分支

- [ ] **Step 1: 从 umbrella 切子分支**

Run:
```bash
git checkout feat/tech-debt-cleanup
git pull --ff-only 2>/dev/null || true
git checkout -b feat/p0-run-audit-split
```

- [ ] **Step 2: 确认分支**

Run: `git branch --show-current`
Expected: `feat/p0-run-audit-split`

---

## Task 1: 扩充集成测试终态断言（护栏 B）

**Files:**
- Modify: `tests/contract/test_pipeline_b_with_mocks.py`

- [ ] **Step 1: 读当前测试结构**

Run: `cat tests/contract/test_pipeline_b_with_mocks.py | head -80`
Expected: 看到既有的 `test_pipeline_b_with_mock_pes_replay` 函数

- [ ] **Step 2: 在 `test_pipeline_b_with_mock_pes_replay` 最后添加 6 类终态断言**

现有测试末尾已有 L135-144 的基础断言（`result.status == "draft_ready"`、`drafts`、`point_runs` 等）。在那些断言之后追加（保留原有不变，变量 `result` / `drafts` / `point_runs` 已在上文捕获）：

```python
    # === Guardrail assertions for P0 run_audit refactor ===
    # I1: behavior-preservation checks. Any helper extraction must preserve these.

    # 1. AuditRun 最终 status 在合法集合内
    assert result.status in {"draft_ready", "partial_ready", "waiting_retry", "failed"}, \
        f"unexpected audit_run.status: {result.status}"

    # 2. 每个 point_run 的 status 都在合法集合内
    for pr in point_runs:
        assert pr.status in {"completed", "failed", "pending", "running"}, \
            f"unexpected point_run.status: {pr.status}"

    # 3. 每个 completed point_run 的 finding_json 可解析为 GovFinding，且 verdict 合法
    for pr in point_runs:
        if pr.status == "completed":
            assert pr.finding_json and pr.finding_json.strip(), \
                f"completed point_run {pr.id} has empty finding_json"
            finding = GovFinding.model_validate_json(pr.finding_json)
            assert finding.verdict in {"合规", "不合规", "存疑"}

    # 4. draft_ready 时 WorkpaperDraft 的 docx 文件必须实际存在
    if result.status == "draft_ready":
        assert len(drafts) >= 1, "draft_ready but no WorkpaperDraft"
        for d in drafts:
            assert d.docx_path and Path(d.docx_path).is_file(), \
                f"WorkpaperDraft.docx_path 文件不存在: {d.docx_path}"

    # 5. trajectory 落盘：completed/failed 的 point_run 应在 store 里有记录
    # FakeTrajectoryStore 的接口见 scrivai；若无 list/get 方法可省略本条。
    # 原断言（既有的 pr.workspace_archive_path is not None）已覆盖等价信息。

    # 6. tender_collection 清理：replay 模式下 tender_doc.qmd_collection 是占位名，不检查真 qmd
    # 非 replay 模式由 _cleanup_tender_collection 保证；P0 拆分后该 helper 单测覆盖
```

⚠️ **说明**：
- 断言 5 在 replay 模式下意义不大（`FakeTrajectoryStore` 是内存假对象），原第 144 行 `pr.workspace_archive_path is not None` 已提供等价保证，本条留注释不强断言
- 断言 6 的语义由拆分出的 helper 单测 (`test_cleanup_tender_collection`) 保证，这里不重复

- [ ] **Step 3: 确保必要的 import 齐全**

文件顶部追加（如缺）：
```python
from pathlib import Path  # 可能已有
from govdoc.schemas import GovFinding  # 可能已有（见 schemas/__init__.py）
```

其他用到的 `AuditPointRun` / `WorkpaperDraft` / `select` 在现有测试中已有 import。

- [ ] **Step 4: 运行测试，确认新断言在当前代码上通过**

Run:
```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/contract/test_pipeline_b_with_mocks.py::test_pipeline_b_with_mock_pes_replay -v
```

Expected: 全绿（因为当前代码行为本就满足这些断言）

- [ ] **Step 5: 提交护栏测试**

```bash
git add tests/contract/test_pipeline_b_with_mocks.py
git commit -m "test: 扩充管道 B 集成测试终态断言作为 P0 拆分护栏"
```

---

## Task 2: 编写 golden 采集脚本（护栏 A）

**Files:**
- Create: `tests/contract/golden/__init__.py`（空）
- Create: `tests/contract/golden/capture.py`
- Create: `tests/contract/test_audit_golden.py`

- [ ] **Step 1: 创建 golden 目录和 `__init__.py`**

```bash
mkdir -p tests/contract/golden
touch tests/contract/golden/__init__.py
```

- [ ] **Step 2: 写 `capture.py` — 采集 audit_case_01 的 DB + 文件树 hash**

Create `tests/contract/golden/capture.py`:

```python
"""P0 拆分 golden 采集：对 audit_case_01 fixture 采集 DB 字段快照 + 文件树 hash。

用途：在拆分前跑一次作为 baseline，拆分后再跑一次对比。
排除不稳定字段（时间戳 / UUID / 路径前缀）。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from govdoc.db.models import (
    AuditPointRun,
    AuditRun,
    TenderDoc,
    WorkpaperDraft,
)


# 不稳定字段（每次跑都会变），diff 时排除
UNSTABLE_FIELDS = {"id", "created_at", "updated_at", "completed_at", "workspace_archive_path", "workspace_failed_path", "docx_path"}


def _sanitize(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k not in UNSTABLE_FIELDS}


@dataclass
class AuditGolden:
    audit_run: dict[str, Any]
    point_runs: list[dict[str, Any]]  # sorted by checkpoint_final_id
    findings: list[dict[str, Any]]    # parsed + sorted by checkpoint_id
    workpaper_drafts: list[dict[str, Any]]  # sorted by version


def capture(session: Session, audit_run_id: str) -> AuditGolden:
    """采集 DB 终态为可比较的 dict。"""
    audit_run = session.get(AuditRun, audit_run_id)
    assert audit_run is not None

    point_runs = session.exec(
        select(AuditPointRun).where(AuditPointRun.audit_run_id == audit_run_id)
    ).all()
    point_runs_sorted = sorted(point_runs, key=lambda pr: pr.checkpoint_final_id)

    findings = []
    for pr in point_runs_sorted:
        if pr.finding_json:
            findings.append(json.loads(pr.finding_json))
    findings.sort(key=lambda f: f.get("checkpoint_id", ""))

    drafts = session.exec(
        select(WorkpaperDraft).where(WorkpaperDraft.audit_run_id == audit_run_id)
    ).all()
    drafts_sorted = sorted(drafts, key=lambda d: d.version)

    return AuditGolden(
        audit_run=_sanitize(audit_run.model_dump()),
        point_runs=[_sanitize(pr.model_dump()) for pr in point_runs_sorted],
        findings=findings,
        workpaper_drafts=[_sanitize(d.model_dump()) for d in drafts_sorted],
    )


def golden_hash(golden: AuditGolden) -> str:
    """对 golden 做稳定 hash（排序后 JSON）。"""
    blob = json.dumps(asdict(golden), ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def write_golden(golden: AuditGolden, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(golden), ensure_ascii=False, indent=2, sort_keys=True))


def load_golden(path: Path) -> AuditGolden:
    data = json.loads(path.read_text())
    return AuditGolden(**data)
```

- [ ] **Step 3: 写 `test_audit_golden.py` — 拆分前后对比测试**

Create `tests/contract/test_audit_golden.py`。**复用已有 `test_pipeline_b_with_mock_pes_replay` 的 inline setup 模式**（monkeypatch + tmp_path + 手工 seed 而非 pytest fixtures）：

```python
"""P0 拆分的 golden 对比测试。

流程：
1. 首次跑：采集当前行为的 golden 到 tests/contract/golden/audit_case_01.json（skip）
2. 拆分后跑：与 golden 对比，要求 diff 为 0

注意：本测试只在 replay 模式下运行（确定性），不吃真 LLM。
实现参考 tests/contract/test_pipeline_b_with_mocks.py::test_pipeline_b_with_mock_pes_replay 的 inline setup。
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine

from govdoc.db.models import (
    AuditPointRun,
    AuditRun,
    CheckpointFinal,
    Project,
    TenderDoc,
)
from scrivai import FakeTrajectoryStore, TempWorkspaceManager
from govdoc.pipelines.audit_tender import run_audit
from tests.contract.golden.capture import capture, load_golden, write_golden
from tests.contract.test_pipeline_b_with_mocks import _write_test_config


GOLDEN_PATH = Path(__file__).parent / "golden" / "audit_case_01.json"


def test_audit_case_01_golden_match(monkeypatch, tmp_path):
    """跑 audit_case_01，采集结果，和 golden 对比。首次跑自动生成 golden（skip）。"""
    repo_root = Path(__file__).resolve().parents[2]
    fixtures_root = repo_root / "tests" / "fixtures"
    monkeypatch.setenv("GOVDOC_FIXTURES", str(fixtures_root))
    monkeypatch.setenv("GOVDOC_CONFIG_PATH", str(_write_test_config(tmp_path)))

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    checkpoints_payload = json.loads(
        (fixtures_root / "checkpoints_golden.json").read_text(encoding="utf-8")
    )["checkpoints"]

    with Session(engine) as session:
        project = Project(name="golden 测试项目", created_by="tester")
        session.add(project); session.commit(); session.refresh(project)

        tender_doc = TenderDoc(
            project_id=project.id,
            filename="tender_small.docx",
            storage_path="tests/fixtures/tender_small.docx",
            markdown_path=str(fixtures_root / "tender_small.md"),
            qmd_collection="test-tender-collection",
        )
        session.add(tender_doc); session.commit(); session.refresh(tender_doc)

        final_ids: list[str] = []
        for payload in checkpoints_payload:
            cf = CheckpointFinal(
                payload_json=json.dumps(payload, ensure_ascii=False),
                approved_by="tester",
            )
            session.add(cf); session.commit(); session.refresh(cf)
            final_ids.append(cf.id)

        audit_run = AuditRun(
            project_id=project.id,
            tender_doc_id=tender_doc.id,
            checkpoint_final_ids=json.dumps(final_ids, ensure_ascii=False),
            total_count=len(final_ids),
        )
        session.add(audit_run); session.commit(); session.refresh(audit_run)

        for cp_id in final_ids:
            session.add(AuditPointRun(audit_run_id=audit_run.id, checkpoint_final_id=cp_id))
        session.commit()

        result = asyncio.run(
            run_audit(
                audit_run.id,
                session,
                workspace_manager=TempWorkspaceManager(tmp_path / "workspaces"),
                trajectory_store=FakeTrajectoryStore(),
                replay_dir=fixtures_root / "mock_agent_trajectories" / "audit_case_01",
                project_root=repo_root,
                template_path=fixtures_root / "workpaper_template.docx",
            )
        )

        actual = capture(session, result.id)

    if not GOLDEN_PATH.exists():
        write_golden(actual, GOLDEN_PATH)
        pytest.skip(f"golden 首次生成于 {GOLDEN_PATH}，下次跑开始对比")

    expected = load_golden(GOLDEN_PATH)
    actual_dict = asdict(actual)
    expected_dict = asdict(expected)

    assert actual_dict == expected_dict, (
        f"golden 不匹配！\n"
        f"实际: {json.dumps(actual_dict, ensure_ascii=False, indent=2)[:500]}...\n"
        f"期望: {json.dumps(expected_dict, ensure_ascii=False, indent=2)[:500]}..."
    )
```

⚠️ **依赖确认**：
- `FakeTrajectoryStore` / `TempWorkspaceManager` 来自 `scrivai`（external，已在 `test_pipeline_a/b_with_mocks.py` 用过）
- `_write_test_config` 是 `tests/contract/test_pipeline_b_with_mocks.py` L19 的模块级函数，可直接 import

执行时若 `_write_test_config` 前缀下划线引发 lint 警告，可用 `from tests.contract.test_pipeline_b_with_mocks import _write_test_config  # noqa: F401`。

- [ ] **Step 4: 首次跑生成 golden baseline**

Run:
```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/contract/test_audit_golden.py -v
```

Expected: 首次 skip + 生成 `tests/contract/golden/audit_case_01.json`

- [ ] **Step 5: 再跑一次，应该对比成功**

Run:
```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/contract/test_audit_golden.py -v
```

Expected: PASS

- [ ] **Step 6: 提交 golden 基建**

```bash
git add tests/contract/golden/ tests/contract/test_audit_golden.py
git commit -m "test: 添加 P0 golden 采集与对比脚本（护栏 A）"
```

---

## Task 3: 抽取 `_index_tender_doc` helper

**Files:**
- Modify: `govdoc/pipelines/audit_tender.py`
- Modify: `tests/unit/test_audit_tender_helpers.py` (新建)

- [ ] **Step 1: 创建单元测试文件**

Create `tests/unit/test_audit_tender_helpers.py`:

```python
"""P0 拆分后 helper 函数的单元测试。

这些测试独立验证每个 helper 的行为，与集成测试配合提供双层护栏。
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# 导入将在 Task 3-7 中逐步可用
# from govdoc.pipelines.audit_tender import (
#     _index_tender_doc,
#     _resolve_point_runs,
#     _run_single_point,
#     _persist_point_result,
#     _cleanup_tender_collection,
#     _assemble_workpaper_draft,
# )
```

- [ ] **Step 2: 写 `_index_tender_doc` 的失败测试**

追加到 `tests/unit/test_audit_tender_helpers.py`:

```python
from govdoc.pipelines.audit_tender import _index_tender_doc  # 初次应 import 失败


def test_index_tender_doc_replay_mode_returns_placeholder():
    """replay 模式返回占位名，不触发真 qmd。"""
    audit_run = MagicMock(id="run_123")
    tender_doc = MagicMock()
    result = _index_tender_doc(audit_run, tender_doc, replay=True)
    assert result == "run_run_123_tender"


def test_index_tender_doc_non_replay_mode_calls_qmd():
    """非 replay 模式调用 qmd 索引（此处 mock），返回 collection 名。"""
    # 此测试需 monkeypatch 底层 qmd 客户端，见实际实现后补全
    pass
```

- [ ] **Step 3: 跑失败测试，确认 import 失败**

Run:
```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_audit_tender_helpers.py::test_index_tender_doc_replay_mode_returns_placeholder -v
```

Expected: FAIL（ImportError，因为 `_index_tender_doc` 未定义）

- [ ] **Step 4: 抽取 `_index_tender_doc` 到 `audit_tender.py`**

在 `govdoc/pipelines/audit_tender.py` 中 `def _ensure_tender_collection(...)` 之后（约 L175-200 区域）添加：

```python
def _index_tender_doc(
    audit_run: AuditRun,
    tender_doc: TenderDoc,
    *,
    replay: bool,
) -> str | None:
    """为本次 audit run 准备 qmd tender collection。

    - replay 模式：返回占位名，不触发 qmd（保持确定性）
    - 非 replay 模式：调用 _ensure_tender_collection 做真索引；失败时返回 None（允许降级）

    Args:
        audit_run: 当前 audit run 实例（需要 audit_run.id）
        tender_doc: 招标文书（需要其路径）
        replay: 是否 replay 模式

    Returns:
        tender collection 名，或 None（真索引失败时）
    """
    if replay:
        return f"run_{audit_run.id}_tender"
    try:
        return _ensure_tender_collection(audit_run.id, tender_doc)
    except Exception:
        return None
```

然后**修改 `run_audit` 原 L241-249**，把那段逻辑换成一行调用：

```python
# 原 L241-249 替换为：
tender_collection = _index_tender_doc(audit_run, tender_doc, replay=replay_dir is not None)
```

- [ ] **Step 5: 跑单测确认 helper 通过**

Run:
```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_audit_tender_helpers.py::test_index_tender_doc_replay_mode_returns_placeholder -v
```

Expected: PASS

- [ ] **Step 6: 跑集成测试确认整体仍通过**

Run:
```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/contract/test_pipeline_b_with_mocks.py::test_pipeline_b_with_mock_pes_replay tests/contract/test_audit_golden.py -v
```

Expected: 全绿（golden 对比通过）

- [ ] **Step 7: 提交**

```bash
git add govdoc/pipelines/audit_tender.py tests/unit/test_audit_tender_helpers.py
git commit -m "refactor: 抽取 _index_tender_doc helper"
```

---

## Task 4: 抽取 `_resolve_point_runs` helper

**Files:**
- Modify: `govdoc/pipelines/audit_tender.py`
- Modify: `tests/unit/test_audit_tender_helpers.py`

- [ ] **Step 1: 写单测**

追加到 `tests/unit/test_audit_tender_helpers.py`:

```python
from govdoc.pipelines.audit_tender import _resolve_point_runs


def test_resolve_point_runs_no_filter_returns_all_unfinished(session_with_point_runs):
    """不传 point_run_ids 时返回所有 status != completed 的 point_runs。"""
    # session_with_point_runs: 一个 pytest fixture，seed 3 个 point_runs（2 pending, 1 completed）
    audit_run = session_with_point_runs.audit_run
    runs = _resolve_point_runs(session_with_point_runs.session, audit_run, None)
    assert len(runs) == 2  # 只返回 2 个未完成的


def test_resolve_point_runs_with_filter_returns_only_selected(session_with_point_runs):
    """传入 point_run_ids 时只返回 intersect 部分。"""
    audit_run = session_with_point_runs.audit_run
    all_runs = session_with_point_runs.point_runs
    selected_id = all_runs[0].id
    runs = _resolve_point_runs(session_with_point_runs.session, audit_run, [selected_id])
    assert len(runs) == 1
    assert runs[0].id == selected_id
```

需要在 `tests/unit/conftest.py`（新建或复用）提供 `session_with_point_runs` fixture。

- [ ] **Step 2: 跑测试失败**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_audit_tender_helpers.py::test_resolve_point_runs_no_filter_returns_all_unfinished -v`
Expected: FAIL（ImportError 或 fixture 缺失）

- [ ] **Step 3: 抽取 helper**

在 `audit_tender.py` 中添加：

```python
def _resolve_point_runs(
    session: Session,
    audit_run: AuditRun,
    point_run_ids: Sequence[str] | None,
) -> list[AuditPointRun]:
    """查找本次 audit run 下所有 point_runs，应用 point_run_ids 过滤，跳过已 completed。

    Returns:
        待运行的 point_runs，按 created_at/id 稳定排序
    """
    point_runs = session.exec(
        select(AuditPointRun)
        .where(AuditPointRun.audit_run_id == audit_run.id)
        .order_by(AuditPointRun.created_at, AuditPointRun.id)
    ).all()
    selected = set(point_run_ids) if point_run_ids is not None else None
    return [
        pr for pr in point_runs
        if (selected is None or pr.id in selected) and pr.status != "completed"
    ]
```

修改 `run_audit`：把原 L223-227 的 query + L253-257 的过滤逻辑合并为一行：

```python
point_runs_to_run = _resolve_point_runs(session, audit_run, point_run_ids)
# 后续循环改为 for point_run in point_runs_to_run
```

注意 `audit_run.total_count = len(point_runs)` 这行要保留**原始 point_runs 总数**（不是过滤后的），所以内部仍需先查一次不过滤的总数 —— 或让 `_resolve_point_runs` 返回 `(total, to_run)` 元组。

**选 B 方案**：`_resolve_point_runs` 只返回"待运行的"，`audit_run.total_count` 在 `run_audit` 主体内另查一次，或直接信任原 `point_runs` 查询。

- [ ] **Step 4: 补 fixture 到 `tests/unit/conftest.py`（如不存在则新建）**

```python
import pytest
from dataclasses import dataclass
from sqlmodel import Session, create_engine, SQLModel
from govdoc.db.models import AuditRun, AuditPointRun, CheckpointFinal


@dataclass
class PointRunsBundle:
    session: Session
    audit_run: AuditRun
    point_runs: list[AuditPointRun]


@pytest.fixture
def session_with_point_runs() -> PointRunsBundle:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    # 按 SQLModel 定义创建最小 seed
    # TODO: 根据 models.py 实际必填字段填
    audit_run = AuditRun(
        id="ar_test",
        project_id="p_test",
        tender_doc_id="td_test",
        status="pending",
        total_count=0,
    )
    session.add(audit_run)
    session.commit()

    # 3 个 point_runs：2 pending, 1 completed
    # 注意：需要先建 CheckpointFinal 满足外键
    checkpoint_finals = [CheckpointFinal(id=f"cf_{i}", ...) for i in range(3)]  # 补齐字段
    for cf in checkpoint_finals:
        session.add(cf)
    session.commit()

    point_runs = [
        AuditPointRun(id="pr_0", audit_run_id="ar_test", checkpoint_final_id="cf_0", status="pending"),
        AuditPointRun(id="pr_1", audit_run_id="ar_test", checkpoint_final_id="cf_1", status="pending"),
        AuditPointRun(id="pr_2", audit_run_id="ar_test", checkpoint_final_id="cf_2", status="completed"),
    ]
    for pr in point_runs:
        session.add(pr)
    session.commit()

    return PointRunsBundle(session=session, audit_run=audit_run, point_runs=point_runs)
```

执行时按 `govdoc/db/models.py` 实际字段补齐 `CheckpointFinal` 与 `AuditPointRun` 的必填。

- [ ] **Step 5: 跑测试通过**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_audit_tender_helpers.py -v`
Expected: PASS

- [ ] **Step 6: 跑集成测试**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/ -v`
Expected: 全绿（golden 对比通过）

- [ ] **Step 7: 提交**

```bash
git add govdoc/pipelines/audit_tender.py tests/unit/
git commit -m "refactor: 抽取 _resolve_point_runs helper"
```

---

## Task 5-8: 抽取剩余 4 个 helper

对以下 4 个 helper 按**与 Task 3-4 相同的 5 步节奏**逐个抽取：

```
Task 5: _run_single_point          (搬原 L276-323)
Task 6: _persist_point_result      (搬原 L325-344)
Task 7: _cleanup_tender_collection (新增逻辑，非 replay 模式下在 finally 块清理)
Task 8: _assemble_workpaper_draft  (搬原 L367-403)
```

每个 helper 的抽取都遵循：

- [ ] 写 2-3 个单测
- [ ] 运行失败
- [ ] 实现 helper + 改 `run_audit` 调用点
- [ ] 单测通过
- [ ] 集成测试 + golden 对比通过
- [ ] 提交 `refactor: 抽取 <helper 名>`

**关键签名（供执行者参考）：**

```python
async def _run_single_point(
    point_run: AuditPointRun,
    checkpoint: GovCheckpoint,
    tender_doc: TenderDoc,
    *,
    audit_run: AuditRun,
    tender_collection: str | None,
    manager: Any,
    store: Any,
    cfg: Any,
    repo_root: Path,
    replay_dir: str | Path | None,
) -> tuple[Any | None, Any | None]:
    """运行单点 PES，返回 (workspace, result)。
    任一为 None 表示该点启动失败，调用方需处理 point_run.status 落地。
    """


def _persist_point_result(
    point_run: AuditPointRun,
    result: Any,
    workspace: Any,
    checkpoint: GovCheckpoint,
    manager: Any,
) -> None:
    """把 PES result 落到 point_run 字段。仅修改 point_run 对象，不提交 session。"""


def _cleanup_tender_collection(collection_id: str | None, *, replay: bool) -> None:
    """清理 qmd 临时 tender collection。
    - replay 模式：no-op
    - 非 replay 模式：best-effort 删除，异常静默（日志 warning）
    """


def _assemble_workpaper_draft(
    audit_run: AuditRun,
    session: Session,
    tender_doc: TenderDoc,
    template_path: str | Path | None,
) -> None:
    """按 completed point_runs 汇总 findings，生成 WorkpaperDraft，更新 audit_run.status。

    Status 分派规则（保持原 L399-403 行为）：
    - 所有 completed 且无 failed：draft_ready + 生成 WorkpaperDraft
    - 部分 completed：partial_ready
    - 全部 failed 或无 completed：waiting_retry
    """
```

---

## Task 9: 收敛 `run_audit` 为薄编排层

**Files:**
- Modify: `govdoc/pipelines/audit_tender.py`

- [ ] **Step 1: 重写 `run_audit` 主体**

把 `run_audit` 改写为纯编排（目标 ≤70 行不含 docstring/签名）：

```python
async def run_audit(
    audit_run_id: str,
    session: Session,
    *,
    workspace_manager: Any | None = None,
    trajectory_store: Any | None = None,
    replay_dir: str | Path | None = None,
    project_root: str | Path | None = None,
    template_path: str | Path | None = None,
    point_run_ids: Sequence[str] | None = None,
) -> AuditRun:
    """管道 B 入口：审核点 + 招标文书 → 工作底稿。

    编排层，所有重活委托给 helper。见本模块同名 _* 函数。
    """
    audit_run = session.get(AuditRun, audit_run_id)
    if audit_run is None:
        raise ValueError(f"未找到 AuditRun: {audit_run_id}")
    tender_doc = session.get(TenderDoc, audit_run.tender_doc_id)
    if tender_doc is None:
        raise ValueError(f"未找到 TenderDoc: {audit_run.tender_doc_id}")

    manager = workspace_manager or get_workspace_manager()
    store = trajectory_store or get_trajectory_store()
    repo_root = Path(project_root).expanduser().resolve() if project_root else get_project_root()
    cfg = get_config()
    is_replay = replay_dir is not None

    audit_run.status = "running"
    audit_run.total_count = len(session.exec(
        select(AuditPointRun).where(AuditPointRun.audit_run_id == audit_run.id)
    ).all())
    session.add(audit_run); session.commit(); session.refresh(audit_run)

    tender_collection = _index_tender_doc(audit_run, tender_doc, replay=is_replay)
    point_runs_to_run = _resolve_point_runs(session, audit_run, point_run_ids)

    try:
        for point_run in point_runs_to_run:
            checkpoint_row = session.get(CheckpointFinal, point_run.checkpoint_final_id)
            if checkpoint_row is None:
                point_run.status = "failed"
                point_run.error = f"未找到 CheckpointFinal: {point_run.checkpoint_final_id}"
                session.add(point_run); session.commit()
                continue

            checkpoint = GovCheckpoint.model_validate_json(checkpoint_row.payload_json)
            point_run.status = "running"
            session.add(point_run); session.commit()

            try:
                workspace, result = await _run_single_point(
                    point_run, checkpoint, tender_doc,
                    audit_run=audit_run,
                    tender_collection=tender_collection,
                    manager=manager, store=store, cfg=cfg,
                    repo_root=repo_root, replay_dir=replay_dir,
                )
                _persist_point_result(point_run, result, workspace, checkpoint, manager)
            except Exception as exc:
                point_run.status = "failed"
                point_run.error = str(exc)

            audit_run.processed_count = count_processed_points(session, audit_run.id)
            session.add(point_run); session.add(audit_run); session.commit()

        _assemble_workpaper_draft(audit_run, session, tender_doc, template_path)
        session.add(audit_run); session.commit(); session.refresh(audit_run)
        return audit_run

    except Exception as exc:
        audit_run.status = "failed"
        audit_run.error = str(exc)
        session.add(audit_run); session.commit()
        raise
    finally:
        _cleanup_tender_collection(tender_collection, replay=is_replay)
```

- [ ] **Step 2: 验证行数 ≤70**

Run:
```bash
awk '/^async def run_audit/,/^async def retry_point_run/' govdoc/pipelines/audit_tender.py | wc -l
```

Expected: ≤70（不含 docstring 可适当放宽；spec 要求 ≤70 是硬指标）

- [ ] **Step 3: 跑全部测试**

Run:
```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/ -v
```

Expected: 全绿（含 golden 对比）

- [ ] **Step 4: 提交**

```bash
git add govdoc/pipelines/audit_tender.py
git commit -m "refactor: 收敛 run_audit 为薄编排层（≤70 行）"
```

---

## Task 10: 最终验收 + PR

- [ ] **Step 1: 跑 ruff**

Run:
```bash
conda run -n govdoc-auditor-v3 ruff check govdoc/pipelines/audit_tender.py tests/
conda run -n govdoc-auditor-v3 ruff format --check govdoc/pipelines/audit_tender.py tests/
```

Expected: 零 warning、无格式差异

- [ ] **Step 2: 跑全量测试**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/ -v`
Expected: 全绿

- [ ] **Step 3: 推到远端 + 开 PR**

```bash
git push -u origin feat/p0-run-audit-split
```

PR 目标分支：`feat/tech-debt-cleanup`（umbrella），不是 master。

PR 描述模板：
```
## 目的
P0 · 把 run_audit（214 行单函数）拆成薄编排层 + 5 个 helper。

## 护栏
- 扩充 `test_pipeline_b_with_mock_pes_replay` 的 6 类终态断言
- 新增 `test_audit_golden.py`：拆分前采集 baseline，拆分后对比零 diff

## 变更文件
- `govdoc/pipelines/audit_tender.py` — run_audit 重构
- `tests/contract/test_pipeline_b_with_mocks.py` — 扩断言
- `tests/contract/test_audit_golden.py` — 新增 golden 对比
- `tests/contract/golden/capture.py` — 采集脚本
- `tests/unit/test_audit_tender_helpers.py` — helper 单测

## DoD
- [x] 集成测试 6 类终态断言全绿
- [x] golden 对比零 diff
- [x] run_audit ≤ 70 行
- [x] ruff check 零新增 warning

## 不变式
I1 行为不变：由 golden 对比保证
I2 测试先行：commit history 证明
I3 独立可回滚：见 umbrella plan 的回滚演练
I4 契约零扩张：diff 不含 routes/models/schemas 修改
```

- [ ] **Step 4: Merge 到 umbrella（由用户/PR review 触发）**

当 CI 绿且 review 通过：
```bash
git checkout feat/tech-debt-cleanup
git merge --no-ff feat/p0-run-audit-split -m "Merge P0 · run_audit 拆分"
```

- [ ] **Step 5: 执行回滚演练**

按 umbrella index plan §"回滚演练"章节执行 6 步演练。

---

## P0 DoD 汇总（合入 umbrella 前必须全打勾）

- [ ] 集成测试 6 类终态断言全绿
- [ ] golden 对比脚本运行零 diff
- [ ] `run_audit` ≤ 70 行（不含 docstring/签名）
- [ ] `ruff check` 零新增 warning
- [ ] 单元测试覆盖 5 个新 helper
- [ ] Commit history 清晰：`test:` 先、`refactor:` 后
- [ ] PR 描述填写完整
- [ ] 回滚演练通过
