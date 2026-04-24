import { Download, FileText, GitCompareArrows, Upload } from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type DragEvent,
  type FormEvent,
} from "react";

import {
  buildCompareDownloadUrl,
  compareDocxFiles,
  type CompareCategoryId,
  type CompareDocument,
  type CompareMatch,
  type CompareResponse,
  type CompareSummary,
} from "../api/compare";
import {
  Button,
  Card,
  CardHeader,
  EmptyState,
  InlineNotice,
  MetricCard,
  PageHero,
} from "../components/Ui";

const CATEGORY_PRIORITY: Record<CompareCategoryId, number> = {
  paragraph: 0,
  sentence: 1,
  segment: 2,
};

const DEFAULT_VISIBLE_CATEGORIES: Record<CompareCategoryId, boolean> = {
  paragraph: true,
  sentence: true,
  segment: true,
};

function categoryCount(summary: CompareSummary, category: CompareCategoryId): number {
  if (category === "paragraph") return summary.commonParagraphCount;
  if (category === "sentence") return summary.commonSentenceCount;
  return summary.commonSegmentCount;
}

function isDocxFile(file: File): boolean {
  return file.name.toLowerCase().endsWith(".docx");
}

function fileSizeLabel(file: File): string {
  if (file.size < 1024 * 1024) return `${(file.size / 1024).toFixed(1)} KB`;
  return `${(file.size / 1024 / 1024).toFixed(2)} MB`;
}

export function DocComparePage() {
  const [firstFile, setFirstFile] = useState<File | null>(null);
  const [secondFile, setSecondFile] = useState<File | null>(null);
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);
  const [visibleCategories, setVisibleCategories] = useState(DEFAULT_VISIBLE_CATEGORIES);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const visibleMatches = useMemo(() => {
    if (!result) return [];
    return result.matches.filter((match) => visibleCategories[match.category]);
  }, [result, visibleCategories]);

  const visibleMatchLookup = useMemo(() => {
    return visibleMatches.reduce<Record<string, CompareMatch>>((lookup, match) => {
      lookup[match.id] = match;
      return lookup;
    }, {});
  }, [visibleMatches]);

  useEffect(() => {
    if (selectedMatchId && !visibleMatchLookup[selectedMatchId]) {
      setSelectedMatchId(visibleMatches[0]?.id ?? null);
    }
  }, [selectedMatchId, visibleMatchLookup, visibleMatches]);

  async function handleCompare(event: FormEvent) {
    event.preventDefault();
    if (!firstFile || !secondFile) {
      setErrorMessage("请先上传两份 DOCX 文件。");
      return;
    }
    if (!isDocxFile(firstFile) || !isDocxFile(secondFile)) {
      setErrorMessage("仅支持 .docx 文件。");
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      const payload = await compareDocxFiles(firstFile, secondFile);
      setResult(payload);
      setSelectedMatchId(payload.matches[0]?.id ?? null);
      setVisibleCategories(DEFAULT_VISIBLE_CATEGORIES);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "文档对比失败。");
    } finally {
      setLoading(false);
    }
  }

  function toggleCategory(category: CompareCategoryId) {
    setVisibleCategories((current) => ({
      ...current,
      [category]: !current[category],
    }));
  }

  return (
    <>
      <PageHero
        eyebrow="文档对比"
        title="DOCX 文档对比"
        description="对两份 Word 文档生成并排高亮视图和可下载高亮稿。"
        actions={
          result ? (
            <div className="compare-download-actions">
              <a
                className="button button--secondary button--md"
                href={buildCompareDownloadUrl(result.downloads.first)}
              >
                <Download size={16} />
                <span>下载文档 A</span>
              </a>
              <a
                className="button button--secondary button--md"
                href={buildCompareDownloadUrl(result.downloads.second)}
              >
                <Download size={16} />
                <span>下载文档 B</span>
              </a>
            </div>
          ) : null
        }
      />

      <form className="compare-upload-form" onSubmit={handleCompare}>
        <Card>
          <CardHeader
            title="上传文档"
            description="支持拖拽或选择两份 .docx 文件。"
            actions={
              <Button
                type="submit"
                icon={GitCompareArrows}
                busy={loading}
                disabled={loading}
              >
                开始对比
              </Button>
            }
          />
          <div className="compare-upload-grid">
            <CompareFileDropzone
              label="文档 A"
              file={firstFile}
              onFile={setFirstFile}
            />
            <CompareFileDropzone
              label="文档 B"
              file={secondFile}
              onFile={setSecondFile}
            />
          </div>
          {errorMessage ? (
            <div className="compare-notice">
              <InlineNotice tone="warning" message={errorMessage} />
            </div>
          ) : null}
        </Card>
      </form>

      {result ? (
        <div className="compare-result-stack">
          <div className="metric-grid">
            <MetricCard label="匹配总数" value={result.summary.matchCount} tone="blue" />
            <MetricCard
              label="相同段落"
              value={result.summary.commonParagraphCount}
              tone="amber"
            />
            <MetricCard
              label="相同句子"
              value={result.summary.commonSentenceCount}
              tone="green"
            />
            <MetricCard
              label="公共片段"
              value={result.summary.commonSegmentCount}
              tone="slate"
            />
          </div>

          <div className="compare-category-row">
            {result.categories.map((category) => (
              <button
                key={category.id}
                className={`compare-category-toggle${
                  visibleCategories[category.id] ? " is-active" : ""
                }`}
                type="button"
                onClick={() => toggleCategory(category.id)}
                style={
                  {
                    "--compare-match-color": category.color,
                  } as CSSProperties
                }
              >
                <span>{category.label}</span>
                <strong>{categoryCount(result.summary, category.id)}</strong>
              </button>
            ))}
          </div>

          <main className="compare-workspace">
            <section className="compare-document-grid">
              <CompareDocumentColumn
                title={result.summary.firstFileName}
                documentData={result.documents.first}
                visibleMatchLookup={visibleMatchLookup}
                selectedMatchId={selectedMatchId}
                onSelectMatch={setSelectedMatchId}
              />
              <CompareDocumentColumn
                title={result.summary.secondFileName}
                documentData={result.documents.second}
                visibleMatchLookup={visibleMatchLookup}
                selectedMatchId={selectedMatchId}
                onSelectMatch={setSelectedMatchId}
              />
            </section>

            <Card className="compare-match-panel">
              <CardHeader
                title="匹配清单"
                description={`${visibleMatches.length} 项当前可见匹配`}
              />
              {visibleMatches.length ? (
                <div className="compare-match-list">
                  {visibleMatches.map((match) => (
                    <button
                      key={match.id}
                      className={`compare-match-card${
                        selectedMatchId === match.id ? " is-active" : ""
                      }`}
                      type="button"
                      onClick={() => setSelectedMatchId(match.id)}
                      style={
                        {
                          "--compare-match-color": match.color,
                        } as CSSProperties
                      }
                    >
                      <span className="compare-match-card__label">{match.label}</span>
                      <strong>{match.text}</strong>
                      <span className="compare-match-card__meta">
                        A 侧 {match.firstCount} 处 · B 侧 {match.secondCount} 处 ·{" "}
                        {match.length} 字符
                      </span>
                    </button>
                  ))}
                </div>
              ) : (
                <EmptyState title="暂无可见匹配" description="当前类别筛选下没有匹配项。" />
              )}
            </Card>
          </main>
        </div>
      ) : (
        <div className="compare-empty">
          <EmptyState title="等待文档" description="上传两份 DOCX 后将在此显示对比结果。" />
        </div>
      )}
    </>
  );
}

