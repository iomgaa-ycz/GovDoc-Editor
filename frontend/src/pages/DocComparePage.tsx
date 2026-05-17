import { Download, FileText, GitCompareArrows, Upload } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type CSSProperties, type DragEvent, type FormEvent } from "react";

import { buildCompareDownloadUrl, compareDocxFiles, type CompareCategoryId, type CompareDocument, type CompareMatch, type CompareResponse, type CompareSummary } from "@/api/compare";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MetricCard } from "@/components/MetricCard";
import { EmptyState } from "@/components/EmptyState";

const CATEGORY_PRIORITY: Record<CompareCategoryId, number> = { paragraph: 0, sentence: 1, segment: 2 };

function categoryCount(summary: CompareSummary, cat: CompareCategoryId): number {
  if (cat === "paragraph") return summary.commonParagraphCount;
  if (cat === "sentence") return summary.commonSentenceCount;
  return summary.commonSegmentCount;
}

export function DocComparePage() {
  const [firstFile, setFirstFile] = useState<File | null>(null);
  const [secondFile, setSecondFile] = useState<File | null>(null);
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);
  const [visibleCats, setVisibleCats] = useState<Record<CompareCategoryId, boolean>>({ paragraph: true, sentence: true, segment: true });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const visibleMatches = useMemo(() => result?.matches.filter((m) => visibleCats[m.category]) ?? [], [result, visibleCats]);
  const visibleLookup = useMemo(() => Object.fromEntries(visibleMatches.map((m) => [m.id, m])), [visibleMatches]);

  useEffect(() => {
    if (selectedMatchId && !visibleLookup[selectedMatchId]) setSelectedMatchId(visibleMatches[0]?.id ?? null);
  }, [selectedMatchId, visibleLookup, visibleMatches]);

  async function handleCompare(e: FormEvent) {
    e.preventDefault();
    if (!firstFile || !secondFile) return;
    setLoading(true);
    setError(null);
    try {
      const r = await compareDocxFiles(firstFile, secondFile);
      setResult(r);
      setSelectedMatchId(r.matches[0]?.id ?? null);
    } catch (err) { setError(err instanceof Error ? err.message : "对比失败"); }
    finally { setLoading(false); }
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
            <p className="text-sm text-text-muted">上传两份 Word 文档，自动对比并标记相似内容</p>
          </div>
          <Card>
            <CardHeader><CardTitle>上传文档</CardTitle></CardHeader>
            <CardContent>
              <form onSubmit={handleCompare} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <CmpDropzone label="文档 A" file={firstFile} onFile={setFirstFile} />
                  <CmpDropzone label="文档 B" file={secondFile} onFile={setSecondFile} />
                </div>
                {error && <p className="text-sm text-status-err">{error}</p>}
                <div className="flex justify-end">
                  <Button type="submit" disabled={!firstFile || !secondFile || loading}>
                    <GitCompareArrows className="h-4 w-4" /> {loading ? "对比中..." : "开始对比"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
          <EmptyState icon={<GitCompareArrows className="h-7 w-7 text-accent" />} title="上传两份文档开始对比" description="上传两份 DOCX 文件后将在此显示对比结果" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen">
      <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
        <span className="text-base font-semibold text-text-primary">文档对比</span>
        <div className="flex items-center gap-2">
          <a href={buildCompareDownloadUrl(result.downloads.first)}><Button variant="secondary" size="sm"><Download className="h-4 w-4" /> 下载文档 A</Button></a>
          <a href={buildCompareDownloadUrl(result.downloads.second)}><Button variant="secondary" size="sm"><Download className="h-4 w-4" /> 下载文档 B</Button></a>
        </div>
      </header>
      <div className="flex-1 overflow-auto space-y-4 p-5">
        <div className="grid grid-cols-4 gap-3">
          <MetricCard label="匹配总数" value={result.summary.matchCount} tone="blue" />
          <MetricCard label="相同段落" value={result.summary.commonParagraphCount} tone="amber" />
          <MetricCard label="相同句子" value={result.summary.commonSentenceCount} tone="green" />
          <MetricCard label="公共片段" value={result.summary.commonSegmentCount} tone="slate" />
        </div>
        <div className="flex items-center gap-2">
          {result.categories.map((cat) => (
            <button key={cat.id} className={cn("rounded-full px-3 py-1 text-xs font-medium border transition-colors", visibleCats[cat.id] ? "border-transparent text-white" : "border-gray-300 bg-white text-text-secondary")} style={visibleCats[cat.id] ? { backgroundColor: cat.color } : undefined} onClick={() => setVisibleCats((c) => ({ ...c, [cat.id]: !c[cat.id] }))}>
              {cat.label} ({categoryCount(result.summary, cat.id)})
            </button>
          ))}
        </div>
        <div className="grid grid-cols-[1fr_1fr_280px] gap-4">
          <DocCol title={result.summary.firstFileName} doc={result.documents.first} lookup={visibleLookup} selectedId={selectedMatchId} onSelect={setSelectedMatchId} />
          <DocCol title={result.summary.secondFileName} doc={result.documents.second} lookup={visibleLookup} selectedId={selectedMatchId} onSelect={setSelectedMatchId} />
          <Card>
            <CardHeader><CardTitle>匹配清单</CardTitle><p className="text-xs text-text-muted">{visibleMatches.length} 项</p></CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[500px]">
                {visibleMatches.map((m) => (
                  <button key={m.id} className={cn("w-full text-left px-4 py-2.5 border-b hover:bg-surface transition-colors", selectedMatchId === m.id && "bg-accent-light")} onClick={() => setSelectedMatchId(m.id)}>
                    <span className="text-xs font-medium" style={{ color: m.color }}>{m.label}</span>
                    <p className="text-sm text-text-primary line-clamp-2 mt-0.5">{m.text}</p>
                    <p className="text-xs text-text-muted mt-0.5">A 侧 {m.firstCount} 处 · B 侧 {m.secondCount} 处</p>
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

function CmpDropzone({ label, file, onFile }: { label: string; file: File | null; onFile: (f: File | null) => void }) {
  const [dragging, setDragging] = useState(false);
  function handleDrop(e: DragEvent<HTMLLabelElement>) { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files?.[0]; if (f) onFile(f); }
  return (
    <label className={cn("flex flex-col items-center gap-2 rounded-card border-2 border-dashed p-8 cursor-pointer transition-colors", dragging ? "border-accent bg-accent-light/50" : "hover:border-accent")} onDragEnter={(e) => { e.preventDefault(); setDragging(true); }} onDragOver={(e) => e.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={handleDrop}>
      <input className="sr-only" type="file" accept=".docx" onChange={(e) => onFile(e.target.files?.[0] ?? null)} />
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-light">
        {file ? <FileText className="h-5 w-5 text-accent" /> : <Upload className="h-5 w-5 text-accent" />}
      </div>
      <strong className="text-sm">{label}</strong>
      <span className="text-xs text-text-muted">{file ? file.name : "选择或拖入 DOCX"}</span>
    </label>
  );
}

function DocCol({ title, doc, lookup, selectedId, onSelect }: {
  title: string; doc: CompareDocument; lookup: Record<string, CompareMatch>; selectedId: string | null; onSelect: (id: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!selectedId || !ref.current) return;
    ref.current.querySelector(`[data-match-ids~="${selectedId}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [selectedId]);

  return (
    <Card>
      <CardHeader><CardTitle className="text-sm">{title}</CardTitle><p className="text-xs text-text-muted">{doc.blockCount} 段</p></CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-[500px] px-4">
          <div ref={ref}>
            {doc.blocks.map((block) => (
              <p key={block.id} className="flex gap-2 py-1 text-sm leading-relaxed">
                <span className="shrink-0 text-xs text-text-muted w-6 text-right">{String(block.index).padStart(2, "0")}</span>
                <span>
                  {block.segments.map((seg, i) => {
                    const visible = seg.matchIds.filter((id) => lookup[id]);
                    const primary = [...visible].sort((a, b) => CATEGORY_PRIORITY[lookup[a].category] - CATEGORY_PRIORITY[lookup[b].category])[0];
                    if (!primary) return <span key={`${block.id}-${i}`}>{seg.text}</span>;
                    const m = lookup[primary];
                    const isActive = selectedId != null && visible.includes(selectedId);
                    return (
                      <button key={`${block.id}-${i}`} className={cn("rounded px-0.5 transition-colors", isActive && "ring-2 ring-offset-1")} style={{ backgroundColor: `${m.color}33`, "--tw-ring-color": m.color } as CSSProperties} data-match-ids={visible.join(" ")} onClick={() => onSelect(primary)}>
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
