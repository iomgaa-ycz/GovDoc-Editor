import { Download, FileText, GitCompareArrows, RotateCcw, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type CSSProperties, type FormEvent } from "react";

import {
  buildCompareDownloadUrl,
  compareFiles,
  type CompareCategoryId,
  type CompareDocument,
  type CompareMatch,
  type CompareResponse,
  type CompareSummary,
} from "@/api/compare";
import { EmptyState } from "@/components/EmptyState";
import { FileDropzone } from "@/components/FileDropzone";
import { MetricCard } from "@/components/MetricCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

const CATEGORY_PRIORITY: Record<CompareCategoryId, number> = {
  paragraph: 0,
  sentence: 1,
  segment: 2,
};

function categoryCount(summary: CompareSummary, cat: CompareCategoryId): number {
  if (cat === "paragraph") return summary.commonParagraphCount;
  if (cat === "sentence") return summary.commonSentenceCount;
  return summary.commonSegmentCount;
}

function formatFileIndices(indices: number[]): string {
  return indices.map((index) => `文件 ${index + 1}`).join("、");
}

function isSupportedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return name.endsWith(".docx") || name.endsWith(".pdf");
}

export function DocComparePage() {
  const [files, setFiles] = useState<File[]>([]);
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);
  const [visibleCats, setVisibleCats] = useState<Record<CompareCategoryId, boolean>>({
    paragraph: true,
    sentence: true,
    segment: true,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const visibleMatches = useMemo(
    () => result?.matches.filter((match) => visibleCats[match.category]) ?? [],
    [result, visibleCats],
  );
  const visibleLookup = useMemo(
    () => Object.fromEntries(visibleMatches.map((match) => [match.id, match])),
    [visibleMatches],
  );

  useEffect(() => {
    if (selectedMatchId && !visibleLookup[selectedMatchId]) {
      setSelectedMatchId(visibleMatches[0]?.id ?? null);
    }
  }, [selectedMatchId, visibleLookup, visibleMatches]);

  function addFiles(nextFiles: File[]) {
    const supported = nextFiles.filter(isSupportedFile);
    setFiles((current) => [...current, ...supported]);
    if (nextFiles.length !== supported.length) {
      setError("仅支持 DOCX 和 PDF 文件。");
    } else {
      setError(null);
    }
  }

  function removeFile(index: number) {
    setFiles((current) => current.filter((_, itemIndex) => itemIndex !== index));
  }

  async function handleCompare(event: FormEvent) {
    event.preventDefault();
    if (files.length < 2) return;
    setLoading(true);
    setError(null);
    try {
      const response = await compareFiles(files);
      setResult(response);
      setSelectedMatchId(response.matches[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "对比失败");
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setResult(null);
    setSelectedMatchId(null);
    setError(null);
  }

  if (!result) {
    return (
      <div className="flex flex-col">
        <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
          <span className="text-base font-semibold text-text-primary">文档对比</span>
        </header>
        <div className="space-y-6 p-7">
          <div>
            <h2 className="text-lg font-semibold">文档对比</h2>
            <p className="text-sm text-text-muted">
              上传多份 Word 或 PDF 文件，自动找出跨文件重复内容
            </p>
          </div>
          <Card>
            <CardHeader>
              <CardTitle>上传文档</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCompare} className="space-y-4">
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
                        className="flex min-w-0 items-center gap-2 rounded-card border bg-white px-3 py-2"
                      >
                        <FileText className="h-4 w-4 shrink-0 text-accent" />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-text-primary">
                            文件 {index + 1} · {file.name}
                          </p>
                          <p className="text-xs text-text-muted">
                            {(file.size / 1024).toFixed(1)} KB
                          </p>
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
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
                <div className="flex justify-end">
                  <Button type="submit" disabled={files.length < 2 || loading}>
                    <GitCompareArrows className="h-4 w-4" />
                    {loading ? "文档转换与对比中..." : "开始对比"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
          <EmptyState
            icon={<GitCompareArrows className="h-7 w-7 text-accent" />}
            title="上传至少两份文档开始对比"
            description="支持 DOCX 和 PDF，结果会按文件展示重复段落、句子和公共片段"
          />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between gap-3 border-b bg-surface-card px-7 py-3.5">
        <div>
          <span className="text-base font-semibold text-text-primary">文档对比</span>
          <p className="text-xs text-text-muted">共 {result.summary.fileCount} 份文件</p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {result.documents.files.slice(0, 3).map((doc) => {
            const path = result.downloads.files[String(doc.fileIndex)];
            const filename = result.artifacts.downloadNames[String(doc.fileIndex)];
            if (!path) return null;
            return (
              <a key={doc.fileIndex} href={buildCompareDownloadUrl(path)}>
                <Button variant="secondary" size="sm" title={filename}>
                  <Download className="h-4 w-4" />
                  文件 {doc.fileIndex + 1} 高亮副本
                </Button>
              </a>
            );
          })}
          <Button variant="ghost" size="sm" onClick={reset}>
            <RotateCcw className="h-4 w-4" />
            重新上传
          </Button>
        </div>
      </header>

      <div className="flex-1 space-y-4 overflow-auto p-5">
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
          <MetricCard label="匹配总数" value={result.summary.matchCount} tone="blue" />
          <MetricCard label="相同段落" value={result.summary.commonParagraphCount} tone="amber" />
          <MetricCard label="相同句子" value={result.summary.commonSentenceCount} tone="green" />
          <MetricCard label="公共片段" value={result.summary.commonSegmentCount} tone="slate" />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {result.categories.map((cat) => (
            <button
              key={cat.id}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                visibleCats[cat.id]
                  ? "border-transparent text-white"
                  : "border-gray-300 bg-white text-text-secondary",
              )}
              style={visibleCats[cat.id] ? { backgroundColor: cat.color } : undefined}
              onClick={() => setVisibleCats((current) => ({ ...current, [cat.id]: !current[cat.id] }))}
            >
              {cat.label} ({categoryCount(result.summary, cat.id)})
            </button>
          ))}
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
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

          <Card>
            <CardHeader>
              <CardTitle>匹配清单</CardTitle>
              <p className="text-xs text-text-muted">{visibleMatches.length} 项</p>
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[560px]">
                {visibleMatches.map((match) => (
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
                ))}
              </ScrollArea>
            </CardContent>
          </Card>
        </div>
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
    const target = Array.from(ref.current.querySelectorAll<HTMLElement>("[data-match-ids]")).find(
      (node) => node.dataset.matchIds?.split(" ").includes(selectedId),
    );
    target?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [selectedId]);

  return (
    <Card>
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
