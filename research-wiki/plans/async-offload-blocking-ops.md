---
type: plan
node_id: plan:async-offload-blocking-ops
title: "async offload 实现计划"
date: 2026-05-24
---

# async offload 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 解除 `run_audit()` 中同步阻塞函数对 asyncio 事件循环的阻塞，使 progress 轮询在审核期间正常响应。

**Architecture:** `run_audit()` 保持 async 编排层，4 处同步重活（qmd embedding、workspace 归档、DOCX 渲染、collection 清理）通过 `asyncio.to_thread()` offload 到线程池。`_assemble_workpaper_draft` 因使用 session 需拆分为 DB 查询（主线程）+ DOCX 渲染（offload）。前端轮询加 `visibilitychange` 暂停。

**Tech Stack:** Python `asyncio.to_thread` (3.9+)、React `document.visibilitychange`

---

## 文件变更清单

| 文件 | 操作 | 职责 |
|------|------|------|
| `govdoc/pipelines/audit_tender.py` | MODIFY | `run_audit` 4 处阻塞调用 → `to_thread`；拆分 `_assemble_workpaper_draft` |
| `frontend/src/context/V3WorkbenchContext.tsx` | MODIFY | 轮询加 visibility 暂停 |

---

### Task 1: offload `_index_tender_doc`

**Files:**
- Modify: `govdoc/pipelines/audit_tender.py:672-677`

- [ ] **Step 1: 修改 `run_audit` 中 `_index_tender_doc` 调用**

将 L672-677 的直接调用改为 `await asyncio.to_thread(...)`：

```python
# 原代码（L672-677）：
    tender_collection = _index_tender_doc(
        audit_run,
        tender_doc,
        supplementary_docs=supplementary_docs,
        replay=replay_dir is not None,
    )

# 改为：
    tender_collection = await asyncio.to_thread(
        _index_tender_doc,
        audit_run,
        tender_doc,
        supplementary_docs=supplementary_docs,
        replay=replay_dir is not None,
    )
```

线程安全验证：`_index_tender_doc` 不接收 session，内部只操作 qmd client 和文件系统 ✓

- [ ] **Step 2: 运行单元测试确认无破坏**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v --timeout=30 -q
```

预期：全部 PASS

- [ ] **Step 3: 提交**

```bash
git add govdoc/pipelines/audit_tender.py
git commit -m "perf: offload _index_tender_doc 到线程池避免阻塞事件循环"
```

---

### Task 2: offload `_persist_point_result`

**Files:**
- Modify: `govdoc/pipelines/audit_tender.py:724`

- [ ] **Step 1: 修改 `run_audit` 中 `_persist_point_result` 调用**

将 L724 的直接调用改为 `await asyncio.to_thread(...)`：

```python
# 原代码（L724）：
                _persist_point_result(point_run, result, workspace, checkpoint, manager)

# 改为：
                await asyncio.to_thread(
                    _persist_point_result, point_run, result, workspace, checkpoint, manager,
                )
```

线程安全验证：`_persist_point_result` 不接收 session，不调用 `session.commit/add`（docstring 明确标注）；只操作 point_run 对象字段（Python GIL 保护）和 workspace manager ✓

- [ ] **Step 2: 运行单元测试确认无破坏**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v --timeout=30 -q
```

预期：全部 PASS

- [ ] **Step 3: 提交**

```bash
git add govdoc/pipelines/audit_tender.py
git commit -m "perf: offload _persist_point_result 到线程池"
```

---

### Task 3: 拆分 `_assemble_workpaper_draft` 并 offload DOCX 渲染

**Files:**
- Modify: `govdoc/pipelines/audit_tender.py:534-595` 和 `run_audit` L751-752

`_assemble_workpaper_draft` 使用 session（查询 point_runs、写入 WorkpaperDraft），不能整体 offload。拆分为：
- **DB 查询 + 状态判定**留在主线程（使用 session）
- **`render_workpaper_docx`**（CPU 密集的 DOCX 渲染）offload 到线程池

- [ ] **Step 1: 将 `_assemble_workpaper_draft` 改为 async**

```python
async def _assemble_workpaper_draft(
    audit_run: AuditRun,
    session: Session,
    tender_doc: TenderDoc,
    template_path: str | Path | None,
) -> None:
    """按 completed point_runs 汇总 findings，生成 WorkpaperDraft，更新 audit_run.status。

    DB 查询和状态判定在事件循环线程执行，DOCX 渲染 offload 到线程池。
    **不**调 ``session.commit``；调用方负责 DB 提交。
    """
    all_runs = session.exec(
        select(AuditPointRun).where(AuditPointRun.audit_run_id == audit_run.id)
    ).all()
    completed_runs = [pr for pr in all_runs if pr.status == "completed" and pr.finding_json]
    failed_runs = [pr for pr in all_runs if pr.status == "failed"]

    if completed_runs and not failed_runs:
        findings = [GovFinding.model_validate_json(pr.finding_json) for pr in completed_runs]
        workpaper = Workpaper(
            project_id=audit_run.project_id,
            tender_doc_path=tender_doc.storage_path,
            findings=findings,
            summary=generate_summary(findings),
        )
        current_versions = session.exec(
            select(WorkpaperDraft).where(WorkpaperDraft.audit_run_id == audit_run.id)
        ).all()
        next_version = max((d.version for d in current_versions), default=0) + 1

        # DOCX 渲染是 CPU 密集操作 → offload 到线程池
        draft_path = await asyncio.to_thread(
            render_workpaper_docx,
            workpaper,
            audit_run.id,
            template_path=template_path,
            version=next_version,
        )

        session.add(
            WorkpaperDraft(
                audit_run_id=audit_run.id,
                workpaper_json=workpaper.model_dump_json(),
                docx_path=str(draft_path),
                version=next_version,
            )
        )
        audit_run.status = "draft_ready"
    elif completed_runs and failed_runs:
        audit_run.status = "partial_ready"
    else:
        audit_run.status = "waiting_retry"
```

