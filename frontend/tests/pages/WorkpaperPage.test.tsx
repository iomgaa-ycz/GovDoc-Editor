import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { WorkpaperPage } from "@/pages/WorkpaperPage";
import type { AuditRun, Project, TenderDoc, WorkpaperPayload } from "@/types/ui";
import { renderWithWorkbench } from "./workbenchTestUtils";

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

const workpaper: WorkpaperPayload = {
  project_id: project.id,
  tender_doc_path: "/tmp/main.md",
  findings: [],
  summary: "底稿摘要",
  generated_at: "2026-04-28T14:40:00",
  final: false,
};

describe("WorkpaperPage", () => {
  it("下拉展示短标签，并在下方展示当前运行信息", () => {
    renderWithWorkbench(<WorkpaperPage />, {
      auditRuns: [run],
      selectedAuditRunId: run.id,
      activeAuditRun: run,
      projects: [project],
      auditInputDocs: {
        [project.id]: {
          mainDoc: tenderDoc,
          supplementaryDocs: [],
        },
      },
    }, "/workpaper");

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

  it("选择审核运行时加载工作底稿", async () => {
    const setSelectedAuditRunId = vi.fn();
    const loadWorkpaper = vi.fn().mockResolvedValue(undefined);

    renderWithWorkbench(<WorkpaperPage />, {
      auditRuns: [run],
      projects: [project],
      auditInputDocs: {
        [project.id]: {
          mainDoc: tenderDoc,
          supplementaryDocs: [],
        },
      },
      setSelectedAuditRunId,
      loadWorkpaper,
    }, "/workpaper");

    await userEvent.selectOptions(screen.getByRole("combobox"), run.id);

    expect(setSelectedAuditRunId).toHaveBeenCalledWith(run.id);
    expect(loadWorkpaper).toHaveBeenCalledWith(run.id);
  });

  it("选择空值时清空工作底稿", async () => {
    const setSelectedAuditRunId = vi.fn();
    const clearWorkpaper = vi.fn();

    renderWithWorkbench(<WorkpaperPage />, {
      auditRuns: [run],
      selectedAuditRunId: run.id,
      activeAuditRun: run,
      workpaperHtml: "<h2>审查工作底稿</h2>",
      workpaperJson: workpaper,
      setSelectedAuditRunId,
      clearWorkpaper,
    }, "/workpaper");

    await userEvent.selectOptions(screen.getByRole("combobox"), "");

    expect(setSelectedAuditRunId).toHaveBeenCalledWith(null);
    expect(clearWorkpaper).toHaveBeenCalled();
  });

  it("手动保存按钮调用 saveWorkpaper", async () => {
    const saveWorkpaper = vi.fn().mockResolvedValue(undefined);

    renderWithWorkbench(<WorkpaperPage />, {
      auditRuns: [run],
      selectedAuditRunId: run.id,
      activeAuditRun: run,
      workpaperHtml: "<h2>审查工作底稿</h2>",
      workpaperJson: workpaper,
      saveWorkpaper,
    }, "/workpaper");

    await userEvent.click(screen.getByRole("button", { name: "保存草稿" }));

    expect(saveWorkpaper).toHaveBeenCalled();
  });
});
