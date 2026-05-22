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

function makeWorkpaper(findings: GovFinding[]): WorkpaperPayload {
  return {
    project_id: "project-1",
    tender_doc_path: "tender.docx",
    findings,
    summary: "测试总结",
    generated_at: "2026-01-01T00:00:00Z",
    final: false,
  };
}

describe("workpaperToHtml", () => {
  it("渲染审核结论时使用面向用户的结论文案", () => {
    const html = workpaperToHtml(makeWorkpaper([
      makeFinding("合规"),
      makeFinding("不合规"),
      makeFinding("存疑"),
    ]));

    expect(html).toContain("合规通过");
    expect(html).toContain("不合规");
    expect(html).toContain("存疑待定");
  });
});
