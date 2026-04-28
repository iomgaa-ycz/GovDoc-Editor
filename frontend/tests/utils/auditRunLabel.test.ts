import { describe, expect, it } from "vitest";

import {
  findAuditRunTenderDoc,
  formatAuditRunCreatedAt,
  formatAuditRunOptionLabel,
  formatAuditRunStatus,
  getAuditRunDisplayInfo,
} from "@/utils/auditRunLabel";
import type { AuditRun, Project, TenderDoc } from "@/types/ui";

const project: Project = {
  id: "project-1",
  name: "市医院设备采购",
  created_at: "2026-04-28T00:00:00",
  created_by: "admin",
};

const mainDoc: TenderDoc = {
  id: "doc-main",
  project_id: project.id,
  filename: "招标文件.docx",
  markdown_path: "/tmp/main.md",
};

const supplementaryDoc: TenderDoc = {
  id: "doc-supp",
  project_id: project.id,
  filename: "答疑纪要.docx",
  markdown_path: "/tmp/supp.md",
};

function makeRun(overrides: Partial<AuditRun> = {}): AuditRun {
  return {
    id: "audit-run-1234567890",
    project_id: project.id,
    tender_doc_id: mainDoc.id,
    supplementary_doc_ids: [supplementaryDoc.id],
    status: "draft_ready",
    processed_count: 1,
    total_count: 1,
    error: null,
    created_at: "2026-04-28T14:30:12",
    ...overrides,
  };
}

describe("auditRunLabel", () => {
  it("将审核运行状态映射为中文", () => {
    expect(formatAuditRunStatus("draft_ready")).toBe("已生成底稿");
    expect(formatAuditRunStatus("running")).toBe("审核中");
    expect(formatAuditRunStatus("failed")).toBe("审核失败");
  });

  it("格式化创建时间为短日期", () => {
    expect(formatAuditRunCreatedAt("2026-04-28T14:30:12")).toBe("04-28 14:30");
    expect(formatAuditRunCreatedAt("2026-04-28 09:05:00")).toBe("04-28 09:05");
  });

  it("通过 tender_doc_id 精确匹配主文书", () => {
    const run = makeRun();

    expect(
      findAuditRunTenderDoc(run, {
        [project.id]: {
          mainDoc,
          supplementaryDocs: [supplementaryDoc],
        },
      }),
    ).toEqual(mainDoc);
  });

  it("即使 tender_doc_id 指向附件，也能匹配正确文书名", () => {
    const run = makeRun({ tender_doc_id: supplementaryDoc.id });

    expect(
      findAuditRunTenderDoc(run, {
        [project.id]: {
          mainDoc,
          supplementaryDocs: [supplementaryDoc],
        },
      }),
    ).toEqual(supplementaryDoc);
  });

  it("下拉选项只展示项目、时间和状态", () => {
    const label = formatAuditRunOptionLabel({
      run: makeRun(),
      projects: [project],
      auditInputDocs: {
        [project.id]: {
          mainDoc,
          supplementaryDocs: [supplementaryDoc],
        },
      },
    });

    expect(label).toBe("市医院设备采购 / 04-28 14:30 / 已生成底稿");
  });

  it("当前运行信息包含主文书、附件数和状态", () => {
    const info = getAuditRunDisplayInfo({
      run: makeRun(),
      projects: [project],
      auditInputDocs: {
        [project.id]: {
          mainDoc,
          supplementaryDocs: [supplementaryDoc],
        },
      },
    });

    expect(info).toMatchObject({
      tenderDocName: "招标文件.docx",
      supplementaryCount: 1,
      status: "已生成底稿",
    });
  });
});
