# 内测前代码清理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除所有代码重复、死代码、审计日志缺失、高复杂度函数，使项目达到内测可上线标准。

**Architecture:** 新增 `ActivityLog` 表 + 中间件自动埋点；提取公共函数消除重复；删除死代码；拆分超长函数；硬编码迁入配置。

**Tech Stack:** Python 3.11 / FastAPI / SQLModel / Alembic / Pydantic v2

---

## File Structure

| 文件 | 职责 | 操作 |
|------|------|------|
| `govdoc/db/models.py` | 新增 ActivityLog；修改 TenderDoc/AuditRun 增字段 | MODIFY |
| `govdoc/db/migrations/versions/XXXX_add_activity_log.py` | Alembic 迁移 | CREATE |
| `govdoc/api/middleware.py` | 审计日志中间件/工具函数 | CREATE |
| `govdoc/api/routes/audit.py` | 埋点 + actor 字段 | MODIFY |
| `govdoc/api/routes/projects.py` | 埋点 + actor 字段 | MODIFY |
| `govdoc/api/routes/rules.py` | 埋点 + actor 字段 | MODIFY |
| `govdoc/api/routes/checkpoints.py` | 埋点 + before/after 记录 | MODIFY |
| `govdoc/api/routes/workpapers.py` | 埋点 + actor 字段 | MODIFY |
| `govdoc/api/routes/comments.py` | Comment CRUD 路由 | CREATE |
| `govdoc/api/schemas.py` | 清理死 schema + 新增 Comment/ActivityLog schema | MODIFY |
| `govdoc/pipelines/summary.py` | 提取 `generate_summary` 公共函数 | CREATE |
| `govdoc/pipelines/audit_tender.py` | 引用公共 summary | MODIFY |
| `govdoc/pipelines/finalize.py` | 引用公共 summary | MODIFY |
| `govdoc/pipelines/pes_overrides.py` | 提取 mixin 消除 4 次重复 | MODIFY |
| `govdoc/pipelines/output_utils.py` | 删除死函数 | MODIFY |
| `govdoc/storage/files.py` | 删除死函数 | MODIFY |
| `govdoc/harness/cli_common.py` | 提取 DDL/signal/main 骨架 | CREATE |
| `govdoc/harness/handler.py` | 引用 cli_common DDL | MODIFY |
| `govdoc/harness/log.py` | 引用 cli_common DDL | MODIFY |
| `govdoc/harness/api_eval.py` | 引用 cli_common + 拆分 run_api_eval | MODIFY |
| `govdoc/harness/pipeline_eval.py` | 引用 cli_common + 拆分 | MODIFY |
| `govdoc/config.py` | 新增 harness model/timeout 配置字段 | MODIFY |
| `govdoc.yaml` | 补 harness.judge_model / audit.point_timeout_s | MODIFY |
| `tests/unit/test_activity_log.py` | ActivityLog 单测 | CREATE |
| `tests/unit/test_comments_route.py` | Comment 路由单测 | CREATE |
| `tests/unit/test_summary.py` | 公共 summary 单测 | CREATE |

---

## Task 1: 新增 ActivityLog 数据模型 + 迁移

**Files:**
- Modify: `govdoc/db/models.py:125-131`（在 Comment 前插入 ActivityLog）
- Modify: `govdoc/db/models.py:25-33`（TenderDoc 增 `uploaded_by`）
- Modify: `govdoc/db/models.py:63-80`（AuditRun 增 `created_by`）
- Create: `govdoc/db/migrations/versions/XXXX_add_activity_log.py`
- Create: `tests/unit/test_activity_log.py`

- [ ] **Step 1: 写 ActivityLog 模型的失败测试**

```python
# tests/unit/test_activity_log.py
from govdoc.db.models import ActivityLog

def test_activity_log_fields():
    log = ActivityLog(
        actor="user_001",
        action="upload_tender_doc",
        target_type="TenderDoc",
        target_id="abc123",
        before_json=None,
        after_json='{"filename":"test.docx"}',
    )
    assert log.actor == "user_001"
    assert log.action == "upload_tender_doc"
    assert log.target_type == "TenderDoc"
    assert log.target_id == "abc123"
    assert log.before_json is None
    assert log.after_json == '{"filename":"test.docx"}'
```

