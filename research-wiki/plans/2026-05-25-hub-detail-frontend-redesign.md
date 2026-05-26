---
type: plan
node_id: plan:2026-05-25-hub-detail-frontend-redesign
title: Hub+Detail 前端页面重构实施计划
date: 2026-05-25
---

# Hub+Detail 前端页面重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将文档对比和 AI 审查从阻塞式单页面改为 Hub+Detail 双页模式，Hub 永不阻塞，Detail 通过 URL 参数恢复状态，支持刷新不丢失。

**Architecture:** 后端新增 CompareRun 列表端点，前端新增 URL 参数路由（`/compare/:reviewId`、`/ai-review/:auditRunId`），每个功能拆为 Hub 页（上传/创建 + 历史列表）和 Detail 页（进度/结果自适应）。AI 审查的创建表单改为 Drawer 组件叠加在 Hub 上。

**Tech Stack:** FastAPI / SQLModel / React / React Router / TypeScript / Tailwind CSS / shadcn/ui

**Design:** `research-wiki/designs/hub-detail-frontend-redesign.md`

---

## 文件变更总览

| 文件 | 动作 | 职责 |
|------|------|------|
| `govdoc/api/routes/compare.py` | MODIFY | 新增 `GET /api/v1/compare` 列表端点 |
| `frontend/src/api/compare.ts` | MODIFY | 新增 `listCompareRuns()` 函数 |
| `frontend/src/App.tsx` | MODIFY | 路由重构：新增参数路由，删除旧路由 |
| `frontend/src/components/Sidebar.tsx` | MODIFY | 更新侧边栏导航项（删除审核结果/工作底稿） |
| `frontend/src/pages/DocCompareHubPage.tsx` | CREATE | 对比 Hub：上传区 + 历史列表 |
| `frontend/src/pages/DocCompareDetailPage.tsx` | CREATE | 对比 Detail：进度/结果自适应 |
| `frontend/src/pages/AIReviewHubPage.tsx` | CREATE | 审查 Hub：统计 + 任务列表 + Drawer 触发 |
| `frontend/src/pages/AIReviewDrawer.tsx` | CREATE | 审查 Drawer：选项目/文书/要点 + 提交 |
| `frontend/src/pages/AIReviewDetailPage.tsx` | CREATE | 审查 Detail：进度/工作底稿自适应 |
| `frontend/src/pages/DocComparePage.tsx` | DELETE | 被 Hub + Detail 替代 |
| `frontend/src/pages/AIReviewPage.tsx` | DELETE | 被 Hub + Drawer + Detail 替代 |
| `frontend/src/pages/AuditResultsPage.tsx` | DELETE | 合并入 AIReviewDetailPage |
| `frontend/src/pages/WorkpaperPage.tsx` | DELETE | 合并入 AIReviewDetailPage |

---

## Task 1: 后端 — 新增 CompareRun 列表端点

**Files:**
- Modify: `govdoc/api/routes/compare.py`
- Modify: `frontend/src/api/compare.ts`

- [ ] **Step 1: 在 compare route 新增列表端点**

在 `govdoc/api/routes/compare.py` 中，在 `compare_uploaded_files` 之前添加：

```python
@router.get("")
def list_compare_runs() -> list[CompareRunStatus]:
    """列出所有文档对比任务。"""
    with get_db_session() as session:
        from sqlmodel import select

        runs = session.exec(
            select(CompareRun).order_by(CompareRun.created_at.desc())
        ).all()
        return [
            CompareRunStatus(
                review_id=run.id,
                status=run.status,
                file_count=run.file_count,
                file_names=_load_json_list(run.file_names_json),
                progress=_load_json_dict(run.progress_json),
                error=run.error,
                created_at=str(run.created_at),
                completed_at=str(run.completed_at) if run.completed_at else None,
            )
            for run in runs
        ]
```

注意：此端点必须放在 `@router.post("")` **之前**，否则 FastAPI 路由匹配会冲突。但因为 HTTP 方法不同（GET vs POST），实际不冲突，位置无所谓。为可读性建议放在 POST 之前。

