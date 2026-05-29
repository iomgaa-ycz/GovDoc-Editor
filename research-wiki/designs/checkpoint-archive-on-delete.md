---
type: design
node_id: design:checkpoint-archive-on-delete
title: 审核点删除归档与数据一致性设计
date: 2026-05-29
---

# 审核点删除归档与数据一致性设计

## 1. 问题背景

审核点（CheckpointFinal）被手动删除后，引用它的已完成审查任务（AuditPointRun）成为"孤儿数据"：

- 前端通过 `checkpoint_final_id` 去 checkpoints 列表匹配名字，匹配失败后显示 ID 前 8 位（如「审核点 0a09777f」）
- 详情弹窗因 checkpoint 为 null 显示「暂无审查点详情」，实际 finding_json 数据完整

**根因：** 删除端点（`delete_checkpoint`）只级联删除了 CheckpointLibraryItem，完全未检查 AuditPointRun 引用。而导入去重逻辑（`deduplicate_existing_checkpoints`）已有完善的引用迁移（`_rewire_checkpoint_references`），但删除端点未复用。

## 2. 设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 删除策略 | 无引用→硬删，有引用→归档 | 引用计数驱动的生命周期，兼顾灵活和安全 |
| 归档实现 | CheckpointFinal 加 `status` 字段 | 比 `deleted_at` 语义更清晰，MVP 不需要撤销 |
| 归档后可见范围 | 库列表隐藏，审查结果页标记「已归档」 | 不影响库管理，历史结果保留上下文 |
| 删除确认交互 | 透明提示「被 N 个任务引用，将自动归档」 | 律师能理解发生了什么，不需要理解技术细节 |
| 导入同名审核点时 | 自动迁移历史引用到新版，硬删旧归档记录 | 复用 `_rewire_checkpoint_references`，finding_json 保留历史快照不被篡改 |
| 孤儿 point_run 处理 | 后端 progress API 过滤，数据库保留 | 前端零感知，数据保留供排查 |

### 被否决的方案

- **方案 A（仅前端容错）：** 从 finding_json 读取审核点信息做 fallback。只治标不治本，下次删除仍会产生不一致。
- **方案 C（全软删除）：** 所有删除都用 `deleted_at` 时间戳。MVP 阶段不需要撤销功能，过度工程化。
- **前端显示孤儿数据 fallback：** 从 finding_json 中恢复展示。设计上归档记录始终保留，不应出现"查不到"；真正查不到说明数据损坏，硬拼凑展示反而误导律师，不如直接隐藏。

## 3. 数据库变更

**CheckpointFinal 新增字段：**

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `status` | `str` | `"active"` | `active` = 正常可用，`archived` = 被引用但用户已"删除" |

Migration：现有记录全部填充 `status = "active"`。

## 4. 后端删除端点改造

**`DELETE /api/v1/checkpoints/{checkpoint_id}`**

```
收到删除请求
  │
  ├─ 查询是否有 AuditPointRun 引用此 checkpoint_final_id
  │
  ├─ 无引用 → 硬删除（现有行为不变，返回 204）
  │
  └─ 有引用 → 归档：
       ├─ checkpoint.status = "archived"
       ├─ 级联删除 CheckpointLibraryItem（从库中移除）
       ├─ 记录审计日志（action="archive_checkpoint"）
       └─ 返回 200 + { "action": "archived", "referenced_by": N }
```

| 情况 | 旧响应 | 新响应 |
|------|--------|--------|
| 无引用 | 204 | 204（不变） |
| 有引用 | 204（静默删除，留孤儿） | 200 + JSON |
| 不存在 | 404 | 404（不变） |

## 5. 导入时的归档迁移

扩展 `deduplicate_existing_checkpoints`，去重候选范围纳入 archived 记录：

```
导入新审核点（title = "2.逾期退还保证金。"）
  │
  ├─ 现有去重：active 记录间去重（不变）
  │
  └─ 新增：检查是否有同 title 的 archived 记录
       │
       ├─ 无 → 正常导入
       └─ 有 → _rewire_checkpoint_references(archived_id → new_id)
              → 硬删 archived 记录
              → 日志记录迁移详情
```

核心迁移逻辑完全复用现有 `_rewire_checkpoint_references`，不新增函数。

## 6. 后端 progress 端点过滤

**`GET /api/v1/audit/runs/{id}/progress`**

返回 point_runs 之前，过滤掉 checkpoint_final_id 在 CheckpointFinal 表中不存在的记录，同步调整 `total_count` / `processed_count`。

孤儿 point_run 数据库中保留不删除，仅 API 层过滤。

## 7. 前端改造

| 页面 | 改动 |
|------|------|
| **审核点库页面（AuditLibraryPage）** | 删除响应为 `{ action: "archived" }` 时 toast「该审核点被 N 个历史审查任务引用，已自动归档」 |
| **审查结果页（AIReviewDetailPage）** | `listCheckpoints` 加 `include_archived=true` 参数；archived 审核点正常渲染，标题旁灰色「已归档」标签 |
| **API 层（v3.ts）** | `listCheckpoints` 支持 `include_archived` 参数 |

**不改：** PointInsight 组件、WorkpaperEditor、工作底稿逻辑。

## 8. 完整变更清单

| 层 | 文件 | 改动 | 类型 |
|---|------|------|------|
| DB | `govdoc/db/models.py` | CheckpointFinal 加 `status` 字段 | MODIFY |
| DB | `govdoc/db/migrations/` | 新 Alembic migration | NEW |
| 后端 | `govdoc/api/routes/checkpoints.py` · `delete_checkpoint` | 有引用→归档，无引用→硬删 | MODIFY |
| 后端 | `govdoc/api/routes/checkpoints.py` · `deduplicate_existing_checkpoints` | 去重范围扩展到 archived | MODIFY |
| 后端 | `govdoc/api/routes/checkpoints.py` · `list_checkpoints` | 默认 active，支持 `include_archived` | MODIFY |
| 后端 | `govdoc/api/routes/audit.py` · progress 端点 | 过滤孤儿 point_run，调整计数 | MODIFY |
| 前端 | `frontend/src/api/v3.ts` | `listCheckpoints` 加参数 | MODIFY |
| 前端 | `frontend/src/pages/AIReviewDetailPage.tsx` | 传 `include_archived=true`，archived 标签 | MODIFY |
| 前端 | `frontend/src/pages/AuditLibraryPage.tsx` | archived 响应 toast | MODIFY |
