---
type: plan
node_id: plan:audit-status-ui-v2-impl
title: "审核状态 UI 改进版实现计划"
date: 2026-05-22
---

# 审核状态 UI 改进版实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 PR #26 的"减一层"策略，改进审核要点列表和 PointInsight 面板的视觉样式，同时清理死代码。

**Architecture:** 修改 3 个页面级组件（AuditResultsPage、AIReviewPage、PointInsight）和 1 个 adapter（backendToUi），清理未使用的函数和 import。StatusBadge 和 shadcn/ui 组件不做修改。所有样式使用 Tailwind CSS token，禁止手写 CSS。

**Tech Stack:** React + TypeScript + Tailwind CSS + shadcn/ui + lucide-react（仅 PointInsight）

**设计稿核对约束:** 每个任务完成后，必须调用 Pencil MCP 截取 `pencil/pencil-new.pen` 中对应节点的截图，与实现结果做视觉比对。

---

## File Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/src/adapters/backendToUi.ts` | MODIFY | 删除 `verdictToStatus`/`severityToRisk`，修复 `workpaperToHtml` |
| `frontend/src/context/V3WorkbenchContext.tsx` | MODIFY | 删除未使用的 `verdictToStatus` import |
| `frontend/src/components/PointInsight.tsx` | MODIFY | 新增 verdict 面板（图标+文字） |
| `frontend/src/pages/AuditResultsPage.tsx` | MODIFY | 色条列表 + useMemo 优化 |
| `frontend/src/pages/AIReviewPage.tsx` | MODIFY | 色条列表 + useMemo + 删除 Dialog + 内联 PointInsight |
| `frontend/tests/adapters/backendToUi.test.ts` | MODIFY | 删除旧测试，改测 `workpaperToHtml` |

---

### Task 1: 清理 backendToUi.ts 死代码 + 修复 workpaperToHtml

**Files:**
- Modify: `frontend/src/adapters/backendToUi.ts:34-56` (删除两个函数)
- Modify: `frontend/src/adapters/backendToUi.ts:99` (workpaperToHtml 改用 verdictLabel)
- Modify: `frontend/src/context/V3WorkbenchContext.tsx:30` (删除未使用 import)
- Modify: `frontend/src/pages/AuditResultsPage.tsx:5` (删除未使用 import)

- [ ] **Step 1: 删除 backendToUi.ts 中的 verdictToStatus 和 severityToRisk**

删除 `frontend/src/adapters/backendToUi.ts` 第 34-56 行（`verdictToStatus` 和 `severityToRisk` 两个函数）。

- [ ] **Step 2: 修复 workpaperToHtml 中的 verdict 显示**

在 `frontend/src/adapters/backendToUi.ts` 第 99 行，将：
```tsx
`<blockquote><strong>${escapeHtml(cp.title)}</strong> — ${escapeHtml(v.verdict)}</blockquote>`,
```
改为：
```tsx
`<blockquote><strong>${escapeHtml(cp.title)}</strong> — ${escapeHtml(verdictLabel(v.verdict))}</blockquote>`,
```

- [ ] **Step 3: 删除 V3WorkbenchContext.tsx 中未使用的 import**

在 `frontend/src/context/V3WorkbenchContext.tsx` 第 25-31 行，将：
```tsx
import {
  extractSummaryFromHtml,
  parseCheckpointPayload,
  parseFindingJson,
  pointRunToLog,
  verdictToStatus,
} from "../adapters/backendToUi";
```
改为：
```tsx
import {
  extractSummaryFromHtml,
  parseCheckpointPayload,
  parseFindingJson,
  pointRunToLog,
} from "../adapters/backendToUi";
```

- [ ] **Step 4: 删除 AuditResultsPage.tsx 中未使用的 import**

在 `frontend/src/pages/AuditResultsPage.tsx` 第 5 行，将：
```tsx
import { parseFindingJson, verdictToStatus } from "@/adapters/backendToUi";
```
改为：
```tsx
import { parseFindingJson } from "@/adapters/backendToUi";
```

- [ ] **Step 5: 运行测试确认无编译错误**

```bash
cd frontend && npx tsc --noEmit
```
Expected: 编译通过（测试文件会报错，因为仍引用 `verdictToStatus`，这在 Task 2 修复）

- [ ] **Step 6: Commit**