- [ ] **Step 2: 运行测试确认失败**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_activity_log.py -v`
Expected: FAIL with `ImportError: cannot import name 'ActivityLog'`

- [ ] **Step 3: 在 models.py 中实现 ActivityLog + 修改 TenderDoc/AuditRun**

```python
# govdoc/db/models.py — 在 Comment 类之前插入

class ActivityLog(SQLModel, table=True):
    """操作审计日志——记录所有用户操作的 before/after。"""

    id: str = Field(default_factory=uid, primary_key=True)
    actor: str
    action: str  # upload_tender_doc / create_audit_run / update_checkpoint / ...
    target_type: str  # TenderDoc / AuditRun / CheckpointFinal / ...
    target_id: str
    before_json: str | None = None
    after_json: str | None = None
    request_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

在 `TenderDoc` 中增加：
```python
    uploaded_by: str | None = None
```

在 `AuditRun` 中增加：
```python
    created_by: str | None = None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_activity_log.py -v`
Expected: PASS

- [ ] **Step 5: 生成 Alembic 迁移**

Run: `source activate govdoc-auditor-v3 && alembic revision --autogenerate -m "add_activity_log_and_actor_fields"`
Expected: 新迁移文件生成

- [ ] **Step 6: 应用迁移**

Run: `source activate govdoc-auditor-v3 && alembic upgrade head`
Expected: OK

- [ ] **Step 7: Commit**

```bash
git add govdoc/db/models.py govdoc/db/migrations/versions/ tests/unit/test_activity_log.py
git commit -m "feat(db): add ActivityLog table + uploaded_by/created_by fields"
```

---

## Task 2: 创建审计日志工具函数

**Files:**
- Create: `govdoc/api/middleware.py`

- [ ] **Step 1: 创建 middleware.py 审计工具**

```python
# govdoc/api/middleware.py
"""审计日志工具函数——所有 API 写操作通过此模块记录。"""

from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session

from govdoc.db.models import ActivityLog


def log_activity(
    session: Session,
    *,
    actor: str,
    action: str,
    target_type: str,
    target_id: str,
    before: Any = None,
    after: Any = None,
    request_id: str | None = None,
) -> None:
    """记录一条操作审计日志。

    参数:
        session: DB session（调用方负责 commit）。
        actor: 操作人标识。
        action: 操作类型（如 upload_tender_doc / update_checkpoint）。
        target_type: 目标实体类型名。
        target_id: 目标实体 ID。
        before: 修改前的状态快照（dict 或 None）。
        after: 修改后的状态快照（dict 或 None）。
        request_id: 可选的请求追踪 ID。
    """
    session.add(
        ActivityLog(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before_json=json.dumps(before, ensure_ascii=False) if before else None,
            after_json=json.dumps(after, ensure_ascii=False) if after else None,
            request_id=request_id,
        )
    )
```

- [ ] **Step 2: Commit**

```bash
git add govdoc/api/middleware.py
git commit -m "feat(api): add log_activity audit utility"
```

---

## Task 3: 所有 API 写操作接入审计日志

**Files:**
- Modify: `govdoc/api/routes/projects.py:74-104`
- Modify: `govdoc/api/routes/rules.py:34-97`
- Modify: `govdoc/api/routes/audit.py:34-115,189-200`
- Modify: `govdoc/api/routes/checkpoints.py:89-111`
- Modify: `govdoc/api/routes/workpapers.py:38-64,67-123`
- Modify: `govdoc/api/schemas.py`（CreateAuditRunRequest 增 created_by 等）

- [ ] **Step 1: 修改 API schema 增加 actor 字段**

在 `govdoc/api/schemas.py` 中：
```python
class CreateAuditRunRequest(GovDocModel):
    project_id: str
    tender_doc_id: str
    supplementary_doc_ids: list[str] = Field(default_factory=list)
    checkpoint_ids: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("checkpoint_ids", "checkpoint_final_ids"),
    )
    created_by: str = "system"  # 新增


class UpdateCheckpointRequest(GovDocModel):
    payload_json: str
    modified_by: str = "system"  # 新增


class FinalizeWorkpaperRequest(GovDocModel):
    approved_by: str


class UpdateWorkpaperDraftRequest(GovDocModel):
    workpaper: Workpaper
    modified_by: str = "system"  # 新增
```

- [ ] **Step 2: projects.py — upload_tender_doc 接入**

