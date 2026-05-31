import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CircleCheck,
  CircleX,
  File as FileIcon,
  FileText,
  Files,
  Inbox,
  Loader,
  RefreshCw,
  Search,
  Tag as TagIcon,
  Trash2,
  X,
} from "lucide-react";

import {
  batchTagDocuments,
  createTag,
  deleteDocument,
  listDocuments,
  listTags,
  reconvertDocument,
  removeDocumentTag,
  uploadSingleDocument,
} from "../api/documents";
import TagPopover from "../components/TagPopover";
import UploadBar from "../components/UploadBar";
import VirtualProgressBar from "../components/VirtualProgressBar";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import type { GovDocument, Tag } from "../types/ui";

type TypeFilter = "all" | "pdf" | "docx";

const TAG_COLOR_PALETTE = [
  "#EFF6FF:#1D4ED8",
  "#F0FDF4:#15803D",
  "#FFFBEB:#B45309",
  "#FDF2F8:#BE185D",
  "#F5F3FF:#6D28D9",
  "#ECFDF5:#047857",
];

const STATUS_LABEL: Record<GovDocument["status"], string> = {
  uploading: "上传中",
  converting: "转换中",
  ready: "已就绪",
  failed: "失败",
};

function normalizeType(fileType: string): "pdf" | "docx" {
  const lowered = fileType.toLowerCase();
  return lowered.includes("pdf") ? "pdf" : "docx";
}

function formatFileSize(size: number): string {
  return `${(size / 1024 / 1024).toFixed(2)} MB`;
}

