import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Download, Loader2, RotateCcw } from "lucide-react";

import {
  buildCompareDownloadUrl,
  getCompareContext,
  getCompareSummary,
  type CompareCategoryId,
  type CompareContextResponse,
  type CompareSummaryResponse,
  type MatchPagination,
  type MatchSummaryItem,
} from "@/api/compare";
import { MetricCard } from "@/components/MetricCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

const CATEGORY_FILTERS: Array<{ id: CompareCategoryId; label: string }> = [
  { id: "paragraph", label: "相同段落" },
  { id: "sentence", label: "相同句子" },
  { id: "similar", label: "近似段落组" },
];

const LENGTH_FILTER_MAX = 500;

function formatFileIndices(indices: number[]): string {
  return indices.map((i) => `文件 ${i + 1}`).join("、");
}

function totalParagraphCount(summary: CompareSummaryResponse): number {
  return summary.summary.files.reduce((total, f) => total + f.paragraphCount, 0);
}

export function DocCompareResultPage() {
  const { reviewId } = useParams<{ reviewId: string }>();
  const [summary, setSummary] = useState<CompareSummaryResponse | null>(null);
  const [activeCategory, setActiveCategory] = useState<CompareCategoryId>("paragraph");
  const [matches, setMatches] = useState<MatchSummaryItem[]>([]);
  const [pagination, setPagination] = useState<MatchPagination | null>(null);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);
  const [context, setContext] = useState<CompareContextResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [contextLoading, setContextLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [minLength, setMinLength] = useState(0);

  useEffect(() => {
    if (!reviewId) return;
    setLoading(true);
    setMatches([]);
    getCompareSummary(reviewId, activeCategory, 1, 100, minLength)
      .then((data) => {
        setSummary(data);
        setMatches(data.matches);
        setPagination(data.matchPagination);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [reviewId, activeCategory, minLength]);

  function loadMore() {
    if (!reviewId || !pagination || pagination.page >= pagination.totalPages || loadingMore) return;
    setLoadingMore(true);
    getCompareSummary(reviewId, activeCategory, pagination.page + 1, pagination.pageSize, minLength)
      .then((data) => {
        setMatches((prev) => [...prev, ...data.matches]);
        setPagination(data.matchPagination);
      })
      .catch(() => {})
      .finally(() => setLoadingMore(false));
  }

  function handleCategoryChange(category: CompareCategoryId) {
    setActiveCategory(category);
    setSelectedMatchId(null);
    setContext(null);
  }

  function handleMinLengthChange(value: number) {
    setMinLength(value);
    setSelectedMatchId(null);
    setContext(null);
  }

  useEffect(() => {
    if (!reviewId || !selectedMatchId) {
      setContext(null);
      return;
    }
    setContextLoading(true);
    getCompareContext(reviewId, selectedMatchId)
      .then((data) => {
        setContext(data);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "加载上下文失败"))
      .finally(() => setContextLoading(false));
  }, [reviewId, selectedMatchId]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-accent" />
      </div>
    );
  }

  if (error && !summary) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4">
        <p className="text-sm text-status-err">{error}</p>
        <Button asChild>
          <Link to="/compare">
            <ArrowLeft className="h-4 w-4" />
            返回列表
          </Link>
        </Button>
      </div>
    );
  }

  if (!summary) return null;

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
        <Link
          to="/compare"
          className="flex items-center gap-1 text-sm font-medium text-text-primary hover:text-accent"
        >
          <ArrowLeft className="h-4 w-4" />
          对比列表
        </Link>
        <span className="inline-flex h-7 items-center rounded-full bg-green-50 px-2.5 text-xs font-medium text-[#16A34A]">
          已完成
        </span>
      </header>

      <main className="min-h-0 flex-1 overflow-hidden">
        {selectedMatchId && context ? (
          <ContextView
            summary={summary}
            matches={matches}
            pagination={pagination}
            context={context}
            selectedMatchId={selectedMatchId}
            activeCategory={activeCategory}
            minLength={minLength}
            onSelect={setSelectedMatchId}
            onCategoryChange={handleCategoryChange}
            onMinLengthChange={handleMinLengthChange}
            onBack={() => setSelectedMatchId(null)}
            onLoadMore={loadMore}
            loading={contextLoading}
            loadingMore={loadingMore}
          />
        ) : (
          <SummaryView
            summary={summary}
            matches={matches}
            pagination={pagination}
            activeCategory={activeCategory}
            minLength={minLength}
            onCategoryChange={handleCategoryChange}
            onMinLengthChange={handleMinLengthChange}
            onSelectMatch={setSelectedMatchId}
            onLoadMore={loadMore}
            loadingMore={loadingMore}
          />
        )}
      </main>
    </div>
  );
}