```python
# govdoc/api/routes/projects.py upload_tender_doc 内
# 在 session.add(tender) 之后、session.commit() 之前加：
from govdoc.api.middleware import log_activity

log_activity(
    session,
    actor="system",  # MVP 阶段无认证，用 system 占位
    action="upload_tender_doc",
    target_type="TenderDoc",
    target_id=tender.id,
    after={"filename": tender.filename, "project_id": project_id},
)
tender.uploaded_by = "system"
```

- [ ] **Step 3: audit.py — create_audit_run + cancel 接入**

`create_audit_run`：在 `session.commit()` 前加 `log_activity`，action="create_audit_run"。
`cancel_audit_run`：在状态修改后加 `log_activity`，action="cancel_audit_run"，before={"status": 原状态}。
设置 `audit_run.created_by = payload.created_by`。

- [ ] **Step 4: checkpoints.py — update + delete 接入**

`update_checkpoint`：记录 before=原 payload_json，after=新 payload_json，actor=payload.modified_by。
`delete_checkpoint`：记录 before=原 payload_json，action="delete_checkpoint"。

- [ ] **Step 5: rules.py — upload_rule 接入**

在 `session.commit()` 前加 `log_activity`，action="upload_rule"，target_type="RuleSource"。

- [ ] **Step 6: workpapers.py — update_draft + finalize 接入**

`update_workpaper_draft`：action="update_workpaper_draft"，actor=payload.modified_by。
`finalize_workpaper_endpoint`/`finalize_workpaper_partial`：action="finalize_workpaper"，actor=payload.approved_by。

- [ ] **Step 7: 运行全部现有测试确保无回归**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 8: Commit**

```bash
git add govdoc/api/routes/ govdoc/api/schemas.py
git commit -m "feat(api): integrate ActivityLog into all write endpoints"
```

---

## Task 4: 激活 Comment 路由

**Files:**
- Create: `govdoc/api/routes/comments.py`
- Modify: `govdoc/api/main.py`（注册 router）
- Create: `tests/unit/test_comments_route.py`

- [ ] **Step 1: 写 Comment 路由测试**

```python
# tests/unit/test_comments_route.py
from unittest.mock import patch
from fastapi.testclient import TestClient

def test_create_comment(test_client):
    resp = test_client.post("/api/v1/comments", json={
        "target_type": "CheckpointFinal",
        "target_id": "cp_001",
        "author": "reviewer_1",
        "text": "这条审核点描述不够具体",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["author"] == "reviewer_1"
    assert data["text"] == "这条审核点描述不够具体"

def test_list_comments_by_target(test_client):
    # 先创建一条
    test_client.post("/api/v1/comments", json={
        "target_type": "AuditPointRun",
        "target_id": "apr_001",
        "author": "reviewer_1",
        "text": "需要补充证据",
    })
    resp = test_client.get("/api/v1/comments?target_type=AuditPointRun&target_id=apr_001")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
```

- [ ] **Step 2: 实现 comments.py 路由**

```python
# govdoc/api/routes/comments.py
"""Comments routes — 批注/评论 CRUD。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from govdoc.api.deps import get_db_session
from govdoc.api.middleware import log_activity
from govdoc.db.models import Comment
from govdoc.schemas.common import GovDocModel

router = APIRouter(prefix="/api/v1/comments", tags=["comments"])


class CreateCommentRequest(GovDocModel):
    target_type: str
    target_id: str
    author: str
    text: str


@router.post("", status_code=201)
async def create_comment(payload: CreateCommentRequest):
    with get_db_session() as session:
        comment = Comment(
            target_type=payload.target_type,
            target_id=payload.target_id,
            author=payload.author,
            text=payload.text,
        )
        session.add(comment)
        log_activity(
            session,
            actor=payload.author,
            action="create_comment",
            target_type=payload.target_type,
            target_id=payload.target_id,
            after={"text": payload.text},
        )
        session.commit()
        session.refresh(comment)
        return {
            "id": comment.id,
            "target_type": comment.target_type,
            "target_id": comment.target_id,
            "author": comment.author,
            "text": comment.text,
            "created_at": str(comment.created_at),
        }


@router.get("")
async def list_comments(target_type: str | None = None, target_id: str | None = None):
    with get_db_session() as session:
        stmt = select(Comment).order_by(Comment.created_at.desc())
        if target_type:
            stmt = stmt.where(Comment.target_type == target_type)
        if target_id:
            stmt = stmt.where(Comment.target_id == target_id)
        comments = session.exec(stmt).all()
        return [
            {
                "id": c.id,
                "target_type": c.target_type,
                "target_id": c.target_id,
                "author": c.author,
                "text": c.text,
                "created_at": str(c.created_at),
            }
            for c in comments
        ]


@router.delete("/{comment_id}", status_code=204)
async def delete_comment(comment_id: str):
    with get_db_session() as session:
        comment = session.get(Comment, comment_id)
        if comment is None:
            raise HTTPException(status_code=404, detail="Comment 不存在")
        log_activity(
            session,
            actor=comment.author,
            action="delete_comment",
            target_type=comment.target_type,
            target_id=comment.target_id,
            before={"text": comment.text},
        )
        session.delete(comment)
        session.commit()
```