- [ ] **Step 2: 运行后端测试验证**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_compare_service.py -v`
Expected: 全部 PASS（新端点不影响已有测试）

- [ ] **Step 3: 前端 API 层新增 listCompareRuns**

在 `frontend/src/api/compare.ts` 末尾 `buildCompareDownloadUrl` 之前添加：

```typescript
export function listCompareRuns(): Promise<CompareRunStatus[]> {
  return request("/api/v1/compare");
}
```

- [ ] **Step 4: 验证前端编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 5: Commit**

```bash
git add govdoc/api/routes/compare.py frontend/src/api/compare.ts
git commit -m "feat(compare): 新增 GET /api/v1/compare 列表端点 + 前端 listCompareRuns"
```

---

## Task 2: 前端 — DocCompare Hub 页面

**Files:**
- Create: `frontend/src/pages/DocCompareHubPage.tsx`

- [ ] **Step 1: 创建 DocCompareHubPage**

创建 `frontend/src/pages/DocCompareHubPage.tsx`。页面包含：
- 标题区（"文档对比" + 说明文字）
- 上传卡片（FileDropzone + 文件标签列表 + "开始对比"按钮）
- 历史对比列表卡片（表格：文件名、状态徽标、匹配数、创建时间、操作按钮）

关键交互逻辑：
```typescript
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { compareFiles, listCompareRuns, type CompareRunStatus } from "@/api/compare";

export function DocCompareHubPage() {
  const navigate = useNavigate();
  const [files, setFiles] = useState<File[]>([]);
  const [runs, setRuns] = useState<CompareRunStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { listCompareRuns().then(setRuns).catch(() => {}); }, []);

  async function handleCompare(e: FormEvent) {
    e.preventDefault();
    if (files.length < 2) return;
    setLoading(true);
    try {
      const res = await compareFiles(files);
      navigate(`/compare/${res.reviewId}`);  // 跳转到 Detail 页
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
      setLoading(false);
    }
  }
  // ... 渲染上传区 + 历史列表
}
```

UI 结构参照 Pencil 设计 `Screen/DocCompare-Hub`：
- 上传区：`FileDropzone` 组件 + 已选文件标签（带删除按钮）+ "开始对比"按钮
- 历史列表：表头（文件/状态/匹配数/时间/操作）+ 数据行（点击"查看结果/进度"→ `navigate(/compare/${id})`）
- 状态徽标颜色：completed=绿，running=蓝，failed=红
- 空列表显示 `EmptyState` 组件

- [ ] **Step 2: 验证编译**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/DocCompareHubPage.tsx
git commit -m "feat(compare): DocCompare Hub 页面（上传区 + 历史列表）"
```

---

## Task 3: 前端 — DocCompare Detail 页面

**Files:**
- Create: `frontend/src/pages/DocCompareDetailPage.tsx`

- [ ] **Step 1: 创建 DocCompareDetailPage**

创建 `frontend/src/pages/DocCompareDetailPage.tsx`。页面逻辑：
- `useParams()` 取 `reviewId`
- 轮询 `getCompareStatus(reviewId)` 直到 completed/failed
- `running` 状态：渲染进度视图（文件列表 + 6 步进度条）
- `completed` 状态：调用 `getCompareResult(reviewId)` 加载结果 → 渲染结果视图（复用现有 DocComparePage 的结果渲染逻辑：MetricCard + category 筛选 + 文档列 + 匹配清单）
- `failed` 状态：显示错误信息 + "返回列表"按钮
- 顶部面包屑：`← 对比列表`（Link to `/compare`）+ 当前状态徽标

关键逻辑框架：
```typescript
import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getCompareStatus, getCompareResult, type CompareRunStatus, type CompareResponse } from "@/api/compare";

export function DocCompareDetailPage() {
  const { reviewId } = useParams<{ reviewId: string }>();
  const [status, setStatus] = useState<CompareRunStatus | null>(null);
  const [result, setResult] = useState<CompareResponse | null>(null);

  useEffect(() => {
    if (!reviewId) return;
    let active = true;
    const poll = async () => {
      const s = await getCompareStatus(reviewId);
      if (!active) return;
      setStatus(s);
      if (s.status === "completed") {
        const r = await getCompareResult(reviewId);
        if (active) setResult(r);
      } else if (s.status !== "failed") {
        setTimeout(poll, 2000);
      }
    };
    poll();
    return () => { active = false; };
  }, [reviewId]);

  if (result) return <CompareResultView result={result} />;
  if (status?.status === "failed") return <FailedView error={status.error} />;
  return <ProgressView status={status} />;
}
```

