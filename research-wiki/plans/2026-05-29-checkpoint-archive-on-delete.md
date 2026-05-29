---
type: plan
node_id: plan:checkpoint-archive-on-delete
title: 审核点删除归档实施计划
date: 2026-05-29
---

# 审核点删除归档与数据一致性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除被审查任务引用的审核点时改为"归档"而非硬删，消除孤儿引用导致的前端名字异常与详情缺失。

**Architecture:** CheckpointFinal 新增 `status` 字段（active/archived）。删除端点按是否被 AuditPointRun 引用分流：无引用→硬删，有引用→标记 archived。导入去重逻辑将 archived 记录也纳入候选，同名导入时自动迁移历史引用并清理旧归档记录。列表 API 默认只返回 active，progress API 过滤孤儿 point_run。前端审查结果页加载 archived 审核点并标注「已归档」。

**Tech Stack:** Python 3.11 / FastAPI / SQLModel / SQLite / Alembic / pytest（后端）；React + TypeScript + Vite（前端）

设计来源：`research-wiki/designs/checkpoint-archive-on-delete.md`

---

## 文件结构

| 文件 | 责任 | 改动 |
|------|------|------|
| `govdoc/db/models.py` | CheckpointFinal 加 `status` 字段 | MODIFY |
| `govdoc/db/migrations/versions/<new>_add_status_to_checkpointfinal.py` | DB schema migration | NEW |
| `govdoc/api/routes/checkpoints.py` | 删除分流 / 去重含 archived / 列表过滤 | MODIFY |
| `govdoc/api/routes/audit.py` | progress 端点过滤孤儿 point_run | MODIFY |
| `tests/unit/test_checkpoint_archive.py` | 后端归档逻辑单测 | NEW |
| `frontend/src/api/v3.ts` | `listCheckpoints` 加 `include_archived` 参数 | MODIFY |
| `frontend/src/pages/AIReviewDetailPage.tsx` | 传 `include_archived=true`、archived 标签 | MODIFY |
| `frontend/src/pages/AuditLibraryPage.tsx` | 归档响应提示 | MODIFY |

**关键约定（贯穿全部任务）：**
- `CheckpointFinal.status` 取值：`"active"`（默认）/ `"archived"`
- 归档判定：存在 `AuditPointRun.checkpoint_final_id == checkpoint_id` 即"被引用"
- `_serialize_final` 响应新增 `archived: bool` 字段（`final.status == "archived"`）
- 删除端点响应：无引用→204；归档→200 + `{"action": "archived", "referenced_by": N}`

---

## Task 1: CheckpointFinal 新增 status 字段 + Migration

**Files:**
- Modify: `govdoc/db/models.py:34-38`
- Create: `govdoc/db/migrations/versions/<rev>_add_status_to_checkpointfinal.py`

- [ ] **Step 1: 修改模型，新增 status 字段**

`govdoc/db/models.py` 中 CheckpointFinal 类（第 34-38 行）改为：

```python
class CheckpointFinal(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    payload_json: str
    approved_by: str
    approved_at: datetime = Field(default_factory=datetime.utcnow)
    # active = 正常可用；archived = 被审查任务引用但用户已"删除"
    status: str = "active"
```

- [ ] **Step 2: 生成 Alembic migration**

Run:
```bash
source activate govdoc-auditor-v3 && alembic revision -m "add status to checkpointfinal"
```
Expected: 在 `govdoc/db/migrations/versions/` 生成新文件，输出 `Generating ...<rev>_add_status_to_checkpointfinal.py ... done`

- [ ] **Step 3: 编写 migration 内容**

打开新生成的文件，把 `upgrade` / `downgrade` 替换为（保留文件顶部自动生成的 `revision` / `down_revision`）：

```python
def upgrade() -> None:
    # SQLite 需用 batch 模式加列；server_default 保证存量行回填 active
    with op.batch_alter_table("checkpointfinal") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(), nullable=False, server_default="active")
        )


def downgrade() -> None:
    with op.batch_alter_table("checkpointfinal") as batch_op:
        batch_op.drop_column("status")
```