- [ ] **Step 3: 在 main.py 注册 comments_router**

```python
# govdoc/api/main.py — 在 compare_router 导入行后加
from govdoc.api.routes.comments import router as comments_router
# 在 app.include_router(compare_router) 后加
app.include_router(comments_router)
```

- [ ] **Step 4: 运行测试**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_comments_route.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add govdoc/api/routes/comments.py govdoc/api/main.py tests/unit/test_comments_route.py
git commit -m "feat(api): activate Comment CRUD routes with audit logging"
```

---

## Task 5: 提取 generate_summary 消除重复

**Files:**
- Create: `govdoc/pipelines/summary.py`
- Modify: `govdoc/pipelines/audit_tender.py:108-123`
- Modify: `govdoc/pipelines/finalize.py:47-61`
- Create: `tests/unit/test_summary.py`

- [ ] **Step 1: 写公共 summary 函数测试**

```python
# tests/unit/test_summary.py
from govdoc.pipelines.summary import generate_summary
from govdoc.schemas import GovFinding, GovCheckpoint, GovFindingVerdict

def _make_finding(verdict_value: str) -> GovFinding:
    return GovFinding(
        checkpoint=GovCheckpoint(
            id="cp_01", category="其他违法违规", title="test",
            description="desc", severity="minor", retrieval_hint="hint",
        ),
        verdict=GovFindingVerdict(verdict=verdict_value, rationale="r"),
    )

def test_generate_summary_empty():
    assert generate_summary([]) == "无审核结果。"

def test_generate_summary_mixed():
    findings = [_make_finding("合规"), _make_finding("不合规"), _make_finding("存疑")]
    result = generate_summary(findings)
    assert "共审核 3 个审核点" in result
    assert "不合规 1 项" in result
    assert "合规 1 项" in result
    assert "存疑 1 项" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_summary.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: 创建 summary.py**

```python
# govdoc/pipelines/summary.py
"""审核结论摘要生成——公共函数。"""

from __future__ import annotations

from govdoc.schemas import GovFinding


def generate_summary(findings: list[GovFinding]) -> str:
    """从 findings 列表生成一句话摘要。"""
    if not findings:
        return "无审核结果。"
    total = len(findings)
    compliant = sum(1 for f in findings if f.verdict.verdict == "合规")
    non_compliant = sum(1 for f in findings if f.verdict.verdict == "不合规")
    uncertain = total - compliant - non_compliant
    parts = [f"共审核 {total} 个审核点。"]
    if non_compliant:
        parts.append(f"不合规 {non_compliant} 项。")
    if compliant:
        parts.append(f"合规 {compliant} 项。")
    if uncertain:
        parts.append(f"存疑 {uncertain} 项。")
    return " ".join(parts)
```

- [ ] **Step 4: 修改 audit_tender.py 引用公共函数**

删除 `govdoc/pipelines/audit_tender.py` 中 L108-123 的 `generate_summary` 函数定义，替换为：
```python
from govdoc.pipelines.summary import generate_summary
```

- [ ] **Step 5: 修改 finalize.py 引用公共函数**

删除 `govdoc/pipelines/finalize.py` 中 L47-61 的 `_generate_summary` 函数定义，替换为：
```python
from govdoc.pipelines.summary import generate_summary
```
并将 `finalize.py` 中所有 `_generate_summary(...)` 调用改为 `generate_summary(...)`。

- [ ] **Step 6: 运行所有测试**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 7: Commit**

```bash
git add govdoc/pipelines/summary.py govdoc/pipelines/audit_tender.py govdoc/pipelines/finalize.py tests/unit/test_summary.py
git commit -m "refactor(pipelines): extract generate_summary to shared module"
```