`CompareResultView` 从现有 `DocComparePage.tsx` 中提取（result 渲染部分，约 line 105-368 的 JSX）。
`ProgressView` 参照 Pencil 设计 `Screen/DocCompare-Detail`：左侧文件列表 + 右侧进度步骤（上传→转换→段落匹配→句子匹配→近似检测→生成结果）。

- [ ] **Step 2: 验证编译**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/DocCompareDetailPage.tsx
git commit -m "feat(compare): DocCompare Detail 页面（进度/结果自适应）"
```

---

## Task 4: 前端 — AIReview Hub 页面 + Drawer

**Files:**
- Create: `frontend/src/pages/AIReviewHubPage.tsx`
- Create: `frontend/src/pages/AIReviewDrawer.tsx`

- [ ] **Step 1: 创建 AIReviewDrawer 组件**

创建 `frontend/src/pages/AIReviewDrawer.tsx`。这是一个右侧滑出的抽屉组件：
```typescript
interface AIReviewDrawerProps {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;  // 创建成功后回调刷新列表
}
```

抽屉内容（参照 Pencil 设计 `Screen/AIReview-Hub-DrawerOpen`）：
1. 选择项目（下拉框，数据来自 `listProjects()`）
2. 上传招标文书（`FileDropzone`，调用 `uploadTenderDoc()`）
3. 审查要点勾选列表（数据来自 `listCheckpoints()`，checkbox 多选）
4. "开始审查"按钮 → 调用 `createAuditRun()` → `onCreated()` + `onClose()`

从现有 `AIReviewPage.tsx` 和 `useProjectWorkflow.ts` 中提取项目/文书/审核点选择逻辑。关键是：提交后**不导航到 Detail**，而是关闭抽屉并刷新 Hub 列表。

抽屉 UI 结构：
```
<div className="fixed inset-0 z-40">  {/* 遮罩 + 抽屉 */}
  <div className="absolute inset-0 bg-black/30" onClick={onClose} />
  <div className="absolute right-0 top-0 h-full w-[640px] bg-white shadow-xl flex flex-col">
    {/* header + body + footer */}
  </div>
</div>
```

- [ ] **Step 2: 创建 AIReviewHubPage**

创建 `frontend/src/pages/AIReviewHubPage.tsx`。页面包含：
- 标题 + "新建审查"按钮（点击打开 Drawer）
- 统计卡片（总任务/进行中/已完成/失败）
- 任务列表表格（项目名/文书/审核点数/状态/进度条/创建时间/操作）

数据来源：`listAuditRuns()` 已有（`GET /api/v1/audit/runs`）

关键逻辑：
```typescript
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listAuditRuns, type AuditRun } from "@/api/v3";
import { AIReviewDrawer } from "./AIReviewDrawer";

export function AIReviewHubPage() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<AuditRun[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const loadRuns = () => listAuditRuns().then(setRuns).catch(() => {});
  useEffect(() => { loadRuns(); }, []);

  return (
    <>
      {/* 标题 + 统计 + 表格 */}
      {/* 表格行点击 → navigate(`/ai-review/${run.id}`) */}
      <AIReviewDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onCreated={loadRuns}
      />
    </>
  );
}
```

UI 结构参照 Pencil 设计 `Screen/AIReview-Hub`：
- 4 个统计卡片（复用 `MetricCard`）
- 表格列：项目/文书、审核点数、状态（Badge）、进度条（`<Progress>`）、时间、操作按钮
- 行点击 → `navigate(/ai-review/${id})`

- [ ] **Step 3: 验证编译**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/AIReviewHubPage.tsx frontend/src/pages/AIReviewDrawer.tsx
git commit -m "feat(audit): AIReview Hub 页面 + Drawer 组件（新建审查抽屉）"
```