确认文件顶部已 `import sqlalchemy as sa` 和 `from alembic import op`（Alembic 模板默认包含）。

- [ ] **Step 4: 应用 migration**

Run:
```bash
source activate govdoc-auditor-v3 && alembic upgrade head
```
Expected: 输出 `Running upgrade ... -> <rev>, add status to checkpointfinal`，无报错

- [ ] **Step 5: 验证存量数据回填**

Run:
```bash
source activate govdoc-auditor-v3 && python3 -c "
from sqlmodel import Session, select
from govdoc.db.models import CheckpointFinal
from govdoc.db.session import get_engine
with Session(get_engine()) as s:
    rows = s.exec(select(CheckpointFinal)).all()
    print('total:', len(rows))
    print('non-active:', [r.id for r in rows if r.status != 'active'])
"
```
Expected: `non-active: []`（所有存量记录都是 active）

> 注：若 `get_engine` 名称不符，查看 `govdoc/db/session.py` 取实际的 engine 构造方式（database_url 默认 `sqlite:///./data/app.sqlite`）。

- [ ] **Step 6: Commit**

```bash
git add govdoc/db/models.py govdoc/db/migrations/versions/
git commit -m "feat(db): CheckpointFinal 新增 status 字段（active/archived）"
```

---

## Task 2: _serialize_final 响应携带 archived 标志

**Files:**
- Modify: `govdoc/api/routes/checkpoints.py:29-36`
- Test: `tests/unit/test_checkpoint_archive.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/unit/test_checkpoint_archive.py`：

```python
"""审核点删除归档逻辑单测。"""

from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

from govdoc.api.routes.checkpoints import _serialize_final
from govdoc.db.models import CheckpointFinal


def _make_engine():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return engine


def test_serialize_final_marks_archived() -> None:
    """_serialize_final 应根据 status 输出 archived 布尔标志。"""
    active = CheckpointFinal(payload_json="{}", approved_by="t", status="active")
    archived = CheckpointFinal(payload_json="{}", approved_by="t", status="archived")

    assert _serialize_final(active)["archived"] is False
    assert _serialize_final(archived)["archived"] is True
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_checkpoint_archive.py::test_serialize_final_marks_archived -v
```
Expected: FAIL，`KeyError: 'archived'`

- [ ] **Step 3: 修改 _serialize_final**

`govdoc/api/routes/checkpoints.py` 第 29-36 行改为：

```python
def _serialize_final(final: CheckpointFinal) -> dict[str, str | bool | None]:
    return {
        "id": final.id,
        "kind": "final",
        "status": "final",
        "payload_json": final.payload_json,
        "approved_by": final.approved_by,
        "archived": final.status == "archived",
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_checkpoint_archive.py::test_serialize_final_marks_archived -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add govdoc/api/routes/checkpoints.py tests/unit/test_checkpoint_archive.py
git commit -m "feat(api): _serialize_final 输出 archived 标志"
```

---

## Task 3: 列表 API 默认只返回 active，支持 include_archived

**Files:**
- Modify: `govdoc/api/routes/checkpoints.py:39-45`
- Test: `tests/unit/test_checkpoint_archive.py`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_checkpoint_archive.py` 追加（顶部 import 增加 `_filter_listed_finals`）：

```python
def test_filter_listed_finals_excludes_archived_by_default() -> None:
    """默认只返回 active；include_archived=True 时返回全部。"""
    active = CheckpointFinal(payload_json="{}", approved_by="t", status="active")
    archived = CheckpointFinal(payload_json="{}", approved_by="t", status="archived")
    finals = [active, archived]

    default = _filter_listed_finals(finals, include_archived=False)
    assert default == [active]

    full = _filter_listed_finals(finals, include_archived=True)
    assert full == [active, archived]