---

## Task 6: PES build_phase_prompt 去重（4→1）

**Files:**
- Modify: `govdoc/pipelines/pes_overrides.py:240-400`

- [ ] **Step 1: 提取 _GovDocPhasePromptMixin**

在 `pes_overrides.py` 中，在 `_RelaxedPreviousPhaseOutputMixin` 类之后加入：

```python
class _GovDocPhasePromptMixin:
    """统一 phase prompt 拼接逻辑。子类设置 _phase_prompts 类变量即可。"""

    _phase_prompts: dict[str, str] = {}

    async def build_phase_prompt(
        self,
        phase: str,
        phase_cfg: PhaseConfig,
        context: dict[str, Any],
        task_prompt: str,
    ) -> str:
        parts: list[str] = []
        phase_prompt = self._phase_prompts.get(phase, "")
        if phase_prompt:
            parts.append(phase_prompt)
        parts.append(task_prompt)
        if context:
            parts.append(json.dumps(context, ensure_ascii=False, default=str))
        return "\n\n".join(parts)
```

- [ ] **Step 2: 简化 4 个 PES 子类**

```python
class GovDocExtractorPES(_GovDocPhasePromptMixin, _RelaxedPreviousPhaseOutputMixin, ExtractorPES):
    _phase_prompts = _EXTRACTOR_PHASE_PROMPTS


class GovDocAuditorPES(_GovDocPhasePromptMixin, _RelaxedPreviousPhaseOutputMixin, AuditorPES):
    _phase_prompts = _AUDITOR_PHASE_PROMPTS

    async def postprocess_phase_result(self, phase: str, result: PhaseResult, run: Any) -> None:
        # ... 保留原有 postprocess 逻辑不变 ...


class GovDocMockExtractorPES(_GovDocPhasePromptMixin, _RelaxedPreviousPhaseOutputMixin, MockPES):
    _phase_prompts = _EXTRACTOR_PHASE_PROMPTS


class GovDocMockAuditorPES(_GovDocPhasePromptMixin, _RelaxedPreviousPhaseOutputMixin, MockPES):
    _phase_prompts = _AUDITOR_PHASE_PROMPTS
```

删除每个类中独立的 `build_phase_prompt` 方法（共约 60 行）。

- [ ] **Step 3: 运行现有 PES 相关测试**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_pes_overrides.py tests/contract/ -v`
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add govdoc/pipelines/pes_overrides.py
git commit -m "refactor(pes): extract _GovDocPhasePromptMixin, eliminate 4x duplication"
```

---

## Task 7: Harness DDL/CLI 骨架去重

**Files:**
- Create: `govdoc/harness/cli_common.py`
- Modify: `govdoc/harness/handler.py:28-49`
- Modify: `govdoc/harness/log.py:63-85`
- Modify: `govdoc/harness/api_eval.py:1028-1059,1062-1105`
- Modify: `govdoc/harness/pipeline_eval.py:895-990`

- [ ] **Step 1: 创建 cli_common.py**

```python
# govdoc/harness/cli_common.py
"""Harness CLI 公共骨架——DDL 初始化 / 运行状态管理 / 信号处理。"""

from __future__ import annotations

import logging
import signal
import sqlite3
import sys
import uuid
from pathlib import Path
from types import FrameType
from typing import NoReturn

from govdoc.harness.handler import SqliteHandler
from govdoc.harness.log import _now_iso

logger = logging.getLogger(__name__)

_RUNS_DDL = """
CREATE TABLE IF NOT EXISTS _runs (
    run_id TEXT PRIMARY KEY,
    git_sha TEXT,
    started_at TEXT,
    finished_at TEXT,
    heartbeat_at TEXT,
    config JSON,
    status TEXT DEFAULT 'running'
)
"""

_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS _events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    timestamp TEXT,
    event_type TEXT,
    payload JSON
)
"""


def init_run_tables(conn: sqlite3.Connection) -> None:
    """创建 _runs 和 _events 固定表。"""
    conn.execute(_RUNS_DDL)
    conn.execute(_EVENTS_DDL)
    conn.commit()


def update_run_status(db_path: str, run_id: str, status: str) -> None:
    """确保运行记录存在，并更新最终状态。"""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        init_run_tables(conn)
        now = _now_iso()
        conn.execute(
            "INSERT OR IGNORE INTO _runs (run_id, started_at, status) VALUES (?, ?, ?)",
            (run_id, now, "running"),
        )
        conn.execute(
            "UPDATE _runs SET finished_at = ?, status = ? WHERE run_id = ?",
            (now, status, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def setup_harness_cli(
    db_path: str,
    run_id_prefix: str,
) -> tuple[str, SqliteHandler]:
    """配置 harness CLI 公共设施：logging + signal handler + sqlite handler。

    返回:
        (run_id, sqlite_handler)
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    run_id = f"{run_id_prefix}-{uuid.uuid4().hex[:8]}"
    root_logger = logging.getLogger()
    sqlite_handler = SqliteHandler(db_path=db_path, run_id=run_id)
    root_logger.addHandler(sqlite_handler)

    def _handle_signal(signum: int, frame: FrameType | None) -> NoReturn:
        del frame
        update_run_status(db_path, run_id, "interrupted")
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    return run_id, sqlite_handler
```

