import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import * as api from "../api/v3";
import type {
  AuditPointRun,
  AuditRun,
  AuditRunProgress,
  CheckpointItem,
  GovCheckpointPayload,
  GovFinding,
  LogEntry,
  Project,
  RuleSource,
  RuleUploadResult,
  TenderDoc,
  WorkpaperPayload,
} from "../types/ui";
import {
  extractSummaryFromHtml,
  parseCheckpointPayload,
  parseFindingJson,
  pointRunToLog,
  verdictToStatus,
} from "../adapters/backendToUi";

// ── Context value ──

export interface AuditInputDocs {
  mainDoc?: TenderDoc;
  supplementaryDocs: TenderDoc[];
}

export interface WorkbenchContextValue {
  // Connection
  apiConnected: boolean;

  // Rule sources (replaces V2 libraries)
  ruleSources: RuleSource[];
  activeRuleSource: RuleSource | undefined;
  selectedRuleSourceId: string | null;
  setSelectedRuleSourceId: (id: string | null) => void;

  // Checkpoints
  checkpoints: CheckpointItem[];
  finalCheckpoints: Array<CheckpointItem & { parsed: GovCheckpointPayload }>;

  // Extraction
  extractingRuleSourceId: string | null;
  extractStatus: string | null;
  extractError: string | null;
  uploadRuleAndExtract: (title: string, file: File) => Promise<RuleUploadResult>;
  pollExtractRun: (ruleId: string, runId: string) => Promise<void>;

  // Projects
  projects: Project[];
  activeProject: Project | undefined;
  selectedProjectId: string | null;
  setSelectedProjectId: (id: string | null) => void;
  createProject: (name: string) => Promise<Project>;
  uploadTenderDoc: (projectId: string, file: File) => Promise<TenderDoc>;
  uploadAuditInputDocs: (
    projectId: string,
    mainFile: File,
    supplementaryFiles: File[],
  ) => Promise<AuditInputDocs>;

  // Tender docs (per project)
  auditInputDocs: Record<string, AuditInputDocs>;
  /** Deprecated compatibility alias for the current project's main tender doc. */
  tenderDocs: Record<string, TenderDoc>;

  // Audit runs
  auditRuns: AuditRun[];
  activeAuditRun: AuditRun | undefined;
  selectedAuditRunId: string | null;
  setSelectedAuditRunId: (id: string | null) => void;
  createAuditRun: (
    projectId: string,
    tenderDocId: string,
    supplementaryDocIds: string[],
    checkpointIds: string[],
  ) => Promise<{ audit_run_id: string }>;
  auditProgress: AuditRunProgress | null;
  logs: LogEntry[];

  // Point runs
  pointRuns: AuditPointRun[];
  activePointRun: AuditPointRun | undefined;
  selectedPointRunId: string | null;
  setSelectedPointRunId: (id: string | null) => void;
  retryPointRun: (pointRunId: string) => Promise<void>;

  // Workpaper
  workpaperHtml: string;
  workpaperJson: WorkpaperPayload | null;
  workpaperSaveStatus: "idle" | "saving" | "saved" | "error";
  finalizeStatus: "idle" | "finalizing" | "finalized" | "error";
  loadWorkpaper: (auditRunId: string) => Promise<void>;
  setWorkpaperHtml: (html: string) => void;
  saveWorkpaper: () => Promise<void>;
  finalizeWorkpaper: (auditRunId: string) => Promise<void>;

  // Checkpoint import
  importCheckpointFile: (file: File) => Promise<{ imported_count: number; skipped_count: number }>;

  // Checkpoint CRUD
  updateCheckpoint: (id: string, payload: GovCheckpointPayload) => Promise<void>;
  deleteCheckpoint: (id: string) => Promise<void>;

  // Refresh
  refreshAll: () => Promise<void>;
}

// 导出以便测试用 MockWorkbenchProvider 直接注入；生产代码仍应通过 useWorkbench() 消费。
export const WorkbenchContext = createContext<WorkbenchContextValue | null>(null);

export function useWorkbench(): WorkbenchContextValue {
  const ctx = useContext(WorkbenchContext);
  if (!ctx) throw new Error("useWorkbench must be used within WorkbenchProvider");
  return ctx;
}

// ── Provider ──

