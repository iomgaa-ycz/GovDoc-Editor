# 审核部分失败恢复 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 审核任务有失败点时不再卡死——只要有 ≥1 个点完成就自动出（残缺）底稿，并提供批量「重试失败点」「跳过失败点」两条路推进到完整底稿；附历史回填脚本。

**Architecture:** 单一真相在后端 `_assemble_workpaper_draft`：completed 非空即渲染底稿，按有无 failed 分派 `draft_ready`/`partial_ready`。新增 `AuditPointRun.status == "excluded"` 软剔除（不计入总数、不重跑、不参与出底稿）。两个 run 级端点复用现有 `run_audit(point_run_ids=…)` 与单点重试的清 workspace 逻辑。前端加"部分完成"提示条 + 两按钮。

**Tech Stack:** Python 3.11 / FastAPI / SQLModel / SQLite / pytest；React + TS + vitest。环境 `govdoc-auditor-v3`，命令用 `source activate govdoc-auditor-v3 && …`（禁用 `conda run`）。

**设计依据:** `research-wiki/designs/2026-06-06-audit-partial-failure-recovery-design.md`

---

## 约定：状态与统计口径（贯穿全计划）

- `AuditPointRun.status`：`pending / running / completed / failed / excluded`。
- **有效总数** = 该 run 下 `status != "excluded"` 的点数。出现在四处，必须一致：`_resolve_point_runs`、`_assemble_workpaper_draft`、`get_audit_run_progress`、`create_audit_run`（新建无 excluded，天然一致）。
- **出底稿规则**：`C = completed 且有 finding_json 的数`，`F = status=="failed" 的数`（不含 excluded）。`C≥1 且 F=0 → draft_ready + 完整底稿`；`C≥1 且 F≥1 → partial_ready + 残缺底稿`；`C=0 → waiting_retry`，不出底稿。出底稿总是新版本号。

---

## Phase 1 — 后端核心：出底稿规则 + excluded 全链路

### Task 1: `_assemble_workpaper_draft` 改造（completed 非空即出稿）

**Files:**
- Modify: `govdoc/pipelines/audit_tender.py`（`_assemble_workpaper_draft`，约 L544-606）
- Test: `tests/unit/test_assemble_workpaper_draft.py`

- [ ] **Step 1: 写失败测试（三分支矩阵 + excluded 不计数）**

```python
# tests/unit/test_assemble_workpaper_draft.py
import json
import pytest
from sqlmodel import Session, SQLModel, create_engine
from govdoc.db.models import AuditRun, AuditPointRun, Document, WorkpaperDraft
from govdoc.pipelines.audit_tender import _assemble_workpaper_draft

FINDING = json.dumps({
    "checkpoint": {"id": "c1", "category": "x", "title": "t", "severity": "high",
                   "description": "d", "legal_basis": []},
    "verdict": {"verdict": "pass", "rationale": "r", "suggestion": None},
    "evidence": [],
}, ensure_ascii=False)

def _mk(session, n_completed, n_failed, n_excluded):
    run = AuditRun(project_id="p1", main_document_id="d1",
                   checkpoint_final_ids="[]", total_count=n_completed+n_failed+n_excluded)
    session.add(run); session.commit(); session.refresh(run)
    for i in range(n_completed):
        session.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id=f"c{i}",
                                  status="completed", finding_json=FINDING))
    for i in range(n_failed):
        session.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id=f"f{i}", status="failed"))
    for i in range(n_excluded):
        session.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id=f"e{i}", status="excluded"))
    session.commit(); session.refresh(run)
    return run

@pytest.fixture
def session(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/t.db")
    SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Document(id="d1", filename="t.pdf", file_type="pdf", file_size=1,
                       sha256="x", raw_path="/tmp/t.pdf", markdown_path="/tmp/t.md", status="ready"))
        s.commit()
        yield s

@pytest.mark.asyncio
async def test_all_completed_no_failed_draft_ready(session, monkeypatch):
    monkeypatch.setattr("govdoc.pipelines.audit_tender.render_workpaper_docx",
                        lambda *a, **k: "/tmp/wp.docx")
    run = _mk(session, 3, 0, 0)
    doc = session.get(Document, "d1")
    await _assemble_workpaper_draft(run, session, doc, None)
    session.commit()
    assert run.status == "draft_ready"
    assert session.query(WorkpaperDraft).filter_by(audit_run_id=run.id).count() == 1

@pytest.mark.asyncio
async def test_some_failed_generates_partial_draft(session, monkeypatch):
    monkeypatch.setattr("govdoc.pipelines.audit_tender.render_workpaper_docx",
                        lambda *a, **k: "/tmp/wp.docx")
    run = _mk(session, 2, 1, 0)
    doc = session.get(Document, "d1")
    await _assemble_workpaper_draft(run, session, doc, None)
    session.commit()
    assert run.status == "partial_ready"
    # 关键：残缺也出底稿（旧行为不出）
    assert session.query(WorkpaperDraft).filter_by(audit_run_id=run.id).count() == 1

@pytest.mark.asyncio
async def test_excluded_not_counted_as_failed(session, monkeypatch):
    monkeypatch.setattr("govdoc.pipelines.audit_tender.render_workpaper_docx",
                        lambda *a, **k: "/tmp/wp.docx")
    run = _mk(session, 2, 0, 2)  # 2 完成 + 2 剔除 + 0 失败
    doc = session.get(Document, "d1")
    await _assemble_workpaper_draft(run, session, doc, None)
    session.commit()
    assert run.status == "draft_ready"          # excluded 不算 failed
    assert run.total_count == 2                  # 有效总数扣掉 excluded

@pytest.mark.asyncio
async def test_zero_completed_waiting_retry(session, monkeypatch):
    run = _mk(session, 0, 2, 0)
    doc = session.get(Document, "d1")
    await _assemble_workpaper_draft(run, session, doc, None)
    session.commit()
    assert run.status == "waiting_retry"
    assert session.query(WorkpaperDraft).filter_by(audit_run_id=run.id).count() == 0
```