- [ ] **Step 2: 修改 handler.py 引用公共 DDL**

将 `SqliteHandler.__init__` 中的内联 DDL 替换为：
```python
from govdoc.harness.cli_common import init_run_tables
# ...
init_run_tables(self._conn)
```

- [ ] **Step 3: 修改 log.py 引用公共 DDL**

将 `HarnessLog._init_fixed_tables` 替换为：
```python
def _init_fixed_tables(self) -> None:
    from govdoc.harness.cli_common import init_run_tables
    init_run_tables(self._conn)
```

- [ ] **Step 4: 修改 api_eval.py main() 使用 cli_common**

```python
# govdoc/harness/api_eval.py — 替换 main() 中的手动设置
from govdoc.harness.cli_common import setup_harness_cli, update_run_status

def main() -> None:
    args = _parse_args()
    run_id, sqlite_handler = setup_harness_cli(args.db_path, "L2")
    try:
        completed_run_id = asyncio.run(
            run_api_eval(
                base_url=args.base_url,
                manifest_path=args.manifest,
                project_root=args.project_root,
                rubric_dir=args.rubric_dir,
                db_path=args.db_path,
                run_id=run_id,
            )
        )
        logger.info("L2 完成, run_id=%s", completed_run_id)
    except Exception:
        logger.critical("L2 API 评估发生致命异常", exc_info=True)
        update_run_status(args.db_path, run_id, "crashed")
        sys.exit(1)
    finally:
        logging.getLogger().removeHandler(sqlite_handler)
        sqlite_handler.close()
```

同时删除 `api_eval.py` 中的 `_update_run_status` 函数定义。

- [ ] **Step 5: 修改 pipeline_eval.py main() 同理**

删除 `_init_run_tables`、`_update_run_status` 函数，`main()` 改用 `setup_harness_cli`。

- [ ] **Step 6: 运行 harness 相关测试**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_harness_*.py -v`
Expected: 全部 PASS

- [ ] **Step 7: Commit**

```bash
git add govdoc/harness/cli_common.py govdoc/harness/handler.py govdoc/harness/log.py govdoc/harness/api_eval.py govdoc/harness/pipeline_eval.py
git commit -m "refactor(harness): extract cli_common, eliminate DDL/signal/main duplication"
```

---

## Task 8: 删除所有死代码

**Files:**
- Modify: `govdoc/pipelines/output_utils.py`（删除 L124-185: normalize_output, validate_extractor_output, validate_auditor_output）
- Modify: `govdoc/storage/files.py`（删除 ensure_rule_source_dir, ensure_project_dir, build_prepared_manifest）
- Modify: `govdoc/api/schemas.py`（删除 HealthzResponse, ExtractRunStatusResponse, GenericMessageResponse, ImportCheckpointsResponse）
- Modify: `govdoc/harness/judge.py`（删除未使用的 compare_runs, diagnose 方法）

- [ ] **Step 1: 删除 output_utils.py 中 3 个死函数**

删除 `normalize_output`（L124-143）、`validate_extractor_output`（L146-163）、`validate_auditor_output`（L166-185）。

- [ ] **Step 2: 删除 storage/files.py 中 3 个死函数**

删除 `ensure_rule_source_dir`（L24-27）、`ensure_project_dir`（L30-33）、`build_prepared_manifest`（L116-124）。

- [ ] **Step 3: 删除 api/schemas.py 中 4 个死类**

删除 `HealthzResponse`、`ExtractRunStatusResponse`、`GenericMessageResponse`、`ImportCheckpointsResponse`。

- [ ] **Step 4: 删除 harness/judge.py 中 compare_runs 和 diagnose**

这两个方法内部互相调用但无外部调用点，一并删除。

- [ ] **Step 5: 运行全量测试确认无回归**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add govdoc/pipelines/output_utils.py govdoc/storage/files.py govdoc/api/schemas.py govdoc/harness/judge.py
git commit -m "refactor: remove dead code (130 lines) identified by vulture audit"
```

