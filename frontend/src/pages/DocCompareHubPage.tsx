import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { GitCompareArrows, Play, FolderOpen, FileText, X, Circle, CircleCheck, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import FilePickerModal from "../components/FilePickerModal";
import { compareDocuments, listCompareRuns, retryCompareRun, type CompareRunStatus } from "../api/compare";
import { getDocument } from "../api/documents";
import type { GovDocument } from "../types/ui";

type NormalizedRunStatus = "completed" | "running" | "pending" | "failed" | "unknown";

// 与后端 govdoc.yaml compare.max_files、_validate_file_count 三处同步。
const MAX_COMPARE_FILES = 10;

function normalizeStatus(status: string): NormalizedRunStatus {
  if (status === "completed" || status === "running" || status === "pending" || status === "failed") {
    return status;
  }
  return "unknown";
}

function statusLabel(status: string): string {
  const normalized = normalizeStatus(status);
  if (normalized === "completed") return "已完成";
  if (normalized === "failed") return "失败";
  if (normalized === "running") return "进行中";
  if (normalized === "pending") return "排队中";
  return "未知";
}

function statusBadgeClass(status: string): string {
  const normalized = normalizeStatus(status);
  if (normalized === "completed") return "bg-green-50 text-[#16A34A]";
  if (normalized === "failed") return "bg-red-50 text-[#DC2626]";
  if (normalized === "running") return "bg-blue-50 text-[#3B82F6]";
  if (normalized === "pending") return "bg-gray-50 text-text-muted";
  return "bg-gray-50 text-text-muted";
}

function formatFileSize(size: number): string {
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  return `${(size / 1024).toFixed(1)} KB`;
}

function deduplicateDocuments(documents: GovDocument[]): GovDocument[] {
  return [...new Map(documents.map((document) => [document.id, document])).values()];
}

function formatCreatedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatRunFiles(run: CompareRunStatus): string {
  if (run.fileNames.length === 0) return `${run.fileCount} 份文件`;
  if (run.fileNames.length <= 2) return run.fileNames.join("、");
  return `${run.fileNames.slice(0, 2).join("、")} 等 ${run.fileCount} 份文件`;
}

function formatMatchCount(run: CompareRunStatus): string {
  const enrichedRun = run as CompareRunStatus & {
    matchCount?: number;
    summary?: { matchCount?: number };
  };
  const count = enrichedRun.matchCount ?? enrichedRun.summary?.matchCount;
  return typeof count === "number" ? `${count} 组匹配` : "-";
}

function progressIndex(run: CompareRunStatus): number {
  if (run.status === "completed") return 6;
  if (run.status === "pending") return 0;
  if (!run.progress) return 0;
  if (run.progress.phase === "converting") return 1;
  if (run.progress.phase === "matching") {
    if (run.progress.step === "paragraph") return 2;
    if (run.progress.step === "sentence") return 3;
    if (run.progress.step === "similar") return 4;
  }
  if (run.status === "running") return 5;
  return 0;
}

const PROGRESS_STEPS = ["上传文件", "文档转换", "段落匹配", "句子匹配", "近似检测", "生成结果"];

function InlineProgress({ run }: { run: CompareRunStatus }) {
  const stepIndex = progressIndex(run);
  return (
    <div className="flex items-center gap-4 border-t border-blue-100 px-4 py-2">
      {PROGRESS_STEPS.map((step, i) => (
        <div key={step} className="flex items-center gap-1.5">
          {i < stepIndex ? (
            <CircleCheck className="h-3.5 w-3.5 text-[#16A34A]" />
          ) : i === stepIndex ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-[#3B82F6]" />
          ) : (
            <Circle className="h-3.5 w-3.5 text-gray-300" />
          )}
          <span
            className={cn(
              "text-xs",
              i < stepIndex && "text-[#16A34A]",
              i === stepIndex && "font-medium text-[#3B82F6]",
              i > stepIndex && "text-text-muted",
            )}
          >
            {step}
          </span>
        </div>
      ))}
    </div>
  );
}

export function DocCompareHubPage() {
  const navigate = useNavigate();
  const [selectedDocs, setSelectedDocs] = useState<GovDocument[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [runs, setRuns] = useState<CompareRunStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [retryingIds, setRetryingIds] = useState<Set<string>>(() => new Set());
  const [retryErrors, setRetryErrors] = useState<Record<string, string>>({});
  const exceedsMaxFiles = selectedDocs.length > MAX_COMPARE_FILES;

  useEffect(() => {
    let active = true;

    listCompareRuns()
      .then((items) => {
        if (active) {
          setRuns(items);
          setHistoryError(null);
        }
      })
      .catch((err) => {
        if (active) {
          setHistoryError(err instanceof Error ? err.message : "历史记录加载失败");
        }
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const hasActive = runs.some((r) => r.status === "running" || r.status === "pending");
    if (!hasActive) return;
    const timer = setInterval(() => {
      listCompareRuns().then(setRuns).catch(() => {});
    }, 3000);
    return () => clearInterval(timer);
  }, [runs]);

  function removeDocument(documentId: string) {
    setSelectedDocs((current) => current.filter((document) => document.id !== documentId));
  }

  async function handlePickerConfirm(selectedIds: string[]): Promise<void> {
    if (selectedIds.length === 0) return;
    setError(null);
    try {
      const selected = await Promise.all(selectedIds.map((id) => getDocument(id)));
      setSelectedDocs((current) => deduplicateDocuments([...current, ...selected]));
      setPickerOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "选择文件失败");
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (selectedDocs.length < 2 || selectedDocs.length > MAX_COMPARE_FILES || loading) return;

    setLoading(true);
    setError(null);
    try {
      await compareDocuments(selectedDocs.map((document) => document.id));
      setSelectedDocs([]);
      refreshRuns();
      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
      setLoading(false);
    }
  }

  function refreshRuns() {
    listCompareRuns().then(setRuns).catch(() => {});
  }

  async function handleRetry(failedReviewId: string) {
    if (retryingIds.has(failedReviewId)) return;
    setRetryingIds((current) => new Set(current).add(failedReviewId));
    setRetryErrors((current) => {
      const next = { ...current };
      delete next[failedReviewId];
      return next;
    });
    try {
      await retryCompareRun(failedReviewId);
    } catch (err) {
      setRetryErrors((current) => ({
        ...current,
        [failedReviewId]: err instanceof Error ? err.message : "重试请求失败，请稍后再试",
      }));
    } finally {
      setRetryingIds((current) => {
        const next = new Set(current);
        next.delete(failedReviewId);
        return next;
      });
      refreshRuns();
    }
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="border-b bg-surface-card px-7 py-4">
        <h1 className="text-lg font-semibold text-text-primary">文档对比</h1>
        <p className="mt-1 text-sm text-text-muted">
          从文件库选择已转换文件，自动找出跨文件重复与近似内容
        </p>
      </header>

      <main className="flex min-h-0 flex-1 flex-col gap-6 p-7">
        <Card className="rounded-lg border bg-surface-card shadow-none">
          <CardHeader className="flex-row items-center justify-between space-y-0 border-b">
            <CardTitle className="flex items-center gap-2">
              <GitCompareArrows className="h-4 w-4 text-accent" />
              新建对比任务
              <span className="rounded-full bg-surface px-2.5 py-1 text-xs font-medium text-text-muted">
                已选 {selectedDocs.length} 个文件
              </span>
            </CardTitle>
            <div className="flex items-center gap-2">
              <Button type="button" variant="secondary" onClick={() => setPickerOpen(true)}>
                <FolderOpen className="h-4 w-4" />
                从文件库添加
              </Button>
              <Button
                type="submit"
                form="compare-upload-form"
                disabled={selectedDocs.length < 2 || exceedsMaxFiles || loading}
              >
                <Play className="h-4 w-4" />
                {loading ? "提交中..." : "开始对比"}
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-5">
            <form id="compare-upload-form" onSubmit={handleSubmit} className="space-y-4">
              {selectedDocs.length === 0 ? (
                <div className="flex flex-col items-center justify-center rounded-lg border border-dashed bg-surface px-6 py-12 text-center">
                  <GitCompareArrows className="h-10 w-10 text-text-muted" />
                  <h2 className="mt-3 text-base font-semibold text-text-primary">新建对比任务</h2>
                  <p className="mt-1 text-sm text-text-muted">
                    从文件库选择已转换完成的文件，至少选择 2 个文件后开始对比。
                  </p>
                  <Button type="button" className="mt-4" onClick={() => setPickerOpen(true)}>
                    <FolderOpen className="h-4 w-4" />
                    从文件库选择文件
                  </Button>
                </div>
              ) : (
                <div className="flex flex-wrap gap-3">
                  {selectedDocs.map((document) => (
                    <div
                      key={document.id}
                      className="flex min-w-[240px] max-w-[320px] items-center gap-2 rounded-lg border bg-white px-3 py-2"
                    >
                      <FileText className="h-4 w-4 shrink-0 text-accent" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-text-primary">{document.filename}</p>
                        <p className="text-xs text-text-muted">{formatFileSize(document.file_size)}</p>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {document.tags.length > 0 ? (
                            document.tags.map((tag) => (
                              <span
                                key={tag.id}
                                className="rounded-full px-2 py-0.5 text-[11px] font-medium text-white"
                                style={{ backgroundColor: tag.color }}
                              >
                                {tag.name}
                              </span>
                            ))
                          ) : (
                            <span className="rounded-full bg-surface px-2 py-0.5 text-[11px] font-medium text-text-muted">
                              无标签
                            </span>
                          )}
                        </div>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => removeDocument(document.id)}
                        aria-label={`移除 ${document.filename}`}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}

              {error && <p className="text-sm text-status-err">{error}</p>}
              {exceedsMaxFiles && (
                <p className="text-sm text-status-err">
                  {`单次对比最多 ${MAX_COMPARE_FILES} 份文件，请移除多余文件`}
                </p>
              )}
            </form>
          </CardContent>
        </Card>

        <Card className="flex min-h-0 flex-1 flex-col rounded-lg border bg-surface-card shadow-none">
          <CardHeader className="flex-row items-center justify-between space-y-0 border-b">
            <CardTitle>历史对比</CardTitle>
            <span className="rounded-full bg-surface px-2.5 py-1 text-xs font-medium text-text-muted">
              {runs.length}
            </span>
          </CardHeader>
          <CardContent className="min-h-0 flex-1 overflow-auto p-0">
            <div className="grid grid-cols-[minmax(0,1fr)_90px_90px_150px_80px] border-b px-4 py-2 text-xs font-medium text-text-muted">
              <span>文件</span>
              <span>状态</span>
              <span>匹配组</span>
              <span>创建时间</span>
              <span>操作</span>
            </div>

            {historyError && (
              <div className="px-4 py-6 text-sm text-status-err">{historyError}</div>
            )}

            {!historyError && runs.length === 0 && (
              <div className="px-4 py-10 text-center text-sm text-text-muted">暂无历史对比记录</div>
            )}

            {!historyError &&
              runs.map((run) => {
                const isRunning = run.status === "running";
                const isRetrying = retryingIds.has(run.reviewId);
                return (
                  <div
                    key={run.reviewId}
                    className={cn(
                      "border-b last:border-b-0",
                      isRunning && "border-l-4 border-l-[#3B82F6] bg-[#F0F9FF]",
                    )}
                  >
                    <div
                      className={cn(
                        "grid grid-cols-[minmax(0,1fr)_90px_90px_150px_80px] items-center px-4 py-3 text-sm",
                        !isRunning && "hover:bg-surface/60",
                      )}
                    >
                      <div className="flex min-w-0 items-center gap-2 pr-3">
                        <FileText className="h-4 w-4 shrink-0 text-text-muted" />
                        <span className="truncate text-text-primary" title={run.fileNames.join("、")}>
                          {formatRunFiles(run)}
                        </span>
                      </div>
                      <div>
                        <span
                          className={cn(
                            "inline-flex h-6 items-center rounded-full px-2 text-xs font-medium",
                            statusBadgeClass(run.status),
                          )}
                        >
                          {statusLabel(run.status)}
                        </span>
                      </div>
                      <span className="text-text-primary">{formatMatchCount(run)}</span>
                      <span className="text-text-muted">{formatCreatedAt(run.createdAt)}</span>
                      <div>
                        {run.status === "completed" && (
                          <Button variant="ghost" size="sm" onClick={() => navigate(`/compare/${run.reviewId}`)}>
                            查看
                          </Button>
                        )}
                        {run.status === "failed" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-[#DC2626] hover:text-[#DC2626]"
                            disabled={isRetrying}
                            onClick={() => handleRetry(run.reviewId)}
                          >
                            {isRetrying ? "重试中…" : "重试"}
                          </Button>
                        )}
                      </div>
                    </div>
                    {/* 重试失败原因优先展示并替代历史失败原因，避免两行红字并列造成困惑 */}
                    {run.status === "failed" && run.error && !retryErrors[run.reviewId] && (
                      <p className="my-1 line-clamp-2 px-4 text-xs text-status-err" title={run.error}>
                        {run.error}
                      </p>
                    )}
                    {run.status === "failed" && retryErrors[run.reviewId] && (
                      <p
                        className="my-1 line-clamp-2 px-4 text-xs text-status-err"
                        title={retryErrors[run.reviewId]}
                      >
                        重试失败：{retryErrors[run.reviewId]}
                      </p>
                    )}
                    {isRunning && <InlineProgress run={run} />}
                  </div>
                );
              })}
          </CardContent>
        </Card>
      </main>

      <FilePickerModal
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onConfirm={handlePickerConfirm}
        mode="multi"
        initialSelected={selectedDocs.map((document) => document.id)}
      />
    </div>
  );
}