```

import 行改为：
```python
from govdoc.api.routes.checkpoints import _filter_listed_finals, _serialize_final
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_checkpoint_archive.py::test_filter_listed_finals_excludes_archived_by_default -v
```
Expected: FAIL，`ImportError: cannot import name '_filter_listed_finals'`

- [ ] **Step 3: 实现过滤辅助函数 + 改 list 端点**

`govdoc/api/routes/checkpoints.py` 中，把第 39-45 行的 `list_checkpoints` 替换为：

```python
def _filter_listed_finals(
    finals: list[CheckpointFinal],
    *,
    include_archived: bool,
) -> list[CheckpointFinal]:
    """按 include_archived 过滤审核点列表。

    Args:
        finals: 全部 CheckpointFinal 记录。
        include_archived: 为 False 时仅保留 status == "active" 的记录。

    Returns:
        过滤后的列表。
    """
    if include_archived:
        return list(finals)
    return [final for final in finals if final.status == "active"]


@router.get("")
async def list_checkpoints(include_archived: bool = False):
    with get_db_session() as session:
        finals = session.exec(select(CheckpointFinal)).all()
        visible = _filter_listed_finals(list(finals), include_archived=include_archived)
        payload = [_serialize_final(final) for final in visible]
        payload.sort(key=lambda item: item["id"] or "")
        return payload
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_checkpoint_archive.py -v
```
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add govdoc/api/routes/checkpoints.py tests/unit/test_checkpoint_archive.py
git commit -m "feat(api): list_checkpoints 默认隐藏 archived，支持 include_archived"
```

---

## Task 4: 删除端点分流（无引用硬删 / 有引用归档）

**Files:**
- Modify: `govdoc/api/routes/checkpoints.py:487-512`
- Test: `tests/unit/test_checkpoint_archive.py`

- [ ] **Step 1: 写失败测试（提取纯函数 _archive_or_delete_checkpoint）**

在 `tests/unit/test_checkpoint_archive.py` 追加：

```python
from govdoc.api.routes.checkpoints import _archive_or_delete_checkpoint
from govdoc.db.models import AuditPointRun, AuditRun, CheckpointLibraryItem


def test_archive_when_referenced() -> None:
    """被 AuditPointRun 引用时归档，不删除记录，且解除库关联。"""
    engine = _make_engine()
    with Session(engine) as session:
        final = CheckpointFinal(payload_json="{}", approved_by="t", status="active")
        session.add(final)
        session.commit()
        session.refresh(final)

        session.add(
            CheckpointLibraryItem(library_id="lib1", checkpoint_final_id=final.id)
        )
        session.add(
            AuditPointRun(audit_run_id="run1", checkpoint_final_id=final.id)
        )
        session.commit()

        result = _archive_or_delete_checkpoint(session, final)
        session.commit()

        assert result == {"action": "archived", "referenced_by": 1}
        refreshed = session.get(CheckpointFinal, final.id)
        assert refreshed is not None
        assert refreshed.status == "archived"
        items = session.exec(select(CheckpointLibraryItem)).all()
        assert items == []


def test_hard_delete_when_not_referenced() -> None:
    """无 AuditPointRun 引用时硬删除。"""
    engine = _make_engine()
    with Session(engine) as session:
        final = CheckpointFinal(payload_json="{}", approved_by="t", status="active")
        session.add(final)
        session.commit()
        session.refresh(final)
        fid = final.id

        result = _archive_or_delete_checkpoint(session, final)
        session.commit()

        assert result == {"action": "deleted"}
        assert session.get(CheckpointFinal, fid) is None
```

顶部补充 import：
```python
from sqlmodel import Session, SQLModel, create_engine, select
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_checkpoint_archive.py::test_archive_when_referenced tests/unit/test_checkpoint_archive.py::test_hard_delete_when_not_referenced -v
```
Expected: FAIL，`ImportError: cannot import name '_archive_or_delete_checkpoint'`

- [ ] **Step 3: 实现 _archive_or_delete_checkpoint + 改删除端点**

`govdoc/api/routes/checkpoints.py` 第 487-512 行的 `delete_checkpoint` 替换为：