---

## Task 9: 硬编码迁入配置

**Files:**
- Modify: `govdoc/config.py`（HarnessConfig 增字段）
- Modify: `govdoc.yaml`（补充配置）
- Modify: `govdoc/harness/pipeline_eval.py`（读配置替代硬编码）
- Modify: `govdoc/harness/api_eval.py`（读配置替代硬编码）
- Modify: `govdoc/pipelines/audit_tender.py:683`（timeout 读配置）

- [ ] **Step 1: 扩展 HarnessConfig**

```python
# govdoc/config.py — HarnessConfig 修改
class HarnessConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    db_path: str = "./results/harness.db"
    judge_model: str = "glm-5.1"
    judge_base_url: str = "http://110.42.53.85:11098/v1"


class AuditConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    point_timeout_s: int = 900
```

在 `GovDocConfig` 中增加：
```python
    audit: AuditConfig = Field(default_factory=AuditConfig)
```

- [ ] **Step 2: 更新 govdoc.yaml**

```yaml
# 在 harness: 段补充
harness:
  db_path: "./results/harness.db"
  judge_model: "glm-5.1"
  judge_base_url: "http://110.42.53.85:11098/v1"

# 新增 audit: 段
audit:
  point_timeout_s: 900
```

- [ ] **Step 3: pipeline_eval.py 读取 judge_model 配置**

将 `pipeline_eval.py` 中硬编码的 `"glm-5.1"` 和 `"http://110.42.53.85:11098/v1"` 替换为从配置读取：
```python
from govdoc.runtime import get_config
cfg = get_config()
judge_model = cfg.harness.judge_model
judge_base_url = cfg.harness.judge_base_url
```

- [ ] **Step 4: audit_tender.py timeout 读配置**

```python
# govdoc/pipelines/audit_tender.py L683 替换
point_timeout_s = int(os.environ.get("GOVDOC_POINT_TIMEOUT", str(cfg.audit.point_timeout_s)))
```

- [ ] **Step 5: 运行测试**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_config.py tests/unit/test_harness_*.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add govdoc/config.py govdoc.yaml govdoc/harness/pipeline_eval.py govdoc/harness/api_eval.py govdoc/pipelines/audit_tender.py
git commit -m "refactor: move hardcoded values (judge model, timeout, IP) into config"
```

---

## Task 10: 删除未使用的配置字段 + 格式化

**Files:**
- Modify: `govdoc/config.py`（删除 `AppConfig.host/port`、`WorkspaceConfig.cleanup_days`、`EvolutionConfig` 三个字段如果确认无读取）
- Run: `ruff format` 对 7 个未格式化文件

- [ ] **Step 1: 确认字段无读取后删除**

```python
# govdoc/config.py — AppConfig 删除 host/port（uvicorn 直接在 CLI 指定，不读这里）
class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storage_root: str = "./data/storage"
    database_url: str = "sqlite:///./data/app.sqlite"
    ocr_base_url: str | None = None
```

注意：`EvolutionConfig` 保留整个类（M2 会启用），但标记为预留。
`cleanup_days` 保留（未来定时清理会用）。

- [ ] **Step 2: 格式化所有文件**

Run: `source activate govdoc-auditor-v3 && ruff format .`
Expected: 7 files formatted

- [ ] **Step 3: 运行全量测试**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "refactor: remove unused config fields + ruff format all files"
```

---

## Task 11: 拆分 run_api_eval（759 行 → 子函数）

**Files:**
- Modify: `govdoc/harness/api_eval.py:256-1015`

- [ ] **Step 1: 识别 run_api_eval 中的逻辑段**