- [ ] **Step 2: 运行确认失败**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_assemble_workpaper_draft.py -v`
Expected: FAIL（残缺不出稿 / total 未扣 excluded）。

- [ ] **Step 3: 改实现**

把 `_assemble_workpaper_draft` 主体替换为：

```python
    all_runs = session.exec(
        select(AuditPointRun).where(AuditPointRun.audit_run_id == audit_run.id)
    ).all()
    completed_runs = [pr for pr in all_runs if pr.status == "completed" and pr.finding_json]
    failed_runs = [pr for pr in all_runs if pr.status == "failed"]  # excluded 不计

    # 有效总数：排除 excluded
    audit_run.total_count = sum(1 for pr in all_runs if pr.status != "excluded")

    if completed_runs:
        findings = [GovFinding.model_validate_json(pr.finding_json) for pr in completed_runs]
        workpaper = Workpaper(
            project_id=audit_run.project_id,
            tender_doc_path=tender_doc.raw_path,
            findings=findings,
            summary=generate_summary(findings),
        )
        current_versions = session.exec(
            select(WorkpaperDraft).where(WorkpaperDraft.audit_run_id == audit_run.id)
        ).all()
        next_version = max((d.version for d in current_versions), default=0) + 1
        draft_path = await asyncio.to_thread(
            render_workpaper_docx, workpaper, audit_run.id,
            template_path=template_path, version=next_version,
        )
        session.add(WorkpaperDraft(
            audit_run_id=audit_run.id,
            workpaper_json=workpaper.model_dump_json(),
            docx_path=str(draft_path),
            version=next_version,
        ))
        audit_run.status = "draft_ready" if not failed_runs else "partial_ready"
    else:
        audit_run.status = "waiting_retry"
```

同步更新 docstring 的"Status 分派规则"为新逻辑（残缺也出稿）。

- [ ] **Step 4: 运行确认通过**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_assemble_workpaper_draft.py -v`
Expected: 4 passed。

- [ ] **Step 5: 提交**

```bash
git add govdoc/pipelines/audit_tender.py tests/unit/test_assemble_workpaper_draft.py
git commit -m "feat(audit): 有完成点即生成（残缺）底稿，excluded 不计入失败/总数"
```

---

### Task 2: `_resolve_point_runs` 跳过 excluded + progress 端点排除 excluded

