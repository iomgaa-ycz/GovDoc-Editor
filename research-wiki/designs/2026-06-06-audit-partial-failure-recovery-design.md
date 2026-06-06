# 审核部分失败恢复：自动残缺底稿 + 重试/跳过 + 历史回填

## 概述

当前管道 B 的审核任务（AuditRun）只要有**任何一个审核点失败**，收尾时就不生成工作底稿，任务停在 `partial_ready`/`waiting_retry` 且前端无底稿可看，进度条永久卡在 99%——对律师表现为"卡死"。

本设计改为：**只要有 ≥1 个审核点完成，就自动生成底稿**（有失败则为"残缺底稿"）；并提供两个批量操作——**重试失败点**、**跳过（剔除）失败点**——两条路都能把任务推进到"完整底稿/`draft_ready`"。同时提供一次性脚本回填历史卡死任务。

核心原则：**单一真相在后端**（出底稿与状态判定都收口在 `_assemble_workpaper_draft`），前端只展示与触发；最大化复用现有 `run_audit` / 单点重试 / WorkpaperDraft 版本机制；遵循 MVP，不引入作业队列或自动重试策略。

## 问题与现状

`govdoc/pipelines/audit_tender.py::_assemble_workpaper_draft`（约 L544）现有三分支：

| 现状情况 | 状态 | 出底稿 |
|---|---|---|
| 有 completed、**无 failed** | `draft_ready` | ✅ 生成 |
| 有 completed、**有 failed** | `partial_ready` | ❌ **不生成** ← 痛点 |
| 无 completed | `waiting_retry` | ❌ 不生成 |

前端 `AIReviewDetailPage.tsx`：`percent = round(processed/total*100)`（L103），`partial_ready` 已在 `TERMINAL_STATUSES`（L75，停止轮询）和 `WORKPAPER_STATUSES`（L84，期待有底稿）中——但后端不产底稿，于是显示"暂无工作底稿"，形成"99% 卡死"。

已有但不足的能力：单点重试 `retry_point_run`（`audit.py` L355 + `audit_tender.py` L790，会 `shutil.rmtree` 旧 workspace 后调 `run_audit(point_run_ids=[id])`）；`finalize-partial`（`workpapers.py` L76，能从完成点出底稿，但语义是"定稿"且需手动逐个触发）。

## 设计

### 1. 状态模型

**AuditPointRun.status** 新增 `excluded`：

| 状态 | 含义 |
|---|---|
| pending / running / completed / failed | 不变 |
| **excluded（新增）** | 被"跳过/剔除"的点：不计入总数、不参与出底稿、`run_audit` 不再重跑。软标记（不删行），数据层可逆 |

**AuditRun.status** 沿用 `running / draft_ready / partial_ready / waiting_retry / cancelled / finalized`，但 `partial_ready` 语义变为"**有失败点但已产出残缺底稿**"。

### 2. 出底稿规则（核心改动 · `_assemble_workpaper_draft`）

设 C = completed 数、F = failed 数（**不含 excluded**）：

| 情况 | AuditRun 状态 | 出底稿 |
|---|---|---|
| C≥1 且 F=0 | `draft_ready` | ✅ 完整底稿（新版本）|
| C≥1 且 F≥1 | `partial_ready` | ✅ **残缺底稿（新版本，含 C 条 finding）** ← 改动点 |
| C=0 | `waiting_retry` | ❌ 无可写内容 |

实现：把现有"仅 `completed and not failed` 分支才渲染底稿"扩为"`completed_runs` 非空即渲染"，渲染逻辑（findings 组装 + `render_workpaper_docx` + WorkpaperDraft 版本号 +1）原样复用；仅状态赋值按上表分派。**总是生成新版本**，旧版保留，不检测律师编辑。

### 3. 两个批量端点（复用现有机制）

| | 重试失败点 | 跳过（剔除）失败点 |
|---|---|---|
| 接口 | `POST /api/v1/audit/runs/{id}/retry-failed` | `POST /api/v1/audit/runs/{id}/exclude-failed` |
| 行为 | 取该 run 所有 `failed` 点 → 逐个 `shutil.rmtree` workspace + 置 `pending` → 后台 `run_audit(id, point_run_ids=[失败点])` → 收尾 assemble | 取所有 `failed` 点 → 置 `excluded` → 重算 total → 同步 assemble |
| 耗时/返回 | 慢，后台任务，202「重试中」 | 快，200「已跳过 N 项」 |
| 跑完结果 | 全成功→`draft_ready`+完整底稿；仍有失败→新残缺底稿/`partial_ready` | F=0 → `draft_ready`+完整底稿 |

- 重试 = 把单点重试的"清 workspace + 置 pending"逻辑从单点扩成批量（复用 `prepare_point_run_retry` 的核心），执行仍走 `run_audit` 的 `point_run_ids` 白名单（已存在）。
- 单点重试端点保留（前端已接 `retryPointRun`）。
- **状态守卫**：两端点仅当 run 处于终态（`partial_ready`/`waiting_retry`/`draft_ready`）时允许；`running` 时返回 409/400。`exclude-failed` 无失败点时返回提示。

### 4. 进度/总数语义（易漏点）

