/**
 * AIReviewPage 行为护栏（Tailwind + shadcn/ui 重构后）。
 *
 * 策略：MockWorkbenchProvider 直接注入 WorkbenchContextValue。
 *
 * 覆盖范围（与重构前等价）：
 *   Setup 模式：
 *     1. 首次渲染显示步骤向导标题
 *     2. 无 activeProject 时不渲染上传和审核点选择区域
 *     3. 创建项目按钮调用 createProject
 *     4. 审核点选中数量控制「开始审核」按钮 disabled
 *     5. 上传成功后显示文件名
 *   Running 模式：
 *     6. 进度指标卡片显示 总审核点/已完成/审查中/失败 数值
 *     7. 审核点列表中 verdict 状态通过 StatusBadge 渲染
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";

vi.mock("@radix-ui/react-progress", () => ({
  Root: ({ children, ...props }: any) => <div data-testid="progress" {...props}>{children}</div>,
  Indicator: (props: any) => <div {...props} />,
}));

vi.mock("@radix-ui/react-dialog", () => ({
  Root: ({ children }: any) => <>{children}</>,
  Trigger: ({ children }: any) => <>{children}</>,
  Portal: ({ children }: any) => <>{children}</>,
  Overlay: () => null,
  Content: ({ children }: any) => <div data-testid="dialog-content">{children}</div>,
  Close: ({ children }: any) => <button>{children}</button>,
  Title: ({ children }: any) => <h2>{children}</h2>,
  Description: ({ children }: any) => <p>{children}</p>,
}));

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

type FinalCheckpoint = CheckpointItem & { parsed: GovCheckpointPayload };

function makePayload(id: string, title: string): GovCheckpointPayload {
  return { id, category: "其他违法违规", title, description: "", legal_basis: [], severity: "minor", retrieval_hint: "" };
}

function makeFinal(id: string, title: string): FinalCheckpoint {
  const payload = makePayload(id, title);
  return { id, kind: "final", status: "approved", payload_json: JSON.stringify(payload), approved_by: "admin", parsed: payload };
}

function defaultValue(): WorkbenchContextValue {
  return {
    apiConnected: true, ruleSources: [], activeRuleSource: undefined,
    selectedRuleSourceId: null, setSelectedRuleSourceId: vi.fn(),
    checkpoints: [], finalCheckpoints: [],
    extractingRuleSourceId: null, extractStatus: null, extractError: null, extractCurrentPhase: null,
    uploadRuleAndExtract: vi.fn(), pollExtractRun: vi.fn(),
    projects: [], activeProject: undefined,
    selectedProjectId: null, setSelectedProjectId: vi.fn(),
    createProject: vi.fn(), uploadTenderDoc: vi.fn(), uploadAuditInputDocs: vi.fn(),
    auditInputDocs: {}, resetProjectDocs: vi.fn(), tenderDocs: {},
    auditRuns: [], activeAuditRun: undefined,
    selectedAuditRunId: null, setSelectedAuditRunId: vi.fn(),
    createAuditRun: vi.fn(), auditProgress: null, logs: [],
    pointRuns: [], activePointRun: undefined,
    selectedPointRunId: null, setSelectedPointRunId: vi.fn(),
    retryPointRun: vi.fn(),
    workpaperHtml: "", workpaperJson: null,
    workpaperSaveStatus: "idle", finalizeStatus: "idle",
    loadWorkpaper: vi.fn(), setWorkpaperHtml: vi.fn(),
    saveWorkpaper: vi.fn(), finalizeWorkpaper: vi.fn(),
    importCheckpointFile: vi.fn(), updateCheckpoint: vi.fn(),
    deleteCheckpoint: vi.fn(), refreshAll: vi.fn(),
  };
}

function MockWorkbenchProvider(props: { children: ReactNode; overrides?: Partial<WorkbenchContextValue> }) {
  return (
    <WorkbenchContext.Provider value={{ ...defaultValue(), ...(props.overrides ?? {}) }}>
      {props.children}
    </WorkbenchContext.Provider>
  );
}

function renderPage(overrides?: Partial<WorkbenchContextValue>) {
  return render(
    <MemoryRouter initialEntries={["/ai-review"]}>
      <MockWorkbenchProvider overrides={overrides}><AIReviewPage /></MockWorkbenchProvider>
    </MemoryRouter>,
  );
}

const sampleProject: Project = { id: "p-1", name: "项目甲", created_at: "2026-04-19T00:00:00Z", created_by: "admin" };
const sampleTenderDoc: TenderDoc = { id: "td-1", project_id: "p-1", filename: "tender.docx", markdown_path: "/tmp/tender.md" };
const sampleCheckpoints: FinalCheckpoint[] = [makeFinal("cp-1", "采购范围"), makeFinal("cp-2", "供应商资格")];

/* ──────────────────────────────────────────────────────────────
 * Setup 模式
 * ────────────────────────────────────────────────────────────── */