---

## Task 5: 前端 — AIReview Detail 页面

**Files:**
- Create: `frontend/src/pages/AIReviewDetailPage.tsx`

- [ ] **Step 1: 创建 AIReviewDetailPage**

创建 `frontend/src/pages/AIReviewDetailPage.tsx`。页面逻辑：
- `useParams()` 取 `auditRunId`
- 轮询 `getAuditRunProgress(auditRunId)` 直到 completed/failed
- `running` / `pending` 状态：渲染进度视图
- `draft_ready` / `completed` / `finalized` 状态：渲染工作底稿视图
- `failed` 状态：错误信息
- 顶部面包屑：`← 审查列表`（Link to `/ai-review`）+ 项目名 + 状态

进度视图（参照 Pencil 设计 `Screen/AIReview-Detail`）：
- 左侧：任务信息卡（项目/文书/审核点数/时间）
- 右侧：进度时间线（复用 `ProgressTimeline` 组件）+ 进度条
- 下方：审核点状态网格（每行一个审核点，图标+名称+状态徽标+详情按钮）

工作底稿视图：从现有 `WorkpaperPage.tsx` 提取核心逻辑（`WorkpaperEditor` + 导出按钮 + finalize 功能）

审核结果视图：从现有 `AuditResultsPage.tsx` 提取核心逻辑（审核点列表 + `PointInsight` 弹窗 + 评论功能）

状态切换逻辑：
```typescript
function DetailContent({ auditRunId }: { auditRunId: string }) {
  const [progress, setProgress] = useState<AuditRunProgress | null>(null);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      const p = await getAuditRunProgress(auditRunId);
      if (!active) return;
      setProgress(p);
      if (!["completed", "failed", "draft_ready", "finalized", "cancelled"].includes(p.status)) {
        setTimeout(poll, 3000);
      }
    };
    poll();
    return () => { active = false; };
  }, [auditRunId]);

  if (!progress) return <LoadingSpinner />;

  const isCompleted = ["draft_ready", "completed", "finalized"].includes(progress.status);
  if (isCompleted) return <WorkpaperView auditRunId={auditRunId} progress={progress} />;
  if (progress.status === "failed") return <FailedView error={...} />;
  return <ProgressView progress={progress} />;
}
```

- [ ] **Step 2: 验证编译**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/AIReviewDetailPage.tsx
git commit -m "feat(audit): AIReview Detail 页面（进度/工作底稿自适应）"
```

---

## Task 6: 前端 — 路由 + 侧边栏更新 + 删除旧组件

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`
- Delete: `frontend/src/pages/DocComparePage.tsx`
- Delete: `frontend/src/pages/AIReviewPage.tsx`
- Delete: `frontend/src/pages/AuditResultsPage.tsx`
- Delete: `frontend/src/pages/WorkpaperPage.tsx`

- [ ] **Step 1: 更新 App.tsx 路由**

```typescript
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { AuditLibraryPage } from "./pages/AuditLibraryPage";
import { DocCompareHubPage } from "./pages/DocCompareHubPage";
import { DocCompareDetailPage } from "./pages/DocCompareDetailPage";
import { AIReviewHubPage } from "./pages/AIReviewHubPage";
import { AIReviewDetailPage } from "./pages/AIReviewDetailPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/audit-library" element={<AuditLibraryPage />} />
        <Route path="/compare" element={<DocCompareHubPage />} />
        <Route path="/compare/:reviewId" element={<DocCompareDetailPage />} />
        <Route path="/ai-review" element={<AIReviewHubPage />} />
        <Route path="/ai-review/:auditRunId" element={<AIReviewDetailPage />} />
        {/* 旧路由重定向 */}
        <Route path="/audit-results" element={<Navigate replace to="/ai-review" />} />
        <Route path="/workpaper" element={<Navigate replace to="/ai-review" />} />
        <Route path="*" element={<Navigate replace to="/" />} />
      </Route>
    </Routes>
  );
}
```

