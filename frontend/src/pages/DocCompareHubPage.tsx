import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, GitCompareArrows, Upload, X } from "lucide-react";

import { compareFiles, listCompareRuns, type CompareRunStatus } from "@/api/compare";
import { FileDropzone } from "@/components/FileDropzone";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type NormalizedRunStatus = "completed" | "running" | "pending" | "failed" | "unknown";

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
  if (normalized === "running" || normalized === "pending") return "进行中";
  return "未知";
}

function statusBadgeClass(status: string): string {
  const normalized = normalizeStatus(status);
  if (normalized === "completed") return "bg-green-50 text-[#16A34A]";
  if (normalized === "failed") return "bg-red-50 text-[#DC2626]";
  if (normalized === "running" || normalized === "pending") return "bg-blue-50 text-[#3B82F6]";
  return "bg-gray-50 text-text-muted";
}

function actionLabel(status: string): string {
  const normalized = normalizeStatus(status);
  if (normalized === "completed") return "查看结果";
  if (normalized === "failed") return "重试";
  return "查看进度";
}

function isSupportedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return name.endsWith(".docx") || name.endsWith(".pdf");
}

function formatFileSize(size: number): string {
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  return `${(size / 1024).toFixed(1)} KB`;
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
  return typeof count === "number" ? String(count) : "-";
}

export function DocCompareHubPage() {
  const navigate = useNavigate();
  const [files, setFiles] = useState<File[]>([]);
  const [runs, setRuns] = useState<CompareRunStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);

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

  function addFiles(nextFiles: File[]) {
    const supported = nextFiles.filter(isSupportedFile);
    setFiles((current) => [...current, ...supported]);
    if (supported.length !== nextFiles.length) {
      setError("仅支持 DOCX 和 PDF 文件。");
    } else {
      setError(null);
    }
  }

  function removeFile(index: number) {
    setFiles((current) => current.filter((_, itemIndex) => itemIndex !== index));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (files.length < 2 || loading) return;

    setLoading(true);
    setError(null);
    try {
      const res = await compareFiles(files);
      navigate(`/compare/${res.reviewId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
      setLoading(false);
    }
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="border-b bg-surface-card px-7 py-4">
        <h1 className="text-lg font-semibold text-text-primary">文档对比</h1>
        <p className="mt-1 text-sm text-text-muted">
          上传多份 Word 或 PDF 文件，自动找出跨文件重复与近似内容
        </p>
      </header>

      <main className="flex min-h-0 flex-1 flex-col gap-6 p-7">
        <Card className="rounded-lg border bg-surface-card shadow-none">
          <CardHeader className="flex-row items-center justify-between space-y-0 border-b">
            <CardTitle className="flex items-center gap-2">
              <Upload className="h-4 w-4 text-accent" />
              上传文档
            </CardTitle>
            <Button type="submit" form="compare-upload-form" disabled={files.length < 2 || loading}>
              <GitCompareArrows className="h-4 w-4" />
              {loading ? "提交中..." : "开始对比"}
            </Button>
          </CardHeader>
          <CardContent className="p-5">
            <form id="compare-upload-form" onSubmit={handleSubmit} className="space-y-4">
              <FileDropzone
                title="选择或拖入对比文件"
                subtitle="支持 .docx, .pdf，可多选"
                accept=".docx,.pdf"
                multiple
                onSelect={addFiles}
              />

              {files.length > 0 && (
                <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                  {files.map((file, index) => (
                    <div
                      key={`${file.name}-${file.size}-${index}`}
                      className="flex min-w-0 items-center gap-2 rounded-lg border bg-white px-3 py-2"
                    >
                      <FileText className="h-4 w-4 shrink-0 text-accent" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-text-primary">{file.name}</p>
                        <p className="text-xs text-text-muted">{formatFileSize(file.size)}</p>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => removeFile(index)}
                        aria-label={`移除 ${file.name}`}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}

              {error && <p className="text-sm text-status-err">{error}</p>}
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
            <div className="grid grid-cols-[minmax(0,1fr)_90px_70px_150px_80px] border-b px-4 py-2 text-xs font-medium text-text-muted">
              <span>文件</span>
              <span>状态</span>
              <span>匹配数</span>
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
              runs.map((run) => (
                <div
                  key={run.reviewId}
                  className="grid grid-cols-[minmax(0,1fr)_90px_70px_150px_80px] items-center border-b px-4 py-3 text-sm last:border-b-0 hover:bg-surface/60"
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
                  <Button variant="ghost" size="sm" onClick={() => navigate(`/compare/${run.reviewId}`)}>
                    {actionLabel(run.status)}
                  </Button>
                </div>
              ))}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