**Files:**
- Modify: `govdoc/pipelines/audit_tender.py`（`_resolve_point_runs` L271-301）
- Modify: `govdoc/api/routes/audit.py`（`get_audit_run_progress` L289-327、`_filter_orphan_point_runs`）
- Test: `tests/unit/test_resolve_and_progress_excluded.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_resolve_and_progress_excluded.py
from sqlmodel import Session, SQLModel, create_engine
from govdoc.db.models import AuditRun, AuditPointRun
from govdoc.pipelines.audit_tender import _resolve_point_runs

def _session(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/t.db"); SQLModel.metadata.create_all(eng)
    return Session(eng)

def test_resolve_skips_completed_and_excluded(tmp_path):
    s = _session(tmp_path)
    run = AuditRun(project_id="p", main_document_id="d", checkpoint_final_ids="[]")
    s.add(run); s.commit(); s.refresh(run)
    s.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id="a", status="completed"))
    s.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id="b", status="excluded"))
    s.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id="c", status="failed"))
    s.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id="e", status="pending"))
    s.commit()
    total, to_run = _resolve_point_runs(s, run, None)
    assert total == 3                                  # 4 - 1 excluded
    assert {pr.status for pr in to_run} == {"failed", "pending"}  # 跳过 completed+excluded
```

- [ ] **Step 2: 运行确认失败**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_resolve_and_progress_excluded.py -v`
Expected: FAIL（total=4 且 to_run 含 excluded）。

- [ ] **Step 3: 改实现**

`_resolve_point_runs` 内：

```python
    to_run = [
        pr
        for pr in point_runs
        if (selected is None or pr.id in selected)
        and pr.status not in ("completed", "excluded")
    ]
    total = sum(1 for pr in point_runs if pr.status != "excluded")
    return total, to_run
```

`get_audit_run_progress`：在构造 `point_runs` 后过滤掉 excluded，再走孤儿过滤：

```python
        point_runs = [
            pr for pr in session.exec(
                select(AuditPointRun).where(AuditPointRun.audit_run_id == audit_run_id)
            ).all()
            if pr.status != "excluded"
        ]
```

（`total_count`/`processed_count` 既有 `max(...)` 兜底逻辑保持不变即可。）

- [ ] **Step 4: 运行确认通过 + 跑既有 audit 测试不回归**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_resolve_and_progress_excluded.py tests/unit -k "audit or progress or assemble" -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add govdoc/pipelines/audit_tender.py govdoc/api/routes/audit.py tests/unit/test_resolve_and_progress_excluded.py
git commit -m "feat(audit): _resolve_point_runs 与 progress 端点忽略 excluded 点"
```

---

## Phase 2 — 后端批量端点

### Task 3: 批量重试失败点 `retry-failed`

**Files:**
- Modify: `govdoc/pipelines/audit_tender.py`（新增 `prepare_failed_points_retry`）
- Modify: `govdoc/api/routes/audit.py`（新增端点）
- Test: `tests/unit/test_retry_failed.py`

- [ ] **Step 1: 写失败测试（pipeline helper）**

```python
# tests/unit/test_retry_failed.py
from sqlmodel import Session, SQLModel, create_engine
from govdoc.db.models import AuditRun, AuditPointRun
from govdoc.pipelines.audit_tender import prepare_failed_points_retry

def _session(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/t.db"); SQLModel.metadata.create_all(eng)
    return Session(eng)

def test_prepare_failed_resets_all_failed_to_pending(tmp_path):
    s = _session(tmp_path)
    run = AuditRun(project_id="p", main_document_id="d", checkpoint_final_ids="[]", status="partial_ready")
    s.add(run); s.commit(); s.refresh(run)
    s.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id="a", status="completed"))
    f1 = AuditPointRun(audit_run_id=run.id, checkpoint_final_id="b", status="failed", error="x")
    f2 = AuditPointRun(audit_run_id=run.id, checkpoint_final_id="c", status="failed", error="y")
    s.add(f1); s.add(f2); s.commit()
    ids = prepare_failed_points_retry(run.id, s)
    assert set(ids) == {f1.id, f2.id}
    s.refresh(f1); s.refresh(run)
    assert f1.status == "pending" and f1.error is None
    assert run.status == "running"
```

