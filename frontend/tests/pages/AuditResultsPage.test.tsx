import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AuditResultsPage } from "@/pages/AuditResultsPage";
import type {
  AuditRun,
  AuditRunProgress,
  CheckpointItem,
  GovCheckpointPayload,
  GovFinding,
  Project,
  TenderDoc,
} from "@/types/ui";
import { renderWithWorkbench } from "./workbenchTestUtils";

function makeCheckpoint(id: string, title: string): GovCheckpointPayload {
  return {
    id,
    category: "其他违法违规",
    title,
    description: "检查是否存在不合理限制",
    legal_basis: [],
    severity: "minor",
    retrieval_hint: "",
  };
}

function makeFinalCheckpoint(id: string, title: string): CheckpointItem & { parsed: GovCheckpointPayload } {
  const payload = makeCheckpoint(id, title);
  return {
    id,
    kind: "final",
    status: "approved",
    payload_json: JSON.stringify(payload),
    approved_by: "admin",
    parsed: payload,
  };
}

function makeFinding(checkpoint: GovCheckpointPayload): GovFinding {
  return {
    checkpoint,
    verdict: {
      verdict: "不合规",
      rationale: "存在限制供应商的表述",
      evidence_quotes: ["供应商须为本地企业"],
      suggestion: "建议删除地域限制",
    },
    evidence_refs: [],
    case_refs: [],
  };
}

const project: Project = {
  id: "project-1",
  name: "市医院设备采购",
  created_at: "2026-04-28T00:00:00",
  created_by: "admin",
};

const tenderDoc: TenderDoc = {
  id: "doc-main",
  project_id: project.id,
  filename: "招标文件.docx",
  markdown_path: "/tmp/main.md",
};

const run: AuditRun = {
  id: "audit-run-1234567890",
  project_id: project.id,
  tender_doc_id: tenderDoc.id,
  supplementary_doc_ids: [],
  status: "draft_ready",
  processed_count: 1,
  total_count: 1,
  error: null,
  created_at: "2026-04-28T14:30:12",
};

describe("AuditResultsPage", () => {
  it("下拉展示项目、时间和中文状态，并在下方展示当前运行信息", () => {
    renderWithWorkbench(<AuditResultsPage />, {
      auditRuns: [run],
      selectedAuditRunId: run.id,
      projects: [project],
      auditInputDocs: {
        [project.id]: {
          mainDoc: tenderDoc,
          supplementaryDocs: [],
        },
      },
    }, "/audit-results");

    expect(
      screen.getByRole("option", {
        name: "市医院设备采购 / 04-28 14:30 / 已生成底稿",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "当前审核运行" })).toBeInTheDocument();
    expect(screen.getByText("主文书")).toBeInTheDocument();
    expect(screen.getByText("招标文件.docx")).toBeInTheDocument();
    expect(screen.getByText("0 个")).toBeInTheDocument();
    expect(screen.getAllByText("已生成底稿").length).toBeGreaterThan(0);
  });

  it("选择审核运行时加载对应 progress 并清空当前审核点选择", async () => {
    const setSelectedAuditRunId = vi.fn();
    const setSelectedPointRunId = vi.fn();
    const loadAuditRunProgress = vi.fn().mockResolvedValue(undefined);

    renderWithWorkbench(<AuditResultsPage />, {
      auditRuns: [run],
      projects: [project],
      auditInputDocs: {
        [project.id]: {
          mainDoc: tenderDoc,
          supplementaryDocs: [],
        },
      },
      setSelectedAuditRunId,
      setSelectedPointRunId,
      loadAuditRunProgress,
    }, "/audit-results");

    await userEvent.selectOptions(screen.getByRole("combobox"), run.id);

    expect(setSelectedAuditRunId).toHaveBeenCalledWith(run.id);
    expect(setSelectedPointRunId).toHaveBeenCalledWith(null);
    expect(loadAuditRunProgress).toHaveBeenCalledWith(run.id);
  });

  it("展示所选审核运行的审核点列表和详情", () => {
    const checkpoint = makeCheckpoint("cp-1", "供应商资格限制");
    const finalCheckpoint = makeFinalCheckpoint("cp-1", "供应商资格限制");
    const progress: AuditRunProgress = {
      audit_run_id: run.id,
      status: "draft_ready",
      total_count: 1,
      processed_count: 1,
      point_runs: [
        {
          id: "pr-1",
          checkpoint_final_id: "cp-1",
          status: "completed",
          error: null,
          finding_json: JSON.stringify(makeFinding(checkpoint)),
        },
      ],
    };

    renderWithWorkbench(<AuditResultsPage />, {
      auditRuns: [run],
      selectedAuditRunId: run.id,
      auditProgress: progress,
      selectedPointRunId: "pr-1",
      finalCheckpoints: [finalCheckpoint],
    }, "/audit-results");

    expect(screen.getAllByText("供应商资格限制").length).toBeGreaterThan(0);
    expect(screen.getByText("存在限制供应商的表述")).toBeInTheDocument();
    expect(screen.getByText("供应商须为本地企业")).toBeInTheDocument();
  });

  it("历史审核点不在当前审核点库时，从 finding_json 兜底展示标题和详情", () => {
    const checkpoint = makeCheckpoint("cp-deleted", "已删除的历史审核点");
    const progress: AuditRunProgress = {
      audit_run_id: run.id,
      status: "draft_ready",
      total_count: 1,
      processed_count: 1,
      point_runs: [
        {
          id: "pr-1",
          checkpoint_final_id: "cp-deleted",
          status: "completed",
          error: null,
          finding_json: JSON.stringify(makeFinding(checkpoint)),
        },
      ],
    };

    renderWithWorkbench(<AuditResultsPage />, {
      auditRuns: [run],
      selectedAuditRunId: run.id,
      auditProgress: progress,
      selectedPointRunId: "pr-1",
      finalCheckpoints: [],
    }, "/audit-results");

    expect(screen.getAllByText("已删除的历史审核点").length).toBeGreaterThan(0);
    expect(screen.getByText("存在限制供应商的表述")).toBeInTheDocument();
  });
});
