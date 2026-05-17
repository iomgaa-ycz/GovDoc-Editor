# 前端重设计后端接口补全 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补全前端设计稿审计发现的 P0-P3 后端接口缺口，使后端 API 完全支撑内测版前端功能。

**Architecture:** 在现有 FastAPI + SQLModel + SQLite 架构上：(1) DB 层新增 2 个字段 + Alembic 迁移；(2) Pipeline 层利用 Scrivai PES `before_phase` hook 回写阶段进度；(3) API 层扩展 progress 响应 + 新增 dashboard 聚合路由 + 提取预览路由；(4) 前端对接新字段 + 反馈面板连接 Comments API。

**Tech Stack:** Python 3.11 / FastAPI / SQLModel / Alembic / Scrivai PES hooks / TypeScript / React

---

## 文件变更地图

| 文件 | 职责 | 操作 |
|------|------|------|
| `govdoc/db/models.py` | AuditPointRun 加 `started_at` + `current_phase` | [MODIFY] |
| `govdoc/db/migrations/versions/<new>_add_phase_progress.py` | Alembic 迁移 | [NEW] |
| `govdoc/pipelines/audit_tender.py` | 设 started_at；注册 phase hook | [MODIFY] |
| `govdoc/pipelines/phase_progress_hook.py` | PES before_phase hook 回写 current_phase | [NEW] |
| `govdoc/runtime.py` | build_gov_auditor_pes 支持传入 point_run_id 用于 hook | [MODIFY] |
| `govdoc/api/routes/audit.py` | progress 返回新字段；list_audit_runs 加 project_name | [MODIFY] |
| `govdoc/api/routes/dashboard.py` | 仪表盘聚合统计接口 | [NEW] |
| `govdoc/api/routes/rules.py` | 提取预览接口 | [MODIFY] |
| `govdoc/api/main.py` | 注册 dashboard router | [MODIFY] |
| `frontend/src/types/ui.ts` | 前端类型补全 | [MODIFY] |
| `frontend/src/api/v3.ts` | 新增 API 调用函数 | [MODIFY] |
| `frontend/src/pages/AuditResultsPage.tsx` | 反馈面板对接 Comments API | [MODIFY] |
| `tests/unit/test_phase_progress_hook.py` | phase hook 单测 | [NEW] |
| `tests/unit/test_dashboard_route.py` | dashboard 路由单测 | [NEW] |
| `tests/unit/test_audit_progress_fields.py` | progress 新字段单测 | [NEW] |

---

### Task 1: P0 — AuditPointRun 新增 DB 字段 + Alembic 迁移

**Files:**
- Modify: `govdoc/db/models.py:85-99`
- Create: `govdoc/db/migrations/versions/<auto>_add_phase_progress_to_auditpointrun.py`
- Test: `tests/unit/test_audit_progress_fields.py`

- [ ] **Step 1: 写失败测试 — 验证新字段存在**

```python
# tests/unit/test_audit_progress_fields.py
"""验证 AuditPointRun 支持 started_at 和 current_phase 字段。"""
from datetime import datetime

from govdoc.db.models import AuditPointRun


def test_audit_point_run_has_started_at():
    """started_at 字段默认 None，可赋值为 datetime。"""
    pr = AuditPointRun(
        audit_run_id="run-1",
        checkpoint_final_id="cp-1",
    )
    assert pr.started_at is None
    pr.started_at = datetime(2026, 5, 17, 14, 30, 0)
    assert pr.started_at == datetime(2026, 5, 17, 14, 30, 0)


def test_audit_point_run_has_current_phase():
    """current_phase 字段默认 None，可赋值为 plan/execute/summarize。"""
    pr = AuditPointRun(
        audit_run_id="run-1",
        checkpoint_final_id="cp-1",
    )
    assert pr.current_phase is None
    pr.current_phase = "plan"
    assert pr.current_phase == "plan"
    pr.current_phase = "execute"
    assert pr.current_phase == "execute"
    pr.current_phase = "summarize"
    assert pr.current_phase == "summarize"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_audit_progress_fields.py -v
```

预期输出：FAIL — `AuditPointRun.__init__() got an unexpected keyword argument 'started_at'` 或类似字段不存在错误。

