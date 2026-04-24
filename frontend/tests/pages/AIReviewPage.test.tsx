/**
 * AIReviewPage 行为护栏（P1a Bundle 1）。
 *
 * 目的：
 *   在 Bundle 2–4（拆 hooks / 子组件 / 收敛容器）重构之前，锁住当前 UI 行为。
 *   重构过程中只要 5 个 case 保持全绿，行为即未退化。
 *
 * 策略选择：
 *   采用 MockWorkbenchProvider（直接注入 WorkbenchContextValue），
 *   而非 real WorkbenchProvider + MSW。理由：
 *     - P1a 验证的是「页面如何消费 context」，非 context 内部行为
 *     - 真 Provider 会在 mount 时发起 4 路并发 API + 每个 project 再拉 tender docs，
 *       测试将陷入轮询 / setInterval 地狱，与拆分目标无关
 *     - Mock 版让每个 case 用最小 overrides 精确构造断言场景
 *
 * 最小外部改动：
 *   V3WorkbenchContext.tsx 将 `WorkbenchContext` 由 private 改为 `export`，
 *   以便本文件的 Provider 使用同一 Context 对象（否则 useWorkbench 走不通）。
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";

import { AIReviewPage } from "@/pages/AIReviewPage";
import {
  WorkbenchContext,
  type WorkbenchContextValue,
} from "@/context/V3WorkbenchContext";
import type {
  AuditRunProgress,
  CheckpointItem,
  GovCheckpointPayload,
  Project,
  TenderDoc,
} from "@/types/ui";

/* ──────────────────────────────────────────────────────────────
 * MockWorkbenchProvider：提供最小可用的 WorkbenchContextValue
 * ────────────────────────────────────────────────────────────── */

type FinalCheckpoint = CheckpointItem & { parsed: GovCheckpointPayload };

function makePayload(id: string, title: string): GovCheckpointPayload {
  return {
    id,
    category: "其他违法违规",
    title,
    description: "",
    legal_basis: [],
    severity: "minor",
    retrieval_hint: "",
  };
}

function makeFinal(id: string, title: string): FinalCheckpoint {
  const payload = makePayload(id, title);
  return {
    id,
    kind: "final",
    status: "approved",
    payload_json: JSON.stringify(payload),
    approved_by: "admin",
    rule_source_id: null,
    parsed: payload,
  };
}

function defaultValue(): WorkbenchContextValue {
  return {
    apiConnected: true,
    ruleSources: [],
    activeRuleSource: undefined,
    selectedRuleSourceId: null,
    setSelectedRuleSourceId: vi.fn(),
    checkpoints: [],
    finalCheckpoints: [],
    activeRuleSourceCheckpoints: [],
    extractingRuleSourceId: null,
    extractStatus: null,
    extractError: null,
    uploadRuleAndExtract: vi.fn(),
    pollExtractRun: vi.fn(),
    projects: [],
    activeProject: undefined,
    selectedProjectId: null,
    setSelectedProjectId: vi.fn(),
    createProject: vi.fn(),
    uploadTenderDoc: vi.fn(),
    uploadWarning: null,
    tenderDocs: {},
    auditRuns: [],
    activeAuditRun: undefined,
    selectedAuditRunId: null,
    setSelectedAuditRunId: vi.fn(),
    createAuditRun: vi.fn(),
    auditProgress: null,
    logs: [],
    pointRuns: [],
    activePointRun: undefined,
    selectedPointRunId: null,
    setSelectedPointRunId: vi.fn(),
    retryPointRun: vi.fn(),
    workpaperHtml: "",
    workpaperJson: null,
    workpaperSaveStatus: "idle",
    finalizeStatus: "idle",
    loadWorkpaper: vi.fn(),
    setWorkpaperHtml: vi.fn(),
    saveWorkpaper: vi.fn(),
    finalizeWorkpaper: vi.fn(),
    importCheckpointFile: vi.fn(),
    updateCheckpoint: vi.fn(),
    deleteCheckpoint: vi.fn(),
    refreshAll: vi.fn(),
  };
}

function MockWorkbenchProvider(props: {
  children: ReactNode;
  overrides?: Partial<WorkbenchContextValue>;
}) {
  const value: WorkbenchContextValue = {
    ...defaultValue(),
    ...(props.overrides ?? {}),
  };
  return (
    <WorkbenchContext.Provider value={value}>
      {props.children}
    </WorkbenchContext.Provider>
  );
}

function renderPage(overrides?: Partial<WorkbenchContextValue>) {
  return render(
    <MemoryRouter initialEntries={["/ai-review"]}>
      <MockWorkbenchProvider overrides={overrides}>
        <AIReviewPage />
      </MockWorkbenchProvider>
    </MemoryRouter>,
  );
}