function SummaryView({
  summary,
  matches,
  pagination,
  activeCategory,
  minLength,
  onCategoryChange,
  onMinLengthChange,
  onSelectMatch,
  onLoadMore,
  loadingMore,
}: {
  summary: CompareSummaryResponse;
  matches: MatchSummaryItem[];
  pagination: MatchPagination | null;
  activeCategory: CompareCategoryId;
  minLength: number;
  onCategoryChange: (cat: CompareCategoryId) => void;
  onMinLengthChange: (value: number) => void;
  onSelectMatch: (id: string) => void;
  onLoadMore: () => void;
  loadingMore: boolean;
}) {
  const counts = pagination?.categoryCounts ?? {};
  const totalInCategory = pagination?.totalInCategory ?? matches.length;
  const hasMore = pagination ? pagination.page < pagination.totalPages : false;

  return (
    <div className="flex h-full flex-col gap-5 overflow-auto p-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">文档对比结果</h1>
          <p className="text-sm text-text-muted">
            共 {summary.summary.fileCount} 份文件
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {summary.summary.files.map((file) => {
            const path = summary.downloads.files[String(file.fileIndex)];
            const filename = summary.artifacts.downloadNames[String(file.fileIndex)];
            if (!path) return null;
            return (
              <a key={file.fileIndex} href={buildCompareDownloadUrl(path)} download={filename}>
                <Button variant="secondary" size="sm" title={filename}>
                  <Download className="h-4 w-4" />
                  文件 {file.fileIndex + 1} 高亮副本
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
        <MetricCard label="总段落数" value={totalParagraphCount(summary)} tone="blue" />
        <MetricCard label="相同段落" value={summary.summary.commonParagraphCount} tone="amber" />
        <MetricCard label="相同句子" value={summary.summary.commonSentenceCount} tone="green" />
        <MetricCard label="近似段落组" value={summary.summary.commonSimilarCount} tone="slate" />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {CATEGORY_FILTERS.map((filter) => {
            const active = activeCategory === filter.id;
            const count = counts[filter.id] ?? 0;
            return (
              <button
                key={filter.id}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                  active
                    ? "border-accent bg-accent text-white"
                    : "border-gray-300 bg-white text-text-secondary hover:bg-surface",
                )}
                onClick={() => onCategoryChange(filter.id)}
              >
                {filter.label} ({count.toLocaleString()})
              </button>
            );
          })}
        </div>
        <LengthThresholdControl value={minLength} onChange={onMinLengthChange} />
      </div>

      <Card className="flex min-h-0 flex-1 flex-col rounded-lg border bg-surface-card shadow-none">
        <CardHeader className="flex-row items-center justify-between space-y-0 border-b">
          <div>
            <CardTitle>匹配清单</CardTitle>
            <p className="mt-1 text-xs text-text-muted">
              {totalInCategory.toLocaleString()} 组 · 已加载 {matches.length} 组 · 点击查看各文件对应段落
            </p>
          </div>
        </CardHeader>
        <CardContent className="min-h-0 flex-1 overflow-auto p-0">
          <div className="grid grid-cols-[100px_minmax(0,1fr)_140px_80px] border-b bg-surface px-4 py-2 text-xs font-medium text-text-muted">
            <span>类型</span>
            <span>匹配内容</span>
            <span>涉及文件</span>
            <span>出现位置</span>
          </div>
          {matches.map((match) => (
            <button
              key={match.id}
              className="grid w-full grid-cols-[100px_minmax(0,1fr)_140px_80px] items-center border-b px-4 py-3 text-left text-sm transition-colors last:border-b-0 hover:bg-accent-light"
              onClick={() => onSelectMatch(match.id)}
            >
              <div>
                <span
                  className="inline-flex rounded px-1.5 py-0.5 text-xs font-medium"
                  style={{ backgroundColor: `${match.color}1A`, color: match.color }}
                >
                  {match.label}
                </span>
              </div>
              <span className="truncate pr-4 text-text-primary">{match.preview}</span>
              <span className="text-xs text-text-muted">{formatFileIndices(match.fileIndices)}</span>
              <span className="text-xs text-text-muted">{match.occurrenceCount} 处</span>
            </button>
          ))}
          {hasMore && (
            <div className="flex justify-center border-t py-3">
              <Button variant="ghost" size="sm" onClick={onLoadMore} disabled={loadingMore}>
                {loadingMore ? (
                  <><Loader2 className="h-4 w-4 animate-spin" /> 加载中...</>
                ) : (
                  `加载更多（还有 ${(totalInCategory - matches.length).toLocaleString()} 条）`
                )}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ContextView({
  summary,
  matches,
  pagination,
  context,
  selectedMatchId,
  activeCategory,
  minLength,
  onSelect,
  onCategoryChange,
  onMinLengthChange,
  onBack,
  onLoadMore,
  loading,
  loadingMore,
}: {
  summary: CompareSummaryResponse;
  matches: MatchSummaryItem[];
  pagination: MatchPagination | null;
  context: CompareContextResponse;
  selectedMatchId: string;
  activeCategory: CompareCategoryId;
  minLength: number;
  onSelect: (id: string) => void;
  onCategoryChange: (cat: CompareCategoryId) => void;
  onMinLengthChange: (value: number) => void;
  onBack: () => void;
  onLoadMore: () => void;
  loading: boolean;
  loadingMore: boolean;
}) {
  const counts = pagination?.categoryCounts ?? {};
  const hasMore = pagination ? pagination.page < pagination.totalPages : false;

  return (
    <div className="flex h-full">
      <div className="flex w-[300px] shrink-0 flex-col border-r bg-surface-card">
        <div className="space-y-3 border-b p-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary">匹配清单</h3>
            <span className="text-xs text-text-muted">
              {(pagination?.totalInCategory ?? matches.length).toLocaleString()} 组
            </span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {CATEGORY_FILTERS.map((f) => (
              <button
                key={f.id}
                className={cn(
                  "rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors",
                  activeCategory === f.id
                    ? "bg-accent text-white"
                    : "bg-surface text-text-muted hover:bg-gray-200",
                )}
                onClick={() => onCategoryChange(f.id)}
              >
                {f.label} ({(counts[f.id] ?? 0).toLocaleString()})
              </button>
            ))}
          </div>
          <LengthThresholdControl value={minLength} onChange={onMinLengthChange} compact />
          <Button variant="ghost" size="sm" className="w-full justify-start" onClick={onBack}>
            <ArrowLeft className="h-3.5 w-3.5" />
            返回匹配表格
          </Button>
        </div>
        <ScrollArea className="flex-1">
          {matches.map((match) => (
            <button
              key={match.id}
              className={cn(
                "w-full border-b px-4 py-2.5 text-left transition-colors hover:bg-surface",
                selectedMatchId === match.id && "bg-accent-light",
              )}
              onClick={() => onSelect(match.id)}
            >
              <span className="text-[11px] font-medium" style={{ color: match.color }}>
                {match.label}
              </span>
              <p className="mt-0.5 line-clamp-2 text-xs text-text-primary">{match.preview}</p>
              <p className="mt-0.5 text-[11px] text-text-muted">
                {formatFileIndices(match.fileIndices)} · {match.occurrenceCount} 处
              </p>
            </button>
          ))}
          {hasMore && (
            <div className="flex justify-center py-3">
              <Button variant="ghost" size="sm" onClick={onLoadMore} disabled={loadingMore}>
                {loadingMore ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "加载更多"}
              </Button>
            </div>
          )}
        </ScrollArea>
      </div>

      {/* 右侧文档上下文 */}
      <div className="flex min-w-0 flex-1 flex-col gap-4 overflow-auto p-5">
        <div className="flex items-center gap-2">
          <span
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: context.match.color }}
          />
          <h2 className="text-sm font-semibold text-text-primary">
            {context.match.label} · 涉及 {context.fileContexts.length} 个文件
          </h2>
          {loading && <Loader2 className="h-4 w-4 animate-spin text-accent" />}
        </div>

        <div className="flex min-h-0 flex-1 gap-3">
          {context.fileContexts.map((fc) => (
            <FileContextCol
              key={fc.fileIndex}
              fc={fc}
              match={context.match}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function LengthThresholdControl({
  value,
  onChange,
  compact = false,
}: {
  value: number;
  onChange: (value: number) => void;
  compact?: boolean;
}) {
  return (
    <label className={cn("flex items-center gap-3", compact ? "w-full" : "min-w-[280px]")}>
      <span className="shrink-0 text-xs font-medium text-text-muted">最小长度</span>
      <input
        type="range"
        min={0}
        max={LENGTH_FILTER_MAX}
        step={1}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-2 flex-1 accent-accent"
        aria-label="最小匹配长度"
      />
      <span className="w-16 shrink-0 text-right text-xs tabular-nums text-text-primary">
        ≥ {value}
      </span>
    </label>
  );
}

function FileContextCol({
  fc,
  match,
}: {
  fc: {
    fileIndex: number;
    name: string;
    totalBlocks: number;
    matchBlockIndex: number;
    blocks: Array<{
      id: string;
      index: number;
      text: string;
      segments: Array<{ text: string; matchIds: string[]; categories: CompareCategoryId[]; primaryMatchId: string | null }>;
    }>;
  };
  match: MatchSummaryItem;
}) {
  const targetRef = useRef<HTMLDivElement>(null);
  const perFileCount = match.perFileCounts?.[String(fc.fileIndex)] ?? 0;
  const matchColor = match.color;

  useEffect(() => {
    targetRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [fc.matchBlockIndex]);

  return (
    <Card className="flex min-w-[280px] flex-1 flex-col rounded-lg border bg-surface-card shadow-none">
      <CardHeader className="border-b py-3">
        <CardTitle className="text-xs">
          文件 {fc.fileIndex + 1} · {fc.name}
        </CardTitle>
        <p className="text-[11px] text-text-muted">
          第 {fc.matchBlockIndex + 1} 段 / 共 {fc.totalBlocks.toLocaleString()} 段
        </p>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-auto p-0">
        <ScrollArea className="h-full px-3 py-2">
          {fc.blocks.map((block) => {
            const isTarget = block.index === fc.matchBlockIndex;
            return (
              <div
                key={block.id}
                ref={isTarget ? targetRef : undefined}
                className={cn(
                  "flex gap-2 rounded px-2 py-1.5 text-sm leading-relaxed",
                  isTarget && "border-2 bg-amber-50",
                )}
                style={isTarget ? { borderColor: matchColor } : undefined}
              >
                <span className="w-7 shrink-0 text-right text-xs text-text-muted">
                  {String(block.index + 1).padStart(2, "0")}
                </span>
                <span
                  className={cn(
                    "flex-1 space-y-1",
                    isTarget ? "font-medium text-amber-900" : "text-text-primary",
                  )}
                >
                  <span>{block.text || block.segments?.map((s) => s.text).join("") || ""}</span>
                  {isTarget && perFileCount > 1 && (
                    <span className="block text-[11px] font-normal text-text-muted">
                      本文件共 {perFileCount} 处相似位置
                    </span>
                  )}
                </span>
              </div>
            );
          })}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
