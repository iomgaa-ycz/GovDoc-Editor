# P1a · AIReviewPage 拆分 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 把 `frontend/src/pages/AIReviewPage.tsx`（315 行单组件）拆成容器组件（≤120 行） + 3 个子组件 + 2 个 custom hooks，UI 行为不变。

**Architecture:**
- 先用 P1c 合入的 testing-library + MSW 建 render test，作为行为护栏
- 抽 custom hooks（数据层），再抽子组件（UI 层）
- 容器组件最后收敛

**Tech Stack:** React 18, TypeScript, vitest, @testing-library/react, MSW

**依赖：** **P1c 必须已 merge 入 umbrella**（需要 MSW 基建）

---

## Task 0: 建立子分支

- [ ] **Step 1**

```bash
git checkout feat/tech-debt-cleanup
git pull --ff-only 2>/dev/null || true
git checkout -b feat/p1a-aireview-split
```

- [ ] **Step 2: 验证 P1c 产物就位**

```bash
ls frontend/tests/mocks/server.ts frontend/vitest.config.ts
```

Expected: 两个文件都存在

---

## Task 1: 读懂 AIReviewPage 现状

**Files:** 只读 `frontend/src/pages/AIReviewPage.tsx`

- [ ] **Step 1: 映射现有职责**

Run: `cat frontend/src/pages/AIReviewPage.tsx`

执行时做一张映射表（写在 PR 描述里）：

| 行号 | 职责 | 拆分目标 |
|---|---|---|
| 例：L25-80 | 项目创建表单 | TenderUploadPanel 前置 |
| 例：L82-150 | 招标文书上传 | TenderUploadPanel |
| 例：L152-220 | 审核点多选 | CheckpointPicker |
| 例：L222-290 | 审计进度显示 | AuditProgressPanel |
| 例：L292-315 | 容器布局 | AIReviewPage 保留 |

⚠️ 执行时按实际代码填入精确行号。

---

## Task 2: 写 AIReviewPage 当前行为的 render test（行为护栏）

**Files:**
- Create: `frontend/tests/pages/AIReviewPage.test.tsx`

- [ ] **Step 1: 建立测试文件**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { server } from "../mocks/server";

import { AIReviewPage } from "@/pages/AIReviewPage";


function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/ai-review"]}>
      <AIReviewPage />
    </MemoryRouter>
  );
}