```python
def _archive_or_delete_checkpoint(
    session: Session,
    final: CheckpointFinal,
) -> dict[str, str | int]:
    """按是否被 AuditPointRun 引用，对审核点执行归档或硬删除。

    被引用：标记 status="archived"，解除全部库关联，记录保留供历史审查结果展示。
    无引用：删除库关联后硬删除记录。
    调用方负责 commit。

    Args:
        session: 当前数据库 session。
        final: 待处理的 CheckpointFinal。

    Returns:
        归档时 {"action": "archived", "referenced_by": N}；
        删除时 {"action": "deleted"}。
    """
    ref_count = len(
        session.exec(
            select(AuditPointRun).where(
                AuditPointRun.checkpoint_final_id == final.id
            )
        ).all()
    )
    # 两种情况都解除库关联——审核点从所有库中消失
    items = session.exec(
        select(CheckpointLibraryItem).where(
            CheckpointLibraryItem.checkpoint_final_id == final.id,
        )
    ).all()
    for item in items:
        session.delete(item)

    if ref_count > 0:
        final.status = "archived"
        session.add(final)
        log_activity(
            session,
            actor="system",
            action="archive_checkpoint",
            target_type="CheckpointFinal",
            target_id=final.id,
            before={"payload_json": final.payload_json},
            after={"status": "archived", "referenced_by": ref_count},
        )
        return {"action": "archived", "referenced_by": ref_count}

    log_activity(
        session,
        actor="system",
        action="delete_checkpoint",
        target_type="CheckpointFinal",
        target_id=final.id,
        before={"payload_json": final.payload_json},
    )
    session.delete(final)
    return {"action": "deleted"}


@router.delete("/{checkpoint_id}")
async def delete_checkpoint(checkpoint_id: str):
    with get_db_session() as session:
        final = session.get(CheckpointFinal, checkpoint_id)
        if final is None:
            raise HTTPException(status_code=404, detail="Checkpoint 不存在")
        result = _archive_or_delete_checkpoint(session, final)
        session.commit()
        if result["action"] == "deleted":
            return Response(status_code=204)
        return result
```

> 注意：装饰器从 `@router.delete("/{checkpoint_id}", status_code=204)` 改为不带 `status_code`，因为现在可能返回 204 或 200+JSON。

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_checkpoint_archive.py -v
```
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add govdoc/api/routes/checkpoints.py tests/unit/test_checkpoint_archive.py
git commit -m "feat(api): 删除审核点分流——有引用归档，无引用硬删"
```

---

## Task 5: 导入去重将 archived 纳入候选并迁移引用

**Files:**
- Modify: `govdoc/api/routes/checkpoints.py:171-214`（`deduplicate_existing_checkpoints`）
- Modify: `govdoc/api/routes/checkpoints.py:263-270`（`_title_to_final`）
- Test: `tests/unit/test_checkpoint_archive.py`

**背景：** 当前 `deduplicate_existing_checkpoints` 已对所有 CheckpointFinal 按 title 分组去重并迁移引用（复用 `_rewire_checkpoint_references`）。由于它本就遍历**全部** finals（不区分 status），archived 记录已天然纳入分组。问题在于 `keep` 选择逻辑可能保留 archived 记录。需保证：**同名分组中优先保留 active 记录**，把 archived 的旧记录作为被删除目标，引用迁移到 active 新记录。

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_checkpoint_archive.py` 追加：

```python
import json

from govdoc.api.routes.checkpoints import deduplicate_existing_checkpoints
from govdoc.schemas import GovCheckpoint


def _cp_payload(title: str) -> str:
    return GovCheckpoint(
        id="x",
        category="意向性招标",
        title=title,
        description="d",
        severity="major",
        retrieval_hint="h",
    ).model_dump_json()


