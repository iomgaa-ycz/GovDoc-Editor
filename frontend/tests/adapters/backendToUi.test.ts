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
    project_id: "proj-test",
    tender_doc_path: "/test.docx",
    summary: "测试总结",
    generated_at: "2026-05-22T00:00:00Z",
    final: false,
    findings: verdicts.map((v) => makeFinding(v)),
  };
}

describe("workpaperToHtml", () => {
  it("合规 finding 显示 '合规通过'", () => {
    const html = workpaperToHtml(makeWorkpaper(["合规"]));
    expect(html).toContain("合规通过");
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
