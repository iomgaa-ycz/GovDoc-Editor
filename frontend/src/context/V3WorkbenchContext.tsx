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
  CheckpointImportResult,
  CheckpointLibrary,
  GovCheckpointPayload,
  GovFinding,
  LogEntry,
  Project,
  RuleSource,
  RuleUploadResult,
  WorkpaperPayload,
} from "../types/ui";
import {
  extractSummaryFromHtml,
  parseCheckpointPayload,
  parseFindingJson,
  pointRunToLog,
} from "../adapters/backendToUi";

// ── Context value ──

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
  checkpointLibraries: CheckpointLibrary[];

  // Extraction
  extractingRuleSourceId: string | null;
  extractStatus: string | null;
  extractError: string | null;
  extractCurrentPhase: string | null;
  uploadRuleAndExtract: (title: string, file: File) => Promise<RuleUploadResult>;
  pollExtractRun: (ruleId: string, runId: string) => Promise<void>;

  // Projects
  projects: Project[];
  activeProject: Project | undefined;
  selectedProjectId: string | null;
  setSelectedProjectId: (id: string | null) => void;
  createProject: (name: string) => Promise<Project>;

  // Audit runs
  auditRuns: AuditRun[];
  activeAuditRun: AuditRun | undefined;
  selectedAuditRunId: string | null;
  setSelectedAuditRunId: (id: string | null) => void;
  createAuditRun: (
    projectId: string,
    mainDocumentId: string,
    supplementaryDocIds: string[],
    checkpointIds: string[],
    checkpointLibraryId?: string | null,
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
  importCheckpointFile: (
    file: File,
    libraryIds?: string[],
  ) => Promise<CheckpointImportResult>;

  // Checkpoint libraries
  createCheckpointLibrary: (name: string, description?: string) => Promise<CheckpointLibrary>;
  addCheckpointsToLibraries: (
    libraryIds: string[],
    checkpointIds: string[],
  ) => Promise<number>;
  removeCheckpointsFromLibrary: (
    libraryId: string,
    checkpointIds: string[],
  ) => Promise<number>;
  updateCheckpointLibrary: (
    id: string,
    name: string,
    description: string,
  ) => Promise<void>;
  deleteCheckpointLibrary: (id: string) => Promise<void>;

  // Checkpoint CRUD
  updateCheckpoint: (id: string, payload: GovCheckpointPayload) => Promise<void>;
  deleteCheckpoint: (id: string) => Promise<void>;

  // Refresh
  refreshAll: () => Promise<void>;
}

// 导出以便测试用 MockWorkbenchProvider 直接注入；生产代码仍应通过 useWorkbench() 消费。
export const WorkbenchContext = createContext<WorkbenchContextValue | null>(null);

