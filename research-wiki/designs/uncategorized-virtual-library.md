---
type: design
node_id: design:uncategorized-virtual-library
title: "虚拟「未分类」库 + 提取后自动定位"
date: 2026-05-29
---

# 虚拟「未分类」库 + 提取后自动定位

- **状态**: 已批准（待实现）
- **关联**: 管道 A（extract_rules）、审核点库页面、CheckpointLibrary

## 1. 背景与问题

AI 提取审核点（审核点库 → AI 提取）走 `run_extract`，提取成功后审核点以
`CheckpointFinal(approved_by="system:auto-promote")` 落库，`status` 默认 `"active"`，
**但不挂任何 CheckpointLibrary，也不建库** —— 成为「孤儿点」。

孤儿点只在虚拟视图「全部审核点」(`selectedLibraryId === "all"`) 里可见，**在任何真实库视图下都看不到**。
若用户当时停在某个具体库（如「医疗」）下提取，会以为"提取没用"。这是用户报告「AI 审核点用不了」最可能的真实原因。

### 诊断结论（testing vs stable）

| 维度 | testing (master) | stable | 说明 |
|---|---|---|---|
| AL8 自动化测试 | FAIL (433s) | PASS (360s) | 仅测试时序差异 |
| 提取/入库 | 正常 | 正常 | 都 +5 条孤儿点 |
| 全新加载可见 | 19 条全可见 | 17 条全可见 | 都在「全部审核点」 |
| 后端 extract_rules.py | — | — | 两分支字节级一致 |
| 前端提取/刷新逻辑 | — | — | 两分支一致 |

- 后端 `extract_rules.py` 两分支完全一致，都产生孤儿点（非回归）。
- testing 测试 FAIL 是脚本检测到"提取完成"后仅等 2s 即数行数的**时序竞态**；真人点击间隔以秒计不会触发。
- `refreshAll()` 在 `draft_ready` 时已自动调用，**列表刷新对真人已生效**（stable E2E 即为证）。

## 2. 目标

1. 让 AI 提取的孤儿点有一个明确、稳定的可见入口。
2. 提取完成后用户无需手动刷新即可看到新点。

非目标（YAGNI）：不改 extract_rules 的归库逻辑、不写数据迁移、不加自动刷新轮询。

## 3. 方案：虚拟「未分类」库（计算视图）

「未分类」定义为计算集合，**不是实体库、不写 `CheckpointLibraryItem`**：

> 未分类 = { active 的 CheckpointFinal，且不属于任何真实 CheckpointLibrary }

与现有「全部审核点」(`all`) 同类——前端侧栏的虚拟入口，从 `checkpoints` 全量数据计算。

**关键不变式**：点被加进任意真实库 → `library_count > 0` → 自动从「未分类」消失；
从所有库移除 → 自动回到「未分类」。无需迁移、无需改 extract_rules。

### 3.1 为何不用「实体未分类库 + 写关联 + 迁移回填」

实体库方案的硬伤：点被加进「医疗」后仍保留「未分类」关联 → **同时出现在两个库**，
不再是"未分类"却赖在未分类里，需手动移除、且数据漂移。虚拟视图从根本上规避。

## 4. 组件改动与数据流

### 后端（唯一改动点）
- `govdoc/api/routes/checkpoints.py` `[MODIFY]`
  - `_serialize_final()` 增加 `library_count: int`。
  - `list_checkpoints()`：一次 `group by checkpoint_final_id` 查 `CheckpointLibraryItem` 得每条点的归属库数。
  - 不新增端点、不改 extract_rules.py、不写迁移。
- `govdoc/api/schemas.py` `[MODIFY]`：响应模型加 `library_count`。

### 前端
- `frontend/src/api/v3.ts` / 类型 `[MODIFY]`：`CheckpointItem` 加 `library_count: number`。
- `frontend/src/pages/AuditLibraryPage.tsx` `[MODIFY]`
  - 侧栏在「全部审核点」下插入虚拟项「未分类」，count = `checkpoints.filter(c => c.library_count === 0).length`。
  - `rows` useMemo 增加分支：`selectedLibraryId === "uncategorized"` → `parsed.filter(library_count === 0)`。
  - 对「未分类」禁用：删除库 / 重命名 / 加入库 / 移除（保留 id 从 `["all"]` 扩为 `["all","uncategorized"]`）。
- `frontend/src/context/V3WorkbenchContext.tsx` `[MODIFY]`（锦上添花）
  - `draft_ready` 且 `refreshAll()` 后，暴露信号让页面自动 `setMode("list")` + `setSelectedLibraryId("uncategorized")`。

### 数据流
```
上传+开始抽取 → 后端 PES 提取 → CheckpointFinal(auto-promote, 无关联)
  → extract_run.status=draft_ready
前端轮询见 draft_ready → refreshAll()（重拉 checkpoints，含 library_count）
  → 自动切列表 + 选「未分类」 → 新点 library_count=0 → 显示在「未分类」
用户加入「医疗」库 → library_count=1 → 下次 refresh 自动从「未分类」消失
```

## 5. 边界、错误处理

- 保留 id `"uncategorized"` 与真实库 id（32 位 hex）及 `"all"` 不冲突。
- count 为 0 时侧栏仍显示「未分类」入口（与「全部审核点」一致）。
- `library_count` 只统计真实库关联；虚拟视图不写关联，无自指。
- archived 点：`list_checkpoints` 默认只返回 active，`library_count` 同口径，行为不变。
- 后端 group-by 失败/无关联 → `library_count` 默认 0（不抛错）。
- 前端 `library_count` 缺失（旧响应兼容）→ 视为 0，降级不崩。
- 自动跳转仅 `mode==="extract"` 时触发，避免强制跳走已离开提取页的用户。

## 6. 测试计划

- **单测** `tests/unit/`：构造有/无库关联的 CheckpointFinal，断言 `list_checkpoints` 的 `library_count` 正确；孤儿点 `library_count===0`。
- **前端单测**：`rows` 在 `uncategorized` 下只返回孤儿点；加入真实库后该点被过滤掉。
- **E2E** `audit-AL8-ai-extract.js`：① 列表行数增加 ② 侧栏「未分类」出现且 count>0 ③（可选）成功后停在「未分类」。
- **回归**：`pytest tests/unit tests/contract -q` 全绿 + `ruff check . --fix`。

## 7. 被否决的备选

| 备选 | 否决理由 |
|---|---|
| 实体「未分类」库 + 写关联 + Alembic 回填 | 双重归属漂移；代码更多；维护成本高 |
| 按「法规标题」建库 | 同名复用 / 空标题兜底复杂；用户选择统一未分类 |
| 加独立未分类端点 | 多余；`library_count` 字段 + 前端计算已足够，复用「全部审核点」模式 |
| 自动刷新轮询 | 现有 `refreshAll()` 已生效，非 bug，过度工程化 |