- [ ] **Step 2: 运行确认失败**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_retry_failed.py -v`
Expected: FAIL（函数不存在）。

- [ ] **Step 3: 实现 pipeline helper**

在 `audit_tender.py` 顶部确保 `import shutil`（单点重试已用）。新增：

```python
def prepare_failed_points_retry(audit_run_id: str, session: Session) -> list[str]:
    """把某 run 下所有 failed 点重置为 pending（清产物 + 删旧 workspace），返回其 id 列表。

    复用 prepare_point_run_retry 的字段清理；workspace 删除沿用单点重试的 rmtree 策略。
    """
    failed = session.exec(
        select(AuditPointRun).where(
            AuditPointRun.audit_run_id == audit_run_id,
            AuditPointRun.status == "failed",
        )
    ).all()
    manager = get_workspace_manager()
    store = get_trajectory_store()
    ids: list[str] = []
    for pr in failed:
        old_ws = manager.workspaces_root / pr.id
        if old_ws.exists():
            shutil.rmtree(old_ws)
        _delete_trajectory_run(store, pr.id)
        pr.status = "pending"
        pr.error = None
        pr.usage_json = None
        pr.finding_json = None
        pr.completed_at = None
        pr.workspace_archive_path = None
        pr.workspace_failed_path = None
        session.add(pr)
        ids.append(pr.id)
    audit_run = session.get(AuditRun, audit_run_id)
    if audit_run is not None and ids:
        audit_run.status = "running"
        audit_run.error = None
        session.add(audit_run)
    session.commit()
    return ids
```

- [ ] **Step 4: 实现端点**

在 `audit.py` 新增（紧跟单点 retry 端点之后）：

```python
@router.post("/runs/{audit_run_id}/retry-failed", status_code=202)
async def retry_failed_points(audit_run_id: str, background_tasks: BackgroundTasks):
    """批量重试某审核任务下的全部失败点；跑完自动重新出底稿。"""
    from govdoc.pipelines.audit_tender import prepare_failed_points_retry, run_audit

    with get_db_session() as session:
        run = session.get(AuditRun, audit_run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="AuditRun 不存在")
        if run.status == "running":
            raise HTTPException(status_code=409, detail="任务正在运行，请稍后再试")
        point_ids = prepare_failed_points_retry(audit_run_id, session)
        if not point_ids:
            raise HTTPException(status_code=400, detail="没有失败的审核点可重试")

    async def _run():
        with get_db_session() as s:
            try:
                await run_audit(audit_run_id, s, point_run_ids=point_ids)
            except Exception:
                logger.exception("批量重试失败: %s", audit_run_id)

    background_tasks.add_task(_run)
    return {"audit_run_id": audit_run_id, "status": "retrying", "retry_count": len(point_ids)}
```

- [ ] **Step 5: 运行 + 提交**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_retry_failed.py -v`
Expected: PASS。
```bash
git add govdoc/pipelines/audit_tender.py govdoc/api/routes/audit.py tests/unit/test_retry_failed.py
git commit -m "feat(audit): 新增 retry-failed 批量重试失败点端点"
```

---

### Task 4: 批量跳过（剔除）失败点 `exclude-failed`

**Files:**
- Modify: `govdoc/pipelines/audit_tender.py`（新增 `exclude_failed_points`）
- Modify: `govdoc/api/routes/audit.py`（新增端点）
- Test: `tests/unit/test_exclude_failed.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_exclude_failed.py
import json, pytest
from sqlmodel import Session, SQLModel, create_engine
from govdoc.db.models import AuditRun, AuditPointRun, Document, WorkpaperDraft
from govdoc.pipelines.audit_tender import exclude_failed_points

FINDING = json.dumps({"checkpoint": {"id":"c","category":"x","title":"t","severity":"high",
    "description":"d","legal_basis":[]}, "verdict":{"verdict":"pass","rationale":"r","suggestion":None},
    "evidence":[]}, ensure_ascii=False)

@pytest.mark.asyncio
async def test_exclude_failed_reaches_draft_ready(tmp_path, monkeypatch):
    monkeypatch.setattr("govdoc.pipelines.audit_tender.render_workpaper_docx", lambda *a, **k: "/tmp/w.docx")
    eng = create_engine(f"sqlite:///{tmp_path}/t.db"); SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Document(id="d", filename="t.pdf", file_type="pdf", file_size=1, sha256="x",
                       raw_path="/tmp/t.pdf", markdown_path="/tmp/t.md", status="ready"))
        run = AuditRun(project_id="p", main_document_id="d", checkpoint_final_ids="[]",
                       status="partial_ready", total_count=3)
        s.add(run); s.commit(); s.refresh(run)
        s.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id="a", status="completed", finding_json=FINDING))
        s.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id="b", status="completed", finding_json=FINDING))
        s.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id="c", status="failed"))
        s.commit()
        n = await exclude_failed_points(run.id, s)
        s.refresh(run)
        assert n == 1
        assert run.status == "draft_ready"
        assert run.total_count == 2
        assert s.query(WorkpaperDraft).filter_by(audit_run_id=run.id).count() == 1
```

