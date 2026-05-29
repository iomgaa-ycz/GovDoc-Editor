/* V3 UI-facing types — mirrors backend shapes in TypeScript */

// ── Enums ──

export type CheckpointCategory =
  | "意向性招标"
  | "围标串标"
  | "不合理条件限制或排斥供应商"
  | "其他违法违规";

export type Severity = "critical" | "major" | "minor";
export type VerdictValue = "合规" | "不合规" | "存疑";

export type PointRunStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "waiting_retry";

export type AuditRunStatus =
  | "pending"
  | "running"
  | "draft_ready"
  | "partial_ready"
  | "waiting_retry"
  | "finalized"
  | "failed";

export type ExtractRunStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed";

// ── Checkpoint domain ──

export interface LegalBasis {
  law_name: string;
  article: string;
  quote: string;
}

export interface GovCheckpointPayload {
  id: string;
  category: CheckpointCategory;
  title: string;
  description: string;
  legal_basis: LegalBasis[];
  severity: Severity;
  retrieval_hint: string;
}

export interface CheckpointItem {
  id: string;
  kind: "final";
  status: string;
  payload_json: string; // JSON-encoded GovCheckpointPayload
  approved_by: string | null;
  archived?: boolean;
}

export interface CheckpointLibrary {
  id: string;
  name: string;
  description: string | null;
  created_by: string;
  created_at: string;
  checkpoint_count: number;
  deleted_checkpoint_count: number;
}

export interface CheckpointLibraryMember {
  id: string;
  library_id: string;
  checkpoint_final_id: string;
  checkpoint: CheckpointItem | null;
  deleted: boolean;
  added_by: string;
  added_at: string;
}

export interface CheckpointLibraryDetail extends CheckpointLibrary {
  checkpoints: CheckpointLibraryMember[];
}

export interface CheckpointImportPreview {
  parsed_count: number;
  created_count: number;
  reused_count: number;
  duplicate_count: number;
  skipped_count: number;
  skipped_reasons: string[];
}

export interface CheckpointImportResult {
  imported_count: number;
  created_count: number;
  reused_count: number;
  linked_count: number;
  skipped_count: number;
  skipped_reasons: string[];
  checkpoints: CheckpointItem[];
}

// ── Findings ──

export interface GovFindingVerdict {
  verdict: VerdictValue;
  rationale: string;
  evidence_quotes: string[];
  suggestion: string;
}

export interface ChunkRef {
  chunk_id: string;
  text: string;
  metadata: Record<string, unknown>;
}

export interface GovFinding {
  checkpoint: GovCheckpointPayload;
  verdict: GovFindingVerdict;
  evidence_refs: ChunkRef[];
  case_refs: string[];
}

// ── Workpaper ──

export interface WorkpaperPayload {
  project_id: string;
  tender_doc_path: string;
  findings: GovFinding[];
  summary: string;
  generated_at: string;
  final: boolean;
}

// ── Rule sources & extraction ──

export interface RuleSource {
  id: string;
  title: string;
  source_path: string;
  added_at: string;
}

export interface ExtractRun {
  id: string;
  rule_source_id: string;
  status: ExtractRunStatus;
  workspace_archive_path: string | null;
  workspace_failed_path: string | null;
  error: string | null;
  started_at: string | null;
  current_phase: string | null;
}

// ── Projects & audit ──

export interface Project {
  id: string;
  name: string;
  created_at: string;
  created_by: string;
}

export interface AuditRun {
  id: string;
  project_id: string;
  project_name?: string;
  main_document_id: string;
  supplementary_doc_ids?: string[];
  checkpoint_library_id?: string | null;
  checkpoint_library_name_snapshot?: string | null;
  status: AuditRunStatus;
  processed_count: number;
  total_count: number;
  error: string | null;
  created_at: string;
}

export interface AuditPointRun {
  id: string;
  checkpoint_final_id: string;
  status: PointRunStatus;
  error: string | null;
  finding_json: string | null;
  started_at: string | null;
  completed_at: string | null;
  current_phase: string | null;
}

export interface AuditRunProgress {
  audit_run_id: string;
  status: AuditRunStatus;
  total_count: number;
  processed_count: number;
  point_runs: AuditPointRun[];
}

// ── Workpaper draft ──

export interface WorkpaperDraft {
  id: string;
  version: number;
  workpaper_json: string; // JSON-encoded WorkpaperPayload
  docx_path: string | null;
}

// ── Log entry (reused for UI) ──

export type LogLevel = "info" | "success" | "warning" | "error";

export interface LogEntry {
  id: string;
  time: string;
  level: LogLevel;
  message: string;
}

// ── Upload result ──

export interface RuleUploadResult {
  rule_source_id: string;
  extract_run_id: string;
  status: string;
  warnings: string[];
}

// ── Comments ──

export interface Comment {
  id: string;
  target_type: string;
  target_id: string;
  author: string;
  text: string;
  created_at: string;
}

// ── Dashboard ──

export interface DashboardStats {
  checkpoint_count: number;
  completed_audit_count: number;
  finding_count: number;
  workpaper_count: number;
  recent_projects: RecentProject[];
}

export interface RecentProject {
  project_id: string;
  name: string;
  audit_status: string;
  point_count: number;
  issue_count: number;
  last_active: string;
}

export type DocumentStatus = "uploading" | "converting" | "ready" | "failed";

export interface DocumentTag {
  id: string;
  name: string;
  color: string;
}

export interface GovDocument {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  sha256: string;
  raw_path: string;
  markdown_path: string | null;
  status: DocumentStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  tags: DocumentTag[];
}

export interface Tag {
  id: string;
  name: string;
  color: string;
  created_at: string;
}