def test_dedup_migrates_archived_to_active() -> None:
    """同名 archived 旧记录的历史引用迁移到新导入的 active 记录后删除。"""
    engine = _make_engine()
    with Session(engine) as session:
        # 旧的归档记录
        archived = CheckpointFinal(
            payload_json=_cp_payload("逾期退还保证金"),
            approved_by="t",
            status="archived",
        )
        # 新导入的 active 记录（同 title）
        active = CheckpointFinal(
            payload_json=_cp_payload("逾期退还保证金"),
            approved_by="t",
            status="active",
        )
        session.add(archived)
        session.add(active)
        session.commit()
        session.refresh(archived)
        session.refresh(active)

        # 历史审查任务引用了 archived 记录
        session.add(
            AuditRun(
                id="run1",
                project_id="p1",
                main_document_id="d1",
                checkpoint_final_ids=json.dumps([archived.id]),
            )
        )
        session.add(
            AuditPointRun(audit_run_id="run1", checkpoint_final_id=archived.id)
        )
        session.commit()

        stats = deduplicate_existing_checkpoints(session)
        session.commit()

        assert stats.removed_existing_count == 1
        assert session.get(CheckpointFinal, archived.id) is None
        kept = session.get(CheckpointFinal, active.id)
        assert kept is not None and kept.status == "active"
        # point_run 已迁移到 active 记录
        prs = session.exec(select(AuditPointRun)).all()
        assert all(pr.checkpoint_final_id == active.id for pr in prs)
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_checkpoint_archive.py::test_dedup_migrates_archived_to_active -v
```
Expected: FAIL（当前 `keep` 用 `(approved_at, id)` 排序，可能保留 archived；断言 `kept.status == "active"` 或 removed count 不符）

- [ ] **Step 3: 修改 keep 选择逻辑——优先保留 active**

`govdoc/api/routes/checkpoints.py` 第 193-201 行的去重循环改为：

```python
    for grouped_finals in groups.values():
        if len(grouped_finals) < 2:
            continue
        # 优先保留 active 记录；同 status 内再按 (approved_at, id) 取最新
        keep = max(
            grouped_finals,
            key=lambda item: (item.status == "active", item.approved_at, item.id),
        )
        for final in grouped_finals:
            if final.id == keep.id:
                continue
            replacement_map[final.id] = keep.id
            delete_targets.append(final)
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_checkpoint_archive.py::test_dedup_migrates_archived_to_active -v
```
Expected: PASS

- [ ] **Step 5: 回归——确认导入路径不退化**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_checkpoint_import.py -v
```
Expected: 原有导入测试全部 PASS（若该文件不存在则跳过此步）

- [ ] **Step 6: Commit**

```bash
git add govdoc/api/routes/checkpoints.py tests/unit/test_checkpoint_archive.py
git commit -m "feat(api): 导入去重优先保留 active，归档同名记录引用自动迁移"
```

---

## Task 6: progress 端点过滤孤儿 point_run

**Files:**
- Modify: `govdoc/api/routes/audit.py:247-276`
- Test: `tests/unit/test_checkpoint_archive.py`

**说明：** archived 审核点的 CheckpointFinal 记录仍存在，前端能查到，不算孤儿。只有 CheckpointFinal 被硬删（极端历史数据）才算孤儿，此时 progress 过滤掉对应 point_run 并下调计数。

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_checkpoint_archive.py` 追加：

```python
from govdoc.api.routes.audit import _filter_orphan_point_runs


def test_filter_orphan_point_runs() -> None:
    """checkpoint 不存在的 point_run 被过滤，存在的保留。"""
    existing_ids = {"cp-alive"}
    point_runs = [
        AuditPointRun(audit_run_id="r", checkpoint_final_id="cp-alive"),
        AuditPointRun(audit_run_id="r", checkpoint_final_id="cp-gone"),
    ]
    kept = _filter_orphan_point_runs(point_runs, existing_ids)
    assert len(kept) == 1
    assert kept[0].checkpoint_final_id == "cp-alive"
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_checkpoint_archive.py::test_filter_orphan_point_runs -v
```
Expected: FAIL，`ImportError: cannot import name '_filter_orphan_point_runs'`

- [ ] **Step 3: 实现过滤函数 + 改 progress 端点**

`govdoc/api/routes/audit.py` 中，在 `get_audit_run_progress` 函数（第 247 行）**之前**新增辅助函数：

```python
def _filter_orphan_point_runs(
    point_runs: list[AuditPointRun],
    existing_checkpoint_ids: set[str],
) -> list[AuditPointRun]:
    """过滤掉 checkpoint 已被硬删除的孤儿 point_run。

    archived 审核点的 CheckpointFinal 记录仍存在，不会被过滤。

    Args:
        point_runs: 某 audit_run 下的全部 AuditPointRun。
        existing_checkpoint_ids: 当前 CheckpointFinal 表中存在的 id 集合。

    Returns:
        checkpoint 仍存在的 point_run 列表。
    """
    return [
        pr for pr in point_runs if pr.checkpoint_final_id in existing_checkpoint_ids
    ]
