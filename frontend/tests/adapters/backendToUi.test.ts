import { describe, it, expect } from "vitest";
import { verdictToStatus } from "@/adapters/backendToUi";
import type { GovFinding } from "@/types/ui";

/** 构造一个最小可用的 GovFinding 测试夹具 */
function makeFinding(verdict: string): GovFinding {
  return {
    checkpoint: {
      id: "cp-001",
      category: "其他违法违规",
      title: "测试审核点",
      description: "测试描述",
      legal_basis: [],
      severity: "minor",
      retrieval_hint: "",
    },
    verdict: {
      verdict: verdict as GovFinding["verdict"]["verdict"],
      rationale: "测试理由",
      evidence_quotes: [],
      suggestion: "",
    },
    evidence_refs: [],
    case_refs: [],
  };
}

describe("verdictToStatus", () => {
  it("pointStatus 为 pending → 返回 pending", () => {
    expect(verdictToStatus(null, "pending")).toBe("pending");
  });

  it("pointStatus 为 running → 返回 running", () => {
    expect(verdictToStatus(null, "running")).toBe("running");
  });

  it("pointStatus 为 failed → 返回 error", () => {
    expect(verdictToStatus(null, "failed")).toBe("error");
  });

  it("pointStatus 为 waiting_retry → 返回 error", () => {
    expect(verdictToStatus(null, "waiting_retry")).toBe("error");
  });

  it("completed 状态 + finding 为 null → 返回 failed", () => {
    expect(verdictToStatus(null, "completed")).toBe("failed");
  });

  it("verdict 为 合规 → 返回 passed", () => {
    expect(verdictToStatus(makeFinding("合规"), "completed")).toBe("passed");
  });

  it("verdict 为 不合规 → 返回 failed", () => {
    expect(verdictToStatus(makeFinding("不合规"), "completed")).toBe("failed");
  });

  it("verdict 为 存疑 → 返回 uncertain", () => {
    expect(verdictToStatus(makeFinding("存疑"), "completed")).toBe("uncertain");
  });

  it("verdict 为未知值 → fallback 返回 failed", () => {
    expect(verdictToStatus(makeFinding("其他未知值"), "completed")).toBe("failed");
  });
});
