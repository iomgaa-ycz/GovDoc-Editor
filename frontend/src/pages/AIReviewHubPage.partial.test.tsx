/**
 * AIReviewHubPage 任务列表「部分完成」标签测试。
 *
 * 覆盖 Task 7 的目标行为：
 * - status === "partial_ready" 的任务在状态列渲染「部分完成 X/N」标签（含计数）
 * - 其余状态仍走 StatusBadge 现有映射（如 completed → 已完成）
 *
 * 采用 vi.mock 替换 @/api/v3 与 @/api/documents，避免真实网络请求；
 * 用 MemoryRouter 包裹以满足 useNavigate 依赖。
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import type { AuditRun } from "@/types/ui";

const listAuditRuns = vi.fn();

vi.mock("@/api/v3", () => ({
  listAuditRuns: (...args: unknown[]) => listAuditRuns(...args),
  createAuditRun: vi.fn(),
  listCheckpoints: vi.fn().mockResolvedValue([]),
  request: vi.fn(),
}));

vi.mock("@/api/documents", () => ({
  getDocument: vi.fn().mockResolvedValue({ id: "doc-1", filename: "招标文件.pdf" }),
}));

import { AIReviewHubPage } from "./AIReviewHubPage";

function makeRun(overrides: Partial<AuditRun>): AuditRun {
  return {
    id: "run-x",
    project_id: "proj-1",
    project_name: "测试项目",
    main_document_id: "doc-1",
    status: "running",
    processed_count: 0,
    total_count: 3,
    error: null,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AIReviewHubPage />
    </MemoryRouter>,
  );
}

describe("AIReviewHubPage 部分完成标签", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("partial_ready 任务渲染「部分完成 X/N」标签", async () => {
    listAuditRuns.mockResolvedValue([
      makeRun({ id: "run-1", status: "partial_ready", processed_count: 2, total_count: 5 }),
    ]);

    renderPage();

    expect(await screen.findByText("部分完成 2/5")).toBeInTheDocument();
  });

  it("非 partial_ready 任务仍走 StatusBadge 现有映射", async () => {
    listAuditRuns.mockResolvedValue([
      makeRun({ id: "run-2", status: "running", processed_count: 1, total_count: 3 }),
    ]);

    renderPage();

    expect(await screen.findByText("审查中")).toBeInTheDocument();
    expect(screen.queryByText(/部分完成/)).not.toBeInTheDocument();
  });
});
