import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Circle,
  CircleCheck,
  Download,
  FileText,
  GitCompareArrows,
  Loader2,
  RotateCcw,
} from "lucide-react";

import {
  buildCompareDownloadUrl,
  getCompareResult,
  getCompareStatus,
  type CompareCategoryId,
  type CompareDocument,
  type CompareMatch,
  type CompareResponse,
  type CompareRunStatus,
  type CompareSummary,
} from "@/api/compare";
import { MetricCard } from "@/components/MetricCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

const CATEGORY_PRIORITY: Record<CompareCategoryId, number> = {
  paragraph: 0,
  sentence: 1,
  similar: 2,
};

type FilterId = "all" | CompareCategoryId;
type NormalizedRunStatus = "completed" | "running" | "pending" | "failed" | "unknown";

const FILTERS: Array<{ id: FilterId; label: string; category?: CompareCategoryId }> = [
  { id: "all", label: "全部" },
  { id: "paragraph", label: "相同段落", category: "paragraph" },
  { id: "sentence", label: "相同句子", category: "sentence" },
  { id: "similar", label: "近似段落", category: "similar" },
];

const PROGRESS_STEPS = ["上传文件", "文档转换", "段落匹配", "句子匹配", "近似检测", "生成结果"];

function normalizeStatus(status: string | undefined): NormalizedRunStatus {
  if (status === "completed" || status === "running" || status === "pending" || status === "failed") {
    return status;
  }
  return "unknown";
}

function statusLabel(status: string | undefined): string {
  const normalized = normalizeStatus(status);
  if (normalized === "completed") return "已完成";
  if (normalized === "failed") return "失败";
  if (normalized === "running" || normalized === "pending") return "进行中";
  return "读取中";
}

function statusBadgeClass(status: string | undefined): string {
  const normalized = normalizeStatus(status);
  if (normalized === "completed") return "bg-green-50 text-[#16A34A]";
  if (normalized === "failed") return "bg-red-50 text-[#DC2626]";
  if (normalized === "running" || normalized === "pending") return "bg-blue-50 text-[#3B82F6]";
  return "bg-gray-50 text-text-muted";
}

function categoryCount(summary: CompareSummary, filter: FilterId, totalMatches: number): number {
  if (filter === "all") return totalMatches;
  if (filter === "paragraph") return summary.commonParagraphCount;
  if (filter === "sentence") return summary.commonSentenceCount;
  return summary.commonSimilarCount;
}

function formatFileIndices(indices: number[]): string {
  return indices.map((index) => `文件 ${index + 1}`).join("、");
}

function totalParagraphCount(result: CompareResponse): number {
  return result.summary.files.reduce((total, file) => total + file.paragraphCount, 0);
}

function progressIndex(status: CompareRunStatus | null): number {
  if (!status) return 0;
  if (status.status === "completed") return PROGRESS_STEPS.length;
  if (status.status === "pending") return 0;
  if (status.progress?.phase === "converting") return 1;
  if (status.progress?.phase === "matching") {
    if (status.progress.step === "paragraph") return 2;
    if (status.progress.step === "sentence") return 3;
    if (status.progress.step === "similar") return 4;
  }
  if (status.status === "running") return 5;
  return 0;
}

function progressDetail(status: CompareRunStatus | null): string {
  if (!status?.progress) return "正在读取任务状态";
  if (status.progress.phase === "converting") {
    const current = status.progress.current ?? 0;
    const total = status.progress.total ?? status.fileCount;
    return `正在转换文档 (${current}/${total})`;
  }
  if (status.progress.phase === "matching") {
    if (status.progress.step === "paragraph") return "正在匹配重复段落";
    if (status.progress.step === "sentence") return "正在匹配重复句子";
    if (status.progress.step === "similar") return "正在检测近似内容";
  }
  return "正在生成对比结果";
}

export function DocCompareDetailPage() {
  const { reviewId } = useParams<{ reviewId: string }>();
  const [status, setStatus] = useState<CompareRunStatus | null>(null);
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!reviewId) {
      setError("缺少对比任务 ID。");
      return;
    }

    const currentReviewId = reviewId;
    let active = true;
    let timerId: number | undefined;
    setStatus(null);
    setResult(null);
    setError(null);

    async function poll() {
      try {
        const nextStatus = await getCompareStatus(currentReviewId);
        if (!active) return;

        setStatus(nextStatus);
        setError(null);

        if (nextStatus.status === "completed") {
          const nextResult = await getCompareResult(currentReviewId);
          if (active) setResult(nextResult);
          return;
        }

        if (nextStatus.status === "failed") {
          setError(nextStatus.error || "对比失败");
          return;
        }

        timerId = window.setTimeout(poll, 2000);
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "状态查询失败");
        }
      }
    }

    poll();

    return () => {
      active = false;
      if (timerId !== undefined) window.clearTimeout(timerId);
    };
  }, [reviewId]);

  const failed = status?.status === "failed" || (!result && error != null);

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
        <Link to="/compare" className="flex items-center gap-1 text-sm font-medium text-text-primary hover:text-accent">
          <ArrowLeft className="h-4 w-4" />
          对比列表
        </Link>
        <span
          className={cn(
            "inline-flex h-7 items-center rounded-full px-2.5 text-xs font-medium",
            statusBadgeClass(status?.status),
          )}
        >
          {statusLabel(status?.status)}
        </span>
      </header>

      <main className="min-h-0 flex-1 overflow-auto p-7">
        {result ? (
          <CompareResultView result={result} />
        ) : failed ? (
          <FailedView error={status?.error ?? error ?? "对比失败"} />
        ) : (
          <ProgressView status={status} />
        )}
      </main>
    </div>
  );
}