```bash
git add frontend/src/adapters/backendToUi.ts frontend/src/context/V3WorkbenchContext.tsx frontend/src/pages/AuditResultsPage.tsx
git commit -m "refactor: 删除 verdictToStatus/severityToRisk 死代码，workpaperToHtml 改用 verdictLabel"
```

---

### Task 2: 更新 backendToUi 测试

**Files:**
- Modify: `frontend/tests/adapters/backendToUi.test.ts`

- [ ] **Step 1: 重写测试文件**

将 `frontend/tests/adapters/backendToUi.test.ts` 全部替换为：

```tsx
import { describe, expect, it } from "vitest";

import { workpaperToHtml } from "@/adapters/backendToUi";
import type { GovFinding, VerdictValue, WorkpaperPayload } from "@/types/ui";

function makeFinding(verdict: VerdictValue): GovFinding {
  return {
    checkpoint: {
      id: `cp-${verdict}`,
      category: "其他违法违规",
      title: `${verdict}审核点`,
      description: "测试描述",
      legal_basis: [],
      severity: "minor",
      retrieval_hint: "",
    },
    verdict: {
      verdict,
      rationale: "测试理由",
      evidence_quotes: [],
      suggestion: "",
    },
    evidence_refs: [],
    case_refs: [],
  };
}

function makeWorkpaper(verdicts: VerdictValue[]): WorkpaperPayload {
  return {
    summary: "测试总结",
    findings: verdicts.map((v) => {
      const f = makeFinding(v);
      return { checkpoint: f.checkpoint, verdict: f.verdict, evidence_refs: f.evidence_refs };
    }),
  };
}

describe("workpaperToHtml", () => {
  it("合规 finding 显示 '合规通过'", () => {
    const html = workpaperToHtml(makeWorkpaper(["合规"]));
    expect(html).toContain("合规通过");
    expect(html).not.toContain("— 合规<");
  });

  it("不合规 finding 显示 '不合规'", () => {
    const html = workpaperToHtml(makeWorkpaper(["不合规"]));
    expect(html).toContain("不合规");
  });

  it("存疑 finding 显示 '存疑待定'", () => {
    const html = workpaperToHtml(makeWorkpaper(["存疑"]));
    expect(html).toContain("存疑待定");
  });

  it("包含摘要和发现数量", () => {
    const html = workpaperToHtml(makeWorkpaper(["合规", "不合规"]));
    expect(html).toContain("测试总结");
    expect(html).toContain("审查发现 (2)");
  });
});
```

- [ ] **Step 2: 运行测试验证通过**

```bash
cd frontend && npx vitest run tests/adapters/backendToUi.test.ts
```
Expected: 4 tests PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/adapters/backendToUi.test.ts
git commit -m "test: backendToUi 测试改为覆盖 workpaperToHtml verdict 展示"
```

---

### Task 3: 改进 PointInsight — 新增 Verdict 面板

**Files:**
- Modify: `frontend/src/components/PointInsight.tsx`

**Pencil MCP 核对:** 完成后截取 `pencil/pencil-new.pen` 节点 `O1vOH` (VerdictPanel-Simplified)，比对 verdict 面板样式。

- [ ] **Step 1: 重写 PointInsight.tsx**

将 `frontend/src/components/PointInsight.tsx` 替换为：

```tsx
import { CircleCheck, CircleX, TriangleAlert, type LucideIcon } from "lucide-react";

import type { GovCheckpointPayload, GovFinding, PointRunStatus } from "@/types/ui";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/StatusBadge";

const SEVERITY_LABEL: Record<string, string> = { critical: "高风险", major: "中风险", minor: "低风险" };
const SEVERITY_VARIANT: Record<string, "err" | "warn" | "default"> = { critical: "err", major: "warn", minor: "default" };

const VERDICT_PANEL: Record<string, {
  bg: string; border: string; text: string; icon: LucideIcon; hint: string;
}> = {
  "合规": {
    bg: "bg-status-ok-bg", border: "border-status-ok/40", text: "text-status-ok",
    icon: CircleCheck, hint: "该审核点未发现合规风险",
  },
  "不合规": {
    bg: "bg-status-err-bg", border: "border-status-err-border", text: "text-status-err",
    icon: CircleX, hint: "该审核点存在合规风险",
  },
  "存疑": {
    bg: "bg-status-warn-bg", border: "border-status-warn/40", text: "text-status-warn",
    icon: TriangleAlert, hint: "该审核点需要人工复核",
  },
};

