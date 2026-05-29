import {
  ArrowLeft,
  Check,
  FileSpreadsheet,
  Folder,
  FolderPlus,
  Loader2,
  Pencil,
  Plus,
  Search,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import * as api from "@/api/v3";
import { parseCheckpointPayload } from "@/adapters/backendToUi";
import { StatusBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useWorkbench } from "@/context/V3WorkbenchContext";
import { cn } from "@/lib/utils";
import type {
  CheckpointImportPreview,
  CheckpointImportResult,
  CheckpointItem,
  CheckpointLibraryDetail,
  GovCheckpointPayload,
} from "@/types/ui";
import { UNCATEGORIZED_ID, countUncategorized, isUncategorized } from "./audit-library-utils";

const SEVERITY_VARIANT: Record<string, "err" | "warn" | "default"> = {
  critical: "err",
  major: "warn",
  minor: "default",
};
const SEVERITY_LABEL: Record<string, string> = {
  critical: "严重",
  major: "重要",
  minor: "一般",
};

type ParsedCheckpoint = {
  item: CheckpointItem;
  payload: GovCheckpointPayload;
};

type VisibleRow = {
  key: string;
  checkpointFinalId: string;
  item: CheckpointItem | null;
  payload: GovCheckpointPayload | null;
  deleted: boolean;
};

function toggleValue(values: string[], value: string): string[] {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];
}

function parseRows(checkpoints: CheckpointItem[]): ParsedCheckpoint[] {
  return checkpoints
    .map((item) => ({ item, payload: parseCheckpointPayload(item.payload_json) }))
    .filter((item): item is ParsedCheckpoint => item.payload != null);
}

function FileSelectBox({
  title,
  subtitle,
  accept,
  onSelect,
}: {
  title: string;
  subtitle: string;
  accept: string;
  onSelect: (file: File | null) => void;
}) {
  return (
    <label className="flex cursor-pointer flex-col items-center justify-center rounded-card border border-dashed bg-surface px-4 py-8 text-center transition-colors hover:border-accent hover:bg-accent-light">
      <Upload className="mb-2 h-5 w-5 text-text-muted" />
      <span className="text-sm font-medium text-text-primary">{title}</span>
      <span className="mt-1 text-xs text-text-muted">{subtitle}</span>
      <input
        type="file"
        accept={accept}
        className="sr-only"
        onChange={(event) => onSelect(event.target.files?.[0] ?? null)}
      />
    </label>
  );
}