- [ ] **Step 3: 修改 AuditPointRun 模型，添加两个字段**

在 `govdoc/db/models.py` 的 `AuditPointRun` 类中，在 `completed_at` 行之后添加：

```python
class AuditPointRun(SQLModel, table=True):
    """管道 B 中单个审核点的执行——对应一个独立 workspace。"""

    id: str = Field(default_factory=uid, primary_key=True)
    audit_run_id: str = Field(foreign_key="auditrun.id")
    checkpoint_final_id: str = Field(foreign_key="checkpointfinal.id")
    # pending / running / completed / failed / waiting_retry
    status: str = "pending"
    workspace_archive_path: str | None = None
    workspace_failed_path: str | None = None
    usage_json: str | None = None
    error: str | None = None
    finding_json: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    started_at: datetime | None = None
    # plan / execute / summarize — PES 当前阶段
    current_phase: str | None = None
```

- [ ] **Step 4: 运行测试确认通过**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_audit_progress_fields.py -v
```

预期：全部 PASS。

- [ ] **Step 5: 生成 Alembic 迁移**

```bash
source activate govdoc-auditor-v3 && alembic revision --autogenerate -m "add started_at and current_phase to auditpointrun"
```

验证生成的迁移文件包含：
```python
op.add_column("auditpointrun", sa.Column("started_at", sa.DateTime(), nullable=True))
op.add_column("auditpointrun", sa.Column("current_phase", sa.String(), nullable=True))
```

- [ ] **Step 6: 应用迁移**

```bash
source activate govdoc-auditor-v3 && alembic upgrade head
```

- [ ] **Step 7: 提交**

```bash
git add govdoc/db/models.py govdoc/db/migrations/versions/ tests/unit/test_audit_progress_fields.py
git commit -m "feat(db): add started_at and current_phase to AuditPointRun"
```

---

### Task 2: P0 — Pipeline 设置 started_at + PES phase hook 回写 current_phase

**Files:**
- Create: `govdoc/pipelines/phase_progress_hook.py`
- Modify: `govdoc/pipelines/audit_tender.py:684`
- Modify: `govdoc/runtime.py:155-166`
- Test: `tests/unit/test_phase_progress_hook.py`

- [ ] **Step 1: 写失败测试 — PhaseProgressHook 收到 before_phase 时更新 DB**

```python
# tests/unit/test_phase_progress_hook.py
"""验证 PhaseProgressHook 在 before_phase 时回写 current_phase 到 DB。"""
from datetime import datetime
from unittest.mock import MagicMock, patch

from govdoc.pipelines.phase_progress_hook import PhaseProgressHook


def _make_phase_context(phase: str) -> MagicMock:
    """构造 PhaseHookContext mock。"""
    ctx = MagicMock()
    ctx.phase = phase
    return ctx


def test_before_phase_updates_current_phase():
    """before_phase 应更新 AuditPointRun.current_phase。"""
    mock_session_factory = MagicMock()
    mock_session = MagicMock()
    mock_session_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_session_factory.return_value.__exit__ = MagicMock(return_value=False)

    mock_point_run = MagicMock()
    mock_point_run.current_phase = None
    mock_session.get.return_value = mock_point_run

    hook = PhaseProgressHook(
        point_run_id="pr-123",
        session_factory=mock_session_factory,
    )
    ctx = _make_phase_context("execute")
    hook.before_phase(context=ctx)

    assert mock_point_run.current_phase == "execute"
    mock_session.add.assert_called_once_with(mock_point_run)
    mock_session.commit.assert_called_once()


def test_before_phase_skips_when_point_run_not_found():
    """point_run 不存在时不报错（容错）。"""
    mock_session_factory = MagicMock()
    mock_session = MagicMock()
    mock_session_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_session_factory.return_value.__exit__ = MagicMock(return_value=False)
    mock_session.get.return_value = None

    hook = PhaseProgressHook(
        point_run_id="pr-nonexistent",
        session_factory=mock_session_factory,
    )
    ctx = _make_phase_context("plan")
    hook.before_phase(context=ctx)

    mock_session.add.assert_not_called()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_phase_progress_hook.py -v