export function useWorkbench(): WorkbenchContextValue & Record<string, any> {
  const ctx = useContext(WorkbenchContext);
  if (!ctx) throw new Error("useWorkbench must be used within WorkbenchProvider");
  return ctx as WorkbenchContextValue & Record<string, any>;
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
  const [checkpointLibraries, setCheckpointLibraries] = useState<CheckpointLibrary[]>([]);

  // Extraction
  const [extractingRuleSourceId, setExtractingRuleSourceId] = useState<string | null>(null);
  const [extractStatus, setExtractStatus] = useState<string | null>(null);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [extractCurrentPhase, setExtractCurrentPhase] = useState<string | null>(null);

  // Projects
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);

  // Audit runs
  const [auditRuns, setAuditRuns] = useState<AuditRun[]>([]);
  const [selectedAuditRunId, setSelectedAuditRunId] = useState<string | null>(null);
  const [auditProgress, setAuditProgress] = useState<AuditRunProgress | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const selectedAuditRunIdRef = useRef<string | null>(null);
  selectedAuditRunIdRef.current = selectedAuditRunId;

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
  const activeAuditRun = auditRuns.find((r) => r.id === selectedAuditRunId);
  const pointRuns = auditProgress?.point_runs ?? [];
  const activePointRun = pointRuns.find((pr) => pr.id === selectedPointRunId);

  const finalCheckpoints = checkpoints
    .map((c) => ({ ...c, parsed: parseCheckpointPayload(c.payload_json)! }))
    .filter((c) => c.parsed != null);

  // ── Data fetching ──

  async function refreshAll() {
    try {
      const [sources, cps, libraries, projs, runs] = await Promise.all([
        api.listRuleSources(),
        api.listCheckpoints(),
        api.listCheckpointLibraries(),
        api.listProjects(),
        api.listAuditRuns(),
      ]);
      setRuleSources(sources);
      setCheckpoints(cps);
      setCheckpointLibraries(libraries);
      setProjects(projs);
      setAuditRuns(runs);
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

  // 页面不可见时暂停所有轮询，恢复可见时重启
  useEffect(() => {
    function handleVisibility() {
      if (document.hidden) {
        if (progressRef.current) {
          clearInterval(progressRef.current);
          progressRef.current = null;
        }
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } else {
        if (selectedAuditRunIdRef.current && auditProgress && !terminalAuditStatuses.includes(auditProgress.status)) {
          startAuditProgressPolling(selectedAuditRunIdRef.current);
        }
        if (extractingRuleSourceId && extractRunIdRef.current) {
          pollExtractRun(extractingRuleSourceId, extractRunIdRef.current);
        }
      }
    }
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, [auditProgress, extractingRuleSourceId]);

  // 选中审核运行时自动加载对应的 progress
  useEffect(() => {
    if (!selectedAuditRunId) {
      setAuditProgress(null);
      setSelectedPointRunId(null);
      setLogs([]);
      return;
    }

    setAuditProgress((current) =>
      current?.audit_run_id === selectedAuditRunId ? current : null,
    );
    setSelectedPointRunId(null);
    setLogs([]);

    let cancelled = false;
    api.getAuditRunProgress(selectedAuditRunId).then((progress) => {
      if (!cancelled && selectedAuditRunIdRef.current === progress.audit_run_id) {
        syncAuditProgress(progress);
      }
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [selectedAuditRunId]);

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
  const extractRunIdRef = useRef<string | null>(null);

  async function pollExtractRun(ruleId: string, runId: string) {
    extractRunIdRef.current = runId;
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const status = await api.getExtractRunStatus(ruleId, runId);
        setExtractStatus(status.status);
        setExtractCurrentPhase(status.current_phase ?? null);
        if (status.status === "draft_ready") {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          extractRunIdRef.current = null;
          setExtractingRuleSourceId(null);
          setExtractCurrentPhase(null);
          await refreshAll();
        } else if (status.status === "failed") {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          extractRunIdRef.current = null;
          setExtractError(status.error || "抽取失败");
          setExtractingRuleSourceId(null);
          setExtractCurrentPhase(null);
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

  // ── Audit runs ──

  const progressRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const terminalAuditStatuses = ["draft_ready", "partial_ready", "finalized", "failed", "waiting_retry"];

  function syncAuditProgress(progress: AuditRunProgress) {
    setAuditRuns((prev) =>
      prev.map((r) =>
        r.id === progress.audit_run_id
          ? { ...r, status: progress.status, processed_count: progress.processed_count }
          : r,
      ),
    );

    if (selectedAuditRunIdRef.current !== progress.audit_run_id) return;

    setAuditProgress(progress);
    const newLogs: LogEntry[] = [];
    for (const pr of progress.point_runs) {
      const cp = finalCheckpoints.find((c) => c.id === pr.checkpoint_final_id);
      const title = cp?.parsed?.title ?? pr.checkpoint_final_id;
      newLogs.push(pointRunToLog(pr, title));
    }
    setLogs(newLogs);
    setSelectedPointRunId((current) =>
      progress.point_runs.some((pr) => pr.id === current)
        ? current
        : progress.point_runs[0]?.id ?? null,
    );
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
    mainDocumentId: string,
    supplementaryDocIds: string[],
    checkpointIds: string[],
    checkpointLibraryId?: string | null,
  ) {
    const result = await api.createAuditRun(
      projectId,
      mainDocumentId,
      supplementaryDocIds,
      checkpointIds,
      checkpointLibraryId,
    );
    // Add to auditRuns immediately
    setAuditRuns((prev) => [
      {
        id: result.audit_run_id,
        project_id: projectId,
        main_document_id: mainDocumentId,
        supplementary_doc_ids: supplementaryDocIds,
        checkpoint_library_id: result.checkpoint_library_id ?? checkpointLibraryId ?? null,
        checkpoint_library_name_snapshot: result.checkpoint_library_name_snapshot ?? null,
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
  const finalizePollRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
    // 清理上一次可能残留的轮询
    if (finalizePollRef.current) {
      clearInterval(finalizePollRef.current);
      finalizePollRef.current = null;
    }
    try {
      await api.finalizeWorkpaper(auditRunId, "admin");
      finalizePollRef.current = setInterval(async () => {
        try {
          const progress = await api.getAuditRunProgress(auditRunId);
          if (progress.status === "finalized") {
            clearInterval(finalizePollRef.current!);
            finalizePollRef.current = null;
            setFinalizeStatus("finalized");
          } else if (progress.status === "failed") {
            clearInterval(finalizePollRef.current!);
            finalizePollRef.current = null;
            setFinalizeStatus("error");
          }
        } catch {
          clearInterval(finalizePollRef.current!);
          finalizePollRef.current = null;
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

  async function handleImportCheckpointFile(file: File, libraryIds: string[] = []) {
    const result = await api.importCheckpoints(file, libraryIds);
    await refreshAll();
    return result;
  }

  async function handleCreateCheckpointLibrary(name: string, description = "") {
    const library = await api.createCheckpointLibrary(name, description);
    setCheckpointLibraries((prev) => [
      library,
      ...prev.filter((item) => item.id !== library.id),
    ]);
    return library;
  }

  async function handleAddCheckpointsToLibraries(
    libraryIds: string[],
    checkpointIds: string[],
  ) {
    const result = await api.addCheckpointsToLibraries(libraryIds, checkpointIds);
    setCheckpointLibraries(await api.listCheckpointLibraries());
    return result.added_count;
  }

  async function handleRemoveCheckpointsFromLibrary(
    libraryId: string,
    checkpointIds: string[],
  ) {
    const result = await api.removeCheckpointsFromLibrary(libraryId, checkpointIds);
    setCheckpointLibraries(await api.listCheckpointLibraries());
    return result.removed_count;
  }

  async function handleUpdateCheckpointLibrary(
    id: string,
    name: string,
    description: string,
  ) {
    await api.updateCheckpointLibrary(id, name, description);
    setCheckpointLibraries((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, name, description } : item,
      ),
    );
  }

  async function handleDeleteCheckpointLibrary(id: string) {
    await api.deleteCheckpointLibrary(id);
    setCheckpointLibraries((prev) => prev.filter((item) => item.id !== id));
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
    checkpointLibraries,
    extractingRuleSourceId,
    extractStatus,
    extractError,
    extractCurrentPhase,
    uploadRuleAndExtract,
    pollExtractRun,
    projects,
    activeProject,
    selectedProjectId,
    setSelectedProjectId,
    createProject,
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
    createCheckpointLibrary: handleCreateCheckpointLibrary,
    addCheckpointsToLibraries: handleAddCheckpointsToLibraries,
    removeCheckpointsFromLibrary: handleRemoveCheckpointsFromLibrary,
    updateCheckpointLibrary: handleUpdateCheckpointLibrary,
    deleteCheckpointLibrary: handleDeleteCheckpointLibrary,
    updateCheckpoint: handleUpdateCheckpoint,
    deleteCheckpoint: handleDeleteCheckpoint,
    refreshAll,
  };

  // 组件卸载时清理所有轮询定时器
  useEffect(() => {
    return () => {
      if (finalizePollRef.current) {
        clearInterval(finalizePollRef.current);
      }
    };
  }, []);

  return (
    <WorkbenchContext.Provider value={value}>
      {children}
    </WorkbenchContext.Provider>
  );
}