function formatDate(value: string): string {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function parseTagColor(color: string): { backgroundColor: string; color: string } {
  const [backgroundColor, foregroundColor] = color.split(":");
  return {
    backgroundColor: backgroundColor || "#F3F4F6",
    color: foregroundColor || "#4B5563",
  };
}

function fileTypeMatches(document: GovDocument, typeFilter: TypeFilter): boolean {
  if (typeFilter === "all") return true;
  return normalizeType(document.file_type) === typeFilter;
}

interface FileProgress {
  percentage: number;
  done: boolean;
  error: string | null;
}

export default function FileManagementPage() {
  const [documents, setDocuments] = useState<GovDocument[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [tagFilter, setTagFilter] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const selectAllRef = useRef<HTMLInputElement>(null);

  /* ---- 上传队列相关状态 ---- */
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [fileProgresses, setFileProgresses] = useState<Record<string, FileProgress>>({});
  const [showDoneDialog, setShowDoneDialog] = useState(false);
  const [doneCount, setDoneCount] = useState(0);

  const refresh = useCallback(async () => {
    try {
      const [nextDocuments, nextTags] = await Promise.all([listDocuments(), listTags()]);
      setDocuments(nextDocuments);
      setTags(nextTags);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "文件列表加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const hasConvertingDocument = documents.some((document) => document.status === "converting");

  useEffect(() => {
    if (!hasConvertingDocument) return;
    const intervalId = window.setInterval(() => {
      void refresh();
    }, 5000);
    return () => window.clearInterval(intervalId);
  }, [hasConvertingDocument, refresh]);

  const filteredDocuments = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    return documents.filter((document) => {
      if (keyword && !document.filename.toLowerCase().includes(keyword)) return false;
      if (!fileTypeMatches(document, typeFilter)) return false;
      if (tagFilter.length > 0) {
        const documentTagIds = new Set(document.tags.map((tag) => tag.id));
        if (!tagFilter.every((tagId) => documentTagIds.has(tagId))) return false;
      }
      return true;
    });
  }, [documents, search, tagFilter, typeFilter]);

  const selectedFilteredCount = filteredDocuments.filter((document) => selectedIds.has(document.id)).length;
  const allFilteredSelected = filteredDocuments.length > 0 && selectedFilteredCount === filteredDocuments.length;

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = selectedFilteredCount > 0 && !allFilteredSelected;
    }
  }, [allFilteredSelected, selectedFilteredCount]);

  const stats = useMemo(() => {
    return {
      total: documents.length,
      ready: documents.filter((document) => document.status === "ready").length,
      converting: documents.filter((document) => document.status === "converting").length,
      failed: documents.filter((document) => document.status === "failed").length,
    };
  }, [documents]);

  const selectedTagObjects = tagFilter
    .map((tagId) => tags.find((tag) => tag.id === tagId))
    .filter((tag): tag is Tag => tag != null);

  /** 向待上传队列中添加文件 */
  function addPendingFiles(files: File[]): void {
    setPendingFiles((current) => [...current, ...files]);
  }

  /** 从待上传队列中移除指定索引的文件 */
  function removePendingFile(index: number): void {
    setPendingFiles((current) => current.filter((_, i) => i !== index));
  }

  /** 逐个上传队列中的所有文件 */
  async function handleUploadAll(): Promise<void> {
    if (pendingFiles.length === 0) return;
    setUploading(true);
    setError(null);

    // 初始化所有文件的进度
    const initialProgresses: Record<string, FileProgress> = {};
    for (let i = 0; i < pendingFiles.length; i++) {
      const key = `${i}_${pendingFiles[i].name}`;
      initialProgresses[key] = { percentage: 0, done: false, error: null };
    }
    setFileProgresses(initialProgresses);

    let successCount = 0;

    // 逐个上传
    for (let i = 0; i < pendingFiles.length; i++) {
      const file = pendingFiles[i];
      const key = `${i}_${file.name}`;

      try {
        await uploadSingleDocument(file, (percentage) => {
          setFileProgresses((prev) => ({
            ...prev,
            [key]: { percentage, done: false, error: null },
          }));
        });

        successCount++;
        setFileProgresses((prev) => ({
          ...prev,
          [key]: { percentage: 100, done: true, error: null },
        }));
      } catch (err) {
        setFileProgresses((prev) => ({
          ...prev,
          [key]: {
            percentage: 0,
            done: false,
            error: err instanceof Error ? err.message : "上传失败",
          },
        }));
      }
    }

    // 全部上传完成
    setUploading(false);
    setPendingFiles([]);
    setFileProgresses({});
    setDoneCount(successCount);
    setShowDoneDialog(true);
    await refresh();
  }

  function toggleSelected(id: string): void {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll(): void {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (allFilteredSelected) {
        for (const document of filteredDocuments) next.delete(document.id);
      } else {
        for (const document of filteredDocuments) next.add(document.id);
      }
      return next;
    });
  }

  function toggleTagFilter(tagId: string): void {
    setTagFilter((current) => (
      current.includes(tagId) ? current.filter((id) => id !== tagId) : [...current, tagId]
    ));
  }

  async function createFilterTag(name: string): Promise<void> {
    const color = TAG_COLOR_PALETTE[tags.length % TAG_COLOR_PALETTE.length];
    const tag = await createTag(name, color);
    await refresh();
    setTagFilter((current) => [...current, tag.id]);
  }

  async function toggleDocumentTag(document: GovDocument, tagId: string): Promise<void> {
    const hasTag = document.tags.some((tag) => tag.id === tagId);
    if (hasTag) await removeDocumentTag(document.id, tagId);
    else await batchTagDocuments([document.id], [tagId]);
    await refresh();
  }

  async function createDocumentTag(documentId: string, name: string): Promise<void> {
    const color = TAG_COLOR_PALETTE[tags.length % TAG_COLOR_PALETTE.length];
    const tag = await createTag(name, color);
    await batchTagDocuments([documentId], [tag.id]);
    await refresh();
  }

  async function handleDelete(document: GovDocument): Promise<void> {
    if (!window.confirm(`确定删除「${document.filename}」吗？`)) return;
    await deleteDocument(document.id);
    setSelectedIds((current) => {
      const next = new Set(current);
      next.delete(document.id);
      return next;
    });
    await refresh();
  }

  async function handleReconvert(documentId: string): Promise<void> {
    await reconvertDocument(documentId);
    await refresh();
  }

  return (
    <div className="flex flex-col">
      <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
        <span className="text-base font-semibold text-text-primary">文件管理</span>
      </header>
      <main className="space-y-5 p-7">
        <section>
          <h1 className="text-2xl font-semibold text-text-primary">文件管理</h1>
          <p className="mt-1 text-sm text-text-muted">上传 PDF 或 Word 文件，系统将自动转换为可检索格式</p>
        </section>

        <UploadBar
          pendingFiles={pendingFiles}
          onAddFiles={addPendingFiles}
          onRemoveFile={removePendingFile}
          onUpload={() => void handleUploadAll()}
          uploading={uploading}
          fileProgresses={fileProgresses}
        />

        <section className="flex gap-4">
          <StatsCard icon={<Files className="h-5 w-5 text-blue-600" />} label="总文件" value={stats.total} tone="blue" />
          <StatsCard icon={<CircleCheck className="h-5 w-5 text-green-600" />} label="已就绪" value={stats.ready} tone="green" />
          <StatsCard icon={<Loader className="h-5 w-5 text-orange-600" />} label="转换中" value={stats.converting} tone="orange" />
          <StatsCard icon={<CircleX className="h-5 w-5 text-red-600" />} label="失败" value={stats.failed} tone="red" />
        </section>

        <section className="flex flex-wrap items-center gap-3 rounded-card border bg-surface-card px-4 py-3 shadow-card">
          <div className="relative min-w-64 flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
            <input
              className="h-9 w-full rounded-btn border border-border bg-white pl-9 pr-3 text-sm outline-none transition-colors placeholder:text-text-muted focus:border-accent"
              placeholder="搜索文件名..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>

          <div className="h-6 w-px bg-border" />

          <div className="flex items-center gap-1 rounded-btn bg-surface p-1">
            {[
              ["all", "全部"],
              ["pdf", "PDF"],
              ["docx", "Word"],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setTypeFilter(value as TypeFilter)}
                className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
                  typeFilter === value ? "bg-text-primary text-white" : "text-text-secondary hover:bg-white"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="h-6 w-px bg-border" />

          <div className="flex flex-wrap items-center gap-2">
            {selectedTagObjects.map((tag) => (
              <span
                key={tag.id}
                className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium"
                style={parseTagColor(tag.color)}
              >
                {tag.name}
                <button type="button" onClick={() => toggleTagFilter(tag.id)} aria-label={`移除标签筛选 ${tag.name}`}>
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
            <TagPopover
              allTags={tags}
              activeTags={tagFilter}
              onToggle={toggleTagFilter}
              onCreate={(name) => void createFilterTag(name)}
            >
              <button
                type="button"
                className="inline-flex h-8 items-center gap-1.5 rounded-btn border border-border bg-white px-3 text-xs font-medium text-text-secondary hover:bg-surface"
              >
                <TagIcon className="h-3.5 w-3.5" />
                筛选标签
              </button>
            </TagPopover>
          </div>
        </section>

        {error && (
          <div className="rounded-btn border border-status-err-border bg-status-err-bg px-4 py-3 text-sm text-status-err">
            {error}
          </div>
        )}

        <section className="overflow-hidden rounded-card border bg-surface-card shadow-card">
          <table className="w-full text-sm">
            <thead className="bg-surface text-xs font-medium text-text-muted">
              <tr className="border-b">
                <th className="w-12 px-4 py-3 text-left">
                  <input
                    ref={selectAllRef}
                    type="checkbox"
                    checked={allFilteredSelected}
                    onChange={toggleSelectAll}
                    aria-label="选择全部文件"
                    className="h-4 w-4 rounded border-border text-accent"
                  />
                </th>
                <th className="px-4 py-3 text-left">文件名</th>
                <th className="px-4 py-3 text-left">类型</th>
                <th className="px-4 py-3 text-left">大小</th>
                <th className="px-4 py-3 text-left">标签</th>
                <th className="px-4 py-3 text-left">状态</th>
                <th className="px-4 py-3 text-left">上传时间</th>
                <th className="px-4 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {documents.length === 0 && !loading ? (
                <tr>
                  <td colSpan={8}>
                    <EmptyState />
                  </td>
                </tr>
              ) : filteredDocuments.length === 0 && !loading ? (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-sm text-text-muted">
                    没有匹配的文件
                  </td>
                </tr>
              ) : (
                filteredDocuments.map((document) => (
                  <FileTableRow
                    key={document.id}
                    document={document}
                    tags={tags}
                    selected={selectedIds.has(document.id)}
                    onSelect={() => toggleSelected(document.id)}
                    onToggleTag={(tagId) => void toggleDocumentTag(document, tagId)}
                    onCreateTag={(name) => void createDocumentTag(document.id, name)}
                    onDelete={() => void handleDelete(document)}
                    onReconvert={() => void handleReconvert(document.id)}
                  />
                ))
              )}
              {loading && (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-sm text-text-muted">
                    正在加载文件...
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      </main>

      {/* 上传完成弹窗 */}
      <Dialog open={showDoneDialog} onOpenChange={setShowDoneDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>文件上传完成</DialogTitle>
            <DialogDescription>
              {doneCount > 0
                ? `${doneCount} 个文件已上传完成，正在后台转换为可检索格式，稍后刷新即可查看。`
                : "文件上传未成功，请检查文件格式后重试。"}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <button
              onClick={() => setShowDoneDialog(false)}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
            >
              知道了
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function StatsCard({
  icon,
  label,
  value,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  tone: "blue" | "green" | "orange" | "red";
}) {
  const toneClass = {
    blue: "bg-blue-50",
    green: "bg-green-50",
    orange: "bg-orange-50",
    red: "bg-red-50",
  }[tone];

  return (
    <div className="flex min-w-0 flex-1 items-center gap-3 rounded-card border bg-surface-card p-4 shadow-card">
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${toneClass}`}>{icon}</div>
      <div>
        <p className="text-xs text-text-muted">{label}</p>
        <p className="mt-1 text-2xl font-semibold text-text-primary">{value}</p>
      </div>
    </div>
  );
}

function FileTableRow({
  document,
  tags,
  selected,
  onSelect,
  onToggleTag,
  onCreateTag,
  onDelete,
  onReconvert,
}: {
  document: GovDocument;
  tags: Tag[];
  selected: boolean;
  onSelect: () => void;
  onToggleTag: (tagId: string) => void;
  onCreateTag: (name: string) => void;
  onDelete: () => void;
  onReconvert: () => void;
}) {
  const normalizedType = normalizeType(document.file_type);
  const activeTagIds = document.tags.map((tag) => tag.id);

  return (
    <tr className="border-b last:border-0 hover:bg-surface/60">
      <td className="px-4 py-3">
        <input
          type="checkbox"
          checked={selected}
          onChange={onSelect}
          aria-label={`选择文件 ${document.filename}`}
          className="h-4 w-4 rounded border-border text-accent"
        />
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2.5">
          <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${normalizedType === "pdf" ? "bg-red-50" : "bg-blue-50"}`}>
            {normalizedType === "pdf" ? (
              <FileText className="h-4 w-4 text-red-600" />
            ) : (
              <FileIcon className="h-4 w-4 text-blue-600" />
            )}
          </div>
          <span className="max-w-[280px] truncate font-medium text-text-primary" title={document.filename}>
            {document.filename}
          </span>
        </div>
      </td>
      <td className="px-4 py-3">
        <TypeBadge type={normalizedType} />
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-text-secondary">{formatFileSize(document.file_size)}</td>
      <td className="px-4 py-3">
        <div className="flex max-w-[220px] flex-wrap gap-1.5">
          {document.tags.length > 0 ? (
            document.tags.map((tag) => (
              <span
                key={tag.id}
                className="rounded-full px-2 py-0.5 text-xs font-medium"
                style={parseTagColor(tag.color)}
              >
                {tag.name}
              </span>
            ))
          ) : (
            <span className="text-xs text-text-muted">无标签</span>
          )}
        </div>
      </td>
      <td className="px-4 py-3">
        <StatusCell document={document} />
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-text-secondary">{formatDate(document.created_at)}</td>
      <td className="px-4 py-3">
        <div className="flex justify-end gap-1">
          <TagPopover
            allTags={tags}
            activeTags={activeTagIds}
            onToggle={onToggleTag}
            onCreate={onCreateTag}
          >
            <IconButton label="管理标签">
              <TagIcon className="h-4 w-4" />
            </IconButton>
          </TagPopover>
          {document.status === "failed" && (
            <IconButton label="重新转换" onClick={onReconvert}>
              <RefreshCw className="h-4 w-4" />
            </IconButton>
          )}
          <IconButton label="删除文件" danger onClick={onDelete}>
            <Trash2 className="h-4 w-4" />
          </IconButton>
        </div>
      </td>
    </tr>
  );
}

function TypeBadge({ type }: { type: "pdf" | "docx" }) {
  const className = type === "pdf" ? "bg-red-50 text-red-700" : "bg-blue-50 text-blue-700";
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${className}`}>
      {type === "pdf" ? "PDF" : "DOCX"}
    </span>
  );
}

function StatusCell({ document }: { document: GovDocument }) {
  const statusClass = {
    uploading: "bg-blue-50 text-blue-700",
    converting: "bg-blue-50 text-blue-700",
    ready: "bg-green-50 text-green-700",
    failed: "bg-red-50 text-red-700",
  }[document.status];

  return (
    <div className="w-32 space-y-1.5">
      <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${statusClass}`}>
        {document.status === "ready" && <CircleCheck className="h-3 w-3" />}
        {document.status === "failed" && <CircleX className="h-3 w-3" />}
        {(document.status === "converting" || document.status === "uploading") && <Loader className="h-3 w-3 animate-spin" />}
        {STATUS_LABEL[document.status]}
      </span>
      <VirtualProgressBar createdAt={document.created_at} status={document.status} />
    </div>
  );
}

function IconButton({
  children,
  label,
  danger = false,
  onClick,
}: {
  children: React.ReactNode;
  label: string;
  danger?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onClick={onClick}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-btn transition-colors ${
        danger ? "text-text-muted hover:bg-status-err-bg hover:text-status-err" : "text-text-muted hover:bg-surface hover:text-text-primary"
      }`}
    >
      {children}
    </button>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-16 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-surface">
        <Inbox className="h-7 w-7 text-text-muted" />
      </div>
      <h2 className="mt-4 text-base font-semibold text-text-primary">暂无文件</h2>
      <p className="mt-1 text-sm text-text-muted">上传 PDF 或 Word 文件后，系统会自动转换并展示在这里。</p>
    </div>
  );
}
