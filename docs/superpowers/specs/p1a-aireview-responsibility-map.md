# P1a · AIReviewPage 拆分责任映射表

> 基线文件：`frontend/src/pages/AIReviewPage.tsx`（315 行，2026-04-19 快照）
> 目的：为后续 Bundle 2–4（custom hooks + 子组件 + 容器收敛）提供行号精确的拆分蓝图。
> 注：本页仅一次读懂现状；UI 文案以当前代码为准（"启动审核" / "新建" / "上传文书"）。

## 行号 → 责任 → 拆分目标

| 行号 | 职责片段 | 拆分目标 |
|---|---|---|
| L1-23 | 依赖导入（lucide / context / adapters / UI / PointInsight / Modal） | 容器（AIReviewPage，按需减项） |
| L25-40 | `useWorkbench()` 解构（14 个字段） | 容器（按子组件所需下发 props / 仍保留） |
| L42-50 | 本地 state：`newProjectName` / `tenderFile` / `creating` / `uploadingTender` | useProjectWorkflow |
| L48-50 | 本地 state：`selectedCpIds` / `startingAudit` | useAuditRun（或容器 state + 下发 CheckpointPicker） |
| L52-53 | 本地 state：`detailPointRunId`（弹窗） | 容器（弹窗逻辑留在容器） |
| L55-56 | 派生：`tenderDoc` / `isRunning` | 容器（按需下发） |
| L58-61 | 派生：`completedCount` / `failedCount` / `pendingCount` / `total` | AuditProgressPanel（或 useAuditRun 内派生） |
| L65-74 | handler：`handleCreateProject`（setCreating + createProject + 清空表单） | useProjectWorkflow |
| L76-85 | handler：`handleUploadTender`（setUploadingTender + uploadTenderDoc） | useProjectWorkflow |
| L87-91 | handler：`toggleCheckpoint` | CheckpointPicker（纯 UI）或容器传入 |
| L93-101 | handler：`handleStartAudit`（setStartingAudit + createAuditRun） | useAuditRun |
| L105-110 | 辅助：`getCheckpointForPointRun`（查 cp.parsed） | 容器（仅弹窗用） |
| L114-124 | JSX：PageHero + apiConnected 警示 | 容器 |
| L126-128 | JSX：三栏 `triple-layout` 外壳 | 容器 |
| L129-154 | JSX：任务设置卡片 — 项目下拉 + 新项目名称 + "新建"按钮 | TenderUploadPanel（前置部分） |
| L155-182 | JSX：招标文书上传（FileDropzone + "上传文书"按钮） | TenderUploadPanel |
| L184-186 | JSX：文书已上传 InlineNotice | TenderUploadPanel |
| L188-214 | JSX：审核点多选 + "启动审核"按钮 | CheckpointPicker |
| L219-236 | JSX：中栏 "审核进度" 卡片（ProgressBar + 4 个 MetricCard） | AuditProgressPanel |
| L238-243 | JSX：运行日志 `LogConsole` | AuditProgressPanel（或独立 LogsPanel） |
| L247-295 | JSX：右栏 "审核点进度" 列表（含重试按钮 + StatPill） | AuditProgressPanel（右栏部分） |
| L299-312 | JSX：Modal + PointInsight（弹窗） | 容器 |

## 归类小结（便于 Bundle 2–4 估工）

- **container**：L1-40、L52-53、L55-56、L105-124、L126-128、L219、L299-315（≈60 行壳子 + 弹窗，≤120 行 DoD 充裕）
- **TenderUploadPanel**：L129-186（任务设置 + 文书上传，≈60 行）
- **CheckpointPicker**：L48-49、L87-91、L188-214（≈30 行，props 传入 `finalCheckpoints` + `selected` + `onToggle` + `onStart`）
- **AuditProgressPanel**：L58-61、L219-295（≈80 行，props 传入 `auditProgress` + `logs` + `onRetry` + `onOpenDetail`）
- **useProjectWorkflow**：L43-46、L65-85（状态 + 两个 handler，从 context 取 `activeProject` / `createProject` / `uploadTenderDoc`）
- **useAuditRun**：L49-50、L93-101（状态 + handler，从 context 取 `activeProject` / `tenderDoc` / `createAuditRun`；`auditProgress` / `retryPointRun` 仍由 context 直供子组件）

## 拆分顺序（复核用）

1. Bundle 2：先 hooks（`useProjectWorkflow` → `useAuditRun`），容器 import 替换，跑护栏
2. Bundle 3：再子组件（`TenderUploadPanel` → `CheckpointPicker` → `AuditProgressPanel`），逐个替换，每步跑护栏
3. Bundle 4：容器收敛到 ≤120 行，smoke + tsc 验证