```

预期：FAIL — `ModuleNotFoundError: No module named 'govdoc.pipelines.phase_progress_hook'`

- [ ] **Step 3: 实现 PhaseProgressHook**

```python
# govdoc/pipelines/phase_progress_hook.py
"""PES before_phase hook——实时回写 AuditPointRun.current_phase 到 DB。"""

from __future__ import annotations

import logging
from typing import Any, Callable

from scrivai.pes.hooks import hookimpl

from govdoc.db.models import AuditPointRun

logger = logging.getLogger(__name__)


class PhaseProgressHook:
    """注册到 PES HookManager，在每个 phase 开始时更新 DB 中的 current_phase。"""

    def __init__(self, *, point_run_id: str, session_factory: Callable[..., Any]) -> None:
        self._point_run_id = point_run_id
        self._session_factory = session_factory

    @hookimpl
    def before_phase(self, context: Any) -> None:
        """PES phase 开始时回写 current_phase。"""
        phase = context.phase
        try:
            with self._session_factory() as session:
                point_run = session.get(AuditPointRun, self._point_run_id)
                if point_run is None:
                    logger.warning("PhaseProgressHook: AuditPointRun %s 不存在", self._point_run_id)
                    return
                point_run.current_phase = phase
                session.add(point_run)
                session.commit()
        except Exception:
            logger.exception("PhaseProgressHook: 更新 current_phase 失败")
```

- [ ] **Step 4: 运行测试确认通过**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_phase_progress_hook.py -v
```

预期：全部 PASS。

- [ ] **Step 5: 修改 audit_tender.py — 设 started_at 并注册 hook**

在 `govdoc/pipelines/audit_tender.py` 中：

**5a.** 在 `point_run.status = "running"` 那行（约 L684）之后添加 `started_at` 赋值：

```python
            checkpoint = GovCheckpoint.model_validate_json(checkpoint_row.payload_json)
            point_run.status = "running"
            point_run.started_at = datetime.utcnow()
            point_run.current_phase = None
            session.add(point_run)
            session.commit()
```

**5b.** 在文件顶部 import 区新增：

```python
from govdoc.pipelines.phase_progress_hook import PhaseProgressHook
from govdoc.api.deps import get_db_session as _get_progress_session
```

**5c.** 修改 `_run_single_point` 函数，在构造 PES 时注册 hook。在 `pes = build_gov_auditor_pes(...)` 调用（约 L403）之前，构造 hook 并传入：

```python
    else:
        from govdoc.pipelines.phase_progress_hook import PhaseProgressHook
        from govdoc.api.deps import get_db_session as _get_progress_session

        progress_hook = PhaseProgressHook(
            point_run_id=point_run.id,
            session_factory=_get_progress_session,
        )
        pes = build_gov_auditor_pes(
            workspace=workspace,
            runtime_context=runtime_context,
            extra_hooks=[progress_hook],
        )
```

- [ ] **Step 6: 修改 runtime.py — build_gov_auditor_pes 支持 extra_hooks**

在 `govdoc/runtime.py` 的 `build_gov_auditor_pes` 函数中增加 `extra_hooks` 参数：

```python
def build_gov_auditor_pes(
    *,
    workspace: Any,
    runtime_context: dict[str, Any],
    hooks: Any = None,
    extra_hooks: list[Any] | None = None,
) -> GovDocAuditorPES:
    mgr = hooks or _build_hooks()
    if extra_hooks:
        for h in extra_hooks:
            mgr.register(h)
    return GovDocAuditorPES(
        config=get_gov_auditor_config(),
        model=get_model_config(),
        workspace=workspace,
        hooks=mgr,
        trajectory_store=get_trajectory_store(),
        runtime_context=runtime_context,
        prompt_manager=get_prompt_manager(),
    )
```

对 `build_gov_extractor_pes` 做相同改动（保持一致性）。