export function AuditLibraryPage() {
  const {
    checkpoints,
    checkpointLibraries,
    extractStatus,
    extractError,
    extractCurrentPhase,
    uploadRuleAndExtract,
    updateCheckpoint,
    deleteCheckpoint,
    importCheckpointFile,
    createCheckpointLibrary,
    addCheckpointsToLibraries,
    removeCheckpointsFromLibrary,
    deleteCheckpointLibrary,
    updateCheckpointLibrary,
    refreshAll,
  } = useWorkbench();

  const [mode, setMode] = useState<"list" | "extract" | "import">("list");
  const [selectedLibraryId, setSelectedLibraryId] = useState<string>("all");
  const [libraryDetail, setLibraryDetail] = useState<CheckpointLibraryDetail | null>(null);
  const [loadingLibrary, setLoadingLibrary] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importPreviewing, setImportPreviewing] = useState(false);
  const [importPreview, setImportPreview] = useState<CheckpointImportPreview | null>(null);
  const [importResult, setImportResult] = useState<CheckpointImportResult | null>(null);
  const [importLibraryIds, setImportLibraryIds] = useState<string[]>([]);

  const [editingCp, setEditingCp] = useState<CheckpointItem | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDesc, setEditDesc] = useState("");

  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deletingTitle, setDeletingTitle] = useState("");
  const [deletingLibraries, setDeletingLibraries] = useState<{ id: string; name: string }[]>([]);

  const [newLibraryOpen, setNewLibraryOpen] = useState(false);
  const [newLibraryName, setNewLibraryName] = useState("");
  const [newLibraryDesc, setNewLibraryDesc] = useState("");
  const [creatingLibrary, setCreatingLibrary] = useState(false);
  const [deletingLibraryId, setDeletingLibraryId] = useState<string | null>(null);
  const [editingLibraryId, setEditingLibraryId] = useState<string | null>(null);
  const [editLibraryName, setEditLibraryName] = useState("");
  const [editLibraryDesc, setEditLibraryDesc] = useState("");
  const [savingLibrary, setSavingLibrary] = useState(false);

  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [targetLibraryIds, setTargetLibraryIds] = useState<string[]>([]);
  const [inlineNewLibraryName, setInlineNewLibraryName] = useState("");

  const parsed = useMemo(() => parseRows(checkpoints), [checkpoints]);
  const uncategorizedCount = useMemo(() => countUncategorized(checkpoints), [checkpoints]);
  const activeLibrary = checkpointLibraries.find((item) => item.id === selectedLibraryId);
  const isVirtualLibrary = selectedLibraryId === "all" || selectedLibraryId === UNCATEGORIZED_ID;

  async function loadSelectedLibrary(id = selectedLibraryId) {
    if (id === "all" || id === UNCATEGORIZED_ID) {
      setLibraryDetail(null);
      return;
    }
    setLoadingLibrary(true);
    try {
      setLibraryDetail(await api.getCheckpointLibrary(id));
    } finally {
      setLoadingLibrary(false);
    }
  }

  useEffect(() => {
    setSelectedIds([]);
    void loadSelectedLibrary(selectedLibraryId);
  }, [selectedLibraryId]);

  // 提取完成（draft_ready）后定位到「未分类」，用户点「返回列表」即见新提取的点。
  // 仅在用户正停在提取页时触发，避免页面重挂载（extractStatus 不复位）时被反复弹回未分类。
  useEffect(() => {
    if (extractStatus === "draft_ready" && mode === "extract") {
      setSelectedLibraryId(UNCATEGORIZED_ID);
    }
  }, [extractStatus, mode]);

  const rows = useMemo<VisibleRow[]>(() => {
    if (selectedLibraryId === "all") {
      return parsed.map(({ item, payload }) => ({
        key: item.id,
        checkpointFinalId: item.id,
        item,
        payload,
        deleted: false,
      }));
    }
    if (selectedLibraryId === UNCATEGORIZED_ID) {
      return parsed
        .filter(({ item }) => isUncategorized(item))
        .map(({ item, payload }) => ({
          key: item.id,
          checkpointFinalId: item.id,
          item,
          payload,
          deleted: false,
        }));
    }
    return (libraryDetail?.checkpoints ?? [])
      .filter((member) => !member.deleted && member.checkpoint != null)
      .map((member) => {
        const payload = parseCheckpointPayload(member.checkpoint!.payload_json);
        return {
          key: member.id,
          checkpointFinalId: member.checkpoint_final_id,
          item: member.checkpoint,
          payload,
          deleted: false,
        };
      });
  }, [libraryDetail, parsed, selectedLibraryId]);

  const categories = [...new Set(parsed.map((item) => item.payload.category))];
  const filtered = rows.filter((row) => {
    if (categoryFilter !== "all" && row.payload?.category !== categoryFilter) return false;
    if (!search) return true;
    const needle = search.trim().toLowerCase();
    if (!needle) return true;
    return (
      row.payload?.title.toLowerCase().includes(needle) ||
      row.payload?.description.toLowerCase().includes(needle) ||
      row.checkpointFinalId.toLowerCase().includes(needle)
    );
  });
  const selectableIds = filtered.filter((row) => !row.deleted).map((row) => row.checkpointFinalId);
  const allFilteredSelected =
    selectableIds.length > 0 && selectableIds.every((id) => selectedIds.includes(id));

  function toggleAllFiltered() {
    setSelectedIds((current) => {
      if (allFilteredSelected) {
        return current.filter((id) => !selectableIds.includes(id));
      }
      return [...new Set([...current, ...selectableIds])];
    });
  }

  async function handleExtract() {
    if (!uploadTitle || !uploadFile) return;
    setUploading(true);
    try {
      await uploadRuleAndExtract(uploadTitle, uploadFile);
    } finally {
      setUploading(false);
    }
  }

  async function handlePreviewImport() {
    if (!importFile) return;
    setImportPreviewing(true);
    setImportResult(null);
    try {
      setImportPreview(await api.previewCheckpointImport(importFile, importLibraryIds));
    } catch {
      setImportPreview(null);
    } finally {
      setImportPreviewing(false);
    }
  }

  async function handleImport() {
    if (!importFile) return;
    setImporting(true);
    try {
      const result = await importCheckpointFile(importFile, importLibraryIds);
      setImportResult(result);
      setImportPreview(null);
      setImportFile(null);
      await loadSelectedLibrary();
    } catch {
      setImportResult(null);
    } finally {
      setImporting(false);
    }
  }

  function openEdit(item: CheckpointItem) {
    const payload = parseCheckpointPayload(item.payload_json);
    if (!payload) return;
    setEditingCp(item);
    setEditTitle(payload.title);
    setEditDesc(payload.description);
  }

  async function saveEdit() {
    if (!editingCp) return;
    const payload = parseCheckpointPayload(editingCp.payload_json);
    if (!payload) return;
    await updateCheckpoint(editingCp.id, { ...payload, title: editTitle, description: editDesc });
    setEditingCp(null);
    await loadSelectedLibrary();
  }

  async function openDelete(item: CheckpointItem) {
    const payload = parseCheckpointPayload(item.payload_json);
    setDeletingId(item.id);
    setDeletingTitle(payload?.title ?? "");
    setDeletingLibraries([]);
    try {
      setDeletingLibraries(await api.getCheckpointLibraries(item.id));
    } catch {
      /* 查询失败不影响删除流程 */
    }
  }

  async function confirmDelete() {
    if (!deletingId) return;
    const result = await deleteCheckpoint(deletingId);
    setDeletingId(null);
    if (result?.action === "archived") {
      window.alert(
        `该审核点被 ${result.referenced_by} 个历史审查任务引用，已自动归档（不再出现在审核点库中，历史审查结果仍可查看）。`,
      );
    }
    await loadSelectedLibrary();
  }

  async function confirmCreateLibrary() {
    const name = newLibraryName.trim();
    if (!name) return;
    setCreatingLibrary(true);
    try {
      const library = await createCheckpointLibrary(name, newLibraryDesc);
      setSelectedLibraryId(library.id);
      setNewLibraryName("");
      setNewLibraryDesc("");
      setNewLibraryOpen(false);
    } finally {
      setCreatingLibrary(false);
    }
  }

  async function confirmAddSelectedToLibraries() {
    let libraryIds = [...targetLibraryIds];
    const inlineName = inlineNewLibraryName.trim();
    try {
      if (inlineName) {
        const library = await createCheckpointLibrary(inlineName);
        libraryIds = [...libraryIds, library.id];
        setInlineNewLibraryName("");
      }
      if (libraryIds.length === 0 || selectedIds.length === 0) return;
      await addCheckpointsToLibraries(libraryIds, selectedIds);
      setAddDialogOpen(false);
      setTargetLibraryIds([]);
      setSelectedIds([]);
      await refreshAll();
      await loadSelectedLibrary();
    } catch {
      // API 失败时保留弹窗状态，用户可重试
    }
  }

  async function removeSelectedFromCurrentLibrary() {
    if (selectedLibraryId === "all" || selectedLibraryId === UNCATEGORIZED_ID || selectedIds.length === 0) return;
    await removeCheckpointsFromLibrary(selectedLibraryId, selectedIds);
    setSelectedIds([]);
    await refreshAll();
    await loadSelectedLibrary();
  }

  async function confirmDeleteLibrary() {
    if (!deletingLibraryId) return;
    await deleteCheckpointLibrary(deletingLibraryId);
    setDeletingLibraryId(null);
    setSelectedLibraryId("all");
    await refreshAll();
  }

  function openEditLibrary() {
    const library = checkpointLibraries.find((item) => item.id === selectedLibraryId);
    if (!library) return;
    setEditingLibraryId(library.id);
    setEditLibraryName(library.name);
    setEditLibraryDesc(library.description ?? "");
  }

  async function saveEditLibrary() {
    if (!editingLibraryId) return;
    const name = editLibraryName.trim();
    if (!name) return;
    setSavingLibrary(true);
    try {
      await updateCheckpointLibrary(editingLibraryId, name, editLibraryDesc);
      setEditingLibraryId(null);
    } finally {
      setSavingLibrary(false);
    }
  }

  if (mode === "extract") {
    return (
      <div className="flex flex-col">
        <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
          <div className="flex items-center gap-2">
            <span className="text-base font-semibold text-text-primary">审核点库</span>
            <span className="text-text-muted">/</span>
            <span className="text-sm text-text-muted">AI 智能提取</span>
          </div>
          <Button variant="secondary" size="sm" onClick={() => setMode("list")}>
            <ArrowLeft className="h-4 w-4" /> 返回列表
          </Button>
        </header>
        <div className="space-y-6 p-7">
          <div>
            <h2 className="text-lg font-semibold">AI 智能提取审查要点</h2>
            <p className="text-sm text-text-muted">上传法规或制度文件，AI 将自动提取并入库审查要点</p>
          </div>
          <div className="grid grid-cols-3 gap-6">
            <Card className="col-span-2">
              <CardHeader><CardTitle>上传规范文件</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">法规标题</label>
                  <Input placeholder="例如：政府采购法实施条例" value={uploadTitle} onChange={(event) => setUploadTitle(event.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">法规原文</label>
                  {uploadFile ? (
                    <div className="flex items-center justify-between rounded-card border p-3">
                      <span className="text-sm">{uploadFile.name}</span>
                      <button className="text-sm text-text-muted hover:text-text-primary" onClick={() => setUploadFile(null)}>移除</button>
                    </div>
                  ) : (
                    <FileSelectBox title="选择或拖入法规文件" subtitle="支持 .md, .pdf, .docx" accept=".md,.pdf,.docx" onSelect={(file) => setUploadFile(file)} />
                  )}
                </div>
                {extractStatus === "failed" && (
                  <div className="rounded-btn bg-status-err-bg p-3 text-sm text-status-err">{extractError ?? "处理失败"}</div>
                )}
                {extractStatus === "draft_ready" && (
                  <div className="rounded-btn bg-status-ok-bg p-3 text-sm text-status-ok">提取完成，审核点已入库。</div>
                )}
                <Button disabled={!uploadTitle || !uploadFile || uploading || extractStatus === "running"} onClick={handleExtract}>
                  <Sparkles className="h-4 w-4" /> 开始抽取
                </Button>
              </CardContent>
            </Card>
            {(extractStatus === "pending" || extractStatus === "running") && (
              <ExtractProgressCard currentPhase={extractCurrentPhase} />
            )}
          </div>
        </div>
      </div>
    );
  }

  if (mode === "import") {
    return (
      <div className="flex flex-col">
        <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
          <div className="flex items-center gap-2">
            <span className="text-base font-semibold text-text-primary">审核点库</span>
            <span className="text-text-muted">/</span>
            <span className="text-sm text-text-muted">导入审查点表格</span>
          </div>
          <Button variant="secondary" size="sm" onClick={() => { setMode("list"); setImportResult(null); setImportPreview(null); }}>
            <ArrowLeft className="h-4 w-4" /> 返回列表
          </Button>
        </header>
        <div className="grid grid-cols-[minmax(0,1fr)_360px] gap-6 p-7">
          <Card>
            <CardHeader>
              <CardTitle>批量导入</CardTitle>
              <p className="text-sm text-text-muted">解析表格后可复用同标题审核点，并批量关联到目标审核点库。</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">审查点文件</label>
                {importFile ? (
                  <div className="flex items-center justify-between rounded-card border p-3">
                    <span className="text-sm">{importFile.name}</span>
                    <button className="text-sm text-text-muted hover:text-text-primary" onClick={() => { setImportFile(null); setImportPreview(null); }}>移除</button>
                  </div>
                ) : (
                  <FileSelectBox title="选择审查点表格" subtitle="支持 .xls, .xlsx, .csv" accept=".xls,.xlsx,.csv" onSelect={(file) => setImportFile(file)} />
                )}
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">目标审核点库</label>
                <div className="grid grid-cols-2 gap-2">
                  {checkpointLibraries.map((library) => (
                    <label key={library.id} className="flex cursor-pointer items-center gap-2 rounded-btn border px-3 py-2 text-sm">
                      <input
                        type="checkbox"
                        checked={importLibraryIds.includes(library.id)}
                        onChange={() => setImportLibraryIds((current) => toggleValue(current, library.id))}
                      />
                      <span className="min-w-0 flex-1 truncate">{library.name}</span>
                      <span className="text-xs text-text-muted">{library.checkpoint_count}</span>
                    </label>
                  ))}
                </div>
                {checkpointLibraries.length === 0 && (
                  <p className="text-sm text-text-muted">暂无审核点库，可先返回列表创建。</p>
                )}
              </div>
              {importPreview && (
                <div className="grid grid-cols-4 gap-2 rounded-card border bg-surface p-3 text-sm">
                  <ImportMetric label="新增" value={importPreview.created_count} />
                  <ImportMetric label="复用" value={importPreview.reused_count} />
                  <ImportMetric label="重复" value={importPreview.duplicate_count} />
                  <ImportMetric label="跳过" value={importPreview.skipped_count} />
                </div>
              )}
              {importResult && (
                <div className="rounded-btn bg-status-ok-bg p-3 text-sm text-status-ok">
                  新增 {importResult.created_count} 条，复用 {importResult.reused_count} 条，建立关联 {importResult.linked_count} 条，跳过 {importResult.skipped_count} 条。
                </div>
              )}
              <div className="flex gap-2">
                <Button variant="secondary" disabled={!importFile || importPreviewing} onClick={handlePreviewImport}>
                  {importPreviewing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  解析预览
                </Button>
                <Button disabled={!importFile || importing} onClick={handleImport}>
                  {importing ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />}
                  确认入库
                </Button>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>导入结果</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm text-text-secondary">
              <p>同标题审核点会优先复用已有记录；选择目标库后，新增和复用的审核点都会批量关联到库。</p>
              {importPreview?.skipped_reasons.length ? (
                <div className="max-h-52 overflow-auto rounded-card bg-surface p-3">
                  {importPreview.skipped_reasons.slice(0, 20).map((reason) => (
                    <p key={reason} className="text-xs text-text-muted">{reason}</p>
                  ))}
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="flex flex-col">
        <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
          <span className="text-base font-semibold text-text-primary">审核点库</span>
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => setNewLibraryOpen(true)}>
              <FolderPlus className="h-4 w-4" /> 新建库
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button><Upload className="h-4 w-4" /> 上传</Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem onClick={() => setMode("extract")}><Sparkles className="h-4 w-4" /> AI 提取</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setMode("import")}><FileSpreadsheet className="h-4 w-4" /> 导入审查点表格</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <div className="grid grid-cols-[260px_minmax(0,1fr)] gap-5 p-7">
          <aside className="space-y-3">
            <button
              className={cn(
                "flex w-full items-center justify-between rounded-btn px-3 py-2 text-left text-sm",
                selectedLibraryId === "all" ? "bg-accent text-white" : "bg-surface hover:bg-gray-200",
              )}
              onClick={() => setSelectedLibraryId("all")}
            >
              <span className="flex items-center gap-2"><Folder className="h-4 w-4" /> 全部审核点</span>
              <span>{checkpoints.length}</span>
            </button>
            <button
              className={cn(
                "flex w-full items-center justify-between rounded-btn px-3 py-2 text-left text-sm",
                selectedLibraryId === UNCATEGORIZED_ID ? "bg-accent text-white" : "bg-surface hover:bg-gray-200",
              )}
              onClick={() => setSelectedLibraryId(UNCATEGORIZED_ID)}
            >
              <span className="flex items-center gap-2"><Folder className="h-4 w-4" /> 未分类</span>
              <span>{uncategorizedCount}</span>
            </button>
            <div className="space-y-1">
              {checkpointLibraries.map((library) => (
                <div
                  key={library.id}
                  className={cn(
                    "group flex items-center justify-between rounded-btn px-3 py-2 text-sm",
                    selectedLibraryId === library.id ? "bg-accent text-white" : "hover:bg-surface",
                  )}
                >
                  <button
                    className="min-w-0 flex-1 truncate text-left"
                    onClick={() => setSelectedLibraryId(library.id)}
                  >
                    {library.name}
                    <span className="ml-2 text-xs">{library.checkpoint_count}</span>
                  </button>
                  <button
                    className={cn(
                      "ml-1 shrink-0 rounded p-0.5 opacity-0 transition-opacity hover:bg-black/10",
                      selectedLibraryId === library.id && "text-white",
                      selectedLibraryId === library.id ? "group-hover:opacity-100" : "group-hover:opacity-70",
                    )}
                    onClick={() => {
                      setSelectedLibraryId(library.id);
                      setEditingLibraryId(library.id);
                      setEditLibraryName(library.name);
                      setEditLibraryDesc(library.description ?? "");
                    }}
                  >
                    <Pencil className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          </aside>

          <main className="space-y-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">
                  {selectedLibraryId === "all"
                    ? "全部审核点"
                    : selectedLibraryId === UNCATEGORIZED_ID
                      ? "未分类"
                      : activeLibrary?.name ?? "审核点库"}
                </h2>
                <p className="text-sm text-text-muted">
                  {selectedLibraryId === "all"
                    ? `已收录 ${checkpoints.length} 个审查要点`
                    : selectedLibraryId === UNCATEGORIZED_ID
                      ? `${uncategorizedCount} 个未归库审查要点`
                      : `已收录 ${activeLibrary?.checkpoint_count ?? 0} 个审查要点`}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
                  <Input className="w-60 pl-8" placeholder="搜索审查要点..." value={search} onChange={(event) => setSearch(event.target.value)} />
                </div>
                <Button variant="secondary" disabled={selectedIds.length === 0} onClick={() => setAddDialogOpen(true)}>
                  <Plus className="h-4 w-4" /> 加入库
                </Button>
                {!isVirtualLibrary && (
                  <Button variant="secondary" disabled={selectedIds.length === 0} onClick={removeSelectedFromCurrentLibrary}>
                    移出当前库
                  </Button>
                )}
                {!isVirtualLibrary && (
                  <Button variant="secondary" onClick={openEditLibrary}>
                    <Pencil className="h-4 w-4" /> 编辑库
                  </Button>
                )}
                {!isVirtualLibrary && (
                  <Button variant="secondary" onClick={() => setDeletingLibraryId(selectedLibraryId)}>
                    <Trash2 className="h-4 w-4" /> 删除库
                  </Button>
                )}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button onClick={() => setCategoryFilter("all")} className={cn("rounded-full px-3 py-1 text-xs font-medium transition-colors", categoryFilter === "all" ? "bg-accent text-white" : "bg-surface text-text-secondary hover:bg-gray-200")}>全部分类</button>
              {categories.map((cat) => (
                <button key={cat} onClick={() => setCategoryFilter(cat)} className={cn("rounded-full px-3 py-1 text-xs font-medium transition-colors", categoryFilter === cat ? "bg-accent text-white" : "bg-surface text-text-secondary hover:bg-gray-200")}>{cat}</button>
              ))}
              {selectedIds.length > 0 && (
                <Badge variant="outline">已选择 {selectedIds.length} 个</Badge>
              )}
              {loadingLibrary && <span className="text-sm text-text-muted">加载库中...</span>}
            </div>

            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <input type="checkbox" checked={allFilteredSelected} onChange={toggleAllFiltered} />
                    </TableHead>
                    <TableHead className="w-[40%]">审查要点</TableHead>
                    <TableHead>分类</TableHead>
                    <TableHead>严重程度</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead className="w-20 text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((row) => (
                    <TableRow key={row.key}>
                      <TableCell>
                        {!row.deleted && (
                          <input
                            type="checkbox"
                            checked={selectedIds.includes(row.checkpointFinalId)}
                            onChange={() => setSelectedIds((current) => toggleValue(current, row.checkpointFinalId))}
                          />
                        )}
                      </TableCell>
                      <TableCell>
                        {row.deleted ? (
                          <div>
                            <p className="font-medium text-text-muted">该审核点已被删除</p>
                            <p className="mt-0.5 text-xs text-text-muted">{row.checkpointFinalId}</p>
                          </div>
                        ) : (
                          <div>
                            <p className="font-medium text-text-primary">{row.payload?.title}</p>
                            <p className="mt-0.5 line-clamp-1 text-xs text-text-muted">{row.payload?.description}</p>
                          </div>
                        )}
                      </TableCell>
                      <TableCell>{row.payload && <Badge variant="outline">{row.payload.category}</Badge>}</TableCell>
                      <TableCell>{row.payload && <Badge variant={SEVERITY_VARIANT[row.payload.severity] ?? "muted"}>{SEVERITY_LABEL[row.payload.severity] ?? row.payload.severity}</Badge>}</TableCell>
                      <TableCell>{row.deleted ? <Badge variant="muted">已删除</Badge> : <StatusBadge status="completed" />}</TableCell>
                      <TableCell className="text-right">
                        {row.item && (
                          <div className="flex justify-end gap-1">
                            <Button variant="ghost" size="icon" onClick={() => openEdit(row.item!)}><Pencil className="h-3.5 w-3.5" /></Button>
                            <Button variant="ghost" size="icon" onClick={() => openDelete(row.item!)}><Trash2 className="h-3.5 w-3.5 text-status-err" /></Button>
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                  {filtered.length === 0 && (
                    <TableRow><TableCell colSpan={6} className="py-12 text-center text-text-muted">暂无审核点，请点击「上传」开始创建。</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </Card>
          </main>
        </div>
      </div>

      <Dialog open={editingCp != null} onOpenChange={(open: boolean) => { if (!open) setEditingCp(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑审查要点</DialogTitle>
            <DialogDescription>修改审查要点的标题和描述内容</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 p-5">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">标题</label>
              <Input value={editTitle} onChange={(event) => setEditTitle(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">描述</label>
              <Textarea value={editDesc} onChange={(event) => setEditDesc(event.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setEditingCp(null)}>取消</Button>
            <Button onClick={saveEdit}>保存修改</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deletingId != null} onOpenChange={(open: boolean) => { if (!open) setDeletingId(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>确认删除</DialogTitle></DialogHeader>
          <div className="space-y-3 p-5">
            <div className="rounded-btn border border-status-err-border bg-status-err-bg p-3 text-sm font-medium text-status-err">此操作不可撤销</div>
            <p className="text-sm text-text-secondary">确定要删除审查要点「{deletingTitle}」吗？</p>
            {deletingLibraries.length > 0 && (
              <div className="rounded-btn border p-3 text-sm">
                <p className="font-medium text-text-secondary">该审核点存在于以下库中，删除后将一并移出：</p>
                <ul className="mt-1.5 list-inside list-disc text-text-muted">
                  {deletingLibraries.map((lib) => (
                    <li key={lib.id}>{lib.name}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setDeletingId(null)}>取消</Button>
            <Button variant="danger" onClick={confirmDelete}>确认删除</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={newLibraryOpen} onOpenChange={setNewLibraryOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建审核点库</DialogTitle>
            <DialogDescription>创建后可批量加入审核点，并在发起审查时直接选择整个库。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 p-5">
            <Input placeholder="库名称" value={newLibraryName} onChange={(event) => setNewLibraryName(event.target.value)} />
            <Textarea placeholder="说明（可选）" value={newLibraryDesc} onChange={(event) => setNewLibraryDesc(event.target.value)} />
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setNewLibraryOpen(false)}>取消</Button>
            <Button disabled={!newLibraryName.trim() || creatingLibrary} onClick={confirmCreateLibrary}>
              {creatingLibrary && <Loader2 className="h-4 w-4 animate-spin" />}
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={editingLibraryId != null} onOpenChange={(open: boolean) => { if (!open) setEditingLibraryId(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑审核点库</DialogTitle>
            <DialogDescription>修改库名称和说明。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 p-5">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">库名称</label>
              <Input value={editLibraryName} onChange={(e) => setEditLibraryName(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">说明</label>
              <Textarea placeholder="可选" value={editLibraryDesc} onChange={(e) => setEditLibraryDesc(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setEditingLibraryId(null)}>取消</Button>
            <Button disabled={!editLibraryName.trim() || savingLibrary} onClick={saveEditLibrary}>
              {savingLibrary && <Loader2 className="h-4 w-4 animate-spin" />}
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deletingLibraryId != null} onOpenChange={(open: boolean) => { if (!open) setDeletingLibraryId(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>删除审核点库</DialogTitle>
            <DialogDescription>只删除库和关联关系，不删除审核点本体。</DialogDescription>
          </DialogHeader>
          <div className="p-5 text-sm text-text-secondary">
            确定要删除「{checkpointLibraries.find((library) => library.id === deletingLibraryId)?.name ?? ""}」吗？
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setDeletingLibraryId(null)}>取消</Button>
            <Button variant="danger" onClick={confirmDeleteLibrary}>确认删除</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>加入审核点库</DialogTitle>
            <DialogDescription>将已选择的 {selectedIds.length} 个审核点加入一个或多个库。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 p-5">
            <div className="grid grid-cols-2 gap-2">
              {checkpointLibraries.map((library) => (
                <label key={library.id} className="flex cursor-pointer items-center gap-2 rounded-btn border px-3 py-2 text-sm">
                  <input
                    type="checkbox"
                    checked={targetLibraryIds.includes(library.id)}
                    onChange={() => setTargetLibraryIds((current) => toggleValue(current, library.id))}
                  />
                  <span className="min-w-0 flex-1 truncate">{library.name}</span>
                  <span className="text-xs text-text-muted">{library.checkpoint_count}</span>
                </label>
              ))}
            </div>
            <Input placeholder="或者输入新库名称" value={inlineNewLibraryName} onChange={(event) => setInlineNewLibraryName(event.target.value)} />
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setAddDialogOpen(false)}>取消</Button>
            <Button disabled={selectedIds.length === 0 || (targetLibraryIds.length === 0 && !inlineNewLibraryName.trim())} onClick={confirmAddSelectedToLibraries}>确认加入</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function ImportMetric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-xs text-text-muted">{label}</p>
      <p className="text-lg font-semibold text-text-primary">{value}</p>
    </div>
  );
}

const EXTRACT_STEPS = [
  { label: "分析法规结构", phase: "plan" },
  { label: "逐条提取审查要点", phase: "execute" },
  { label: "汇总并入库", phase: "summarize" },
] as const;

const PHASE_ORDER: Record<string, number> = { plan: 0, execute: 1, summarize: 2 };

function ExtractProgressCard({ currentPhase }: { currentPhase: string | null }) {
  const phaseIdx = currentPhase ? (PHASE_ORDER[currentPhase] ?? -1) : -1;

  return (
    <Card>
      <CardHeader><CardTitle>提取进度</CardTitle></CardHeader>
      <CardContent className="space-y-0">
        {EXTRACT_STEPS.map((step, i) => {
          const isLast = i === EXTRACT_STEPS.length - 1;
          const done = phaseIdx > i;
          const active = phaseIdx === i;

          return (
            <div key={step.phase} className="flex gap-3">
              <div className="flex flex-col items-center">
                <div className={cn(
                  "flex h-[10px] w-[10px] shrink-0 items-center justify-center rounded-full",
                  done && "bg-status-ok",
                  active && "bg-accent",
                  !done && !active && "border-2 border-gray-300",
                )}>
                  {done && <Check className="h-2.5 w-2.5 text-white" />}
                  {active && <Loader2 className="h-2.5 w-2.5 animate-spin text-white" />}
                </div>
                {!isLast && <div className={cn("h-7 w-0.5", done ? "bg-status-ok" : "bg-gray-200")} />}
              </div>
              <div className="pb-3">
                <p className={cn(
                  "text-[13px] font-medium",
                  done && "text-text-primary",
                  active && "text-accent",
                  !done && !active && "text-text-muted",
                )}>{step.label}</p>
                <p className="text-[11px] text-text-muted">
                  {done ? "已完成" : active ? "正在处理中..." : "等待中"}
                </p>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