function ProgressView({ status }: { status: CompareRunStatus | null }) {
  const currentIndex = progressIndex(status);
  const fileNames = status?.fileNames ?? [];

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(280px,360px)_minmax(0,1fr)]">
      <Card className="rounded-lg border bg-surface-card shadow-none">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-accent" />
            对比文件
          </CardTitle>
          <p className="text-sm text-text-muted">{status ? `共 ${status.fileCount} 份文件` : "正在读取文件信息"}</p>
        </CardHeader>
        <CardContent className="space-y-2">
          {fileNames.length === 0 ? (
            <div className="rounded-lg border bg-white px-3 py-2 text-sm text-text-muted">文件列表加载中</div>
          ) : (
            fileNames.map((name, index) => (
              <div key={`${name}-${index}`} className="flex min-w-0 items-center gap-2 rounded-lg border bg-white px-3 py-2">
                <FileText className="h-4 w-4 shrink-0 text-text-muted" />
                <span className="truncate text-sm text-text-primary">
                  文件 {index + 1} · {name}
                </span>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card className="rounded-lg border bg-surface-card shadow-none">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitCompareArrows className="h-4 w-4 text-accent" />
            对比进度
          </CardTitle>
          <p className="text-sm text-text-muted">{progressDetail(status)}</p>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {PROGRESS_STEPS.map((step, index) => {
              const complete = currentIndex > index;
              const current = currentIndex === index;
              return (
                <div key={step} className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white">
                    {complete ? (
                      <CircleCheck className="h-5 w-5 text-[#16A34A]" />
                    ) : current ? (
                      <Loader2 className="h-5 w-5 animate-spin text-[#3B82F6]" />
                    ) : (
                      <Circle className="h-5 w-5 text-gray-300" />
                    )}
                  </div>
                  <span
                    className={cn(
                      "text-sm font-medium",
                      complete && "text-text-primary",
                      current && "text-[#3B82F6]",
                      !complete && !current && "text-text-muted",
                    )}
                  >
                    {step}
                  </span>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function FailedView({ error }: { error: string }) {
  return (
    <Card className="mx-auto max-w-xl rounded-lg border bg-surface-card shadow-none">
      <CardHeader>
        <CardTitle className="text-status-err">对比失败</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="rounded-lg bg-status-err-bg p-3 text-sm text-status-err">{error}</p>
        <Button asChild>
          <Link to="/compare">
            <ArrowLeft className="h-4 w-4" />
            返回列表
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}

function CompareResultView({ result }: { result: CompareResponse }) {
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(result.matches[0]?.id ?? null);
  const [activeFilter, setActiveFilter] = useState<FilterId>("all");

  const categoryColor = useMemo(
    () => Object.fromEntries(result.categories.map((cat) => [cat.id, cat.color])) as Record<CompareCategoryId, string>,
    [result.categories],
  );

  const visibleMatches = useMemo(
    () => (activeFilter === "all" ? result.matches : result.matches.filter((match) => match.category === activeFilter)),
    [activeFilter, result.matches],
  );
  const visibleLookup = useMemo(
    () => Object.fromEntries(visibleMatches.map((match) => [match.id, match])),
    [visibleMatches],
  );

  useEffect(() => {
    if (selectedMatchId && !visibleLookup[selectedMatchId]) {
      setSelectedMatchId(visibleMatches[0]?.id ?? null);
    } else if (!selectedMatchId && visibleMatches.length > 0) {
      setSelectedMatchId(visibleMatches[0].id);
    }
  }, [selectedMatchId, visibleLookup, visibleMatches]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">文档对比结果</h1>
          <p className="text-sm text-text-muted">共 {result.summary.fileCount} 份文件</p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {result.documents.files.map((doc) => {
            const path = result.downloads.files[String(doc.fileIndex)];
            const filename = result.artifacts.downloadNames[String(doc.fileIndex)];
            if (!path) return null;
            return (
              <a key={doc.fileIndex} href={buildCompareDownloadUrl(path)} download={filename}>
                <Button variant="secondary" size="sm" title={filename}>
                  <Download className="h-4 w-4" />
                  文件 {doc.fileIndex + 1} 高亮副本
                </Button>
              </a>
            );
          })}
          <Button asChild variant="ghost" size="sm">
            <Link to="/compare">
              <RotateCcw className="h-4 w-4" />
              重新对比
            </Link>
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <MetricCard label="总段落数" value={totalParagraphCount(result)} tone="blue" />
        <MetricCard label="相同段落" value={result.summary.commonParagraphCount} tone="amber" />
        <MetricCard label="相同句子" value={result.summary.commonSentenceCount} tone="green" />
        <MetricCard label="近似段落" value={result.summary.commonSimilarCount} tone="slate" />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((filter) => {
          const active = activeFilter === filter.id;
          const color = filter.category ? categoryColor[filter.category] : "#3B82F6";
          return (
            <button
              key={filter.id}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                active ? "border-transparent text-white" : "border-gray-300 bg-white text-text-secondary",
              )}
              style={active ? { backgroundColor: color } : undefined}
              onClick={() => setActiveFilter(filter.id)}
            >
              {filter.label} ({categoryCount(result.summary, filter.id, result.matches.length)})
            </button>
          );
        })}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="overflow-x-auto pb-2">
          <div
            className="grid gap-4"
            style={{
              gridAutoFlow: "column",
              gridAutoColumns: "minmax(360px, 420px)",
            }}
          >
            {result.documents.files.map((doc) => (
              <DocCol
                key={doc.fileIndex}
                doc={doc}
                lookup={visibleLookup}
                selectedId={selectedMatchId}
                onSelect={setSelectedMatchId}
              />
            ))}
          </div>
        </div>

        <Card className="rounded-lg border bg-surface-card shadow-none">
          <CardHeader>
            <CardTitle>匹配清单</CardTitle>
            <p className="text-xs text-text-muted">{visibleMatches.length} 项</p>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="h-[560px]">
              {visibleMatches.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-text-muted">当前分类暂无匹配</div>
              ) : (
                visibleMatches.map((match) => (
                  <button
                    key={match.id}
                    className={cn(
                      "w-full border-b px-4 py-2.5 text-left transition-colors hover:bg-surface",
                      selectedMatchId === match.id && "bg-accent-light",
                    )}
                    onClick={() => setSelectedMatchId(match.id)}
                  >
                    <span className="text-xs font-medium" style={{ color: match.color }}>
                      {match.label}
                    </span>
                    <p className="mt-0.5 line-clamp-2 text-sm text-text-primary">{match.text}</p>
                    <p className="mt-0.5 text-xs text-text-muted">
                      {formatFileIndices(match.fileIndices)} · {match.occurrenceCount} 处
                    </p>
                  </button>
                ))
              )}
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function DocCol({
  doc,
  lookup,
  selectedId,
  onSelect,
}: {
  doc: CompareDocument;
  lookup: Record<string, CompareMatch>;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!selectedId || !ref.current) return;
    const target = Array.from(ref.current.querySelectorAll<HTMLElement>("[data-match-ids]")).find((node) =>
      node.dataset.matchIds?.split(" ").includes(selectedId),
    );
    target?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [selectedId]);

  return (
    <Card className="rounded-lg border bg-surface-card shadow-none">
      <CardHeader>
        <CardTitle className="text-sm">
          文件 {doc.fileIndex + 1} · {doc.name}
        </CardTitle>
        <p className="text-xs text-text-muted">
          {doc.suffix.toUpperCase()} · {doc.blockCount} 段
        </p>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-[560px] px-4">
          <div ref={ref}>
            {doc.blocks.map((block) => (
              <p key={block.id} className="flex gap-2 py-1 text-sm leading-relaxed">
                <span className="w-6 shrink-0 text-right text-xs text-text-muted">
                  {String(block.index).padStart(2, "0")}
                </span>
                <span>
                  {block.segments.map((seg, index) => {
                    const visible = seg.matchIds.filter((id) => {
                      const match = lookup[id];
                      return match && match.fileIndices.includes(doc.fileIndex);
                    });
                    const primary = [...visible].sort(
                      (a, b) => CATEGORY_PRIORITY[lookup[a].category] - CATEGORY_PRIORITY[lookup[b].category],
                    )[0];
                    if (!primary) return <span key={`${block.id}-${index}`}>{seg.text}</span>;

                    const match = lookup[primary];
                    const isActive = selectedId != null && visible.includes(selectedId);
                    return (
                      <button
                        key={`${block.id}-${index}`}
                        className={cn("rounded px-0.5 transition-colors", isActive && "ring-2 ring-offset-1")}
                        style={
                          {
                            backgroundColor: `${match.color}33`,
                            "--tw-ring-color": match.color,
                          } as CSSProperties
                        }
                        data-match-ids={visible.join(" ")}
                        onClick={() => onSelect(primary)}
                      >
                        {seg.text}
                      </button>
                    );
                  })}
                </span>
              </p>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