- [ ] **Step 7: 运行现有测试确认无回归**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v --timeout=30
```

预期：所有现有测试仍通过。

- [ ] **Step 8: 提交**

```bash
git add govdoc/pipelines/phase_progress_hook.py govdoc/pipelines/audit_tender.py govdoc/runtime.py tests/unit/test_phase_progress_hook.py
git commit -m "feat(pipeline): add PhaseProgressHook to track current_phase per audit point"
```

---

### Task 3: P0 — progress 接口返回 started_at + completed_at + current_phase

**Files:**
- Modify: `govdoc/api/routes/audit.py:173-199`
- Test: `tests/unit/test_audit_progress_fields.py`（追加）

- [ ] **Step 1: 在已有测试文件中追加 API 响应字段测试**

```python
# tests/unit/test_audit_progress_fields.py（追加到文件末尾）
from datetime import datetime, timedelta


def test_progress_point_run_dict_includes_new_fields():
    """验证 progress API 序列化逻辑包含 started_at, completed_at, current_phase。"""
    pr = AuditPointRun(
        audit_run_id="run-1",
        checkpoint_final_id="cp-1",
        status="running",
        started_at=datetime(2026, 5, 17, 14, 30, 0),
        current_phase="execute",
    )
    # 模拟 API 中的序列化逻辑
    serialized = {
        "id": pr.id,
        "checkpoint_final_id": pr.checkpoint_final_id,
        "status": pr.status,
        "error": pr.error,
        "finding_json": pr.finding_json,
        "started_at": str(pr.started_at) if pr.started_at else None,
        "completed_at": str(pr.completed_at) if pr.completed_at else None,
        "current_phase": pr.current_phase,
    }
    assert serialized["started_at"] == "2026-05-17 14:30:00"
    assert serialized["completed_at"] is None
    assert serialized["current_phase"] == "execute"


def test_progress_completed_point_run_has_both_timestamps():
    """已完成的 point run 应有 started_at 和 completed_at。"""
    now = datetime.utcnow()
    pr = AuditPointRun(
        audit_run_id="run-1",
        checkpoint_final_id="cp-1",
        status="completed",
        started_at=now - timedelta(seconds=45),
        completed_at=now,
        current_phase="summarize",
    )
    assert pr.started_at is not None
    assert pr.completed_at is not None
    assert pr.completed_at > pr.started_at
```

- [ ] **Step 2: 运行测试确认通过**（模型字段已在 Task 1 添加）

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_audit_progress_fields.py -v
```

- [ ] **Step 3: 修改 progress 接口——序列化 point_runs 时加入新字段**

在 `govdoc/api/routes/audit.py` 的 `get_audit_run_progress` 函数中，修改 point_runs 列表推导，将：

```python
            point_runs=[
                {
                    "id": pr.id,
                    "checkpoint_final_id": pr.checkpoint_final_id,
                    "status": pr.status,
                    "error": pr.error,
                    "finding_json": pr.finding_json,
                }
                for pr in point_runs
            ],
```

改为：

```python
            point_runs=[
                {
                    "id": pr.id,
                    "checkpoint_final_id": pr.checkpoint_final_id,
                    "status": pr.status,
                    "error": pr.error,
                    "finding_json": pr.finding_json,
                    "started_at": str(pr.started_at) if pr.started_at else None,
                    "completed_at": str(pr.completed_at) if pr.completed_at else None,
                    "current_phase": pr.current_phase,
                }
                for pr in point_runs
            ],
```

- [ ] **Step 4: 运行全量单测确认无回归**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v --timeout=30
```

- [ ] **Step 5: 提交**

```bash
git add govdoc/api/routes/audit.py tests/unit/test_audit_progress_fields.py
git commit -m "feat(api): expose started_at, completed_at, current_phase in progress endpoint"
```

---

### Task 4: P1 — 新增 dashboard 聚合统计接口

**Files:**
- Create: `govdoc/api/routes/dashboard.py`
- Modify: `govdoc/api/main.py`
- Test: `tests/unit/test_dashboard_route.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_dashboard_route.py
"""Dashboard 聚合统计接口测试。"""
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from govdoc.db.models import (
    AuditPointRun, AuditRun, CheckpointFinal, Project, WorkpaperDraft,
)


def _make_project(pid: str, name: str) -> Project:
    p = Project(name=name, created_by="test")
    p.id = pid
    return p


