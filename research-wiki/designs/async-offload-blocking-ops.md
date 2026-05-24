---
type: design
node_id: design:async-offload-blocking-ops
title: "async offload: 解除 run_audit 同步阻塞事件循环"
date: 2026-05-24
---

# async offload: 解除 run_audit 同步阻塞事件循环

## 问题

`run_audit()` 是 async 函数，在 FastAPI `BackgroundTask` 中执行。内部直接调用 4 个同步阻塞函数，阻塞 uvicorn 单 worker 的 asyncio 事件循环，导致：

1. **progress 轮询无法响应**：前端每 2s 轮询 `/api/v1/audit/runs/{id}/progress`，但事件循环被阻塞 30-60s（qmd embedding），请求堆积无响应
2. **前端 UI 不更新**：`auditProgress` 保持 null，"审核进行中"不显示
3. **E2E 测试 networkidle 永远不触发**：progress 轮询不停 + 后端不响应 = Playwright 判定网络不空闲

## 阻塞函数清单

| 函数 | 阻塞操作 | 耗时 | 位置 |
|------|---------|------|------|
| `_index_tender_doc()` | qmd embedding (Qwen3-Embedding-0.6B) | 30-60s | L672 |
| `_persist_point_result()` | workspace 归档压缩 | 数秒 | L724 |
| `_assemble_workpaper_draft()` | docxtpl DOCX 渲染 | 数秒 | L752 |
| `_cleanup_tender_collection()` | qmd collection 删除 | <1s | L766 |

## 方案：async 编排 + `asyncio.to_thread()` offload

### 核心原则

- `run_audit()` 保持 async，作为**编排层**——状态管理、DB 写入、进度更新留在事件循环
- 同步重活通过 `await asyncio.to_thread(fn, ...)` offload 到默认线程池
- 被 offload 的函数**不接收 session**，避免 SQLite 线程安全问题

### 后端改动

**`govdoc/pipelines/audit_tender.py`**：

```python
# run_audit() 内，4 处阻塞调用改为：
tender_collection = await asyncio.to_thread(
    _index_tender_doc, audit_run, tender_doc,
    supplementary_docs=supplementary_docs, replay=replay_dir is not None,
)

await asyncio.to_thread(_persist_point_result, point_run, result, workspace, checkpoint, manager)

# _assemble_workpaper_draft 使用 session → 拆分：DB 查询主线程，DOCX 渲染 offload
await asyncio.to_thread(_assemble_workpaper_draft, audit_run, session, tender_doc, template_path)

# finally 中：
await asyncio.to_thread(_cleanup_tender_collection, tender_collection, replay=replay_dir is not None)
```

**线程安全约束**：
- `_index_tender_doc`：不使用 session ✓
- `_persist_point_result`：不使用 session ✓（只操作文件和 workspace manager）
- `_assemble_workpaper_draft`：**使用 session** → 需拆分为 DB 查询（主线程）+ DOCX 渲染（offload）
- `_cleanup_tender_collection`：不使用 session ✓

### 前端改动

**`frontend/src/context/V3WorkbenchContext.tsx`**：

`startAuditProgressPolling` 和 `startExtractProgressPolling` 加 `document.visibilitychange` 监听：
- 页面不可见 → 暂停轮询（`clearInterval`）
- 页面恢复可见 → 立即恢复轮询（重新 `setInterval`）

### 不改的

- uvicorn 配置（单 worker，offload 后不再阻塞）
- 轮询间隔（2s 保持不变）
- E2E 测试（上一个 commit 已用超时+选择器修复，后端修复后更稳定）

## 验证计划

1. 手动验证：启动审核后在 embedding 期间 curl `/healthz` 和 `/progress` 确认响应不阻塞
2. E2E 全量跑通（test-05 耗时应显著下降）

## 被否决的方案

- **方案 A（逐调用包装）**：功能等价但散落无序的 `to_thread`，不够优雅
- **方案 B（`@blocking` 装饰器）**：改变函数签名（sync→async），增加间接层，MVP 不值得