- [ ] **Step 2: 修改 `run_audit` 中的调用为 await**

```python
# 原代码（L751-752）：
        if audit_run.status != "cancelled":
            _assemble_workpaper_draft(audit_run, session, tender_doc, template_path)

# 改为：
        if audit_run.status != "cancelled":
            await _assemble_workpaper_draft(audit_run, session, tender_doc, template_path)
```

- [ ] **Step 3: 运行单元测试确认无破坏**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v --timeout=30 -q
```

预期：全部 PASS

- [ ] **Step 4: 提交**

```bash
git add govdoc/pipelines/audit_tender.py
git commit -m "perf: 拆分 _assemble_workpaper_draft，offload DOCX 渲染到线程池"
```

---

### Task 4: offload `_cleanup_tender_collection`

**Files:**
- Modify: `govdoc/pipelines/audit_tender.py:765-766`

- [ ] **Step 1: 修改 `run_audit` finally 块中的调用**

```python
# 原代码（L765-766）：
    finally:
        _cleanup_tender_collection(tender_collection, replay=replay_dir is not None)

# 改为：
    finally:
        await asyncio.to_thread(
            _cleanup_tender_collection, tender_collection, replay=replay_dir is not None,
        )
```

注意：`finally` 块中使用 `await` 在 Python 3.11 async 函数中是完全合法的。

线程安全验证：`_cleanup_tender_collection` 不接收 session，内部只调用 `get_qmd().delete_collection()` ✓

- [ ] **Step 2: 运行单元测试确认无破坏**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v --timeout=30 -q
```

预期：全部 PASS

- [ ] **Step 3: 提交**

```bash
git add govdoc/pipelines/audit_tender.py
git commit -m "perf: offload _cleanup_tender_collection 到线程池"
```

---

### Task 5: 前端轮询加 visibility 暂停

**Files:**
- Modify: `frontend/src/context/V3WorkbenchContext.tsx:293-318` (pollExtractRun) 和 `414-428` (startAuditProgressPolling)

- [ ] **Step 1: 在 Provider 组件中添加 visibility 暂停逻辑**

在 `V3WorkbenchProvider` 函数体中（现有 `useEffect` 附近），添加一个 effect 管理 visibility 暂停：

```tsx
// 页面不可见时暂停所有轮询，恢复可见时重启
useEffect(() => {
  function handleVisibility() {
    if (document.hidden) {
      if (progressRef.current) {
        clearInterval(progressRef.current);
        progressRef.current = null;
      }
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    } else {
      // 恢复可见时，重启活跃的轮询
      if (selectedAuditRunIdRef.current && auditProgress && !terminalAuditStatuses.includes(auditProgress.status)) {
        startAuditProgressPolling(selectedAuditRunIdRef.current);
      }
      if (extractingRuleSourceId && extractRunIdRef.current) {
        pollExtractRun(extractingRuleSourceId, extractRunIdRef.current);
      }
    }
  }
  document.addEventListener("visibilitychange", handleVisibility);
  return () => document.removeEventListener("visibilitychange", handleVisibility);
}, [auditProgress, extractingRuleSourceId]);
```

需要为 extract run ID 增加一个 ref 以便在 visibility 恢复时重启轮询：

```tsx
const extractRunIdRef = useRef<string | null>(null);
```

在 `pollExtractRun` 中保存 run ID：

```tsx
async function pollExtractRun(ruleId: string, runId: string) {
    extractRunIdRef.current = runId;  // 新增
    if (pollRef.current) clearInterval(pollRef.current);
    // ... 后续不变
}
```

在 `pollExtractRun` 的 terminal 分支中清除 ref：

```tsx
if (status.status === "draft_ready") {
    // ... 现有清理 ...
    extractRunIdRef.current = null;  // 新增
} else if (status.status === "failed") {
    // ... 现有清理 ...
    extractRunIdRef.current = null;  // 新增
}
```

- [ ] **Step 2: 运行前端类型检查**

```bash
cd frontend && npx tsc --noEmit
```

预期：无错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/context/V3WorkbenchContext.tsx
git commit -m "perf: 前端轮询在页面不可见时暂停，恢复时重启"
```

---

### Task 6: 集成验证

- [ ] **Step 1: 运行全量单元测试**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v --timeout=30 -q
```

预期：全部 PASS

- [ ] **Step 2: 部署 testing 环境**

```bash
export NO_PROXY="100.83.164.94,100.70.102.30,110.42.53.85,localhost,127.0.0.1"
export no_proxy="$NO_PROXY"
git push origin master
bash scripts/deploy.sh --target testing
```

- [ ] **Step 3: 手动验证事件循环不阻塞**

在测试服务器启动一次审核，同时 curl healthz 验证响应不阻塞：

```bash
# 启动审核后立即运行（在 qmd embedding 进行中）
curl -w "\nHTTP %{http_code} in %{time_total}s\n" http://100.83.164.94:8001/healthz
```

预期：在 embedding 期间仍然 <1s 响应，而非之前的 30-60s 挂起。

- [ ] **Step 4: 运行 E2E 全量测试**

```bash
export NO_PROXY="100.70.102.30,100.83.164.94,110.42.53.85,localhost,127.0.0.1"
bash frontend/e2e/run-tests.sh
```

预期：15/15 PASS。test-05 的"审核进行中"应该在 ~5s 内出现（而非之前的 ~115s）。

- [ ] **Step 5: 最终提交（如有调整）**

```bash
git add -A && git commit -m "fix: 集成验证修复"
```