describe("AIReviewPage · Setup 模式", () => {
  it("首次渲染显示「新建审查任务」标题和 3 个步骤指示器", () => {
    renderPage();
    expect(screen.getByText("新建审查任务")).toBeInTheDocument();
    expect(screen.getByText("选择或创建项目")).toBeInTheDocument();
    expect(screen.getByText("上传招标文件")).toBeInTheDocument();
    expect(screen.getByText("选择审查要点")).toBeInTheDocument();
  });

  it("无 activeProject 时，不渲染「第二步」上传区和审核点 checkbox", () => {
    renderPage();
    expect(screen.queryByText("第二步：上传招标文件")).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /开始审核/ })).not.toBeInTheDocument();
  });

  it("输入项目名称后点击「创建」会调用 createProject", async () => {
    const createProject = vi.fn().mockResolvedValue(sampleProject);
    renderPage({ createProject });

    const nameInput = screen.getByPlaceholderText("输入项目名称");
    await userEvent.type(nameInput, "测试项目");
    const createBtn = screen.getByRole("button", { name: /创建/ });
    await userEvent.click(createBtn);

    expect(createProject).toHaveBeenCalledWith("测试项目");
  });

  it("有 mainDoc + finalCheckpoints 时，「开始审核」按钮随选中数量切换 disabled", async () => {
    renderPage({
      projects: [sampleProject], activeProject: sampleProject, selectedProjectId: sampleProject.id,
      auditInputDocs: { [sampleProject.id]: { mainDoc: sampleTenderDoc, supplementaryDocs: [] } },
      finalCheckpoints: sampleCheckpoints, checkpoints: sampleCheckpoints,
    });

    const startBtn = screen.getByRole("button", { name: /开始审核/ });
    expect(startBtn).toBeDisabled();
    expect(startBtn).toHaveTextContent(/0 个要点/);

    const checkbox = screen.getAllByRole("checkbox")[0];
    await userEvent.click(checkbox);
    expect(startBtn).not.toBeDisabled();
    expect(startBtn).toHaveTextContent(/1 个要点/);
  });

  it("上传成功后显示已上传文件名", () => {
    renderPage({
      projects: [sampleProject], activeProject: sampleProject, selectedProjectId: sampleProject.id,
      auditInputDocs: { [sampleProject.id]: { mainDoc: sampleTenderDoc, supplementaryDocs: [] } },
    });

    expect(screen.getByText("tender.docx")).toBeInTheDocument();
  });

  it("有 activeProject + 无 mainDoc 时渲染第二步上传卡片含主招标文书 label", () => {
    renderPage({
      projects: [sampleProject], activeProject: sampleProject, selectedProjectId: sampleProject.id,
    });
    expect(screen.getByText("主招标文书")).toBeInTheDocument();
    expect(screen.getByText("点击选择或拖入招标文书")).toBeInTheDocument();
  });

  it("mainDoc 已上传时显示绿色状态和「移除」按钮", () => {
    renderPage({
      projects: [sampleProject], activeProject: sampleProject, selectedProjectId: sampleProject.id,
      auditInputDocs: { [sampleProject.id]: { mainDoc: sampleTenderDoc, supplementaryDocs: [] } },
    });
    expect(screen.getByText("tender.docx")).toBeInTheDocument();
    expect(screen.getByText("移除")).toBeInTheDocument();
  });

  it("点击已上传主文件的「移除」调用 resetProjectDocs", async () => {
    const resetProjectDocs = vi.fn();
    renderPage({
      projects: [sampleProject], activeProject: sampleProject, selectedProjectId: sampleProject.id,
      auditInputDocs: { [sampleProject.id]: { mainDoc: sampleTenderDoc, supplementaryDocs: [] } },
      resetProjectDocs,
    });
    await userEvent.click(screen.getByText("移除"));
    expect(resetProjectDocs).toHaveBeenCalledWith(sampleProject.id);
  });

  it("mainDoc 已上传 + supplementaryDocs 非空时显示附件文件名", () => {
    const suppDoc: TenderDoc = { id: "td-s1", project_id: "p-1", filename: "合同.pdf", markdown_path: "/tmp/s1.md" };
    renderPage({
      projects: [sampleProject], activeProject: sampleProject, selectedProjectId: sampleProject.id,
      auditInputDocs: { [sampleProject.id]: { mainDoc: sampleTenderDoc, supplementaryDocs: [suppDoc] } },
    });
    expect(screen.getByText("合同.pdf")).toBeInTheDocument();
    expect(screen.getByText("补充文件（可选）")).toBeInTheDocument();
  });
});