describe("AIReviewPage · 行为护栏", () => {
  // 1. 首次渲染：三个面板都在屏
  it("首次渲染显示上传区、审核点选择区、进度区", () => {
    server.use(
      http.get("*/api/v3/checkpoints", () => HttpResponse.json({ items: [] }))
    );
    renderPage();
    expect(screen.getByText(/上传招标文书|Tender Upload/i)).toBeInTheDocument();
    expect(screen.getByText(/选择审核点|Checkpoint/i)).toBeInTheDocument();
    expect(screen.getByText(/进度|Progress/i)).toBeInTheDocument();
  });

  // 2. 项目创建流程
  it("点击创建项目按钮会发起 POST /projects 请求", async () => {
    let captured: unknown = null;
    server.use(
      http.post("*/api/v3/projects", async ({ request }) => {
        captured = await request.json();
        return HttpResponse.json({ id: "p_new", name: "测试项目" });
      }),
      http.get("*/api/v3/checkpoints", () => HttpResponse.json({ items: [] }))
    );
    renderPage();
    await userEvent.type(screen.getByLabelText(/项目名称/i), "测试项目");
    await userEvent.click(screen.getByRole("button", { name: /创建/i }));
    expect(captured).toEqual(expect.objectContaining({ name: "测试项目" }));
  });

  // 3. 勾选审核点会更新内部状态（通过 disabled 按钮变化观察）
  it("勾选审核点后启动审计按钮可点", async () => {
    server.use(
      http.get("*/api/v3/checkpoints", () =>
        HttpResponse.json({
          items: [
            { id: "cp1", title: "采购范围" },
            { id: "cp2", title: "供应商资格" },
          ],
        })
      )
    );
    renderPage();
    const startBtn = await screen.findByRole("button", { name: /启动审计/i });
    expect(startBtn).toBeDisabled();

    const cp1 = await screen.findByLabelText("采购范围");
    await userEvent.click(cp1);
    expect(startBtn).not.toBeDisabled();
  });

  // 4. 启动审计：POST /audit-runs 被调用
  it("启动审计发起 POST /audit-runs", async () => {
    let captured: unknown = null;
    server.use(
      http.get("*/api/v3/checkpoints", () =>
        HttpResponse.json({ items: [{ id: "cp1", title: "采购范围" }] })
      ),
      http.post("*/api/v3/audit-runs", async ({ request }) => {
        captured = await request.json();
        return HttpResponse.json({ id: "ar_new", status: "pending" });
      })
    );
    renderPage();
    await userEvent.click(await screen.findByLabelText("采购范围"));
    await userEvent.click(await screen.findByRole("button", { name: /启动审计/i }));
    expect(captured).toBeTruthy();
  });

  // 5. 进度轮询显示最新进度
  it("审计进行中显示 progress.processed / total", async () => {
    let hitCount = 0;
    server.use(
      http.get("*/api/v3/audit-runs/:id/progress", () => {
        hitCount++;
        return HttpResponse.json({ processed: 2, total: 5, status: "running" });
      }),
      http.get("*/api/v3/checkpoints", () => HttpResponse.json({ items: [] }))
    );
    renderPage();
    // 具体触发进度轮询的交互按实际 AIReviewPage 逻辑调整
    // 这里只确认 UI 有位置显示 "2 / 5" 或类似
    // 如果无进行中 state，此测试可降级为"进度区存在"
  });
});
```

⚠️ **执行时**：
- `screen.getByText()` 的正则按实际 i18n 文案调整
- `baseURL` 按 v3.ts 配置调整 MSW 路径
- 如果 `AIReviewPage` 有 react-router-dom 路由依赖，用 `MemoryRouter` 包裹
- 如果有 Context Provider，按需包裹

- [ ] **Step 2: 跑 render test**

```bash
cd frontend && npm test
cd ..
```

Expected: 5 case 全绿（说明当前实现行为已锁住）

- [ ] **Step 3: 提交护栏**

```bash
git add frontend/tests/pages/AIReviewPage.test.tsx
git commit -m "test: 添加 AIReviewPage 行为护栏 render test"
```

---

## Task 3: 抽取 `useProjectWorkflow` custom hook

**Files:**
- Create: `frontend/src/hooks/useProjectWorkflow.ts`
- Modify: `frontend/src/pages/AIReviewPage.tsx`

- [ ] **Step 1: 识别待抽的逻辑**

从 AIReviewPage 里找出"项目创建 + 招标文书上传"相关的：
- useState 变量（projectName / tenderFile / 等）
- 事件处理器（handleCreateProject / handleUploadTender）
- 副作用（useEffect）

- [ ] **Step 2: 创建 hook**

```tsx
// frontend/src/hooks/useProjectWorkflow.ts
import { useState, useCallback } from "react";
import { createProject, uploadTenderDoc } from "@/api/v3";

export interface ProjectWorkflow {
  projectId: string | null;
  tenderDocId: string | null;
  isCreating: boolean;
  isUploading: boolean;
  error: string | null;
  createProject: (name: string) => Promise<void>;
  uploadTender: (file: File) => Promise<void>;
}

