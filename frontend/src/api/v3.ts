import type {
  AuditRun,
  AuditRunProgress,
  CheckpointItem,
  Project,
  RuleSource,
  RuleUploadResult,
  TenderDoc,
  WorkpaperDraft,
} from "../types/ui";

/* ── helpers ── */

function resolveBaseUrl(): string {
  return import.meta.env.VITE_GOVDOC_API_BASE_URL || "";
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const base = resolveBaseUrl();
  const res = await fetch(`${base}${path}`, init);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

/* ── Health ── */

export function healthCheck(): Promise<{ status: string }> {
  return request("/healthz");
}

/* ── Projects ── */

export function listProjects(): Promise<Project[]> {
  return request("/api/v1/projects");
}

export function createProject(name: string, createdBy: string): Promise<Project> {
  return request("/api/v1/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, created_by: createdBy }),
  });
}

export function getProject(id: string): Promise<Project> {
  return request(`/api/v1/projects/${id}`);
}

export function uploadTenderDoc(
  projectId: string,
  file: File,
): Promise<TenderDoc> {
  const form = new FormData();
  form.append("file", file);
  return request(`/api/v1/projects/${projectId}/tender-doc`, {
    method: "POST",
    body: form,
  });
}

export function listTenderDocs(
  projectId: string,
): Promise<TenderDoc[]> {
  return request(`/api/v1/projects/${projectId}/tender-docs`);
}

/* ── Rules ── */

export function listRuleSources(): Promise<RuleSource[]> {
  return request("/api/v1/rules");
}

export function uploadRule(
  title: string,
  file: File,
): Promise<RuleUploadResult> {
  const form = new FormData();
  form.append("title", title);
  form.append("file", file);
  return request("/api/v1/rules/upload", {
    method: "POST",
    body: form,
  });
}

export function getExtractRunStatus(
  ruleId: string,
  runId: string,
): Promise<{
  run_id: string;
  status: string;
  workspace_archive_path: string | null;
  workspace_failed_path: string | null;
  error: string | null;
}> {
  return request(`/api/v1/rules/${ruleId}/extract-runs/${runId}/status`);
}

export function listCheckpointDrafts(
  ruleId: string,
): Promise<Array<{ id: string; status: string; payload_json: string }>> {
  return request(`/api/v1/rules/${ruleId}/checkpoints/drafts`);
}

/* ── Checkpoints ── */

export function listCheckpoints(): Promise<CheckpointItem[]> {
  return request("/api/v1/checkpoints");
}

export function updateCheckpoint(
  id: string,
  payloadJson: string,
): Promise<CheckpointItem> {
  return request(`/api/v1/checkpoints/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ payload_json: payloadJson }),
  });
}

export function deleteCheckpoint(id: string): Promise<void> {
  return request(`/api/v1/checkpoints/${id}`, { method: "DELETE" });
}

/* ── Audit ── */

export function listAuditRuns(projectId?: string): Promise<AuditRun[]> {
  const params = projectId ? `?project_id=${projectId}` : "";
  return request(`/api/v1/audit/runs${params}`);
}

export function createAuditRun(
  projectId: string,
  tenderDocId: string,
  checkpointIds: string[],
): Promise<{ audit_run_id: string; total_count: number; status: string }> {
  return request("/api/v1/audit/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: projectId,
      tender_doc_id: tenderDocId,
      checkpoint_ids: checkpointIds,
    }),
  });
}

export function getAuditRunProgress(
  auditRunId: string,
): Promise<AuditRunProgress> {
  return request(`/api/v1/audit/runs/${auditRunId}/progress`);
}

export function retryPointRun(
  pointRunId: string,
): Promise<{ point_run_id: string; status: string }> {
  return request(`/api/v1/audit/point-runs/${pointRunId}/retry`, {
    method: "POST",
  });
}

/* ── Workpapers ── */

export function getWorkpaperDraft(
  auditRunId: string,
): Promise<WorkpaperDraft> {
  return request(`/api/v1/audit/runs/${auditRunId}/workpaper/draft`);
}

export function updateWorkpaperDraft(
  auditRunId: string,
  workpaper: object,
): Promise<{ id: string; version: number }> {
  return request(`/api/v1/audit/runs/${auditRunId}/workpaper/draft`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workpaper }),
  });
}

export function finalizeWorkpaper(
  auditRunId: string,
  approvedBy: string,
): Promise<{ audit_run_id: string; status: string }> {
  return request(`/api/v1/audit/runs/${auditRunId}/workpaper/finalize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved_by: approvedBy }),
  });
}

export function getWorkpaperFinalDocxUrl(auditRunId: string): string {
  const base = resolveBaseUrl();
  return `${base}/api/v1/audit/runs/${auditRunId}/workpaper/final/docx`;
}
