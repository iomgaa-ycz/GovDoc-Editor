# 移除审核点草稿流程计划

> 日期：2026-04-27
> 分支：`chore/remove-checkpoint-drafts`
> 目标：审核点入库统一为“直接入库可审核运行的审核点”，不再维护 `CheckpointDraft` 草稿态。

## 背景

当前代码中存在 `CheckpointDraft` / `CheckpointFinal` 两套模型，但主流程已经绕过草稿审核：

- AI 提取成功后同时写 `CheckpointDraft(status="promoted")` 和 `CheckpointFinal`。
- 审核运行只接受 `CheckpointFinal` ID。
- 前端启动审核只展示 `kind === "final"` 的审核点。
- 表格导入仍只写 `CheckpointDraft(status="draft")`，导致导入结果无法直接参与审核。

这个状态会让用户以为存在“草稿确认 -> 终稿入库”的完整流程，但实际没有对应的确认 API 和前端入口。

## 产品口径

本次改为单一路径：

- 审核点库只维护已入库审核点。
- AI 提取直接写入 `CheckpointFinal`。
- 表格导入直接写入 `CheckpointFinal`。
- 编辑、删除均直接操作已入库审核点。
- 保留 `CheckpointFinal` 表名以降低本次迁移风险，后续可单独重命名为 `Checkpoint`。

## 后端改动

- 删除 `CheckpointDraft` SQLModel 与导出。
- `run_extract()` 不再写 promoted draft，只写 `CheckpointFinal`。
- `/api/v1/checkpoints` 不再合并 draft/final，只返回终稿审核点。
- `/api/v1/checkpoints/import` 返回 `checkpoints`，并直接创建 `CheckpointFinal(approved_by="system:import")`。
- `PUT/DELETE /api/v1/checkpoints/{id}` 只操作 `CheckpointFinal`。
- 移除 `/api/v1/rules/{rule_id}/checkpoints/drafts`。
- 新增 Alembic 迁移：将未 promoted 的旧草稿迁移为 `CheckpointFinal(approved_by="migration:checkpoint-draft")`，再删除 `checkpointdraft` 表。

## 前端改动

- `CheckpointItem.kind` 固定为 `"final"`。
- 移除草稿计数和草稿 badge。
- 导入文案改为“直接导入审核点库”。
- 导入 API 响应字段从 `drafts` 改为 `checkpoints`。
- 删除 `listCheckpointDrafts()` 客户端函数。

## 测试改动

- Pipeline A 合约测试只断言 `CheckpointFinal`。
- 导入 E2E fixture 从 `imported_drafts` 改为 `imported_checkpoints`。
- 法规提取 E2E 不再访问 drafts endpoint，改为检查 `/api/v1/checkpoints` 中存在可用审核点。
- 前端相关类型和页面测试同步更新。

## 验证

- `pytest tests/contract/test_pipeline_a_with_mocks.py tests/unit/test_checkpoint_import.py tests/e2e/test_03_checkpoint_import.py`
- `npm --prefix frontend test -- --run`
- 视环境可补跑全量 `pytest`。