- [ ] **Step 2: 运行确认失败**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_exclude_failed.py -v`
Expected: FAIL（函数不存在）。

- [ ] **Step 3: 实现 pipeline 函数**

```python
async def exclude_failed_points(audit_run_id: str, session: Session,
                                *, template_path: str | Path | None = None) -> int:
    """把某 run 下全部 failed 点标记为 excluded，并立即重新出底稿。返回剔除数量。"""
    audit_run = session.get(AuditRun, audit_run_id)
    if audit_run is None:
        raise ValueError(f"未找到 AuditRun: {audit_run_id}")
    failed = session.exec(
        select(AuditPointRun).where(
            AuditPointRun.audit_run_id == audit_run_id,
            AuditPointRun.status == "failed",
        )
    ).all()
    for pr in failed:
        pr.status = "excluded"
        session.add(pr)
    session.commit()
    tender_doc = session.get(Document, audit_run.main_document_id)
    await _assemble_workpaper_draft(audit_run, session, tender_doc, template_path)
    session.add(audit_run)
    session.commit()
    return len(failed)
```

- [ ] **Step 4: 实现端点**

```python
@router.post("/runs/{audit_run_id}/exclude-failed", status_code=200)
async def exclude_failed_points_endpoint(audit_run_id: str):
    """跳过（剔除）某审核任务下全部失败点，立即重新出（完整）底稿。"""
    from govdoc.pipelines.audit_tender import exclude_failed_points

    with get_db_session() as session:
        run = session.get(AuditRun, audit_run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="AuditRun 不存在")
        if run.status == "running":
            raise HTTPException(status_code=409, detail="任务正在运行，请稍后再试")
        n = await exclude_failed_points(audit_run_id, session)
        if n == 0:
            raise HTTPException(status_code=400, detail="没有失败的审核点可跳过")
        run = session.get(AuditRun, audit_run_id)
        return {"audit_run_id": audit_run_id, "status": run.status, "excluded_count": n}
```

- [ ] **Step 5: 运行 + 提交**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_exclude_failed.py -v`
Expected: PASS。
```bash
git add govdoc/pipelines/audit_tender.py govdoc/api/routes/audit.py tests/unit/test_exclude_failed.py
git commit -m "feat(audit): 新增 exclude-failed 跳过失败点端点（软剔除+重出底稿）"
```

---

## Phase 3 — 前端

### Task 5: 前端 API 客户端

**Files:**
- Modify: `frontend/src/api/v3.ts`（紧邻 `retryPointRun` L265）
- Test: `frontend/tests/api/v3.test.ts`（追加用例）

- [ ] **Step 1: 写失败测试**

```ts
// frontend/tests/api/v3.test.ts 追加
it("retryFailedPoints POSTs to retry-failed", async () => {
  const spy = mockFetchOnce({ audit_run_id: "r1", status: "retrying", retry_count: 2 });
  const r = await retryFailedPoints("r1");
  expect(spy).toHaveBeenCalledWith(expect.stringContaining("/api/v1/audit/runs/r1/retry-failed"),
    expect.objectContaining({ method: "POST" }));
  expect(r.retry_count).toBe(2);
});
it("excludeFailedPoints POSTs to exclude-failed", async () => {
  const spy = mockFetchOnce({ audit_run_id: "r1", status: "draft_ready", excluded_count: 2 });
  const r = await excludeFailedPoints("r1");
  expect(spy).toHaveBeenCalledWith(expect.stringContaining("/api/v1/audit/runs/r1/exclude-failed"),
    expect.objectContaining({ method: "POST" }));
  expect(r.excluded_count).toBe(2);
});
```

