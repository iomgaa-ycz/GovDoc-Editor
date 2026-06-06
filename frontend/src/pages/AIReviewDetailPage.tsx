import {
  AlertCircle,
  ArrowLeft,
  CircleCheck,
  Clock,
  Download,
  FileDown,
  FileText,
  Loader2,
  RefreshCw,
  Save,
  Search,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  extractSummaryFromHtml,
  parseCheckpointPayload,
  parseFindingJson,
  workpaperToHtml,
} from "@/adapters/backendToUi";
import { getDocument } from "@/api/documents";
import {
  finalizeWorkpaper,
  getAuditRunProgress,
  getWorkpaperDraft,
  getWorkpaperFinalDocxUrl,
  listAuditRuns,
  listCheckpoints,
  request,
  excludeFailedPoints,
  retryFailedPoints,
  retryPointRun,
  updateWorkpaperDraft,
} from "@/api/v3";
import { EmptyState } from "@/components/EmptyState";
import { PointInsight } from "@/components/PointInsight";
import { ProgressTimeline } from "@/components/ProgressTimeline";
import { StatusBadge } from "@/components/StatusBadge";
import { WorkpaperEditor } from "@/components/WorkpaperEditor";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type {
  AuditPointRun,
  AuditRun,
  AuditRunProgress,
  CheckpointItem,
  GovCheckpointPayload,
  GovFinding,
  WorkpaperPayload,
} from "@/types/ui";

type ParsedCheckpoint = CheckpointItem & { parsed: GovCheckpointPayload };
type SaveState = "idle" | "saving" | "saved" | "error";
type FinalizeState = "idle" | "finalizing" | "finalized" | "error";
type PointRunView = {
  pr: AuditPointRun;
  checkpoint: GovCheckpointPayload | null;
  finding: GovFinding | null;
  title: string;
  verdict: string | null;
  archived: boolean;
};

const TERMINAL_STATUSES = new Set([
  "completed",
  "failed",
  "cancelled",
  "draft_ready",
  "finalized",
  "partial_ready",
  "waiting_retry",
]);
const WORKPAPER_STATUSES = new Set(["draft_ready", "completed", "finalized", "partial_ready"]);
const CANCELLABLE_STATUSES = new Set(["pending", "running"]);

function cancelAuditRun(auditRunId: string): Promise<{ audit_run_id: string; status: string }> {
  return request(`/api/v1/audit/runs/${auditRunId}/cancel`, { method: "POST" });
}

function toParsedCheckpoint(item: CheckpointItem): ParsedCheckpoint | null {
  const parsed = parseCheckpointPayload(item.payload_json);
  return parsed ? { ...item, parsed } : null;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN");
}

function percent(processed: number, total: number): number {
  if (total <= 0) return 0;
  return Math.round((processed / total) * 100);
}

function projectLabel(run: AuditRun | null): string {
  if (!run) return "审查任务";
  return run.project_name || `项目 ${run.project_id.slice(0, 8)}`;
}

function docLabel(run: AuditRun | null, documentName: string | null): string {
  if (documentName) return documentName;
  if (!run) return "—";
  return `文书 ${run.main_document_id.slice(0, 8)}`;
}

function PointStatusIcon({ status }: { status: string }) {
  if (status === "completed") return <CircleCheck className="h-4 w-4 text-status-ok" />;
  if (status === "failed") return <XCircle className="h-4 w-4 text-status-err" />;
  if (status === "running") return <Loader2 className="h-4 w-4 animate-spin text-accent" />;
  return <Clock className="h-4 w-4 text-text-muted" />;
}

function saveStateLabel(state: SaveState): string {
  if (state === "saving") return "保存中";
  if (state === "saved") return "已保存";
  if (state === "error") return "保存失败";
  return "未保存";
}

function finalizeStateLabel(state: FinalizeState, status: string): string {
  if (status === "finalized" || state === "finalized") return "已定稿";
  if (state === "finalizing") return "定稿中";
  if (state === "error") return "定稿失败";
  return "未定稿";
}

function parseWorkpaper(raw: string): WorkpaperPayload | null {
  try {
    return JSON.parse(raw) as WorkpaperPayload;
  } catch {
    return null;
  }
}