/* ──────────────────────────────────────────────────────────────
 * Running 模式
 * ────────────────────────────────────────────────────────────── */

describe("AIReviewPage · Running 模式", () => {
  const makeProgress = (
    overrides?: Partial<AuditRunProgress>,
  ): AuditRunProgress => ({
    audit_run_id: "ar-1",
    status: "running",
    total_count: 5,
    processed_count: 2,
    point_runs: [
      { id: "pr-1", checkpoint_final_id: "cp-1", status: "completed", error: null, finding_json: null, started_at: null, completed_at: null, current_phase: null },
      { id: "pr-2", checkpoint_final_id: "cp-2", status: "completed", error: null, finding_json: null, started_at: null, completed_at: null, current_phase: null },
      { id: "pr-3", checkpoint_final_id: "cp-3", status: "failed", error: "oops", finding_json: null, started_at: null, completed_at: null, current_phase: null },
      { id: "pr-4", checkpoint_final_id: "cp-4", status: "running", error: null, finding_json: null, started_at: null, completed_at: null, current_phase: "execute" },
      { id: "pr-5", checkpoint_final_id: "cp-5", status: "pending", error: null, finding_json: null, started_at: null, completed_at: null, current_phase: null },
    ],
    ...overrides,
  });

  it("进度指标卡片正确显示 总审核点/已完成/审查中/失败 数值", () => {
    renderPage({
      projects: [sampleProject], activeProject: sampleProject, selectedProjectId: sampleProject.id,
      auditInputDocs: { [sampleProject.id]: { mainDoc: sampleTenderDoc, supplementaryDocs: [] } },
      auditProgress: makeProgress(), finalCheckpoints: sampleCheckpoints,
    });

    // MetricCard 结构：<div><p class="text-sm">label</p><p class="text-2xl">value</p></div>
    // 通过 label 文本定位卡片，再读取同级 value
    const cards = document.querySelectorAll(".border-l-4");
    const cardValues: Record<string, string> = {};
    cards.forEach((card) => {
      const label = card.querySelector(".text-sm")?.textContent ?? "";
      const value = card.querySelector(".text-2xl")?.textContent ?? "";
      cardValues[label] = value;
    });

    expect(cardValues["总审核点"]).toBe("5");
    expect(cardValues["已完成"]).toBe("2");
    expect(cardValues["审查中"]).toBe("1");
    expect(cardValues["失败"]).toBe("1");
  });

  it("顶栏显示已完成/总数和「审核进行中」badge", () => {
    renderPage({
      projects: [sampleProject], activeProject: sampleProject, selectedProjectId: sampleProject.id,
      auditInputDocs: { [sampleProject.id]: { mainDoc: sampleTenderDoc, supplementaryDocs: [] } },
      auditProgress: makeProgress(), finalCheckpoints: sampleCheckpoints,
    });

    expect(screen.getByText("审核进行中")).toBeInTheDocument();
    expect(screen.getByText(/已完成 2\/5/)).toBeInTheDocument();
  });

  it("审核点列表中 completed 状态通过 StatusBadge 渲染为「已完成」", () => {
    renderPage({
      projects: [sampleProject], activeProject: sampleProject, selectedProjectId: sampleProject.id,
      auditInputDocs: { [sampleProject.id]: { mainDoc: sampleTenderDoc, supplementaryDocs: [] } },
      auditProgress: makeProgress(), finalCheckpoints: sampleCheckpoints,
    });

    const badges = screen.getAllByText("已完成");
    expect(badges.length).toBeGreaterThanOrEqual(2);
  });
});