`excluded` 必须在**四处**一致忽略：
1. `create_audit_run` 初始 `total_count`（新建时无 excluded，无影响）；
2. `run_audit::_resolve_point_runs`（L271）选点：跳过 `completed` **和 `excluded`**；
3. `GET /runs/{id}/progress`（`audit.py` L289）：`total_count` 与可见点列表排除 excluded；
4. `_assemble_workpaper_draft`：F 统计排除 excluded；`run.total_count` 重算为"非 excluded 点数"。

效果：122 完成 + 2 失败，跳过 2 失败 → total 122、completed 122 → 100% / `draft_ready` / 完整底稿。

### 5. 前端（`AIReviewDetailPage.tsx` + `v3.ts`）

- **部分完成提示条**（`partial_ready` 时，琥珀色）：「本次审核共 134 个审核点：已完成 122 个，2 个未能完成。当前为部分稿。」+ 两个按钮「重试未完成的 2 项」「跳过这 2 项并出完整稿」。
- 任务 `running` 时按钮置灰。
- `draft_ready` 时转绿：「全部完成，已生成完整底稿」或「已生成完整底稿（含 122 项，已跳过 2 项）」。
- 底稿区：partial 阶段展示残缺底稿（后端已自动产出），不再显示"暂无工作底稿"。
- 任务列表页加标签「部分完成 122/134」。
- 措辞面向律师：用"未能完成 / 重试 / 跳过 / 部分稿 / 完整稿"，不出现 `partial_ready`、workspace 等术语。
- `v3.ts` 新增 `retryFailedPoints(auditRunId)`、`excludeFailedPoints(auditRunId)`。

### 6. 历史回填脚本（`scripts/backfill_partial_drafts.py`）

部署时跑一次：扫描所有 `partial_ready`/`waiting_retry` 任务，对有 ≥1 完成点者调用**同一出底稿函数**补生成残缺底稿并按新规则修正状态；`waiting_retry`（0 完成）跳过；幂等（已有底稿可生成新版，无害）；结束打印回填/跳过计数。须设 `NO_PROXY`（含 LLM 网关 110.42.53.85、MonkeyOCR 100.81.95.44）+ `HF_HUB_OFFLINE=1`，conda `govdoc-auditor-v3`。

## 错误处理

- 后台重试任务用现有同款 try/except 兜底；点重试再失败仍保 `failed`，finally 仍 assemble 出残缺底稿，不让任务崩。
- `render_workpaper_docx` 失败 → 记日志、保状态，不连累整 run。
- 端点状态守卫（running 拒绝）+ 前端置灰，双保险防与后台 `run_audit` 抢同一批点。
- `excluded` 扣减全链路一致性为重点测试对象。

## 测试计划（≥80% 覆盖）

| 层级 | 用例 |
|---|---|
| 单元 `tests/unit` | assemble 三分支矩阵（完整/残缺/无底稿）；excluded 不计数；total 扣减；retry-failed 收集+重置失败点（mock run_audit）；exclude-failed → draft_ready |
| 路由/契约 | 两新端点返回码 + running 拒绝；`v3.ts` 契约 |
| 前端单元 (vitest) | 提示条计数渲染、running 置灰、完整/部分/跳过三态文案 |
| 集成 `tests/integration` | 小 fixture：构造 1 失败点 → 自动残缺底稿；跳过 → 完整底稿；重试用 replay fixture |
| 回填脚本 | 种 partial_ready 任务 → 脚本补出底稿 |

## 受影响文件（函数级）

- `[MODIFY] govdoc/db/models.py`：`AuditPointRun.status`（L168）是普通 `str`、无 Enum/CHECK 约束，**加入 `excluded` 零数据库迁移**，仅更新行内注释（`pending/running/completed/failed/excluded`）。
- `[MODIFY] govdoc/pipelines/audit_tender.py`：`_assemble_workpaper_draft`（出底稿三分支改造 + excluded 排除）、`_resolve_point_runs`（跳过 excluded）、新增 `prepare_failed_points_retry`/批量重试辅助、`count_processed_points`/total 计算排除 excluded。
- `[MODIFY] govdoc/api/routes/audit.py`：新增 `retry_failed`、`exclude_failed` 两端点；`get_audit_run_progress` 排除 excluded。
- `[NEW] scripts/backfill_partial_drafts.py`：历史回填。
- `[MODIFY] frontend/src/pages/AIReviewDetailPage.tsx`：部分完成提示条 + 两按钮 + 三态文案 + 展示残缺底稿。
- `[MODIFY] frontend/src/api/v3.ts`：`retryFailedPoints` / `excludeFailedPoints`。
- `[MODIFY] frontend/src/pages/AIReviewHubPage.tsx`：任务列表加「部分完成 122/134」标签。
- `[NEW] tests/...`：见测试计划。

## 非目标（YAGNI）

- 不做自动重试次数/退避策略、不引入作业队列（方案 C 已否决）。
- 不做"恢复已跳过点"的界面（数据层可逆，留后续）。
- 不做重生成与律师编辑的合并/冲突检测（已定：总是生成新版，旧版保留）。
- 不改部署流程本身（部署前在跑任务的优雅停机是另一议题）。

## 关联

由 stable 部署中断事故（2026-06-04，见 memory `project-stable-deploy-interrupted-audits`）暴露的"失败即卡死"问题驱动；手动 DB 改点（删失败点 + 改 draft_ready）的产品化即本设计的"跳过"功能。