export function AIReviewDetailPage() {
  const { auditRunId } = useParams<{ auditRunId: string }>();
  const navigate = useNavigate();

  const [run, setRun] = useState<AuditRun | null>(null);
  const [documentName, setDocumentName] = useState<string | null>(null);
  const [checkpoints, setCheckpoints] = useState<ParsedCheckpoint[]>([]);
  const [progress, setProgress] = useState<AuditRunProgress | null>(null);
  const [selectedPointRunId, setSelectedPointRunId] = useState<string | null>(null);
  const [insightPointRunId, setInsightPointRunId] = useState<string | null>(null);
  const [pollVersion, setPollVersion] = useState(0);
  const [loadingProgress, setLoadingProgress] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [retryingPointRunId, setRetryingPointRunId] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  const [workpaperHtml, setWorkpaperHtml] = useState("");
  const [workpaperPayload, setWorkpaperPayload] = useState<WorkpaperPayload | null>(null);
  const [draftLoading, setDraftLoading] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [finalizeState, setFinalizeState] = useState<FinalizeState>("idle");
  const workpaperPayloadRef = useRef<WorkpaperPayload | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const currentStatus = (progress?.status ?? run?.status ?? "pending") as string;
  const totalCount = progress?.total_count ?? run?.total_count ?? 0;
  const processedCount = progress?.processed_count ?? run?.processed_count ?? 0;
  const progressPercent = percent(processedCount, totalCount);

  // 部分完成（partial_ready）派生值：用于提示条与重试/跳过按钮
  const pointRuns = progress?.point_runs ?? [];
  const completedCount = pointRuns.filter((p) => p.status === "completed").length;
  const failedCount = pointRuns.filter((p) => p.status === "failed").length;
  const isRunning = currentStatus === "running";
  // 部分稿提示条的展示条件：partial_ready，或仍有失败审核点（运行中也展示，但按钮禁用）
  const isPartial = currentStatus === "partial_ready" || failedCount > 0;

  const checkpointById = useMemo(
    () =>
      new Map(
        checkpoints.map((checkpoint) => [
          checkpoint.id,
          { parsed: checkpoint.parsed, archived: checkpoint.archived === true },
        ]),
      ),
    [checkpoints],
  );

  const pointRunViews = useMemo<PointRunView[]>(() => {
    return (progress?.point_runs ?? []).map((pr) => {
      const entry = checkpointById.get(pr.checkpoint_final_id) ?? null;
      const checkpoint = entry?.parsed ?? null;
      const finding = parseFindingJson(pr.finding_json);
      const verdict = finding?.verdict?.verdict ?? null;
      return {
        pr,
        checkpoint,
        finding,
        verdict,
        archived: entry?.archived ?? false,
        title: checkpoint?.title ?? `审核点 ${pr.checkpoint_final_id.slice(0, 8)}`,
      };
    });
  }, [checkpointById, progress]);

  const selectedTimeline =
    pointRunViews.find((view) => view.pr.id === selectedPointRunId)
    ?? pointRunViews.find((view) => view.pr.status === "running")
    ?? pointRunViews[0]
    ?? null;

  const selectedInsight =
    pointRunViews.find((view) => view.pr.id === insightPointRunId) ?? null;

  const failureMessage =
    run?.error
    ?? pointRunViews.find((view) => view.pr.status === "failed")?.pr.error
    ?? (currentStatus === "cancelled" ? "审查任务已取消。" : "审查任务未能完成。");

  useEffect(() => {
    if (!auditRunId) return;
    let active = true;
    Promise.all([listAuditRuns(), listCheckpoints(true)])
      .then(([runs, checkpointItems]) => {
        if (!active) return;
        const found = runs.find((item) => item.id === auditRunId) ?? null;
        setRun(found);
        setCheckpoints(
          checkpointItems
            .map(toParsedCheckpoint)
            .filter((checkpoint): checkpoint is ParsedCheckpoint => checkpoint != null),
        );
        if (!found) return;
        getDocument(found.main_document_id)
          .then((document) => {
            if (!active) return;
            setDocumentName(document.filename);
          })
          .catch(() => {
            if (active) setDocumentName(null);
          });
      })
      .catch((err: unknown) => {
        if (active) setPageError(err instanceof Error ? err.message : "加载任务元数据失败");
      });
    return () => {
      active = false;
    };
  }, [auditRunId]);

  useEffect(() => {
    if (!auditRunId) return;
    const runId = auditRunId;
    let active = true;
    let intervalId: ReturnType<typeof setInterval> | null = null;

    async function loadProgress() {
      setLoadingProgress(true);
      try {
        const nextProgress = await getAuditRunProgress(runId);
        if (!active) return;
        setProgress(nextProgress);
        setPageError(null);
        if (TERMINAL_STATUSES.has(nextProgress.status as string) && intervalId) {
          clearInterval(intervalId);
          intervalId = null;
        }
      } catch (err) {
        if (active) setPageError(err instanceof Error ? err.message : "加载审查进度失败");
      } finally {
        if (active) setLoadingProgress(false);
      }
    }

    void loadProgress();
    intervalId = setInterval(loadProgress, 3000);
    return () => {
      active = false;
      if (intervalId) clearInterval(intervalId);
    };
  }, [auditRunId, pollVersion]);

  useEffect(() => {
    const pointRuns = progress?.point_runs ?? [];
    if (selectedPointRunId && pointRuns.some((pointRun) => pointRun.id === selectedPointRunId)) {
      return;
    }
    setSelectedPointRunId(
      pointRuns.find((pointRun) => pointRun.status === "running")?.id
      ?? pointRuns[0]?.id
      ?? null,
    );
  }, [progress, selectedPointRunId]);

  useEffect(() => {
    if (!auditRunId || !WORKPAPER_STATUSES.has(currentStatus)) return;
    let active = true;
    setDraftLoading(true);
    setDraftError(null);
    getWorkpaperDraft(auditRunId)
      .then((draft) => {
        if (!active) return;
        const payload = parseWorkpaper(draft.workpaper_json);
        setWorkpaperPayload(payload);
        workpaperPayloadRef.current = payload;
        setWorkpaperHtml(payload ? workpaperToHtml(payload) : "");
        setSaveState("idle");
      })
      .catch((err: unknown) => {
        if (active) setDraftError(err instanceof Error ? err.message : "加载工作底稿失败");
      })
      .finally(() => {
        if (active) setDraftLoading(false);
      });
    return () => {
      active = false;
    };
  }, [auditRunId, currentStatus]);

  useEffect(() => {
    workpaperPayloadRef.current = workpaperPayload;
  }, [workpaperPayload]);

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  async function saveWorkpaperPayload(payload = workpaperPayloadRef.current) {
    if (!auditRunId || !payload) return;
    setSaveState("saving");
    try {
      await updateWorkpaperDraft(auditRunId, payload);
      setSaveState("saved");
    } catch {
      setSaveState("error");
    }
  }

  function handleWorkpaperChange(html: string) {
    setWorkpaperHtml(html);
    const currentPayload = workpaperPayloadRef.current;
    if (!currentPayload) return;
    const nextPayload = {
      ...currentPayload,
      summary: extractSummaryFromHtml(html),
    };
    workpaperPayloadRef.current = nextPayload;
    setWorkpaperPayload(nextPayload);
    setSaveState("idle");
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      void saveWorkpaperPayload(nextPayload);
    }, 700);
  }

  async function handleFinalizeWorkpaper() {
    if (!auditRunId) return;
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    setFinalizeState("finalizing");
    try {
      await saveWorkpaperPayload();
      await finalizeWorkpaper(auditRunId, "reviewer");
      setFinalizeState("finalized");
      const nextProgress = await getAuditRunProgress(auditRunId);
      setProgress(nextProgress);
    } catch {
      setFinalizeState("error");
    }
  }

  async function handleRetryPointRun(pointRunId: string) {
    if (!auditRunId) return;
    setRetryingPointRunId(pointRunId);
    try {
      await retryPointRun(pointRunId);
      const nextProgress = await getAuditRunProgress(auditRunId);
      setProgress(nextProgress);
      setPollVersion((current) => current + 1);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "重试审核点失败");
    } finally {
      setRetryingPointRunId(null);
    }
  }

  async function handleRetryFailed() {
    if (!auditRunId) return;
    try {
      await retryFailedPoints(auditRunId);
      setPollVersion((current) => current + 1);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "重试失败");
    }
  }

  async function handleExcludeFailed() {
    if (!auditRunId) return;
    try {
      await excludeFailedPoints(auditRunId);
      setPollVersion((current) => current + 1);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "跳过失败");
    }
  }

  async function handleCancelAuditRun() {
    if (!auditRunId) return;
    setCancelling(true);
    try {
      await cancelAuditRun(auditRunId);
      const nextProgress = await getAuditRunProgress(auditRunId);
      setProgress(nextProgress);
      setPollVersion((current) => current + 1);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "取消审查失败");
    } finally {
      setCancelling(false);
    }
  }

  function renderStatusBanner() {
    return (
      <>
        {isPartial && (
          <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
            <p>
              本次审核共 {totalCount} 个审核点：已完成 {completedCount} 个，{failedCount} 个未能完成。
            </p>
            <p className="mt-1">当前为「部分稿」，缺少未完成审核点的内容。</p>
            <div className="mt-2 flex gap-2">
              <Button size="sm" disabled={isRunning} onClick={handleRetryFailed}>
                重试未完成的 {failedCount} 项
              </Button>
              <Button size="sm" variant="secondary" disabled={isRunning} onClick={handleExcludeFailed}>
                跳过这 {failedCount} 项并出完整稿
              </Button>
            </div>
          </div>
        )}
        {currentStatus === "draft_ready" && (
          <div className="rounded-md border border-green-300 bg-green-50 p-3 text-sm text-green-800">
            ✅ {totalCount} 个审核点全部完成，已生成完整底稿。
          </div>
        )}
      </>
    );
  }

  function renderProgressView() {
    return (
      <main className="space-y-5 overflow-auto p-7">
        <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
          <Card>
            <CardHeader>
              <CardTitle>任务信息</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between gap-4">
                <span className="text-text-muted">项目</span>
                <span className="truncate text-right font-medium text-text-primary">
                  {projectLabel(run)}
                </span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-text-muted">文书</span>
                <span className="truncate text-right text-text-primary">
                  {docLabel(run, documentName)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">审查点</span>
                <span className="text-text-primary">{totalCount} 个</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-text-muted">创建时间</span>
                <span className="text-right text-text-primary">{formatDate(run?.created_at)}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle>审查进度</CardTitle>
                <p className="mt-1 text-sm text-text-muted">
                  已处理 {processedCount}/{totalCount} 个审查点
                </p>
              </div>
              {loadingProgress && <Loader2 className="h-4 w-4 animate-spin text-text-muted" />}
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-text-secondary">总体进度</span>
                  <span className="font-medium text-text-primary">{progressPercent}%</span>
                </div>
                <Progress value={progressPercent} />
              </div>

              {selectedTimeline ? (
                <ProgressTimeline
                  pointRun={selectedTimeline.pr}
                  checkpoint={selectedTimeline.checkpoint}
                  onRetry={
                    selectedTimeline.pr.status === "failed"
                      ? () => handleRetryPointRun(selectedTimeline.pr.id)
                      : undefined
                  }
                />
              ) : (
                <EmptyState title="暂无审查点进度" description="任务启动后会显示每个审查点的执行进度。" />
              )}
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle>审核点</CardTitle>
              <p className="mt-1 text-sm text-text-muted">点击详情查看单个审查点洞察</p>
            </div>
            <Badge variant="outline">{pointRunViews.length} 个要点</Badge>
          </CardHeader>
          <CardContent>
            {pointRunViews.length === 0 ? (
              <EmptyState title="暂无审核点" description="当前审查任务还没有返回审核点运行记录。" />
            ) : (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {pointRunViews.map((view) => (
                  <div
                    key={view.pr.id}
                    role="button"
                    tabIndex={0}
                    className={cn(
                      "flex min-h-[112px] flex-col rounded-card border bg-white p-4 text-left transition-colors hover:border-accent hover:bg-accent-light/40",
                      selectedTimeline?.pr.id === view.pr.id && "border-accent bg-accent-light/40",
                    )}
                    onClick={() => setSelectedPointRunId(view.pr.id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setSelectedPointRunId(view.pr.id);
                      }
                    }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex min-w-0 items-start gap-2">
                        <PointStatusIcon status={view.pr.status} />
                        <p className="line-clamp-2 text-sm font-medium text-text-primary">
                          {view.title}
                          {view.archived && (
                            <Badge variant="muted" className="ml-2 align-middle text-xs">
                              已归档
                            </Badge>
                          )}
                        </p>
                      </div>
                      <StatusBadge status={view.verdict ?? view.pr.status} />
                    </div>
                    <div className="mt-auto flex items-center justify-between pt-3">
                      <span className="text-xs text-text-muted">
                        {view.pr.current_phase ?? view.pr.status}
                      </span>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={(event) => {
                          event.stopPropagation();
                          setInsightPointRunId(view.pr.id);
                        }}
                      >
                        详情
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    );
  }

  function renderWorkpaperView() {
    return (
      <main className="flex flex-1 gap-5 overflow-hidden p-6">
        <Card className="min-w-0 flex-1 overflow-auto">
          {draftLoading ? (
            <div className="flex h-full min-h-[520px] items-center justify-center text-sm text-text-muted">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              加载工作底稿...
            </div>
          ) : draftError ? (
            <EmptyState title="工作底稿加载失败" description={draftError} />
          ) : workpaperHtml ? (
            <WorkpaperEditor value={workpaperHtml} onChange={handleWorkpaperChange} />
          ) : (
            <EmptyState title="暂无工作底稿" description="任务完成后会在这里展示可编辑工作底稿。" />
          )}
        </Card>

        <aside className="w-80 shrink-0 space-y-4 overflow-auto">
          <Card>
            <CardHeader>
              <CardTitle>底稿操作</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-text-muted">保存状态</span>
                <Badge variant={saveState === "error" ? "err" : saveState === "saved" ? "ok" : "muted"}>
                  {saveStateLabel(saveState)}
                </Badge>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-text-muted">定稿状态</span>
                <Badge
                  variant={
                    currentStatus === "finalized" || finalizeState === "finalized"
                      ? "ok"
                      : finalizeState === "error"
                        ? "err"
                        : "muted"
                  }
                >
                  {finalizeStateLabel(finalizeState, currentStatus)}
                </Badge>
              </div>
              {workpaperPayload && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-text-muted">发现数量</span>
                  <span className="text-text-primary">{workpaperPayload.findings.length} 条</span>
                </div>
              )}
              <div className="grid gap-2 pt-2">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={!workpaperPayload || saveState === "saving"}
                  onClick={() => saveWorkpaperPayload()}
                >
                  <Save className="h-4 w-4" />
                  {saveState === "saving" ? "保存中..." : "保存"}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={!workpaperPayload || finalizeState === "finalizing" || currentStatus === "finalized"}
                  onClick={handleFinalizeWorkpaper}
                >
                  <FileDown className="h-4 w-4" />
                  {finalizeState === "finalizing" ? "定稿中..." : "定稿"}
                </Button>
                {auditRunId && (
                  <Button asChild disabled={currentStatus !== "finalized"}>
                    <a
                      href={getWorkpaperFinalDocxUrl(auditRunId)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <Download className="h-4 w-4" />
                      导出 Word
                    </a>
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>审查发现</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {pointRunViews.length === 0 ? (
                <div className="px-5 pb-5">
                  <EmptyState title="暂无发现" description="审查点完成后会在这里汇总结果。" />
                </div>
              ) : (
                <ScrollArea className="max-h-[520px]">
                  {pointRunViews.map((view) => (
                    <button
                      key={view.pr.id}
                      type="button"
                      className="flex w-full items-start gap-3 border-b px-5 py-3 text-left last:border-b-0 hover:bg-surface"
                      onClick={() => setInsightPointRunId(view.pr.id)}
                    >
                      <PointStatusIcon status={view.pr.status} />
                      <span className="min-w-0 flex-1">
                        <span className="block line-clamp-2 text-sm font-medium text-text-primary">
                          {view.title}
                          {view.archived && (
                            <Badge variant="muted" className="ml-2 align-middle text-xs">
                              已归档
                            </Badge>
                          )}
                        </span>
                        <span className="mt-1 flex items-center gap-2">
                          <StatusBadge status={view.verdict ?? view.pr.status} />
                          {view.finding?.verdict.evidence_quotes.length ? (
                            <span className="text-xs text-text-muted">
                              {view.finding.verdict.evidence_quotes.length} 条证据
                            </span>
                          ) : null}
                        </span>
                      </span>
                    </button>
                  ))}
                </ScrollArea>
              )}
            </CardContent>
          </Card>
        </aside>
      </main>
    );
  }

  function renderErrorView() {
    return (
      <main className="flex flex-1 items-center justify-center p-7">
        <Card className="w-full max-w-xl">
          <CardContent className="space-y-5 p-8 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-status-err-bg">
              <AlertCircle className="h-7 w-7 text-status-err" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-text-primary">
                {currentStatus === "cancelled" ? "审查已取消" : "审查失败"}
              </h2>
              <p className="mt-2 text-sm text-text-muted">{failureMessage}</p>
            </div>
            <Button onClick={() => navigate("/ai-review")}>
              重新创建
            </Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  if (!auditRunId) {
    return (
      <div className="flex h-screen items-center justify-center">
        <EmptyState title="缺少审查任务 ID" description="请从审查列表重新进入任务详情。" />
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between gap-3 border-b bg-surface-card px-7 py-3.5">
        <div className="min-w-0">
          <Link
            to="/ai-review"
            className="mb-1 inline-flex items-center gap-1 text-sm text-text-muted hover:text-accent"
          >
            <ArrowLeft className="h-4 w-4" />
            审查列表
          </Link>
          <div className="flex min-w-0 items-center gap-3">
            <h1 className="truncate text-base font-semibold text-text-primary">
              {projectLabel(run)}
            </h1>
            <StatusBadge status={currentStatus} />
          </div>
        </div>
        <div className="flex items-center gap-2">
          {pageError && (
            <span className="max-w-[360px] truncate text-sm text-status-err" title={pageError}>
              {pageError}
            </span>
          )}
          {CANCELLABLE_STATUSES.has(currentStatus) && (
            <Button
              type="button"
              variant="danger"
              size="sm"
              disabled={cancelling}
              onClick={handleCancelAuditRun}
            >
              {cancelling ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <XCircle className="h-4 w-4" />
              )}
              取消审查
            </Button>
          )}
        </div>
      </header>

      {(isPartial || currentStatus === "draft_ready") && (
        <div className="border-b bg-surface-card px-7 py-3">{renderStatusBanner()}</div>
      )}

      {currentStatus === "failed" || currentStatus === "cancelled"
        ? renderErrorView()
        : WORKPAPER_STATUSES.has(currentStatus)
          ? renderWorkpaperView()
          : renderProgressView()}

      <Dialog
        open={insightPointRunId != null}
        onOpenChange={(open) => {
          if (!open) setInsightPointRunId(null);
        }}
      >
        <DialogContent className="max-h-[85vh] max-w-3xl overflow-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Search className="h-4 w-4 text-accent" />
              审查点详情
            </DialogTitle>
          </DialogHeader>
          <div className="p-5 pt-0">
            {selectedInsight?.checkpoint ? (
              <PointInsight
                checkpoint={selectedInsight.checkpoint}
                finding={selectedInsight.finding}
                pointStatus={selectedInsight.pr.status}
              />
            ) : (
              <EmptyState
                icon={<FileText className="h-7 w-7 text-accent" />}
                title="暂无审查点详情"
                description="该审查点的定义或结果尚未返回。"
              />
            )}
            {selectedInsight?.pr.status === "failed" && (
              <div className="mt-4">
                <Button
                  variant="secondary"
                  disabled={retryingPointRunId === selectedInsight.pr.id}
                  onClick={() => handleRetryPointRun(selectedInsight.pr.id)}
                >
                  <RefreshCw
                    className={cn(
                      "h-4 w-4",
                      retryingPointRunId === selectedInsight.pr.id && "animate-spin",
                    )}
                  />
                  {retryingPointRunId === selectedInsight.pr.id ? "正在重试..." : "重试此审核点"}
                </Button>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default AIReviewDetailPage;