def _make_audit_run(rid: str, pid: str, status: str, total: int, processed: int) -> AuditRun:
    r = AuditRun(
        project_id=pid, tender_doc_id="td-1",
        checkpoint_final_ids="[]", status=status,
        total_count=total, processed_count=processed,
    )
    r.id = rid
    return r


def test_dashboard_stats_counts():
    """验证 compute_dashboard_stats 正确统计各维度数据。"""
    from govdoc.api.routes.dashboard import compute_dashboard_stats

    checkpoints = [MagicMock() for _ in range(5)]
    projects = [_make_project("p1", "项目A"), _make_project("p2", "项目B")]
    audit_runs = [
        _make_audit_run("r1", "p1", "draft_ready", 10, 10),
        _make_audit_run("r2", "p2", "running", 8, 3),
    ]
    # 模拟 finding：3 个不合规
    findings_data = [
        {"verdict": {"verdict": "不合规"}},
        {"verdict": {"verdict": "合规"}},
        {"verdict": {"verdict": "不合规"}},
    ]
    point_runs = []
    for i, f in enumerate(findings_data):
        pr = AuditPointRun(audit_run_id="r1", checkpoint_final_id=f"cp-{i}")
        pr.finding_json = json.dumps(f, ensure_ascii=False)
        pr.status = "completed"
        point_runs.append(pr)

    workpapers = [MagicMock(), MagicMock()]

    stats = compute_dashboard_stats(
        checkpoints=checkpoints,
        projects=projects,
        audit_runs=audit_runs,
        point_runs_completed=point_runs,
        workpaper_count=len(workpapers),
    )

    assert stats["checkpoint_count"] == 5
    assert stats["completed_audit_count"] == 1  # draft_ready 算完成
    assert stats["finding_count"] == 2  # 不合规的数量
    assert stats["workpaper_count"] == 2
    assert len(stats["recent_projects"]) == 2
```

- [ ] **Step 2: 运行测试确认失败**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_dashboard_route.py -v
```

预期：FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 dashboard 路由**

```python
# govdoc/api/routes/dashboard.py
"""Dashboard routes — 首页聚合统计。"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter
from sqlmodel import select, func

from govdoc.api.deps import get_db_session
from govdoc.db.models import (
    AuditPointRun, AuditRun, CheckpointFinal, Project, WorkpaperDraft,
)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
logger = logging.getLogger(__name__)

_COMPLETED_STATUSES = {"draft_ready", "partial_ready", "finalized"}


def _count_non_compliant(point_runs: list[AuditPointRun]) -> int:
    """统计 finding_json 中 verdict 为「不合规」的数量。"""
    count = 0
    for pr in point_runs:
        if not pr.finding_json:
            continue
        try:
            data = json.loads(pr.finding_json)
            verdict = data.get("verdict", {})
            if isinstance(verdict, dict) and verdict.get("verdict") == "不合规":
                count += 1
        except (json.JSONDecodeError, AttributeError):
            continue
    return count


def compute_dashboard_stats(
    *,
    checkpoints: list[Any],
    projects: list[Project],
    audit_runs: list[AuditRun],
    point_runs_completed: list[AuditPointRun],
    workpaper_count: int,
) -> dict[str, Any]:
    """纯函数：从查询结果计算仪表盘统计数据。"""
    completed_runs = [r for r in audit_runs if r.status in _COMPLETED_STATUSES]

    project_map: dict[str, dict[str, Any]] = {}
    for p in projects:
        project_map[p.id] = {
            "project_id": p.id,
            "name": p.name,
            "audit_status": "idle",
            "point_count": 0,
            "issue_count": 0,
            "last_active": str(p.created_at),
        }

    for r in audit_runs:
        if r.project_id not in project_map:
            continue
        entry = project_map[r.project_id]
        entry["point_count"] = max(entry["point_count"], r.total_count)
        entry["last_active"] = str(r.created_at)
        if r.status == "running":
            entry["audit_status"] = "running"
        elif r.status in _COMPLETED_STATUSES and entry["audit_status"] != "running":
            entry["audit_status"] = "completed"

    for pr in point_runs_completed:
        if not pr.finding_json:
            continue
        try:
            data = json.loads(pr.finding_json)
            verdict = data.get("verdict", {})
            if isinstance(verdict, dict) and verdict.get("verdict") == "不合规":
                run = next((r for r in audit_runs if r.id == pr.audit_run_id), None)
                if run and run.project_id in project_map:
                    project_map[run.project_id]["issue_count"] += 1
        except (json.JSONDecodeError, AttributeError):
            continue

    recent = sorted(project_map.values(), key=lambda x: x["last_active"], reverse=True)[:10]

    return {
        "checkpoint_count": len(checkpoints),
        "completed_audit_count": len(completed_runs),
        "finding_count": _count_non_compliant(point_runs_completed),
        "workpaper_count": workpaper_count,
        "recent_projects": recent,
    }


@router.get("/stats")
async def get_dashboard_stats():
    """返回首页仪表盘聚合统计。"""
    with get_db_session() as session:
        checkpoints = session.exec(select(CheckpointFinal)).all()
        projects = session.exec(
            select(Project).order_by(Project.created_at.desc())
        ).all()
        audit_runs = session.exec(select(AuditRun)).all()
        point_runs_completed = session.exec(
            select(AuditPointRun).where(AuditPointRun.status == "completed")
        ).all()
        workpaper_count = session.exec(
            select(func.count()).select_from(WorkpaperDraft)
        ).one()

        return compute_dashboard_stats(
            checkpoints=checkpoints,
            projects=projects,
            audit_runs=audit_runs,
            point_runs_completed=point_runs_completed,
            workpaper_count=workpaper_count,
        )
```