（`mockFetchOnce` 用文件内现有的 fetch mock 工具；若命名不同，按现有测试风格对齐。）

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npm run test -- v3.test.ts`
Expected: FAIL（函数未导出）。

- [ ] **Step 3: 实现**

```ts
export function retryFailedPoints(
  auditRunId: string,
): Promise<{ audit_run_id: string; status: string; retry_count: number }> {
  return request(`/api/v1/audit/runs/${auditRunId}/retry-failed`, { method: "POST" });
}

export function excludeFailedPoints(
  auditRunId: string,
): Promise<{ audit_run_id: string; status: string; excluded_count: number }> {
  return request(`/api/v1/audit/runs/${auditRunId}/exclude-failed`, { method: "POST" });
}
```

- [ ] **Step 4: 运行 + 提交**

Run: `cd frontend && npm run test -- v3.test.ts`
Expected: PASS。
```bash
git add frontend/src/api/v3.ts frontend/tests/api/v3.test.ts
git commit -m "feat(web): v3 新增 retryFailedPoints/excludeFailedPoints"
```

---

### Task 6: 审核详情页 — 部分完成提示条 + 两按钮

**Files:**
- Modify: `frontend/src/pages/AIReviewDetailPage.tsx`（进度卡 L435-468 内注入提示条；新增 handler；展示残缺底稿）
- Test: `frontend/src/pages/AIReviewDetailPage.partial.test.tsx`（新建）

- [ ] **Step 1: 新增计数派生值与 handler**

在组件内（`progressPercent` 附近）加：

```tsx
const pointRuns = progress?.point_runs ?? [];
const completedCount = pointRuns.filter((p) => p.status === "completed").length;
const failedCount = pointRuns.filter((p) => p.status === "failed").length;
const isRunning = currentStatus === "running";
const isPartial = currentStatus === "partial_ready" || (failedCount > 0 && !isRunning);

async function handleRetryFailed() {
  try { await retryFailedPoints(auditRunId); setPollVersion((v) => v + 1); }
  catch (err) { setPageError(err instanceof Error ? err.message : "重试失败"); }
}
async function handleExcludeFailed() {
  try { await excludeFailedPoints(auditRunId); setPollVersion((v) => v + 1); }
  catch (err) { setPageError(err instanceof Error ? err.message : "跳过失败"); }
}
```

并 `import { retryFailedPoints, excludeFailedPoints } from "@/api/v3";`

- [ ] **Step 2: 注入提示条 JSX**

在进度卡 `<Progress value={progressPercent} />`（L451）之后插入：

```tsx
{isPartial && (
  <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
    <p>本次审核共 {totalCount} 个审核点：已完成 {completedCount} 个，{failedCount} 个未能完成。</p>
    <p className="mt-1">当前为「部分稿」，缺少未完成审核点的内容。</p>
    <div className="mt-2 flex gap-2">
      <Button size="sm" disabled={isRunning} onClick={handleRetryFailed}>
        重试未完成的 {failedCount} 项
      </Button>
      <Button size="sm" variant="outline" disabled={isRunning} onClick={handleExcludeFailed}>
        跳过这 {failedCount} 项并出完整稿
      </Button>
    </div>
  </div>
)}
{currentStatus === "draft_ready" && (
  <div className="rounded-md border border-green-300 bg-green-50 p-3 text-sm text-green-800">
    ✅ {totalCount} 个审核点全部完成，已生成完整底稿。
  </div>
)}
```

- [ ] **Step 3: 写 vitest 测试**

```tsx
// frontend/src/pages/AIReviewDetailPage.partial.test.tsx
import { render, screen } from "@testing-library/react";
// 用现有页面测试的渲染封装；mock getAuditRunProgress 返回 partial_ready + 2 failed
// 断言：出现「2 个未能完成」、「重试未完成的 2 项」「跳过这 2 项并出完整稿」按钮
// running 时两按钮 disabled；draft_ready 时显示绿色「全部完成」
```

（按 `AIReviewDetailPage` 既有测试的 mock 方式补全断言。）

- [ ] **Step 4: 运行 + 构建 + 提交**

Run: `cd frontend && npm run test -- AIReviewDetailPage && npm run build`
Expected: PASS + 构建成功。
```bash
git add frontend/src/pages/AIReviewDetailPage.tsx frontend/src/pages/AIReviewDetailPage.partial.test.tsx
git commit -m "feat(web): 审核详情页部分完成提示条 + 重试/跳过按钮"
```

---

### Task 7: 任务列表页「部分完成」标签

**Files:**
- Modify: `frontend/src/pages/AIReviewHubPage.tsx`
- Test: 同文件既有测试或新增小用例

- [ ] **Step 1: 在状态徽章处加分支**

对 `status === "partial_ready"` 的任务显示 `<Badge variant="outline">部分完成 {processed_count}/{total_count}</Badge>`，其余状态保持现有渲染。

- [ ] **Step 2: 运行 + 提交**

Run: `cd frontend && npm run test && npm run build`
```bash
git add frontend/src/pages/AIReviewHubPage.tsx
git commit -m "feat(web): 任务列表显示部分完成标签"
```

---

## Phase 4 — 历史回填 + 集成

### Task 8: 历史回填脚本

**Files:**
- Create: `scripts/backfill_partial_drafts.py`
- Test: `tests/unit/test_backfill_partial_drafts.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_backfill_partial_drafts.py
import json, pytest
from sqlmodel import Session, SQLModel, create_engine
from govdoc.db.models import AuditRun, AuditPointRun, Document, WorkpaperDraft
from scripts.backfill_partial_drafts import backfill