/* ──────────────────────────────────────────────────────────────
 * 测试夹具
 * ────────────────────────────────────────────────────────────── */

const sampleProject: Project = {
  id: "p-1",
  name: "项目甲",
  created_at: "2026-04-19T00:00:00Z",
  created_by: "admin",
};

const sampleTenderDoc: TenderDoc = {
  id: "td-1",
  project_id: "p-1",
  filename: "tender.docx",
  markdown_path: "/tmp/tender.md",
};

const sampleCheckpoints: FinalCheckpoint[] = [
  makeFinal("cp-1", "采购范围"),
  makeFinal("cp-2", "供应商资格"),
];

/* ──────────────────────────────────────────────────────────────
 * 用例
 * ────────────────────────────────────────────────────────────── */

describe("AIReviewPage · 行为护栏", () => {
  it("首次渲染显示「任务设置」与「审核进度」两张卡片", () => {
    renderPage();

    expect(
      screen.getByRole("heading", { level: 3, name: "任务设置" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 3, name: "审核进度" }),
    ).toBeInTheDocument();
  });

  it("无 activeProject 时，不渲染「上传招标文书」与「选择审核点」子区块", () => {
    renderPage();

    // 上传区 / 审核点多选区的 Field label 都不应出现
    expect(screen.queryByText("上传招标文书")).not.toBeInTheDocument();
    expect(screen.queryByText("选择审核点")).not.toBeInTheDocument();
    // 启动审核按钮也应不存在
    expect(
      screen.queryByRole("button", { name: /启动审核/ }),
    ).not.toBeInTheDocument();
  });

  it("输入新项目名称后点击「新建」会调用 createProject", async () => {
    const createProject = vi.fn().mockResolvedValue(sampleProject);
    renderPage({ createProject });

    const nameInput = screen.getByPlaceholderText("输入项目名称");
    await userEvent.type(nameInput, "测试项目");

    const createBtn = screen.getByRole("button", { name: "新建" });
    expect(createBtn).not.toBeDisabled();
    await userEvent.click(createBtn);

    expect(createProject).toHaveBeenCalledWith("测试项目");
  });

  it("有 activeProject + tenderDoc + finalCheckpoints 时，「启动审核」按钮随选中数量切换 disabled", async () => {
    renderPage({
      projects: [sampleProject],
      activeProject: sampleProject,
      selectedProjectId: sampleProject.id,
      tenderDocs: { [sampleProject.id]: sampleTenderDoc },
      finalCheckpoints: sampleCheckpoints,
      checkpoints: sampleCheckpoints,
    });

    // 选中 0 → 按钮 disabled
    const startBtn = screen.getByRole("button", { name: /启动审核/ });
    expect(startBtn).toBeDisabled();

    // 勾选首个审核点 → 按钮可点
    const cp1 = screen.getByLabelText("采购范围");
    await userEvent.click(cp1);
    expect(startBtn).not.toBeDisabled();
    expect(startBtn).toHaveTextContent(/1 个审核点/);
  });

  it("auditProgress 非空时，进度卡片显示总计 / 已完成 / 失败 / 待处理", () => {
    const progress: AuditRunProgress = {
      audit_run_id: "ar-1",
      status: "running",
      total_count: 5,
      processed_count: 2,
      point_runs: [
        { id: "pr-1", checkpoint_final_id: "cp-1", status: "completed", error: null, finding_json: null },
        { id: "pr-2", checkpoint_final_id: "cp-2", status: "completed", error: null, finding_json: null },
        { id: "pr-3", checkpoint_final_id: "cp-3", status: "failed", error: "oops", finding_json: null },
        { id: "pr-4", checkpoint_final_id: "cp-4", status: "running", error: null, finding_json: null },
        { id: "pr-5", checkpoint_final_id: "cp-5", status: "pending", error: null, finding_json: null },
      ],
    };

    renderPage({
      projects: [sampleProject],
      activeProject: sampleProject,
      selectedProjectId: sampleProject.id,
      tenderDocs: { [sampleProject.id]: sampleTenderDoc },
      auditProgress: progress,
    });

    // 用 MetricCard 内部结构断言 label → value 对应关系
    const totalCard = screen.getByText("总计").closest(".metric-card") as HTMLElement;
    const doneCard = screen.getByText("已完成").closest(".metric-card") as HTMLElement;
    const failedCard = screen.getByText("失败").closest(".metric-card") as HTMLElement;
    const pendingCard = screen.getByText("待处理").closest(".metric-card") as HTMLElement;

    expect(within(totalCard).getByText("5")).toBeInTheDocument();
    expect(within(doneCard).getByText("2")).toBeInTheDocument();
    expect(within(failedCard).getByText("1")).toBeInTheDocument();
    // running + pending = 2
    expect(within(pendingCard).getByText("2")).toBeInTheDocument();
  });
});