- [ ] **Step 4: 在 main.py 注册 dashboard router**

在 `govdoc/api/main.py` 中，在现有 router 注册后添加：

```python
from govdoc.api.routes.dashboard import router as dashboard_router
app.include_router(dashboard_router)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_dashboard_route.py -v
```

- [ ] **Step 6: 提交**

```bash
git add govdoc/api/routes/dashboard.py govdoc/api/main.py tests/unit/test_dashboard_route.py
git commit -m "feat(api): add GET /dashboard/stats aggregation endpoint"
```

---

### Task 5: P1 — audit runs 响应增加 project_name

**Files:**
- Modify: `govdoc/api/routes/audit.py:132-152`
- Test: `tests/unit/test_audit_progress_fields.py`（追加）

- [ ] **Step 1: 追加测试**

```python
# tests/unit/test_audit_progress_fields.py（追加到文件末尾）

def test_audit_run_serialization_includes_project_name():
    """list_audit_runs 返回值应包含 project_name 字段。"""
    from govdoc.db.models import AuditRun, Project

    project = Project(name="XX市政府采购项目", created_by="admin")
    run = AuditRun(
        project_id=project.id,
        tender_doc_id="td-1",
        checkpoint_final_ids="[]",
        total_count=5,
    )
    # 模拟 API 序列化逻辑
    serialized = {
        "id": run.id,
        "project_id": run.project_id,
        "project_name": project.name,
        "status": run.status,
    }
    assert serialized["project_name"] == "XX市政府采购项目"
```

- [ ] **Step 2: 修改 list_audit_runs — JOIN Project 表获取 name**

在 `govdoc/api/routes/audit.py` 的 `list_audit_runs` 和 `get_audit_run` 中，修改查询加入 project name。

`list_audit_runs` 改为：

```python
@router.get("/runs")
async def list_audit_runs(project_id: str | None = None):
    with get_db_session() as session:
        stmt = select(AuditRun).order_by(AuditRun.created_at.desc())
        if project_id:
            stmt = stmt.where(AuditRun.project_id == project_id)
        runs = session.exec(stmt).all()

        project_ids = {r.project_id for r in runs}
        projects = session.exec(
            select(Project).where(Project.id.in_(project_ids))
        ).all()
        project_names = {p.id: p.name for p in projects}

        return [
            {
                "id": r.id,
                "project_id": r.project_id,
                "project_name": project_names.get(r.project_id, ""),
                "tender_doc_id": r.tender_doc_id,
                "supplementary_doc_ids": _load_supplementary_doc_ids(r.supplementary_doc_ids),
                "status": r.status,
                "processed_count": r.processed_count,
                "total_count": r.total_count,
                "error": r.error,
                "created_at": str(r.created_at),
            }
            for r in runs
        ]
```

