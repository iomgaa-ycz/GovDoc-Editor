import type {
  AuditRun,
  AuditRunProgress,
  CheckpointItem,
  CheckpointImportPreview,
  CheckpointImportResult,
  CheckpointLibrary,
  CheckpointLibraryDetail,
  Comment,
  DashboardStats,
  Project,
  RuleSource,
  RuleUploadResult,
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
  const res = await fetch(`${base}${path}`, init);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    // FastAPI 常用 {"detail": "..."} 返回业务错误；优先展示给律师看的中文文案。
    if (body) {
      try {
        const parsedBody = JSON.parse(body) as { detail?: unknown };
        if (typeof parsedBody.detail === "string") {
          throw new Error(parsedBody.detail);
        }
      } catch (err) {
        if (err instanceof Error && err.name === "Error") {
          throw err;
        }
      }
    }
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

export function listCheckpoints(
  includeArchived = false,
): Promise<CheckpointItem[]> {
  const params = includeArchived ? "?include_archived=true" : "";
  return request(`/api/v1/checkpoints${params}`);
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

export function getCheckpointLibraries(
  id: string,
): Promise<{ id: string; name: string }[]> {
  return request(`/api/v1/checkpoints/${id}/libraries`);
}

export function deleteCheckpoint(
  id: string,
): Promise<{ action: "archived"; referenced_by: number } | undefined> {
  return request(`/api/v1/checkpoints/${id}`, { method: "DELETE" });
}

export function importCheckpoints(
  file: File,
  libraryIds: string[] = [],
): Promise<CheckpointImportResult> {
  const form = new FormData();
  form.append("file", file);
  if (libraryIds.length > 0) {
    form.append("library_ids", JSON.stringify(libraryIds));
  }
  return request("/api/v1/checkpoints/import", {
    method: "POST",
    body: form,
  });
}

export function previewCheckpointImport(
  file: File,
  libraryIds: string[] = [],
): Promise<CheckpointImportPreview> {
  const form = new FormData();
  form.append("file", file);
  if (libraryIds.length > 0) {
    form.append("library_ids", JSON.stringify(libraryIds));
  }
  return request("/api/v1/checkpoints/import/preview", {
    method: "POST",
    body: form,
  });
}

/* ── Checkpoint libraries ── */

export function listCheckpointLibraries(): Promise<CheckpointLibrary[]> {
  return request("/api/v1/checkpoint-libraries");
}

export function createCheckpointLibrary(
  name: string,
  description = "",
  createdBy = "system",
): Promise<CheckpointLibrary> {
  return request("/api/v1/checkpoint-libraries", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      description: description || null,
      created_by: createdBy,
    }),
  });
}

export function getCheckpointLibrary(id: string): Promise<CheckpointLibraryDetail> {
  return request(`/api/v1/checkpoint-libraries/${id}`);
}

export function updateCheckpointLibrary(
  id: string,
  name: string,
  description = "",
): Promise<CheckpointLibrary> {
  return request(`/api/v1/checkpoint-libraries/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description: description || null }),
  });
}

export function deleteCheckpointLibrary(id: string): Promise<void> {
  return request(`/api/v1/checkpoint-libraries/${id}`, { method: "DELETE" });
}

export function addCheckpointsToLibraries(
  libraryIds: string[],
  checkpointIds: string[],
): Promise<{ library_ids: string[]; checkpoint_ids: string[]; added_count: number }> {
  return request("/api/v1/checkpoint-libraries/batch-add", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      library_ids: libraryIds,
      checkpoint_ids: checkpointIds,
    }),
  });
}

export function removeCheckpointsFromLibrary(
  libraryId: string,
  checkpointIds: string[],
): Promise<{ library_id: string; removed_count: number }> {
  return request(`/api/v1/checkpoint-libraries/${libraryId}/checkpoints/remove`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ checkpoint_ids: checkpointIds }),
  });
}

/* ── Audit ── */

export function listAuditRuns(projectId?: string): Promise<AuditRun[]> {
  const params = projectId ? `?project_id=${projectId}` : "";
  return request(`/api/v1/audit/runs${params}`);
}

export function createAuditRun(
  projectId: string,
  mainDocumentId: string,
  supplementaryDocumentIds: string[],
  checkpointIds: string[],
  checkpointLibraryId?: string | null,
): Promise<{
  audit_run_id: string;
  total_count: number;
  status: string;
  checkpoint_library_id?: string | null;
  checkpoint_library_name_snapshot?: string | null;
  skipped_deleted_count?: number;
}> {
  return request("/api/v1/audit/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: projectId,
      main_document_id: mainDocumentId,
      supplementary_document_ids: supplementaryDocumentIds,
      checkpoint_ids: checkpointIds,
      checkpoint_library_id: checkpointLibraryId || null,
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

export function retryFailedPoints(
  auditRunId: string,
): Promise<{ audit_run_id: string; status: string; retry_count: number }> {
  return request(`/api/v1/audit/runs/${auditRunId}/retry-failed`, {
    method: "POST",
  });
}

export function excludeFailedPoints(
  auditRunId: string,
): Promise<{ audit_run_id: string; status: string; excluded_count: number }> {
  return request(`/api/v1/audit/runs/${auditRunId}/exclude-failed`, {
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