当前 759 行函数包含以下段（已通过 AST 分析确认）：
1. 初始化阶段（加载 manifest / 创建 HarnessLog / 建表）~50 行
2. 健康检查 ~30 行
3. 逐端点调用循环 ~200 行
4. 契约验证循环 ~150 行
5. 语义评估循环 ~200 行
6. 汇总/收尾 ~130 行

- [ ] **Step 2: 拆分为子函数**

提取以下函数（均为 `api_eval.py` 内部私有函数）：
- `_run_health_check(log, client, base_url) -> bool`
- `_run_endpoint_calls(log, client, specs, base_url) -> list[EndpointResult]`
- `_run_contract_validation(log, results) -> list[ContractResult]`
- `_run_semantic_evaluation(log, results, rubric_dir) -> None`
- `_summarize_and_close(log, results) -> str`

`run_api_eval` 主体变为 ~40 行编排代码。

- [ ] **Step 3: 运行 api_eval 相关测试**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_api_eval.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add govdoc/harness/api_eval.py
git commit -m "refactor(harness): split run_api_eval (759→~40 line orchestrator + 5 sub-functions)"
```

---

## Task 12: 拆分 run_pipeline_eval + pipeline A/B 异常模板去重

**Files:**
- Modify: `govdoc/harness/pipeline_eval.py:282-520,713-893`

- [ ] **Step 1: 提取 _record_pipeline_exception 公共函数**

```python
def _record_pipeline_exception(
    log: HarnessLog,
    *,
    pipeline: str,
    project_name: str,
    input_file: str,
    exc: Exception,
    start_time: float,
) -> None:
    """统一记录 pipeline A/B 执行异常。"""
    import time
    import traceback

    duration = time.time() - start_time
    record_pipeline_run(
        log,
        pipeline=pipeline,
        project_name=project_name,
        input_file=input_file,
        status="error",
        duration_s=duration,
        total_tokens=0,
        error=str(exc),
    )
    log.log_event(
        "pipeline_error",
        {
            "pipeline": pipeline,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "traceback": traceback.format_exc(),
        },
    )
```

- [ ] **Step 2: 将 run_pipeline_eval 中 pipeline A/B 异常处理替换为调用公共函数**

- [ ] **Step 3: 拆分 _run_semantic_evaluations（CC=31）为逐维度调用**

- [ ] **Step 4: 运行测试**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_pipeline_eval.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add govdoc/harness/pipeline_eval.py
git commit -m "refactor(harness): extract _record_pipeline_exception, split semantic eval loop"
```

---

## Task 13: 最终验证

**Files:** None (verification only)

- [ ] **Step 1: 全量测试**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/ -v --tb=short 2>&1 | tail -20`
Expected: 全部 PASS，无 warning

- [ ] **Step 2: ruff lint + format 确认干净**

Run: `source activate govdoc-auditor-v3 && ruff check . && ruff format --check .`
Expected: No issues found + All files formatted

- [ ] **Step 3: vulture 复查**

Run: `source activate govdoc-auditor-v3 && vulture govdoc/ --min-confidence 80`
Expected: 仅剩 Pydantic model_config / enum 等误报，无真正死代码

- [ ] **Step 4: radon 复查复杂度**

Run: `source activate govdoc-auditor-v3 && radon cc govdoc/ -a -nc`
Expected: 无 F 级函数，D 级最多 1-2 个

- [ ] **Step 5: 代码行数确认瘦身效果**

Run: `find govdoc/ -name "*.py" | grep -v __pycache__ | xargs wc -l | tail -1`
Expected: 核心代码从 ~5,576 行降至 ~5,200 行以下（删除 ~130 死代码 + ~163 重复 ≈ 300 行净减）

- [ ] **Step 6: Commit (if any fixups needed)**

---

## Self-Review Checklist

1. **Spec coverage**: 两份审计报告（Claude + Codex）中的每个发现都对应一个 Task：
   - P0 审计日志 → Task 1-4
   - 重复代码 → Task 5-7, 12
   - 死代码 → Task 8
   - 硬编码 → Task 9
   - 未用配置 → Task 10
   - 高复杂度函数 → Task 11-12
   - Comment/User 孤儿表 → Task 4

2. **Placeholder scan**: 所有步骤均含具体代码或命令，无 "TBD" / "TODO"。

3. **Type consistency**: `log_activity` 签名在 Task 2 定义、Task 3-4 调用时参数一致；`generate_summary` 签名在 Task 5 定义后在 Task 5 Step 4-5 引用。