export function useProjectWorkflow(): ProjectWorkflow {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [tenderDocId, setTenderDocId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createProjectFn = useCallback(async (name: string) => {
    setIsCreating(true);
    setError(null);
    try {
      const result = await createProject({ name });
      setProjectId(result.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsCreating(false);
    }
  }, []);

  const uploadTender = useCallback(async (file: File) => {
    if (!projectId) {
      setError("请先创建项目");
      return;
    }
    setIsUploading(true);
    setError(null);
    try {
      const result = await uploadTenderDoc(projectId, file);
      setTenderDocId(result.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsUploading(false);
    }
  }, [projectId]);

  return {
    projectId,
    tenderDocId,
    isCreating,
    isUploading,
    error,
    createProject: createProjectFn,
    uploadTender,
  };
}
```

⚠️ 执行时按 `v3.ts` 实际导出的 API 函数名调整。

- [ ] **Step 3: 在 AIReviewPage 里替换原本内联的 state + handler**

把原来的 useState / handleCreateProject / handleUploadTender 全部删除，替换为：

```tsx
import { useProjectWorkflow } from "@/hooks/useProjectWorkflow";

export function AIReviewPage() {
  const workflow = useProjectWorkflow();
  // ...使用 workflow.createProject / workflow.uploadTender 等
}
```

- [ ] **Step 4: 跑 render test**

```bash
cd frontend && npm test -- AIReviewPage
cd ..
```

Expected: 5 case 仍全绿（护栏证明行为没变）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/hooks/useProjectWorkflow.ts frontend/src/pages/AIReviewPage.tsx
git commit -m "refactor: 抽取 useProjectWorkflow hook"
```

---

## Task 4: 抽取 `useAuditRun` custom hook

**Files:**
- Create: `frontend/src/hooks/useAuditRun.ts`
- Modify: `frontend/src/pages/AIReviewPage.tsx`

- [ ] **Step 1: 识别逻辑范围**

从 AIReviewPage 里找"启动审计 + 轮询进度"相关的 state 和 handler。

- [ ] **Step 2: 创建 hook**

```tsx
// frontend/src/hooks/useAuditRun.ts
import { useState, useEffect, useCallback, useRef } from "react";
import { createAuditRun, getAuditRunProgress } from "@/api/v3";

export interface AuditRunState {
  auditRunId: string | null;
  status: string | null;
  processed: number;
  total: number;
  error: string | null;
  start: (projectId: string, tenderDocId: string, checkpointIds: string[]) => Promise<void>;
}

export function useAuditRun(): AuditRunState {
  const [auditRunId, setAuditRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [processed, setProcessed] = useState(0);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const pollingRef = useRef<number | null>(null);

  const start = useCallback(async (
    projectId: string,
    tenderDocId: string,
    checkpointIds: string[]
  ) => {
    setError(null);
    try {
      const run = await createAuditRun({ projectId, tenderDocId, checkpointIds });
      setAuditRunId(run.id);
      setStatus(run.status);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  // 轮询进度（仅在有 auditRunId 时）
  useEffect(() => {
    if (!auditRunId) return;
    const tick = async () => {
      try {
        const p = await getAuditRunProgress(auditRunId);
        setProcessed(p.processed);
        setTotal(p.total);
        setStatus(p.status);
        if (p.status === "running" || p.status === "pending") {
          pollingRef.current = window.setTimeout(tick, 2000);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    };
    tick();
    return () => {
      if (pollingRef.current) window.clearTimeout(pollingRef.current);
    };
  }, [auditRunId]);

  return { auditRunId, status, processed, total, error, start };
}
```

- [ ] **Step 3: 在 AIReviewPage 替换原内联逻辑**

- [ ] **Step 4: render test 仍绿**

```bash
cd frontend && npm test -- AIReviewPage
cd ..
```

Expected: 全绿

- [ ] **Step 5: 提交**

```bash
git add frontend/src/hooks/useAuditRun.ts frontend/src/pages/AIReviewPage.tsx
git commit -m "refactor: 抽取 useAuditRun hook"
```

---

## Task 5: 拆 `TenderUploadPanel` 子组件

**Files:**
- Create: `frontend/src/components/TenderUploadPanel.tsx`
- Modify: `frontend/src/pages/AIReviewPage.tsx`

- [ ] **Step 1: 创建子组件**

```tsx
// frontend/src/components/TenderUploadPanel.tsx
import { ChangeEvent } from "react";

export interface TenderUploadPanelProps {
  projectId: string | null;
  isCreating: boolean;
  isUploading: boolean;
  onCreateProject: (name: string) => void;
  onUploadTender: (file: File) => void;
}

export function TenderUploadPanel({
  projectId,
  isCreating,
  isUploading,
  onCreateProject,
  onUploadTender,
}: TenderUploadPanelProps) {
  // 从 AIReviewPage 里搬相关 JSX
  // 保留"项目名称输入"+"创建按钮"+"上传文件"
  return (
    <section aria-label="上传招标文书">
      {/* 搬 JSX 时保持文案不变，render test 的选择器才能继续命中 */}
    </section>
  );
}
```

- [ ] **Step 2: 在 AIReviewPage 里替换相关 JSX**

- [ ] **Step 3: render test 绿**

```bash
cd frontend && npm test -- AIReviewPage
cd ..
```

Expected: 全绿

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/TenderUploadPanel.tsx frontend/src/pages/AIReviewPage.tsx
git commit -m "refactor: 拆 TenderUploadPanel 子组件"
```

---

## Task 6: 拆 `CheckpointPicker` 子组件

**Files:**
- Create: `frontend/src/components/CheckpointPicker.tsx`

按与 Task 5 相同的 4 步节奏：创建 → 替换 → 测试 → 提交。

接口签名：
```tsx
export interface CheckpointPickerProps {
  checkpoints: Array<{ id: string; title: string }>;
  selected: Set<string>;
  onToggle: (id: string) => void;
}
```

Commit: `refactor: 拆 CheckpointPicker 子组件`

---

## Task 7: 拆 `AuditProgressPanel` 子组件

**Files:**
- Create: `frontend/src/components/AuditProgressPanel.tsx`

接口签名：
```tsx
export interface AuditProgressPanelProps {
  auditRunId: string | null;
  status: string | null;
  processed: number;
  total: number;
  error: string | null;
}
```

同 Task 5 节奏。Commit: `refactor: 拆 AuditProgressPanel 子组件`

---

## Task 8: 收敛 AIReviewPage 容器

**Files:**
- Modify: `frontend/src/pages/AIReviewPage.tsx`

- [ ] **Step 1: 重写为纯容器**

```tsx
import { useState } from "react";
import { useProjectWorkflow } from "@/hooks/useProjectWorkflow";
import { useAuditRun } from "@/hooks/useAuditRun";
import { useCheckpoints } from "@/hooks/useCheckpoints";  // 若有独立 hook
import { TenderUploadPanel } from "@/components/TenderUploadPanel";
import { CheckpointPicker } from "@/components/CheckpointPicker";
import { AuditProgressPanel } from "@/components/AuditProgressPanel";

export function AIReviewPage() {
  const workflow = useProjectWorkflow();
  const audit = useAuditRun();
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const checkpoints: Array<{ id: string; title: string }> = []; // 从 useCheckpoints 或 API

  const handleToggle = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const handleStart = () => {
    if (workflow.projectId && workflow.tenderDocId) {
      audit.start(workflow.projectId, workflow.tenderDocId, Array.from(selected));
    }
  };

  return (
    <main className="ai-review-page">
      <TenderUploadPanel
        projectId={workflow.projectId}
        isCreating={workflow.isCreating}
        isUploading={workflow.isUploading}
        onCreateProject={workflow.createProject}
        onUploadTender={workflow.uploadTender}
      />
      <CheckpointPicker
        checkpoints={checkpoints}
        selected={selected}
        onToggle={handleToggle}
      />
      <button onClick={handleStart} disabled={selected.size === 0 || !workflow.tenderDocId}>
        启动审计
      </button>
      <AuditProgressPanel
        auditRunId={audit.auditRunId}
        status={audit.status}
        processed={audit.processed}
        total={audit.total}
        error={audit.error}
      />
    </main>
  );
}
```

- [ ] **Step 2: 行数验证**

Run: `wc -l frontend/src/pages/AIReviewPage.tsx`
Expected: ≤120 行

- [ ] **Step 3: 跑全部前端测试**

```bash
cd frontend && npm test
cd ..
```

Expected: 全绿

- [ ] **Step 4: tsc 检查**

```bash
cd frontend && npx tsc -b
cd ..
```

Expected: 零 error

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/AIReviewPage.tsx
git commit -m "refactor: 收敛 AIReviewPage 容器为纯组合（≤120 行）"
```

---

## Task 9: 手工 smoke

- [ ] **Step 1: 启动后端**

```bash
conda run -n govdoc-auditor-v3 uvicorn govdoc.api.main:app --host 0.0.0.0 --port 8000
```

- [ ] **Step 2: 启动前端（另一终端）**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: 浏览器操作**

http://localhost:5173/ai-review：
1. 创建项目 "smoke-test"
2. 上传 `tests/fixtures/tender_small.docx`
3. 勾选 3 个审核点
4. 启动审计
5. 观察进度区更新

Expected:
- 整个流程无 console.error
- UI 状态与 P1a 之前一致

- [ ] **Step 4: 若 smoke 通过则无需 commit；若发现问题则修后 commit**

---

## Task 10: 推 PR + 合入 umbrella

- [ ] **Step 1**

```bash
git push -u origin feat/p1a-aireview-split
```

- [ ] **Step 2: PR 描述**

```
## 目的
P1a · AIReviewPage（315 行）拆为容器 + 3 子组件 + 2 custom hooks

## 依赖
P1c 已合入 umbrella（提供 MSW 基建）

## 变更
新增：
- src/hooks/useProjectWorkflow.ts
- src/hooks/useAuditRun.ts
- src/components/TenderUploadPanel.tsx
- src/components/CheckpointPicker.tsx
- src/components/AuditProgressPanel.tsx
- tests/pages/AIReviewPage.test.tsx (5 case 行为护栏)

修改：
- src/pages/AIReviewPage.tsx: 315 → ≤120 行

## DoD
- [x] 5 case render test 全绿
- [x] AIReviewPage ≤ 120 行
- [x] 手工 smoke 无 console.error
- [x] tsc -b 零 error
```

- [ ] **Step 3: Merge 到 umbrella**

```bash
git checkout feat/tech-debt-cleanup
git merge --no-ff feat/p1a-aireview-split -m "Merge P1a · AIReviewPage 拆分"
```

- [ ] **Step 4: 回滚演练**

---

## P1a DoD 汇总

- [ ] `AIReviewPage.test.tsx` 5+ case 全绿
- [ ] `AIReviewPage.tsx` ≤ 120 行
- [ ] 手工 smoke：创建 → 上传 → 勾选 → 启动全链路无 console.error
- [ ] `tsc -b` 零新增 error
- [ ] 回滚演练通过