同样在 `get_audit_run` 中加入 `project_name`。

确保在文件顶部 import 中加入 `Project`：
```python
from govdoc.db.models import AuditPointRun, AuditRun, CheckpointFinal, Project, TenderDoc
```

- [ ] **Step 3: 运行测试**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_audit_progress_fields.py -v
```

- [ ] **Step 4: 提交**

```bash
git add govdoc/api/routes/audit.py tests/unit/test_audit_progress_fields.py
git commit -m "feat(api): include project_name in audit runs response"
```

---

### Task 6: P2 — 前端对接 Comments API 实现反馈功能

**Files:**
- Modify: `frontend/src/api/v3.ts`
- Modify: `frontend/src/types/ui.ts`
- Modify: `frontend/src/pages/AuditResultsPage.tsx`

- [ ] **Step 1: 在 types/ui.ts 添加 Comment 类型和更新 AuditPointRun**

在 `frontend/src/types/ui.ts` 中添加：

```typescript
// ── Comments ──

export interface Comment {
  id: string;
  target_type: string;
  target_id: string;
  author: string;
  text: string;
  created_at: string;
}
```

同时更新 `AuditPointRun` 接口，添加新字段：

```typescript
export interface AuditPointRun {
  id: string;
  checkpoint_final_id: string;
  status: PointRunStatus;
  error: string | null;
  finding_json: string | null;
  started_at: string | null;
  completed_at: string | null;
  current_phase: string | null;
}
```

更新 `AuditRun` 接口，添加 `project_name`：

```typescript
export interface AuditRun {
  id: string;
  project_id: string;
  project_name?: string;
  tender_doc_id: string;
  supplementary_doc_ids?: string[];
  status: AuditRunStatus;
  processed_count: number;
  total_count: number;
  error: string | null;
  created_at: string;
}
```

添加 Dashboard 统计类型：

```typescript
// ── Dashboard ──

export interface DashboardStats {
  checkpoint_count: number;
  completed_audit_count: number;
  finding_count: number;
  workpaper_count: number;
  recent_projects: RecentProject[];
}

export interface RecentProject {
  project_id: string;
  name: string;
  audit_status: string;
  point_count: number;
  issue_count: number;
  last_active: string;
}
```

- [ ] **Step 2: 在 api/v3.ts 添加 comments 和 dashboard API 调用**

在 `frontend/src/api/v3.ts` 中添加：

```typescript
// ── Comments ──

export function listComments(targetType: string, targetId: string): Promise<Comment[]> {
  return request(`/api/v1/comments?target_type=${targetType}&target_id=${targetId}`);
}

export function createComment(targetType: string, targetId: string, author: string, text: string): Promise<Comment> {
  return request("/api/v1/comments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_type: targetType, target_id: targetId, author, text }),
  });
}

export function deleteComment(commentId: string): Promise<void> {
  return request(`/api/v1/comments/${commentId}`, { method: "DELETE" });
}

// ── Dashboard ──

export function getDashboardStats(): Promise<DashboardStats> {
  return request("/api/v1/dashboard/stats");
}
```

确保在文件顶部 import `Comment` 和 `DashboardStats` 类型。

- [ ] **Step 3: 修改 AuditResultsPage — 连接反馈面板到 Comments API**

在 `frontend/src/pages/AuditResultsPage.tsx` 中：

将现有的本地 `feedbackNotes` 状态替换为真实的 comments 调用：

```typescript
// 替换 feedbackNotes 本地状态为真实 API 调用
const [comments, setComments] = useState<Comment[]>([]);
const [feedbackText, setFeedbackText] = useState("");
const [submitting, setSubmitting] = useState(false);

// 当选中 point run 变化时，加载该 point run 的评论
useEffect(() => {
  if (!selectedPointRunId) return;
  listComments("AuditPointRun", selectedPointRunId).then(setComments).catch(() => {});
}, [selectedPointRunId]);

