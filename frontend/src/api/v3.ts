import type {
  AuditRun,
  AuditRunProgress,
  CheckpointItem,
  Comment,
  DashboardStats,
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

// exported for contract testing
export async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const base = resolveBaseUrl();
  const token = localStorage.getItem("token");

  const headers = new Headers(init?.headers);
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${base}${path}`, { ...init, headers });
  if (res.status === 401) {
    localStorage.removeItem("token");
    window.dispatchEvent(new Event("auth:expired"));
    const body = await res.text().catch(() => "");
    throw new Error(`API 401: ${body || "登录已过期"}`);
  }
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
  started_at: string | null;
  current_phase: string | null;
}> {
  return request(`/api/v1/rules/${ruleId}/extract-runs/${runId}/status`);
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

export function importCheckpoints(
  file: File,
): Promise<{
  imported_count: number;
  skipped_count: number;
  skipped_reasons: string[];
  checkpoints: CheckpointItem[];
}> {
  const form = new FormData();
  form.append("file", file);
  return request("/api/v1/checkpoints/import", {
    method: "POST",
    body: form,
  });
}

/* ── Audit ── */

export function listAuditRuns(projectId?: string): Promise<AuditRun[]> {
  const params = projectId ? `?project_id=${projectId}` : "";
  return request(`/api/v1/audit/runs${params}`);
}

export function createAuditRun(
  projectId: string,
  tenderDocId: string,
  supplementaryDocIds: string[],
  checkpointIds: string[],
): Promise<{ audit_run_id: string; total_count: number; status: string }> {
  return request("/api/v1/audit/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: projectId,
      tender_doc_id: tenderDocId,
      supplementary_doc_ids: supplementaryDocIds,
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

// ── Comments ──

export function listComments(targetType: string, targetId: string): Promise<Comment[]> {
  return request(`/api/v1/comments?target_type=${encodeURIComponent(targetType)}&target_id=${encodeURIComponent(targetId)}`);
}

export function createComment(
  targetType: string,
  targetId: string,
  author: string,
  text: string,
): Promise<Comment> {
  return request("/api/v1/comments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_type: targetType, target_id: targetId, author, text }),
  });
}

export function deleteComment(commentId: string): Promise<void> {
  return request(`/api/v1/comments/${commentId}`, { method: "DELETE" });
}

// ── Dashboard ──

export function getDashboardStats(): Promise<DashboardStats> {
  return request("/api/v1/dashboard/stats");
}

// ── Extract preview ──

export function getExtractRunPreview(
  ruleId: string,
  runId: string,
): Promise<{ run_id: string; status: string; extracted_count: number }> {
  return request(`/api/v1/rules/${ruleId}/extract-runs/${runId}/preview`);
}