```

然后把 `get_audit_run_progress` 第 254-276 行的函数体替换为：

```python
        point_runs = session.exec(
            select(AuditPointRun).where(AuditPointRun.audit_run_id == audit_run_id)
        ).all()

        cp_ids = {pr.checkpoint_final_id for pr in point_runs}
        existing_ids = set(
            session.exec(
                select(CheckpointFinal.id).where(CheckpointFinal.id.in_(cp_ids))
            ).all()
        ) if cp_ids else set()
        visible_runs = _filter_orphan_point_runs(list(point_runs), existing_ids)
        orphan_count = len(point_runs) - len(visible_runs)

        return AuditRunProgressResponse(
            audit_run_id=run.id,
            status=run.status,
            total_count=max(run.total_count - orphan_count, len(visible_runs)),
            processed_count=max(run.processed_count - orphan_count, 0),
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
                for pr in visible_runs
            ],
        )
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_checkpoint_archive.py::test_filter_orphan_point_runs -v
```
Expected: PASS

- [ ] **Step 5: 全量后端单测回归**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v
```
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add govdoc/api/routes/audit.py tests/unit/test_checkpoint_archive.py
git commit -m "feat(api): progress 端点过滤孤儿 point_run 并校正计数"
```

---

## Task 7: 前端 listCheckpoints 支持 include_archived

**Files:**
- Modify: `frontend/src/api/v3.ts:98-100`

- [ ] **Step 1: 修改 listCheckpoints 签名**

`frontend/src/api/v3.ts` 第 98-100 行替换为：

```typescript
export function listCheckpoints(
  includeArchived = false,
): Promise<CheckpointItem[]> {
  const params = includeArchived ? "?include_archived=true" : "";
  return request(`/api/v1/checkpoints${params}`);
}
```

- [ ] **Step 2: 给 CheckpointItem 类型加 archived 字段**

`frontend/src/types/ui.ts` 第 54-60 行的 `CheckpointItem` 接口改为：

```typescript
export interface CheckpointItem {
  id: string;
  kind: "final";
  status: string;
  payload_json: string; // JSON-encoded GovCheckpointPayload
  approved_by: string | null;
  archived?: boolean;
}
```

- [ ] **Step 3: 类型检查**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: 无类型错误（`listCheckpoints` 默认参数兼容现有无参调用）

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/v3.ts frontend/src/types/ui.ts
git commit -m "feat(web): listCheckpoints 支持 include_archived 参数"
```

---

## Task 8: 审查结果页加载 archived 并标注「已归档」

**Files:**
- Modify: `frontend/src/pages/AIReviewDetailPage.tsx:66-72`（PointRunView 类型）
- Modify: `frontend/src/pages/AIReviewDetailPage.tsx:214`（listCheckpoints 调用）
- Modify: `frontend/src/pages/AIReviewDetailPage.tsx:177-195`（pointRunViews 构建）
- Modify: `frontend/src/pages/AIReviewDetailPage.tsx:495-497` 和 `632-634`（标题渲染）

- [ ] **Step 1: PointRunView 类型增加 archived**

第 66-72 行的 `PointRunView` 类型改为：

```typescript
type PointRunView = {
  pr: AuditPointRun;
  checkpoint: GovCheckpointPayload | null;
  finding: GovFinding | null;
  title: string;
  verdict: string | null;
  archived: boolean;
};
```

- [ ] **Step 2: 加载时传 include_archived=true**

第 214 行：