export function PointInsight({ checkpoint, finding, pointStatus }: {
  checkpoint: GovCheckpointPayload;
  finding: GovFinding | null;
  pointStatus: PointRunStatus;
}) {
  const verdict = finding?.verdict;
  const panel = verdict ? VERDICT_PANEL[verdict.verdict] : null;

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-base font-semibold text-text-primary">{checkpoint.title}</h3>
        <div className="mt-2 flex items-center gap-2 flex-wrap">
          <Badge variant={SEVERITY_VARIANT[checkpoint.severity] ?? "muted"}>{SEVERITY_LABEL[checkpoint.severity] ?? checkpoint.severity}</Badge>
          <Badge variant="outline">{checkpoint.category}</Badge>
        </div>
      </div>

      {panel && verdict ? (
        <div className={cn("flex items-center justify-between rounded-card border p-4", panel.bg, panel.border)}>
          <div className="flex items-center gap-3">
            <panel.icon className={cn("h-5 w-5 shrink-0", panel.text)} />
            <div>
              <p className="text-xs text-text-muted">审核结论</p>
              <p className={cn("text-base font-bold", panel.text)}>{verdict.verdict}</p>
            </div>
          </div>
          <p className={cn("text-sm font-semibold", panel.text)}>{panel.hint}</p>
        </div>
      ) : (
        <div className="flex items-center justify-between rounded-card border border-gray-200 bg-gray-50 p-4">
          <p className="text-sm font-medium text-text-primary">审核状态</p>
          <StatusBadge status={pointStatus} />
        </div>
      )}

      {verdict && (
        <>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="text-sm font-medium text-text-primary mb-2">审查意见</h4>
              <p className="text-sm text-text-secondary leading-relaxed">{verdict.rationale}</p>
            </div>
            <div>
              <h4 className="text-sm font-medium text-text-primary mb-2">整改建议</h4>
              <p className="text-sm text-text-secondary leading-relaxed">{verdict.suggestion}</p>
            </div>
          </div>

          {verdict.evidence_quotes.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-text-primary mb-2">原文引用</h4>
              <div className="space-y-2">
                {verdict.evidence_quotes.map((q, i) => (
                  <blockquote key={i} className="border-l-2 border-accent pl-3 text-sm text-text-secondary italic">"{q}"</blockquote>
                ))}
              </div>
            </div>
          )}

          {checkpoint.legal_basis.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-text-primary mb-2">法条依据</h4>
              <div className="space-y-2">
                {checkpoint.legal_basis.map((lb, i) => (
                  <div key={i} className="rounded-btn bg-accent-light px-3 py-2">
                    <p className="text-sm font-medium text-accent">{lb.law_name} {lb.article}</p>
                    {lb.quote && <p className="text-xs text-text-secondary mt-0.5">{lb.quote}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 类型检查**

```bash
cd frontend && npx tsc --noEmit
```
Expected: PASS

- [ ] **Step 3: Pencil MCP 设计核对**

调用 Pencil MCP `get_screenshot`，文件 `pencil/pencil-new.pen`，节点 `O1vOH`。比对 verdict 面板：图标+大字文本（非 Badge），浅色背景，右侧提示语。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/PointInsight.tsx
git commit -m "feat: PointInsight 新增 verdict 面板（图标+文字，减一层设计）"
```

---

### Task 4: 改进 AuditResultsPage — 色条列表 + useMemo

**Files:**
- Modify: `frontend/src/pages/AuditResultsPage.tsx`

**Pencil MCP 核对:** 完成后截取 `pencil/pencil-new.pen` 节点 `qr7GB` (PR26-v2 Point List)，比对列表色条、白底、subtle Badge。

- [ ] **Step 1: 重写 AuditResultsPage.tsx**

将 `frontend/src/pages/AuditResultsPage.tsx` 替换为：

```tsx
import { RefreshCw, Send } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useWorkbench } from "@/context/V3WorkbenchContext";
import { parseFindingJson } from "@/adapters/backendToUi";
import { listComments, createComment } from "@/api/v3";
import type { Comment } from "@/types/ui";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { PointInsight } from "@/components/PointInsight";

const VERDICT_BORDER: Record<string, string> = {
  "合规": "border-l-status-ok",
  "不合规": "border-l-status-err",
  "存疑": "border-l-status-warn",
};
const VERDICT_DOT: Record<string, string> = {
  "合规": "bg-status-ok",
  "不合规": "bg-status-err",
  "存疑": "bg-status-warn",
};

export function AuditResultsPage() {
  const {
    auditRuns, auditProgress, selectedAuditRunId, setSelectedAuditRunId,
    selectedPointRunId, setSelectedPointRunId, finalCheckpoints, retryPointRun,
  } = useWorkbench();

  const selectedAuditProgress =
    auditProgress?.audit_run_id === selectedAuditRunId ? auditProgress : null;
  const pointRuns = selectedAuditProgress?.point_runs ?? [];

  const checkpointById = useMemo(
    () => new Map(finalCheckpoints.map((cp) => [cp.id, cp])),
    [finalCheckpoints],
  );
  const pointRunViews = useMemo(() => pointRuns.map((pr) => {
    const checkpoint = checkpointById.get(pr.checkpoint_final_id)?.parsed ?? null;
    const finding = parseFindingJson(pr.finding_json);
    const verdict = finding?.verdict?.verdict;
    return { pr, checkpoint, finding, verdict, title: checkpoint?.title ?? "（已失效）" };
  }), [checkpointById, pointRuns]);

  const activeView = pointRunViews.find((v) => v.pr.id === selectedPointRunId);

  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [feedbackText, setFeedbackText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (auditRuns.length === 0) return;
    if (selectedAuditRunId && auditRuns.some((r) => r.id === selectedAuditRunId)) return;
    setSelectedAuditRunId(auditRuns[0].id);
  }, [auditRuns, selectedAuditRunId, setSelectedAuditRunId]);

  useEffect(() => {
    setComments([]);
    if (!selectedPointRunId) return;
    let cancelled = false;
    listComments("AuditPointRun", selectedPointRunId).then((nextComments) => {
      if (!cancelled) setComments(nextComments);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [selectedPointRunId]);

  async function handleRetry(prId: string) {
    setRetryingId(prId);
    try { await retryPointRun(prId); } finally { setRetryingId(null); }
  }

  async function handleSubmitFeedback() {
    if (!selectedPointRunId || !feedbackText.trim()) return;
    setSubmitting(true);
    try {
      const c = await createComment("AuditPointRun", selectedPointRunId, "reviewer", feedbackText);
      setComments((prev) => [c, ...prev]);
      setFeedbackText("");
    } finally { setSubmitting(false); }
  }

  return (
    <div className="flex flex-col h-screen">
      <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
        <span className="text-base font-semibold text-text-primary">审核结果</span>
        <Select value={selectedAuditRunId ?? ""} onValueChange={(v: string) => setSelectedAuditRunId(v || null)}>
          <SelectTrigger className="w-56"><SelectValue placeholder="选择审核运行" /></SelectTrigger>
          <SelectContent>
            {auditRuns.map((r) => (
              <SelectItem key={r.id} value={r.id}>{r.project_name || r.id.slice(0, 8)} ({r.status})</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </header>

      {pointRunViews.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <EmptyState title="暂无审核结果" description="请先完成一次审核运行。" />
        </div>
      ) : (
        <div className="flex flex-1 overflow-hidden">
          <div className="w-80 shrink-0 border-r bg-surface-card overflow-auto">
            <div className="p-4 border-b">
              <p className="text-sm font-medium text-text-primary">审核要点列表</p>
              <p className="text-xs text-text-muted">{pointRuns.length} 个审核点</p>
            </div>
            <ScrollArea className="h-[calc(100vh-120px)]">
              {pointRunViews.map(({ pr, title, verdict }) => (
                <button
                  key={pr.id}
                  className={cn(
                    "flex w-full items-center justify-between border-b border-l-4 px-4 py-3 text-left transition-colors hover:bg-surface",
                    VERDICT_BORDER[verdict ?? ""] ?? "border-l-transparent",
                    pr.id === selectedPointRunId && "ring-1 ring-inset ring-accent",
                  )}
                  onClick={() => setSelectedPointRunId(pr.id)}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={cn("h-2 w-2 shrink-0 rounded-full", VERDICT_DOT[verdict ?? ""] ?? "bg-gray-300")} />
                    <span className="text-sm truncate">{title}</span>
                  </div>
                  <StatusBadge status={verdict ?? pr.status} />
                </button>
              ))}
            </ScrollArea>
          </div>

          <div className="flex-1 overflow-auto p-7 space-y-5">
            {activeView ? (
              activeView.checkpoint ? (
                <>
                  <PointInsight checkpoint={activeView.checkpoint} finding={activeView.finding} pointStatus={activeView.pr.status} />
                  {(activeView.pr.status === "failed" || activeView.pr.status === "waiting_retry") && (
                    <Button variant="secondary" disabled={retryingId === activeView.pr.id} onClick={() => handleRetry(activeView.pr.id)}>
                      <RefreshCw className={cn("h-4 w-4", retryingId === activeView.pr.id && "animate-spin")} />
                      {retryingId === activeView.pr.id ? "正在重试..." : "重试此审核点"}
                    </Button>
                  )}
                  <Separator />
                  <div>
                    <h4 className="text-sm font-medium text-text-primary mb-3">人工反馈</h4>
                    <div className="flex gap-2 mb-4">
                      <Textarea placeholder="输入审查意见或修改建议..." value={feedbackText} onChange={(e) => setFeedbackText(e.target.value)} className="flex-1" />
                      <Button size="icon" disabled={!feedbackText.trim() || submitting} onClick={handleSubmitFeedback}><Send className="h-4 w-4" /></Button>
                    </div>
                    {comments.map((c) => (
                      <div key={c.id} className="border-b py-2.5 last:border-0">
                        <p className="text-sm text-text-primary">{c.text}</p>
                        <p className="text-xs text-text-muted mt-1">{c.author} · {new Date(c.created_at).toLocaleString("zh-CN")}</p>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <EmptyState title="审核点数据已失效" description="该审核点对应的审查标准已被删除或重新导入，无法显示详细结果。请使用当前审查标准重新发起审核。" />
              )
            ) : (
              <div className="flex-1 flex items-center justify-center h-full">
                <EmptyState title="请选择审核点" description="点击左侧列表查看详细审查结果。" />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 类型检查**

```bash
cd frontend && npx tsc --noEmit
```
Expected: PASS

- [ ] **Step 3: Pencil MCP 设计核对**

调用 Pencil MCP `get_screenshot`，文件 `pencil/pencil-new.pen`，节点 `qr7GB`。比对：
- 白底行 + 左侧 4px 色条（红/绿/黄/透明）
- 选中态为蓝色 ring（非蓝色背景）
- 小圆点颜色匹配 verdict
- subtle Badge（现有 StatusBadge 样式）

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/AuditResultsPage.tsx
git commit -m "feat: AuditResultsPage 色条列表 + useMemo 优化（减一层设计）"
```

---

### Task 5: 改进 AIReviewPage — 色条列表 + 删除 Dialog + 内联 PointInsight

**Files:**
- Modify: `frontend/src/pages/AIReviewPage.tsx`

**Pencil MCP 核对:** 完成后截取 `pencil/pencil-new.pen` 节点 `bixfN` (PR26-v2/AuditResults-Improved 整体)，比对列表色条样式一致性。

- [ ] **Step 1: 重写 AIReviewPage.tsx 的审核进行中部分**

将 `frontend/src/pages/AIReviewPage.tsx` 替换为：

```tsx
import { Check, ChevronRight, FileText, Loader2, Paperclip, Plus, Upload, X } from "lucide-react";
import { useMemo, useState } from "react";

import { useWorkbench } from "@/context/V3WorkbenchContext";
import { useProjectWorkflow } from "@/hooks/useProjectWorkflow";
import { useAuditRun } from "@/hooks/useAuditRun";
import { parseFindingJson } from "@/adapters/backendToUi";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { MetricCard } from "@/components/MetricCard";
import { StatusBadge } from "@/components/StatusBadge";
import { FileDropzone } from "@/components/FileDropzone";
import { EmptyState } from "@/components/EmptyState";
import { ProgressTimeline } from "@/components/ProgressTimeline";
import { PointInsight } from "@/components/PointInsight";

const VERDICT_BORDER: Record<string, string> = {
  "合规": "border-l-status-ok",
  "不合规": "border-l-status-err",
  "存疑": "border-l-status-warn",
};
const VERDICT_DOT: Record<string, string> = {
  "合规": "bg-status-ok",
  "不合规": "bg-status-err",
  "存疑": "bg-status-warn",
};
const STATUS_DOT: Record<string, string> = {
  completed: "bg-status-ok",
  running: "bg-accent",
  failed: "bg-status-err",
  pending: "bg-gray-300",
  waiting_retry: "bg-status-warn",
};

export function AIReviewPage() {
  const {
    projects, activeProject, selectedProjectId, setSelectedProjectId,
    auditInputDocs, finalCheckpoints, auditProgress, retryPointRun, resetProjectDocs,
  } = useWorkbench();

  const wf = useProjectWorkflow();
  const auditRun = useAuditRun();
  const [selectedTimelinePrId, setSelectedTimelinePrId] = useState<string | null>(null);

  const inputDocs = activeProject ? auditInputDocs[activeProject.id] : undefined;
  const mainDoc = inputDocs?.mainDoc;
  const supplementaryDocs = inputDocs?.supplementaryDocs ?? [];
  const isRunning = auditProgress != null;
  const pointRuns = auditProgress?.point_runs ?? [];
  const progress = auditProgress ? (auditProgress.total_count > 0 ? (auditProgress.processed_count / auditProgress.total_count) * 100 : 0) : 0;
  const completedCount = pointRuns.filter((p) => p.status === "completed").length;
  const failedCount = pointRuns.filter((p) => p.status === "failed").length;
  const runningCount = pointRuns.filter((p) => p.status === "running").length;

  const checkpointById = useMemo(
    () => new Map(finalCheckpoints.map((cp) => [cp.id, cp])),
    [finalCheckpoints],
  );
  const pointRunViews = useMemo(() => pointRuns.map((pr) => {
    const checkpoint = checkpointById.get(pr.checkpoint_final_id)?.parsed ?? null;
    const finding = parseFindingJson(pr.finding_json ?? null);
    const verdict = finding?.verdict?.verdict;
    return { pr, checkpoint, finding, verdict, title: checkpoint?.title ?? pr.checkpoint_final_id.slice(0, 8) };
  }), [checkpointById, pointRuns]);

  const selectedTimeline =
    pointRunViews.find((v) => v.pr.id === selectedTimelinePrId)
    ?? pointRunViews.find((v) => v.pr.status === "running")
    ?? pointRunViews[0];

  if (isRunning) {
    return (
      <div className="flex flex-col h-screen">
        <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
          <div className="flex items-center gap-2">
            <span className="text-base font-semibold text-text-primary">AI 审核</span>
            <Badge variant="default">审核进行中</Badge>
          </div>
          <span className="text-xs text-text-muted">已完成 {auditProgress.processed_count}/{auditProgress.total_count}</span>
        </header>
        <div className="flex-1 space-y-5 p-7 overflow-auto">
          <div>
            <h2 className="text-lg font-semibold">{activeProject?.name ?? "审核任务"}</h2>
            <p className="text-sm text-text-muted">共 {auditProgress.total_count} 个审核要点，已处理 {auditProgress.processed_count} 个</p>
          </div>
          <Card>
            <CardContent className="p-4 space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-text-secondary">审核进度</span>
                <span className="font-medium">{Math.round(progress)}%</span>
              </div>
              <Progress value={progress} />
              <div className="grid grid-cols-4 gap-3">
                <MetricCard label="总审核点" value={auditProgress.total_count} tone="blue" />
                <MetricCard label="已完成" value={completedCount} tone="green" />
                <MetricCard label="审查中" value={runningCount} tone="amber" />
                <MetricCard label="失败" value={failedCount} tone="red" />
              </div>
            </CardContent>
          </Card>
          <div className="grid grid-cols-2 gap-5">
            <Card>
              <CardHeader><CardTitle>审核要点</CardTitle></CardHeader>
              <CardContent className="p-0">
                <div className="max-h-[400px] overflow-auto">
                  {pointRunViews.map(({ pr, title, verdict }) => (
                    <button
                      key={pr.id}
                      className={cn(
                        "flex w-full items-center justify-between border-b border-l-4 px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-surface",
                        verdict ? (VERDICT_BORDER[verdict] ?? "border-l-transparent") : "border-l-transparent",
                        pr.id === selectedTimeline?.pr.id && "ring-1 ring-inset ring-accent",
                      )}
                      onClick={() => setSelectedTimelinePrId(pr.id)}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span className={cn("h-2 w-2 shrink-0 rounded-full", verdict ? (VERDICT_DOT[verdict] ?? "bg-gray-300") : (STATUS_DOT[pr.status] ?? "bg-gray-300"))} />
                        <span className="text-sm truncate">{title}</span>
                      </div>
                      <StatusBadge status={verdict ?? pr.status} />
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
            {selectedTimeline && (
              <div className="space-y-4">
                {selectedTimeline.checkpoint && (selectedTimeline.finding || selectedTimeline.pr.status === "completed") && (
                  <Card>
                    <CardContent className="p-5">
                      <PointInsight checkpoint={selectedTimeline.checkpoint} finding={selectedTimeline.finding} pointStatus={selectedTimeline.pr.status} />
                    </CardContent>
                  </Card>
                )}
                <ProgressTimeline
                  pointRun={selectedTimeline.pr}
                  checkpoint={selectedTimeline.checkpoint}
                  onRetry={selectedTimeline.pr.status === "failed" ? () => retryPointRun(selectedTimeline.pr.id) : undefined}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  const step = !selectedProjectId || !activeProject ? 1 : !mainDoc ? 2 : 3;

  return (
    <div className="flex flex-col">
      <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
        <span className="text-base font-semibold text-text-primary">AI 审核</span>
      </header>
      <div className="space-y-6 p-7">
        <div>
          <h2 className="text-lg font-semibold">新建审查任务</h2>
          <p className="text-sm text-text-muted">上传招标文件，选择审查要点，启动 AI 自动审核</p>
        </div>
        <div className="flex items-center gap-3">
          {[{ n: 1, label: "选择或创建项目" }, { n: 2, label: "上传招标文件" }, { n: 3, label: "选择审查要点" }].map((s, i) => (
            <div key={s.n} className="flex items-center gap-3">
              <div className={cn("flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium", step > s.n ? "bg-accent text-white" : step === s.n ? "bg-accent text-white" : "border border-gray-300 text-text-muted")}>
                {step > s.n ? <Check className="h-4 w-4" /> : s.n}
              </div>
              <span className={cn("text-sm", step >= s.n ? "text-text-primary font-medium" : "text-text-muted")}>{s.label}</span>
              {i < 2 && <ChevronRight className="h-4 w-4 text-text-muted" />}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-6">
          <div className="space-y-6">
            <Card>
              <CardHeader><CardTitle>第一步：选择或创建项目</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">选择现有项目</label>
                  <select className="flex h-9 w-full rounded-btn border bg-white px-3 py-1 text-sm" value={selectedProjectId ?? ""} onChange={(e) => setSelectedProjectId(e.target.value || null)}>
                    <option value="">选择项目...</option>
                    {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">或创建新项目</label>
                  <div className="flex gap-2">
                    <Input placeholder="输入项目名称" value={wf.newProjectName} onChange={(e) => wf.setNewProjectName(e.target.value)} />
                    <Button variant="secondary" disabled={!wf.newProjectName || wf.creating} onClick={wf.handleCreateProject}>
                      <Plus className="h-4 w-4" /> 创建
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
            {activeProject && (
              <Card>
                <CardHeader><CardTitle>第二步：上传招标文书</CardTitle></CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-text-secondary">主招标文书</label>
                    {mainDoc ? (
                      <div className="flex items-center gap-2 rounded-card border border-green-300 bg-green-50 p-3">
                        <Check className="h-4 w-4 shrink-0 text-green-600" />
                        <span className="min-w-0 flex-1 truncate text-sm">{mainDoc.filename}</span>
                        <button type="button" className="text-xs text-red-500 hover:text-red-700" onClick={() => resetProjectDocs(activeProject.id)}>移除</button>
                      </div>
                    ) : wf.mainTenderFile ? (
                      <div className="flex items-center gap-2 rounded-card border p-3">
                        <FileText className="h-4 w-4 shrink-0 text-text-muted" />
                        <span className="min-w-0 flex-1 truncate text-sm">{wf.mainTenderFile.name}</span>
                        <button type="button" className="text-xs text-red-500 hover:text-red-700" onClick={() => wf.setMainTenderFile(null)}>移除</button>
                      </div>
                    ) : (
                      <FileDropzone title="点击选择或拖入招标文书" subtitle="支持 .docx, .pdf" accept=".docx,.pdf" onSelect={(files) => { if (files[0]) wf.setMainTenderFile(files[0]); }} />
                    )}
                  </div>
                  {(wf.mainTenderFile || mainDoc) && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-medium text-text-secondary">补充文件（可选）</label>
                        {(wf.supplementaryFiles.length > 0 || supplementaryDocs.length > 0) && (
                          <span className="flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-600">
                            <Paperclip className="h-3 w-3" />
                            {wf.supplementaryFiles.length + supplementaryDocs.length} 个文件
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-text-muted">变更公告、答疑纪要、补充通知等</p>
                      {supplementaryDocs.map((doc) => (
                        <div key={doc.id} className="flex items-center gap-2 rounded-card border bg-gray-50 px-3 py-2">
                          <FileText className="h-4 w-4 shrink-0 text-text-muted" />
                          <span className="min-w-0 flex-1 truncate text-sm">{doc.filename}</span>
                        </div>
                      ))}
                      {wf.supplementaryFiles.map((f, i) => (
                        <div key={`pending-${i}`} className="flex items-center gap-2 rounded-card border bg-gray-50 px-3 py-2">
                          <FileText className="h-4 w-4 shrink-0 text-text-muted" />
                          <span className="min-w-0 flex-1 truncate text-sm">{f.name}</span>
                          <button type="button" className="text-text-muted hover:text-red-500" onClick={() => wf.removeSupplementaryFile(i)}>
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ))}
                      {!mainDoc && (
                        <FileDropzone title="添加补充文件" subtitle="支持 .docx, .pdf，可多选" accept=".docx,.pdf" multiple onSelect={(files) => wf.addSupplementaryFiles(files)} />
                      )}
                    </div>
                  )}
                  {wf.mainTenderFile && !mainDoc && (
                    <Button className="w-full" disabled={wf.uploadingTender} onClick={wf.handleUploadTender}>
                      {wf.uploadingTender ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                      确认上传{wf.supplementaryFiles.length > 0 ? `（含 ${wf.supplementaryFiles.length} 个附件）` : ""}
                    </Button>
                  )}
                  {wf.uploadError && <p className="text-sm text-status-err">{wf.uploadError}</p>}
                </CardContent>
              </Card>
            )}
          </div>
          <Card>
            <CardHeader><CardTitle>第三步：选择审查要点</CardTitle></CardHeader>
            <CardContent>
              {mainDoc ? (
                <div className="space-y-3">
                  <div className="max-h-[360px] overflow-auto space-y-1">
                    {finalCheckpoints.map((cp) => (
                      <label key={cp.id} className="flex items-center gap-3 rounded-btn p-2 hover:bg-surface cursor-pointer">
                        <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-accent" checked={auditRun.selectedCpIds.includes(cp.id)} onChange={() => auditRun.toggleCheckpoint(cp.id)} />
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-text-primary truncate">{cp.parsed.title}</p>
                          <p className="text-xs text-text-muted truncate">{cp.parsed.category}</p>
                        </div>
                      </label>
                    ))}
                    {finalCheckpoints.length === 0 && <p className="text-sm text-text-muted py-4 text-center">暂无审查要点，请先在审核点库中创建。</p>}
                  </div>
                  <Button className="w-full" disabled={auditRun.selectedCpIds.length === 0 || auditRun.startingAudit} onClick={auditRun.handleStartAudit}>
                    {auditRun.startingAudit ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                    开始审核（{auditRun.selectedCpIds.length} 个要点）
                  </Button>
                </div>
              ) : (
                <EmptyState title="请先完成前两步" description="选择项目并上传招标文件后，即可选择审查要点。" />
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 类型检查**

```bash
cd frontend && npx tsc --noEmit
```
Expected: PASS

- [ ] **Step 3: Pencil MCP 设计核对**

调用 Pencil MCP `get_screenshot`，文件 `pencil/pencil-new.pen`，节点 `bixfN`。比对列表样式与 AuditResultsPage 一致：色条 + 白底 + subtle Badge + ring 选中态。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/AIReviewPage.tsx
git commit -m "feat: AIReviewPage 色条列表 + useMemo + 删除 Dialog + 内联 PointInsight"
```

---

### Task 6: 全量测试验证

**Files:** 无新修改

- [ ] **Step 1: 运行全部前端单元测试**

```bash
cd frontend && npx vitest run
```
Expected: 全部 PASS

- [ ] **Step 2: TypeScript 类型检查**

```bash
cd frontend && npx tsc --noEmit
```
Expected: PASS

- [ ] **Step 3: 运行 E2E 测试**

```bash
cd frontend && npx playwright test
```
Expected: 全部 PASS

- [ ] **Step 4: Pencil MCP 整体核对**

调用 Pencil MCP `get_screenshot`，文件 `pencil/pencil-new.pen`，节点 `bixfN` (PR26-v2/AuditResults-Improved 整体页面)。确认最终实现与设计稿一致。

- [ ] **Step 5: 最终 Commit（如有 lint 修复）**

```bash
cd frontend && npx tsc --noEmit && npx vitest run
git status
```
如有未提交的 lint 修复，提交。
