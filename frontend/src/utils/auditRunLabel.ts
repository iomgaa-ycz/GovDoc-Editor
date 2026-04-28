import type { AuditRun, Project, TenderDoc } from "../types/ui";

export interface AuditRunDocs {
  mainDoc?: TenderDoc;
  supplementaryDocs: TenderDoc[];
}

export interface AuditRunLabelInput {
  run: AuditRun;
  projects: Project[];
  auditInputDocs: Record<string, AuditRunDocs>;
}

export interface AuditRunDisplayInfo {
  projectName: string;
  tenderDocName: string;
  supplementaryCount: number;
  createdAt: string;
  status: string;
  shortId: string;
}

const statusLabels: Record<AuditRun["status"], string> = {
  pending: "等待审核",
  running: "审核中",
  draft_ready: "已生成底稿",
  partial_ready: "部分完成",
  waiting_retry: "等待重试",
  finalized: "已定稿",
  failed: "审核失败",
};

function shortId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) : id;
}

export function formatAuditRunStatus(status: AuditRun["status"]): string {
  return statusLabels[status] ?? status;
}

export function formatAuditRunCreatedAt(createdAt: string): string {
  const match = createdAt.match(/^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})/);
  if (match) {
    return `${match[2]}-${match[3]} ${match[4]}:${match[5]}`;
  }
  return "时间未知";
}

export function findAuditRunTenderDoc(
  run: AuditRun,
  auditInputDocs: Record<string, AuditRunDocs>,
): TenderDoc | undefined {
  const docs = auditInputDocs[run.project_id];
  if (!docs) return undefined;
  const allDocs = [
    docs.mainDoc,
    ...docs.supplementaryDocs,
  ].filter((doc): doc is TenderDoc => Boolean(doc));
  return allDocs.find((doc) => doc.id === run.tender_doc_id);
}

export function getAuditRunDisplayInfo(input: AuditRunLabelInput): AuditRunDisplayInfo {
  const { run, projects, auditInputDocs } = input;
  const project = projects.find((p) => p.id === run.project_id);
  const tenderDoc = findAuditRunTenderDoc(run, auditInputDocs);
  return {
    projectName: project?.name ?? `审核运行 ${shortId(run.id)}`,
    tenderDocName: tenderDoc?.filename ?? "暂未匹配到文书",
    supplementaryCount: run.supplementary_doc_ids?.length ?? 0,
    createdAt: formatAuditRunCreatedAt(run.created_at),
    status: formatAuditRunStatus(run.status),
    shortId: shortId(run.id),
  };
}

export function formatAuditRunOptionLabel(input: AuditRunLabelInput): string {
  const info = getAuditRunDisplayInfo(input);
  return `${info.projectName} / ${info.createdAt} / ${info.status}`;
}