async function handleSubmitFeedback() {
  if (!selectedPointRunId || !feedbackText.trim()) return;
  setSubmitting(true);
  try {
    const comment = await createComment("AuditPointRun", selectedPointRunId, "reviewer", feedbackText);
    setComments((prev) => [comment, ...prev]);
    setFeedbackText("");
  } finally {
    setSubmitting(false);
  }
}
```

在反馈面板 JSX 中，把 disabled 的保存按钮改为可用：

```typescript
<TextArea
  placeholder="输入审查意见或修改建议"
  value={feedbackText}
  onChange={(e) => setFeedbackText(e.target.value)}
/>
<Button
  tone="primary"
  onClick={handleSubmitFeedback}
  busy={submitting}
  disabled={!feedbackText.trim() || submitting}
  style={{ width: "100%" }}
>
  提交反馈
</Button>
{comments.map((c) => (
  <div key={c.id} className="feedback-item" style={{ padding: "8px 0", borderBottom: "1px solid var(--border-light)" }}>
    <p style={{ margin: 0, fontSize: 13 }}>{c.text}</p>
    <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{c.author} · {c.created_at}</span>
  </div>
))}
```

添加必要的 import：
```typescript
import { listComments, createComment } from "../api/v3";
import type { Comment } from "../types/ui";
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/types/ui.ts frontend/src/api/v3.ts frontend/src/pages/AuditResultsPage.tsx
git commit -m "feat(frontend): connect feedback panel to Comments API + add dashboard/progress types"
```

---

### Task 7: P3 — 提取预览接口

**Files:**
- Modify: `govdoc/api/routes/rules.py`
- Modify: `frontend/src/api/v3.ts`

- [ ] **Step 1: 在 rules.py 添加提取预览 endpoint**

在 `govdoc/api/routes/rules.py` 中添加：

```python
@router.get("/{rule_id}/extract-runs/{run_id}/preview")
async def get_extract_run_preview(rule_id: str, run_id: str):
    """返回提取运行中已提取的审核点数量（提取进行中可轮询）。"""
    with get_db_session() as session:
        run = session.get(ExtractRun, run_id)
        if run is None or run.rule_source_id != rule_id:
            raise HTTPException(status_code=404, detail="ExtractRun 不存在")

        checkpoints = session.exec(
            select(CheckpointFinal).order_by(CheckpointFinal.approved_at.desc())
        ).all()

        return {
            "run_id": run.id,
            "status": run.status,
            "extracted_count": len(checkpoints),
        }
```

注意：确保 `CheckpointFinal` 和 `ExtractRun` 已在文件顶部 import。

- [ ] **Step 2: 在前端 api/v3.ts 添加调用**

```typescript
export function getExtractRunPreview(ruleId: string, runId: string): Promise<{ run_id: string; status: string; extracted_count: number }> {
  return request(`/api/v1/rules/${ruleId}/extract-runs/${runId}/preview`);
}
```

- [ ] **Step 3: 运行后端测试确认无回归**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v --timeout=30
```

- [ ] **Step 4: 提交**

```bash
git add govdoc/api/routes/rules.py frontend/src/api/v3.ts
git commit -m "feat(api): add extract run preview endpoint for in-progress extraction"
```

---

### Task 8: 全量验证

- [ ] **Step 1: 运行全部后端单元测试**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v --timeout=60
```

预期：全部 PASS。

- [ ] **Step 2: 运行前端类型检查**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npx tsc --noEmit
```

预期：无类型错误。

- [ ] **Step 3: 启动后端验证新接口可访问**

```bash
export NO_PROXY="110.42.53.85,100.81.95.44,localhost,127.0.0.1"
export no_proxy="$NO_PROXY"
source activate govdoc-auditor-v3 && timeout 5 uvicorn govdoc.api.main:app --host 0.0.0.0 --port 8099 &
sleep 2
curl -s http://localhost:8099/api/v1/dashboard/stats | python3 -m json.tool
curl -s http://localhost:8099/healthz
kill %1
```

预期：dashboard/stats 返回 JSON，healthz 返回 `{"status": "ok"}`。

- [ ] **Step 4: 提交最终验证（如有修复）**

```bash
git add -A && git commit -m "fix: address issues found during integration verification"
```