FINDING = json.dumps({"checkpoint":{"id":"c","category":"x","title":"t","severity":"high",
    "description":"d","legal_basis":[]},"verdict":{"verdict":"pass","rationale":"r","suggestion":None},
    "evidence":[]}, ensure_ascii=False)

@pytest.mark.asyncio
async def test_backfill_generates_draft_for_partial(tmp_path, monkeypatch):
    monkeypatch.setattr("govdoc.pipelines.audit_tender.render_workpaper_docx", lambda *a, **k: "/tmp/w.docx")
    eng = create_engine(f"sqlite:///{tmp_path}/t.db"); SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Document(id="d", filename="t.pdf", file_type="pdf", file_size=1, sha256="x",
                       raw_path="/tmp/t.pdf", markdown_path="/tmp/t.md", status="ready"))
        run = AuditRun(project_id="p", main_document_id="d", checkpoint_final_ids="[]",
                       status="partial_ready", total_count=2)
        s.add(run); s.commit(); s.refresh(run)
        s.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id="a", status="completed", finding_json=FINDING))
        s.add(AuditPointRun(audit_run_id=run.id, checkpoint_final_id="b", status="failed"))
        s.commit()
        n = await backfill(s)
        assert n == 1
        assert s.query(WorkpaperDraft).filter_by(audit_run_id=run.id).count() == 1
```

- [ ] **Step 2: 运行确认失败**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_backfill_partial_drafts.py -v`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现脚本**

```python
"""一次性回填：给历史卡死的 partial_ready/waiting_retry 任务补生成（残缺）底稿。

用法（4090 服务器, govdoc-auditor-v3 环境，须先 export NO_PROXY + HF_HUB_OFFLINE=1）：
    python scripts/backfill_partial_drafts.py
"""
from __future__ import annotations
import asyncio, logging
from sqlmodel import Session, select
from govdoc.api.deps import get_db_session
from govdoc.db.models import AuditRun, AuditPointRun, Document
from govdoc.pipelines.audit_tender import _assemble_workpaper_draft

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill")

async def backfill(session: Session) -> int:
    """对所有 partial_ready/waiting_retry 且有 ≥1 完成点的任务重出底稿，返回处理数。"""
    runs = session.exec(
        select(AuditRun).where(AuditRun.status.in_(["partial_ready", "waiting_retry"]))
    ).all()
    done = 0
    for run in runs:
        has_completed = session.exec(
            select(AuditPointRun).where(
                AuditPointRun.audit_run_id == run.id,
                AuditPointRun.status == "completed",
            )
        ).first()
        if not has_completed:
            logger.info("跳过（无完成点）: %s", run.id); continue
        tender = session.get(Document, run.main_document_id)
        await _assemble_workpaper_draft(run, session, tender, None)
        session.add(run); session.commit()
        logger.info("已回填 %s -> %s", run.id, run.status)
        done += 1
    return done

async def main() -> None:
    with get_db_session() as s:
        s.connection().exec_driver_sql("PRAGMA busy_timeout=30000")
        n = await backfill(s)
        logger.info("回填完成，共处理 %d 个任务", n)

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: 运行 + 提交**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_backfill_partial_drafts.py -v`
Expected: PASS。
```bash
git add scripts/backfill_partial_drafts.py tests/unit/test_backfill_partial_drafts.py
git commit -m "feat(audit): 历史卡死任务残缺底稿回填脚本"
```

