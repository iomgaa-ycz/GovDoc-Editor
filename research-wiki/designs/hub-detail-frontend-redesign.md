---
type: design
node_id: design:hub-detail-frontend-redesign
title: "Hub+Detail 前端页面重构设计"
date: 2026-05-25
---

# Hub+Detail 前端页面重构设计

## 1. 背景

当前异步任务（文档对比、AI 审查）页面在任务运行时阻塞整个 UI，刷新丢失进度，无法并行操作。需要重构为 Hub+Detail 模式：Hub 页面永不阻塞，Detail 页面 URL 可恢复。

## 2. 后端 API 补充

新增 1 个端点：

```
GET /api/v1/compare
→ 返回所有 CompareRun 记录列表
→ [{reviewId, status, fileCount, fileNames, progress, error, createdAt, completedAt}]
→ 按 createdAt DESC 排序
```

其余接口（audit/runs list、status、progress、result）已完备。

## 3. 前端路由

| 路由 | 组件 | 说明 |
|------|------|------|
| `/compare` | DocCompareHubPage | 上传区 + 历史任务列表 |
| `/compare/:reviewId` | DocCompareDetailPage | 进度/结果（按状态切换） |
| `/ai-review` | AIReviewHubPage | 统计 + 任务列表 + 新建 Drawer |
| `/ai-review/:auditRunId` | AIReviewDetailPage | 进度/工作底稿（按状态切换） |

删除旧路由：`/audit-results`、`/workpaper`（合并入 `/ai-review/:id`）

## 4. 页面组件

### DocCompare

| 组件 | 职责 |
|------|------|
| DocCompareHubPage | GET /compare 加载历史 + 上传区 + POST 后跳转 /compare/:id |
| DocCompareDetailPage | useParams 取 reviewId → 轮询 status → running 显示进度 / completed 渲染结果 |

### AIReview

| 组件 | 职责 |
|------|------|
| AIReviewHubPage | GET /audit/runs 加载任务列表 + 统计卡片 + 新建按钮 |
| AIReviewDrawer | 右侧抽屉：选项目/文书/审查要点 → POST /audit/runs → 关闭 + 刷新列表 |
| AIReviewDetailPage | useParams 取 auditRunId → 轮询 progress → running 显示时间线 / completed 显示底稿 |

## 5. 前端 API 层

compare.ts 新增 `listCompareRuns(): Promise<CompareRunStatus[]>`

## 6. 删除的旧组件

- DocComparePage.tsx → 拆为 Hub + Detail
- AIReviewPage.tsx → 拆为 Hub + Drawer + Detail
- AuditResultsPage.tsx → 合并入 AIReviewDetailPage
- WorkpaperPage.tsx → 合并入 AIReviewDetailPage（completed 态）

## 7. 被拒绝的方案

| 方案 | 拒绝原因 |
|------|----------|
| 保持现有路由 + URL searchParams | 不够语义化，不利于浏览器历史导航 |
| Modal 代替 Drawer | Setup 表单内容较多，Modal 空间不够 |
| Setup 保持独立页面 | 离开 Hub 页面，无法看到任务列表 |