function CompareFileDropzone(props: {
  label: string;
  file: File | null;
  onFile: (file: File | null) => void;
}) {
  const [dragging, setDragging] = useState(false);

  function acceptDroppedFile(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) props.onFile(file);
  }

  return (
    <label
      className={`compare-dropzone${dragging ? " is-dragging" : ""}`}
      onDragEnter={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={() => setDragging(false)}
      onDrop={acceptDroppedFile}
    >
      <input
        className="sr-only"
        type="file"
        accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        onChange={(event) => props.onFile(event.target.files?.[0] ?? null)}
      />
      <span className="compare-dropzone__icon">
        {props.file ? <FileText size={18} /> : <Upload size={18} />}
      </span>
      <span className="compare-dropzone__copy">
        <strong>{props.label}</strong>
        <span>{props.file ? props.file.name : "选择或拖入 DOCX"}</span>
        {props.file ? <small>{fileSizeLabel(props.file)}</small> : null}
      </span>
    </label>
  );
}

function CompareDocumentColumn(props: {
  title: string;
  documentData: CompareDocument;
  visibleMatchLookup: Record<string, CompareMatch>;
  selectedMatchId: string | null;
  onSelectMatch: (matchId: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!props.selectedMatchId || !containerRef.current) return;
    const target = containerRef.current.querySelector(
      `[data-match-ids~="${props.selectedMatchId}"]`,
    );
    target?.scrollIntoView({
      block: "center",
      behavior: "smooth",
    });
  }, [props.selectedMatchId]);

  return (
    <Card className="compare-document-card">
      <CardHeader
        title={props.title}
        description={`${props.documentData.blockCount} 段`}
      />
      <div className="compare-document-scroll" ref={containerRef}>
        {props.documentData.blocks.map((block) => (
          <p className="compare-paragraph" key={block.id}>
            <span className="compare-block-index">
              {String(block.index).padStart(2, "0")}
            </span>
            <span className="compare-paragraph-text">
              {block.segments.map((segment, index) => {
                const visibleMatchIds = segment.matchIds.filter(
                  (matchId) => props.visibleMatchLookup[matchId],
                );
                const primaryVisibleMatchId = [...visibleMatchIds].sort(
                  (left, right) =>
                    CATEGORY_PRIORITY[props.visibleMatchLookup[left].category] -
                    CATEGORY_PRIORITY[props.visibleMatchLookup[right].category],
                )[0];
                const isActive =
                  props.selectedMatchId != null &&
                  visibleMatchIds.includes(props.selectedMatchId);

                if (!primaryVisibleMatchId) {
                  return <span key={`${block.id}-${index}`}>{segment.text}</span>;
                }

                const primaryMatch = props.visibleMatchLookup[primaryVisibleMatchId];
                return (
                  <button
                    key={`${block.id}-${index}`}
                    className={`compare-highlight${isActive ? " is-active" : ""}`}
                    type="button"
                    data-match-ids={visibleMatchIds.join(" ")}
                    onClick={() => props.onSelectMatch(primaryVisibleMatchId)}
                    title={primaryMatch.label}
                    style={
                      {
                        "--compare-match-color": primaryMatch.color,
                      } as CSSProperties
                    }
                  >
                    {segment.text}
                  </button>
                );
              })}
            </span>
          </p>
        ))}
      </div>
    </Card>
  );
}