export function WorkbenchProvider({ children }: { children: ReactNode }) {
  // Connection
  const [apiConnected, setApiConnected] = useState(false);

  // Rule sources
  const [ruleSources, setRuleSources] = useState<RuleSource[]>([]);
  const [selectedRuleSourceId, setSelectedRuleSourceId] = useState<string | null>(null);

  // Checkpoints
  const [checkpoints, setCheckpoints] = useState<CheckpointItem[]>([]);

  // Extraction
  const [extractingRuleSourceId, setExtractingRuleSourceId] = useState<string | null>(null);
  const [extractStatus, setExtractStatus] = useState<string | null>(null);
  const [extractError, setExtractError] = useState<string | null>(null);

  // Projects
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [auditInputDocs, setAuditInputDocs] = useState<Record<string, AuditInputDocs>>({});

  // Audit runs
  const [auditRuns, setAuditRuns] = useState<AuditRun[]>([]);
  const [selectedAuditRunId, setSelectedAuditRunId] = useState<string | null>(null);
  const [auditProgress, setAuditProgress] = useState<AuditRunProgress | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);

  // Point runs
  const [selectedPointRunId, setSelectedPointRunId] = useState<string | null>(null);

  // Workpaper
  const [workpaperHtml, setWorkpaperHtml] = useState("");
  const [workpaperJson, setWorkpaperJson] = useState<WorkpaperPayload | null>(null);
  const [workpaperSaveStatus, setWorkpaperSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [finalizeStatus, setFinalizeStatus] = useState<"idle" | "finalizing" | "finalized" | "error">("idle");

  // Derived
  const activeRuleSource = ruleSources.find((r) => r.id === selectedRuleSourceId);
  const activeProject = projects.find((p) => p.id === selectedProjectId);
  const tenderDocs: Record<string, TenderDoc> = Object.fromEntries(
    Object.entries(auditInputDocs)
      .filter(([, docs]) => docs.mainDoc)
      .map(([projectId, docs]) => [projectId, docs.mainDoc as TenderDoc]),
  );

  const activeAuditRun = auditRuns.find((r) => r.id === selectedAuditRunId);
  const pointRuns = auditProgress?.point_runs ?? [];
  const activePointRun = pointRuns.find((pr) => pr.id === selectedPointRunId);

  const finalCheckpoints = checkpoints
    .map((c) => ({ ...c, parsed: parseCheckpointPayload(c.payload_json)! }))
    .filter((c) => c.parsed != null);

  // ── Data fetching ──

  async function refreshAll() {
    try {
      const [sources, cps, projs, runs] = await Promise.all([
        api.listRuleSources(),
        api.listCheckpoints(),
        api.listProjects(),
        api.listAuditRuns(),
      ]);
      setRuleSources(sources);
      setCheckpoints(cps);
      setProjects(projs);
      setAuditRuns(runs);
      // Re-fetch tender docs for all known projects
      const docEntries = await Promise.all(
        projs.map(async (p) => {
          try {
            const docs = await api.listTenderDocs(p.id);
            return docs.length > 0 ? ([p.id, docs] as const) : null;
          } catch {
            return null;
          }
        }),
      );
      const docsMap: Record<string, AuditInputDocs> = {};
      for (const entry of docEntries) {
        if (entry) {
          const [pid, docs] = entry;
          docsMap[pid] = {
            mainDoc: docs[0],
            supplementaryDocs: docs.slice(1),
          };
        }
      }
      setAuditInputDocs((prev) => ({ ...prev, ...docsMap }));
      setApiConnected(true);
    } catch {
      setApiConnected(false);
    }
  }

  // Bootstrap
  useEffect(() => {
    refreshAll();
  }, []);

  // Auto-reconnect
  useEffect(() => {
    if (apiConnected) return;
    const id = setInterval(() => { refreshAll(); }, 3000);
    return () => clearInterval(id);
  }, [apiConnected]);

  // Auto-correct selections
  useEffect(() => {
    if (ruleSources.length > 0 && !ruleSources.find((r) => r.id === selectedRuleSourceId)) {
      setSelectedRuleSourceId(ruleSources[0].id);
    }
  }, [ruleSources, selectedRuleSourceId]);

  useEffect(() => {
    if (projects.length > 0 && !projects.find((p) => p.id === selectedProjectId)) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  // ── Extraction ──

  async function uploadRuleAndExtract(title: string, file: File) {
    const result = await api.uploadRule(title, file);
    setExtractingRuleSourceId(result.rule_source_id);
    setExtractStatus("pending");
    setExtractError(null);
    // Auto-poll
    pollExtractRun(result.rule_source_id, result.extract_run_id);
    return result;
  }

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function pollExtractRun(ruleId: string, runId: string) {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const status = await api.getExtractRunStatus(ruleId, runId);
        setExtractStatus(status.status);
        if (status.status === "draft_ready") {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          setExtractingRuleSourceId(null);
          await refreshAll();
        } else if (status.status === "failed") {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          setExtractError(status.error || "抽取失败");
          setExtractingRuleSourceId(null);
        }
      } catch {
        // continue polling
      }
    }, 2000);
  }

  // ── Projects ──

  async function createProject(name: string) {
    const project = await api.createProject(name, "admin");
    setProjects((prev) => [...prev, project]);
    setSelectedProjectId(project.id);
    return project;
  }

  async function handleUploadTenderDoc(projectId: string, file: File) {
    const doc = await api.uploadTenderDoc(projectId, file);
    setAuditInputDocs((prev) => ({
      ...prev,
      [projectId]: {
        mainDoc: doc,
        supplementaryDocs: prev[projectId]?.supplementaryDocs ?? [],
      },
    }));
    return doc;
  }

  async function handleUploadAuditInputDocs(
    projectId: string,
    mainFile: File,
    supplementaryFiles: File[],
  ): Promise<AuditInputDocs> {
    const existing = auditInputDocs[projectId];
    const mainDoc = existing?.mainDoc ?? await api.uploadTenderDoc(projectId, mainFile);
    let supplementaryDocs = [...(existing?.supplementaryDocs ?? [])];

    setAuditInputDocs((prev) => ({
      ...prev,
      [projectId]: {
        mainDoc,
        supplementaryDocs,
      },
    }));

    const filesToUpload = supplementaryFiles.slice(supplementaryDocs.length);
    for (const file of filesToUpload) {
      const doc = await api.uploadTenderDoc(projectId, file);
      supplementaryDocs = [...supplementaryDocs, doc];
      setAuditInputDocs((prev) => ({
        ...prev,
        [projectId]: {
          mainDoc,
          supplementaryDocs,
        },
      }));
    }

    return { mainDoc, supplementaryDocs };
  }

  // ── Audit runs ──

  const progressRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const terminalAuditStatuses = ["draft_ready", "partial_ready", "finalized", "failed", "waiting_retry"];

  function syncAuditProgress(progress: AuditRunProgress) {
    setAuditProgress(progress);
    setAuditRuns((prev) =>
      prev.map((r) =>
        r.id === progress.audit_run_id
          ? { ...r, status: progress.status, processed_count: progress.processed_count }
          : r,
      ),
    );

    const newLogs: LogEntry[] = [];
    for (const pr of progress.point_runs) {
      const cp = finalCheckpoints.find((c) => c.id === pr.checkpoint_final_id);
      const title = cp?.parsed?.title ?? pr.checkpoint_final_id;
      newLogs.push(pointRunToLog(pr, title));
    }
    setLogs(newLogs);
  }

  function startAuditProgressPolling(runId: string) {
    if (progressRef.current) clearInterval(progressRef.current);
    progressRef.current = setInterval(async () => {
      try {
        const progress = await api.getAuditRunProgress(runId);
        syncAuditProgress(progress);
        if (terminalAuditStatuses.includes(progress.status)) {
          clearInterval(progressRef.current!);
          progressRef.current = null;
        }
      } catch {
        // continue polling
      }
    }, 2000);
  }

  async function handleCreateAuditRun(
    projectId: string,
    tenderDocId: string,
    supplementaryDocIds: string[],
    checkpointIds: string[],
  ) {
    const result = await api.createAuditRun(
      projectId,
      tenderDocId,
      supplementaryDocIds,
      checkpointIds,
    );
    // Add to auditRuns immediately
    setAuditRuns((prev) => [
      {
        id: result.audit_run_id,
        project_id: projectId,
        tender_doc_id: tenderDocId,
        supplementary_doc_ids: supplementaryDocIds,
        status: "pending",
        processed_count: 0,
        total_count: result.total_count,
        error: null,
        created_at: new Date().toISOString(),
      },
      ...prev,
    ]);
    startAuditProgressPolling(result.audit_run_id);

    setSelectedAuditRunId(result.audit_run_id);
    return result;
  }

  async function handleRetryPointRun(pointRunId: string) {
    const runId =
      auditProgress?.point_runs.some((pr) => pr.id === pointRunId)
        ? auditProgress.audit_run_id
        : selectedAuditRunId;

    if (runId && auditProgress?.audit_run_id === runId) {
      const nextProgress: AuditRunProgress = {
        ...auditProgress,
        status: "running",
        point_runs: auditProgress.point_runs.map((pr) =>
          pr.id === pointRunId
            ? { ...pr, status: "pending", error: null, finding_json: null }
            : pr,
        ),
      };
      syncAuditProgress(nextProgress);
    } else if (runId) {
      setAuditRuns((prev) =>
        prev.map((r) =>
          r.id === runId
            ? { ...r, status: "running" }
            : r,
        ),
      );
    }

    try {
      await api.retryPointRun(pointRunId);
    } catch (error) {
      if (runId) {
        try {
          const progress = await api.getAuditRunProgress(runId);
          syncAuditProgress(progress);
        } catch {
          // best effort rollback
        }
      }
      throw error;
    }

    if (runId && !progressRef.current) {
      startAuditProgressPolling(runId);
    }
  }

  // ── Workpaper ──

  const wpRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function loadWorkpaper(auditRunId: string) {
    try {
      const draft = await api.getWorkpaperDraft(auditRunId);
      const wp = JSON.parse(draft.workpaper_json) as WorkpaperPayload;
      setWorkpaperJson(wp);
      const { workpaperToHtml } = await import("../adapters/backendToUi");
      setWorkpaperHtml(workpaperToHtml(wp));
    } catch {
      setWorkpaperHtml("");
      setWorkpaperJson(null);
    }
  }

  function handleSetWorkpaperHtml(html: string) {
    setWorkpaperHtml(html);
    // Sync summary back to workpaperJson so saves are not lost
    setWorkpaperJson((prev) => {
      if (!prev) return prev;
      const summary = extractSummaryFromHtml(html);
      return summary ? { ...prev, summary } : prev;
    });
    setWorkpaperSaveStatus("idle");
    // Debounced save
    if (wpRef.current) clearTimeout(wpRef.current);
    wpRef.current = setTimeout(() => { saveWorkpaper(); }, 600);
  }

  async function saveWorkpaper() {
    if (!activeAuditRun || !workpaperJson) return;
    setWorkpaperSaveStatus("saving");
    try {
      await api.updateWorkpaperDraft(activeAuditRun.id, workpaperJson);
      setWorkpaperSaveStatus("saved");
    } catch {
      setWorkpaperSaveStatus("error");
    }
  }

  async function handleFinalizeWorkpaper(auditRunId: string) {
    setFinalizeStatus("finalizing");
    try {
      await api.finalizeWorkpaper(auditRunId, "admin");
      // Poll until the audit run reaches "finalized"
      const pollFinalize = setInterval(async () => {
        try {
          const progress = await api.getAuditRunProgress(auditRunId);
          if (progress.status === "finalized") {
            clearInterval(pollFinalize);
            setFinalizeStatus("finalized");
          } else if (progress.status === "failed") {
            clearInterval(pollFinalize);
            setFinalizeStatus("error");
          }
        } catch {
          clearInterval(pollFinalize);
          setFinalizeStatus("error");
        }
      }, 2000);
    } catch {
      setFinalizeStatus("error");
    }
  }

  // ── Checkpoint CRUD ──

  async function handleUpdateCheckpoint(id: string, payload: GovCheckpointPayload) {
    await api.updateCheckpoint(id, JSON.stringify(payload));
    await refreshAll();
  }

  async function handleDeleteCheckpoint(id: string) {
    await api.deleteCheckpoint(id);
    await refreshAll();
  }

  async function handleImportCheckpointFile(file: File) {
    const result = await api.importCheckpoints(file);
    await refreshAll();
    return { imported_count: result.imported_count, skipped_count: result.skipped_count };
  }

  // ── Context value ──

  const value: WorkbenchContextValue = {
    apiConnected,
    ruleSources,
    activeRuleSource,
    selectedRuleSourceId,
    setSelectedRuleSourceId,
    checkpoints,
    finalCheckpoints,
    extractingRuleSourceId,
    extractStatus,
    extractError,
    uploadRuleAndExtract,
    pollExtractRun,
    projects,
    activeProject,
    selectedProjectId,
    setSelectedProjectId,
    createProject,
    uploadTenderDoc: handleUploadTenderDoc,
    uploadAuditInputDocs: handleUploadAuditInputDocs,
    auditInputDocs,
    tenderDocs,
    auditRuns,
    activeAuditRun,
    selectedAuditRunId,
    setSelectedAuditRunId,
    createAuditRun: handleCreateAuditRun,
    auditProgress,
    logs,
    pointRuns,
    activePointRun,
    selectedPointRunId,
    setSelectedPointRunId,
    retryPointRun: handleRetryPointRun,
    workpaperHtml,
    workpaperJson,
    workpaperSaveStatus,
    finalizeStatus,
    loadWorkpaper,
    setWorkpaperHtml: handleSetWorkpaperHtml,
    saveWorkpaper,
    finalizeWorkpaper: handleFinalizeWorkpaper,
    importCheckpointFile: handleImportCheckpointFile,
    updateCheckpoint: handleUpdateCheckpoint,
    deleteCheckpoint: handleDeleteCheckpoint,
    refreshAll,
  };

  return (
    <WorkbenchContext.Provider value={value}>
      {children}
    </WorkbenchContext.Provider>
  );
}