```typescript
    Promise.all([listAuditRuns(), listCheckpoints()])
```
改为：
```typescript
    Promise.all([listAuditRuns(), listCheckpoints(true)])
```

- [ ] **Step 3: checkpointById 保留 archived 标志，pointRunViews 填充 archived**

第 177-195 行（`checkpointById` 与 `pointRunViews` 两个 useMemo）替换为：

```typescript
  const checkpointById = useMemo(
    () =>
      new Map(
        checkpoints.map((checkpoint) => [
          checkpoint.id,
          { parsed: checkpoint.parsed, archived: checkpoint.archived === true },
        ]),
      ),
    [checkpoints],
  );

  const pointRunViews = useMemo<PointRunView[]>(() => {
    return (progress?.point_runs ?? []).map((pr) => {
      const entry = checkpointById.get(pr.checkpoint_final_id) ?? null;
      const checkpoint = entry?.parsed ?? null;
      const finding = parseFindingJson(pr.finding_json);
      const verdict = finding?.verdict?.verdict ?? null;
      return {
        pr,
        checkpoint,
        finding,
        verdict,
        archived: entry?.archived ?? false,
        title: checkpoint?.title ?? `审核点 ${pr.checkpoint_final_id.slice(0, 8)}`,
      };
    });
  }, [checkpointById, progress]);
```

> 注：`toParsedCheckpoint`（第 90-93 行）已展开 CheckpointItem，`archived` 字段随展开保留，无需改动。

- [ ] **Step 4: 时间线卡片标题旁加「已归档」标签（第 495-497 行）**

把：
```tsx
                        <p className="line-clamp-2 text-sm font-medium text-text-primary">
                          {view.title}
                        </p>
```
改为：
```tsx
                        <p className="line-clamp-2 text-sm font-medium text-text-primary">
                          {view.title}
                          {view.archived && (
                            <Badge variant="secondary" className="ml-2 align-middle text-xs">
                              已归档
                            </Badge>
                          )}
                        </p>
```

- [ ] **Step 5: 列表视图标题旁加「已归档」标签（第 632-634 行）**

把：
```tsx
                        <span className="block line-clamp-2 text-sm font-medium text-text-primary">
                          {view.title}
                        </span>
```
改为：
```tsx
                        <span className="block line-clamp-2 text-sm font-medium text-text-primary">
                          {view.title}
                          {view.archived && (
                            <Badge variant="secondary" className="ml-2 align-middle text-xs">
                              已归档
                            </Badge>
                          )}
                        </span>
```

> `Badge` 已在第 41 行导入，无需新增 import。

- [ ] **Step 6: 类型检查**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: 无类型错误

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/AIReviewDetailPage.tsx
git commit -m "feat(web): 审查结果页加载归档审核点并标注「已归档」"
```

---

## Task 9: 审核点库页面归档响应提示

**Files:**
- Modify: `frontend/src/api/v3.ts:119-121`（deleteCheckpoint 返回类型）
- Modify: `frontend/src/pages/AuditLibraryPage.tsx:298-303`（confirmDelete）

- [ ] **Step 1: deleteCheckpoint 返回归档结果**

`frontend/src/api/v3.ts` 第 119-121 行替换为：

```typescript
export function deleteCheckpoint(
  id: string,
): Promise<{ action: "archived"; referenced_by: number } | undefined> {
  return request(`/api/v1/checkpoints/${id}`, { method: "DELETE" });
}
```

> 后端硬删返回 204，`request` 在 status 204 时返回 `undefined`（见 v3.ts:34）；归档返回 200+JSON。

- [ ] **Step 2: confirmDelete 处理归档提示**

`frontend/src/pages/AuditLibraryPage.tsx` 第 298-303 行的 `confirmDelete` 替换为：

```typescript
  async function confirmDelete() {
    if (!deletingId) return;
    const result = await deleteCheckpoint(deletingId);
    setDeletingId(null);
    if (result?.action === "archived") {
      window.alert(
        `该审核点被 ${result.referenced_by} 个历史审查任务引用，已自动归档（不再出现在审核点库中，历史审查结果仍可查看）。`,
      );
    }
    await loadSelectedLibrary();
  }