---

### Task 9: 集成测试（replay fixture，不调真 LLM）

**Files:**
- Create: `tests/integration/test_partial_failure_flow.py`

- [ ] **Step 1: 写集成测试**

用 `run_audit(..., replay_dir=…)` 配合一个"含 1 个失败点"的 replay fixture（参照 `tests/fixtures/mock_agent_trajectories/`），断言：
1. 跑完 `status == "partial_ready"` 且生成了 1 份残缺底稿；
2. 调 `exclude_failed_points` 后 `status == "draft_ready"`、`total_count` 减 1、生成完整底稿新版本。

```python
import pytest
from govdoc.pipelines.audit_tender import run_audit, exclude_failed_points
# 复用 tests/integration/conftest.py 既有 fixture 装配 AuditRun + replay_dir
# （按现有集成测试风格组织；replay fixture 制造 1 个失败点）

@pytest.mark.asyncio
async def test_partial_then_exclude_to_complete(audit_run_with_one_failure, session):
    run = await run_audit(audit_run_with_one_failure, session, replay_dir="tests/fixtures/replay_one_fail")
    assert run.status == "partial_ready"
    n = await exclude_failed_points(run.id, session)
    assert n >= 1
    session.refresh(run)
    assert run.status == "draft_ready"
```

- [ ] **Step 2: 运行 + 提交**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/integration/test_partial_failure_flow.py -v`
Expected: PASS。
```bash
git add tests/integration/test_partial_failure_flow.py tests/fixtures/replay_one_fail
git commit -m "test(audit): 部分失败→残缺底稿→跳过→完整底稿 集成测试"
```

---

## 收尾：全量校验

- [ ] **Step 1: 后端全测 + 覆盖率**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit tests/contract tests/integration -q`
Expected: 全绿。

- [ ] **Step 2: 前端全测 + 构建 + lint**

Run: `cd frontend && npm run test && npm run build && cd .. && source activate govdoc-auditor-v3 && ruff check govdoc scripts --fix && ruff format govdoc scripts`

- [ ] **Step 3: 文档同步**

更新 `research-wiki/designs/2026-06-06-audit-partial-failure-recovery-design.md` 若实现有偏差；`AuditPointRun.status` 行内注释加 `excluded`。

---

## 部署与历史回填（实现合并到 stable 后）

1. 正常 `feat → master`（PR + 审查）→ 部署 testing 验证；
2. `git checkout stable && git merge master && git push origin stable`；
3. `bash scripts/deploy.sh --target stable`；
4. **部署后**在 4090 跑回填（先 `export NO_PROXY=110.42.53.85,100.81.95.44,100.83.164.94,localhost,127.0.0.1 HF_HUB_OFFLINE=1`）：
   `source activate govdoc-auditor-v3 && python scripts/backfill_partial_drafts.py`
5. 抽查一个历史 partial_ready 任务前端是否已显示残缺底稿 + 提示条按钮可用。

## 验收标准

- 有失败点的任务跑完即出残缺底稿、不再卡死（`partial_ready` + 底稿可见/可下载）。
- 前端清晰显示「X/N 已完成、M 未能完成」+「重试」「跳过」两按钮；running 时禁用。
- 「重试」全成功 或 「跳过」→ `draft_ready` + 完整底稿（新版本）。
- `excluded` 不计入总数/失败/重跑，全链路一致。
- 历史卡死任务经回填脚本补出底稿。
- 后端 ≥80% 覆盖；前端单测 + 构建通过。
