/**
 * AIReviewDetailPage 「部分完成」提示条与重试/跳过按钮测试。
 *
 * 覆盖 Task 6 的目标行为：
 * - partial_ready + 含失败审核点 → 渲染琥珀色提示条 + 重试/跳过按钮（含失败计数）
 * - running + 含失败审核点 → 两个按钮 disabled（审核进行中不可重试/跳过）
 * - draft_ready（全部完成）→ 渲染绿色「全部完成」提示条
 *
 * 采用 vi.mock 直接替换 @/api/v3 与 @/api/documents，避免触发真实网络请求；
 * 用 MemoryRouter + Routes 注入 useParams 的 auditRunId。
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { AuditPointRun, AuditRunProgress } from "@/types/ui";

const auditRunId = "run-1";

// ── mock API 层 ──
const getAuditRunProgress = vi.fn();
const getWorkpaperDraft = vi.fn();
const listAuditRuns = vi.fn();
const listCheckpoints = vi.fn();
const retryFailedPoints = vi.fn();
const excludeFailedPoints = vi.fn();
const getWorkpaperFinalDocxUrl = vi.fn((..._args: unknown[]) => "http://localhost/docx");

vi.mock("@/api/v3", () => ({
  getAuditRunProgress: (...args: unknown[]) => getAuditRunProgress(...args),
  getWorkpaperDraft: (...args: unknown[]) => getWorkpaperDraft(...args),
  listAuditRuns: (...args: unknown[]) => listAuditRuns(...args),
  listCheckpoints: (...args: unknown[]) => listCheckpoints(...args),
  retryFailedPoints: (...args: unknown[]) => retryFailedPoints(...args),
  excludeFailedPoints: (...args: unknown[]) => excludeFailedPoints(...args),
  retryPointRun: vi.fn(),
  finalizeWorkpaper: vi.fn(),
  updateWorkpaperDraft: vi.fn(),
  getWorkpaperFinalDocxUrl: (...args: unknown[]) => getWorkpaperFinalDocxUrl(...args),
  request: vi.fn(),
}));

vi.mock("@/api/documents", () => ({
  getDocument: vi.fn().mockResolvedValue({ id: "doc-1", filename: "招标文件.pdf" }),
}));

import { AIReviewDetailPage } from "./AIReviewDetailPage";

function makePointRun(id: string, status: AuditPointRun["status"]): AuditPointRun {
  return {
    id,
    checkpoint_final_id: `cp-${id}`,
    status,
    error: status === "failed" ? "执行超时" : null,
    finding_json: null,
    started_at: null,
    completed_at: null,
    current_phase: null,
  };
}

function makeProgress(
  status: AuditRunProgress["status"],
  pointRuns: AuditPointRun[],
): AuditRunProgress {
  const completed = pointRuns.filter((p) => p.status === "completed").length;
  return {
    audit_run_id: auditRunId,
    status,
    total_count: pointRuns.length,
    processed_count: completed,
    point_runs: pointRuns,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/ai-review/${auditRunId}`]}>
      <Routes>
        <Route path="/ai-review/:auditRunId" element={<AIReviewDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AIReviewDetailPage 部分完成提示条", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listAuditRuns.mockResolvedValue([
      {
        id: auditRunId,
        project_id: "proj-1",
        project_name: "测试项目",
        main_document_id: "doc-1",
        status: "partial_ready",
        processed_count: 1,
        total_count: 3,
        error: null,
        created_at: new Date().toISOString(),
      },
    ]);
    listCheckpoints.mockResolvedValue([]);
    // 工作底稿视图（partial_ready / draft_ready）会拉取草稿，返回安全的空底稿
    getWorkpaperDraft.mockResolvedValue({
      id: "wp-1",
      version: 1,
      workpaper_json: JSON.stringify({ summary: "", findings: [] }),
      docx_path: null,
    });
    retryFailedPoints.mockResolvedValue({
      audit_run_id: auditRunId,
      status: "running",
      retry_count: 2,
    });
    excludeFailedPoints.mockResolvedValue({
      audit_run_id: auditRunId,
      status: "draft_ready",
      excluded_count: 2,
    });
  });

  it("partial_ready 含 2 个失败点时渲染提示条与重试/跳过按钮", async () => {
    getAuditRunProgress.mockResolvedValue(
      makeProgress("partial_ready", [
        makePointRun("p1", "completed"),
        makePointRun("p2", "failed"),
        makePointRun("p3", "failed"),
      ]),
    );

    renderPage();

    expect(await screen.findByText(/2 个未能完成/)).toBeInTheDocument();
    expect(
      await screen.findByRole("button", { name: /重试未完成的 2 项/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /跳过这 2 项并出完整稿/ }),
    ).toBeInTheDocument();
  });

  it("running 状态下重试/跳过按钮 disabled", async () => {
    getAuditRunProgress.mockResolvedValue(
      makeProgress("running", [
        makePointRun("p1", "running"),
        makePointRun("p2", "failed"),
        makePointRun("p3", "failed"),
      ]),
    );

    renderPage();

    const retryBtn = await screen.findByRole("button", { name: /重试未完成的 2 项/ });
    const excludeBtn = screen.getByRole("button", { name: /跳过这 2 项并出完整稿/ });
    expect(retryBtn).toBeDisabled();
    expect(excludeBtn).toBeDisabled();
  });

  it("draft_ready 全部完成时渲染绿色提示条", async () => {
    getAuditRunProgress.mockResolvedValue(
      makeProgress("draft_ready", [
        makePointRun("p1", "completed"),
        makePointRun("p2", "completed"),
        makePointRun("p3", "completed"),
      ]),
    );

    renderPage();

    expect(await screen.findByText(/全部完成/)).toBeInTheDocument();
  });
});