```

> 代码库无 toast 组件（已确认），MVP 用 `window.alert` 给律师明确反馈。

- [ ] **Step 3: 类型检查**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: 无类型错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/v3.ts frontend/src/pages/AuditLibraryPage.tsx
git commit -m "feat(web): 审核点归档时提示用户被历史任务引用"
```

---

## Task 10: 端到端验证（针对 stable 现网问题数据）

**Files:** 无（验证任务）

- [ ] **Step 1: 本地起后端**

Run:
```bash
source activate govdoc-auditor-v3 && export no_proxy="110.42.53.85,100.81.95.44,localhost,127.0.0.1" && export NO_PROXY="$no_proxy" && uvicorn govdoc.api.main:app --host 0.0.0.0 --port 8000
```
（后台运行；保持终端开启）

- [ ] **Step 2: 验证删除有引用的审核点→归档**

新终端：
```bash
source activate govdoc-auditor-v3 && python3 -c "
import os, requests
os.environ['NO_PROXY']='127.0.0.1,localhost'
# 取一个被 audit run 引用的 checkpoint id 替换 <CP_ID>
r = requests.delete('http://127.0.0.1:8000/api/v1/checkpoints/<CP_ID>')
print(r.status_code, r.text)
"
```
Expected: `200 {"action": "archived", "referenced_by": N}`

- [ ] **Step 3: 验证列表默认不含 archived，include_archived 可见**

```bash
source activate govdoc-auditor-v3 && python3 -c "
import os, requests
os.environ['NO_PROXY']='127.0.0.1,localhost'
a = requests.get('http://127.0.0.1:8000/api/v1/checkpoints').json()
b = requests.get('http://127.0.0.1:8000/api/v1/checkpoints?include_archived=true').json()
print('active only:', len(a), 'with archived:', len(b))
print('archived in b:', [x['id'] for x in b if x.get('archived')])
"
```
Expected: `with archived` 比 `active only` 多，且 archived 列表含刚归档的 id

- [ ] **Step 4: 验证 progress 端点对孤儿数据的过滤（如有历史硬删数据）**

```bash
source activate govdoc-auditor-v3 && python3 -c "
import os, requests, json
os.environ['NO_PROXY']='127.0.0.1,localhost'
# 用一个已知含孤儿引用的 audit_run_id
r = requests.get('http://127.0.0.1:8000/api/v1/audit/runs/<RUN_ID>/progress').json()
print('total:', r['total_count'], 'point_runs:', len(r['point_runs']))
"
```
Expected: `len(point_runs) == total_count`，无 checkpoint 不存在的条目

- [ ] **Step 5: 记录验证结果，停止后端**

把 Step 2-4 的实际输出粘贴到本计划的执行记录中，确认与 Expected 一致后停止 uvicorn。

---

## 验收标准

1. 删除无引用审核点 → 204，记录从库消失（硬删）
2. 删除被引用审核点 → 200 `{"action":"archived",...}`，记录 status=archived，从所有库解除关联
3. `GET /checkpoints` 默认不含 archived；`?include_archived=true` 含 archived 且带 `archived:true`
4. 重新导入同名审核点 → 历史 audit run 引用迁移到新 active 记录，旧 archived 记录被删
5. 审查结果页 archived 审核点正常显示标题/详情，标注「已归档」徽标
6. progress 端点对 checkpoint 已硬删的 point_run 过滤，计数同步校正
7. `tests/unit/` 全绿；`frontend` tsc 无错误

## 风险

| 风险 | 缓解 |
|------|------|
| SQLite 加列需 batch 模式 | migration 用 `op.batch_alter_table`（Task 1 已处理） |
| 删除端点状态码从固定 204 变为 204/200 双形态 | 前端 `request` 已正确处理 204→undefined；归档返回体显式判 `action` |
| dedup 的 keep 逻辑变更影响存量去重 | Task 5 Step 5 回归 `test_checkpoint_import.py` |
| 计数校正出现负数 | `max(..., 0)` / `max(..., len(visible))` 兜底（Task 6） |