- [ ] **Step 2: 更新 Sidebar.tsx 导航项**

```typescript
const navItems = [
  { to: "/", label: "工作台总览", icon: LayoutDashboard },
  { to: "/audit-library", label: "审核点库", icon: LibraryBig },
  { to: "/ai-review", label: "AI 审查", icon: Bot },
  { to: "/compare", label: "文档对比", icon: GitCompareArrows },
];
```

删除 "审核结果" 和 "工作底稿" 入口（已合并入 AI 审查 Detail 页）。

- [ ] **Step 3: 删除旧页面组件**

```bash
rm frontend/src/pages/DocComparePage.tsx
rm frontend/src/pages/AIReviewPage.tsx
rm frontend/src/pages/AuditResultsPage.tsx
rm frontend/src/pages/WorkpaperPage.tsx
```

- [ ] **Step 4: 清理 V3WorkbenchContext 中不再需要的状态**

`frontend/src/context/V3WorkbenchContext.tsx` 中可能有为旧页面设计的状态（如 `selectedAuditRunId`、`auditProgress` 等轮询逻辑）。新页面使用自己的 `useEffect` 轮询，context 中的全局轮询逻辑需要评估是否仍有用。

**保守做法**：先不删除 context 中的状态，等全部页面工作正常后再清理。仅在新页面中不使用 context 中的轮询，改用页面内部 `useEffect`。

- [ ] **Step 5: 验证编译 + 运行**

```bash
cd frontend && npx tsc --noEmit
cd frontend && npm run build
```
Expected: 无错误，构建成功

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/Sidebar.tsx
git rm frontend/src/pages/DocComparePage.tsx frontend/src/pages/AIReviewPage.tsx frontend/src/pages/AuditResultsPage.tsx frontend/src/pages/WorkpaperPage.tsx
git commit -m "refactor: 路由重构 + 删除旧页面（DocCompare/AIReview/AuditResults/Workpaper）"
```

---

## Task 7: 全量验证 + 部署

- [ ] **Step 1: 后端测试**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 2: 前端构建**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 3: 代码检查**

Run: `source activate govdoc-auditor-v3 && ruff check govdoc/api/routes/compare.py`
Expected: 无错误

- [ ] **Step 4: 部署 testing**

Run: `bash scripts/deploy.sh --target testing`

- [ ] **Step 5: 手动验证**

验证项：
- `/compare` → Hub 页显示上传区 + 历史列表
- 上传 2 个 DOCX → 跳转 `/compare/:id` → 显示进度 → 完成后显示结果
- 刷新 `/compare/:id` → 页面恢复
- `/compare` → 历史列表中有刚才的任务
- `/ai-review` → Hub 页显示任务列表 + 统计
- 点击"新建审查" → Drawer 打开 → 填表 → 提交 → Drawer 关闭，列表刷新
- 点击任务行 → 跳转 `/ai-review/:id` → 显示进度
- 刷新 `/ai-review/:id` → 页面恢复
- `/audit-results` → 重定向到 `/ai-review`
- `/workpaper` → 重定向到 `/ai-review`

---

## 验收标准

| 验收项 | 验证方法 |
|--------|----------|
| 后端列表端点 | `curl GET /api/v1/compare` 返回 CompareRun 列表 |
| DocCompare Hub | `/compare` 显示上传区 + 历史列表 |
| DocCompare Detail | `/compare/:id` 显示进度或结果 |
| 刷新恢复（对比） | 刷新 `/compare/:id` 页面恢复状态 |
| AIReview Hub | `/ai-review` 显示统计 + 任务列表 |
| AIReview Drawer | 点击新建 → 抽屉打开 → 提交 → 关闭 + 刷新 |
| AIReview Detail | `/ai-review/:id` 显示进度或底稿 |
| 刷新恢复（审查） | 刷新 `/ai-review/:id` 页面恢复状态 |
| 旧路由重定向 | `/audit-results` 和 `/workpaper` 重定向到 `/ai-review` |
| 侧边栏更新 | 只剩 4 个导航项 |
| 构建成功 | `npm run build` 无错误 |
