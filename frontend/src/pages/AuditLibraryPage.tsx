import { ArrowLeft, FileSpreadsheet, Pencil, Search, Sparkles, Trash2, Upload } from "lucide-react";
import { useState } from "react";

import { useWorkbench } from "@/context/V3WorkbenchContext";
import type { CheckpointItem, GovCheckpointPayload } from "@/types/ui";
import { parseCheckpointPayload } from "@/adapters/backendToUi";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { StatusBadge } from "@/components/StatusBadge";
import { FileDropzone } from "@/components/FileDropzone";

const SEVERITY_VARIANT: Record<string, "err" | "warn" | "default"> = { critical: "err", major: "warn", minor: "default" };
const SEVERITY_LABEL: Record<string, string> = { critical: "严重", major: "重要", minor: "一般" };

export function AuditLibraryPage() {
  const { checkpoints, extractStatus, extractError, uploadRuleAndExtract, updateCheckpoint, deleteCheckpoint, importCheckpointFile } = useWorkbench();

  const [mode, setMode] = useState<"list" | "extract" | "import">("list");
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{ imported_count: number; skipped_count: number } | null>(null);

  const [editingCp, setEditingCp] = useState<CheckpointItem | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDesc, setEditDesc] = useState("");

  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deletingTitle, setDeletingTitle] = useState("");

  const parsed = checkpoints
    .map((c) => ({ item: c, payload: parseCheckpointPayload(c.payload_json) }))
    .filter((c): c is { item: CheckpointItem; payload: GovCheckpointPayload } => c.payload != null);

  const categories = [...new Set(parsed.map((c) => c.payload.category))];

  const filtered = parsed.filter((c) => {
    if (categoryFilter !== "all" && c.payload.category !== categoryFilter) return false;
    if (search && !c.payload.title.includes(search) && !c.payload.description.includes(search)) return false;
    return true;
  });

  async function handleExtract() {
    if (!uploadTitle || !uploadFile) return;
    setUploading(true);
    try { await uploadRuleAndExtract(uploadTitle, uploadFile); } finally { setUploading(false); }
  }

  async function handleImport() {
    if (!importFile) return;
    setImporting(true);
    try {
      const result = await importCheckpointFile(importFile);
      setImportResult(result);
      setImportFile(null);
    } finally { setImporting(false); }
  }

  function openEdit(item: CheckpointItem) {
    const p = parseCheckpointPayload(item.payload_json);
    if (!p) return;
    setEditingCp(item);
    setEditTitle(p.title);
    setEditDesc(p.description);
  }

  async function saveEdit() {
    if (!editingCp) return;
    const p = parseCheckpointPayload(editingCp.payload_json);
    if (!p) return;
    await updateCheckpoint(editingCp.id, { ...p, title: editTitle, description: editDesc });
    setEditingCp(null);
  }

  function openDelete(item: CheckpointItem) {
    const p = parseCheckpointPayload(item.payload_json);
    setDeletingId(item.id);
    setDeletingTitle(p?.title ?? "");
  }

  async function confirmDelete() {
    if (!deletingId) return;
    await deleteCheckpoint(deletingId);
    setDeletingId(null);
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
                  <Input placeholder="例如：政府采购法实施条例" value={uploadTitle} onChange={(e) => setUploadTitle(e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">法规原文</label>
                  {uploadFile ? (
                    <div className="flex items-center justify-between rounded-card border p-3">
                      <span className="text-sm">{uploadFile.name}</span>
                      <button className="text-text-muted hover:text-text-primary text-sm" onClick={() => setUploadFile(null)}>移除</button>
                    </div>
                  ) : (
                    <FileDropzone title="选择或拖入法规文件" subtitle="支持 .md, .pdf, .docx" accept=".md,.pdf,.docx" onSelect={(f) => setUploadFile(f[0] ?? null)} />
                  )}
                </div>
                {extractStatus && extractStatus !== "draft_ready" && (
                  <div className={cn("rounded-btn p-3 text-sm", extractStatus === "failed" ? "bg-status-err-bg text-status-err" : "bg-status-info-bg text-status-info")}>
                    {extractStatus === "pending" ? "等待处理..." : extractStatus === "running" ? "正在提取审核点..." : extractError ?? "处理失败"}
                  </div>
                )}
                {extractStatus === "draft_ready" && (
                  <div className="rounded-btn bg-status-ok-bg p-3 text-sm text-status-ok">提取完成，审核点已入库。</div>
                )}
                <Button disabled={!uploadTitle || !uploadFile || uploading || extractStatus === "running"} onClick={handleExtract}>
                  <Sparkles className="h-4 w-4" /> 开始抽取
                </Button>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>提取说明</CardTitle></CardHeader>
              <CardContent>
                <p className="text-sm text-text-muted leading-relaxed">系统将从上传的法规原文中自动提取审查要点。每个要点包含标题、描述、法条引用和严重程度分级。</p>
                <p className="mt-3 text-sm text-text-muted leading-relaxed">提取完成后，审查要点将自动入库。您可以在列表页面中查看和编辑。</p>
              </CardContent>
            </Card>
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
          <Button variant="secondary" size="sm" onClick={() => { setMode("list"); setImportResult(null); }}>
            <ArrowLeft className="h-4 w-4" /> 返回列表
          </Button>
        </header>
        <div className="flex items-start justify-center p-7">
          <Card className="w-full max-w-xl">
            <CardHeader>
              <CardTitle>导入审查点表格</CardTitle>
              <p className="text-sm text-text-muted">上传已整理好的审查点表格，系统将自动解析并写入审核点库。</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">审查点文件</label>
                {importFile ? (
                  <div className="flex items-center justify-between rounded-card border p-3">
                    <span className="text-sm">{importFile.name}</span>
                    <button className="text-text-muted hover:text-text-primary text-sm" onClick={() => setImportFile(null)}>移除</button>
                  </div>
                ) : (
                  <FileDropzone title="选择审查点表格" subtitle="支持 .xls, .xlsx, .csv" accept=".xls,.xlsx,.csv" onSelect={(f) => setImportFile(f[0] ?? null)} />
                )}
              </div>
              {importResult && (
                <div className="rounded-btn bg-status-ok-bg p-3 text-sm text-status-ok">
                  成功导入 {importResult.imported_count} 条审查点{importResult.skipped_count > 0 ? `，跳过 ${importResult.skipped_count} 条` : ""}
                </div>
              )}
              <Button disabled={!importFile || importing} onClick={handleImport}>
                <FileSpreadsheet className="h-4 w-4" /> 启动解析并导入库
              </Button>
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
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
              <Input className="pl-8 w-56" placeholder="搜索审查要点..." value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="secondary"><Upload className="h-4 w-4" /> 上传</Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem onClick={() => setMode("extract")}><Sparkles className="h-4 w-4" /> AI 提取</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setMode("import")}><FileSpreadsheet className="h-4 w-4" /> 导入审查点表格</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        <div className="space-y-5 p-7">
          <div>
            <h2 className="text-lg font-semibold">审核点管理</h2>
            <p className="text-sm text-text-muted">已收录 {checkpoints.length} 个审查要点，支持 AI 提取或表格批量导入</p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setCategoryFilter("all")} className={cn("rounded-full px-3 py-1 text-xs font-medium transition-colors", categoryFilter === "all" ? "bg-accent text-white" : "bg-surface text-text-secondary hover:bg-gray-200")}>全部分类</button>
            {categories.map((cat) => (
              <button key={cat} onClick={() => setCategoryFilter(cat)} className={cn("rounded-full px-3 py-1 text-xs font-medium transition-colors", categoryFilter === cat ? "bg-accent text-white" : "bg-surface text-text-secondary hover:bg-gray-200")}>{cat}</button>
            ))}
          </div>
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[40%]">审查要点</TableHead>
                  <TableHead>分类</TableHead>
                  <TableHead>严重程度</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="w-20 text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map(({ item, payload }) => (
                  <TableRow key={item.id}>
                    <TableCell>
                      <div>
                        <p className="font-medium text-text-primary">{payload.title}</p>
                        <p className="text-xs text-text-muted mt-0.5 line-clamp-1">{payload.description}</p>
                      </div>
                    </TableCell>
                    <TableCell><Badge variant="outline">{payload.category}</Badge></TableCell>
                    <TableCell><Badge variant={SEVERITY_VARIANT[payload.severity] ?? "muted"}>{SEVERITY_LABEL[payload.severity] ?? payload.severity}</Badge></TableCell>
                    <TableCell><StatusBadge status="completed" /></TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" onClick={() => openEdit(item)}><Pencil className="h-3.5 w-3.5" /></Button>
                        <Button variant="ghost" size="icon" onClick={() => openDelete(item)}><Trash2 className="h-3.5 w-3.5 text-status-err" /></Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {filtered.length === 0 && (
                  <TableRow><TableCell colSpan={5} className="text-center text-text-muted py-12">暂无审核点，请点击「上传」开始创建。</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </Card>
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
              <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">描述</label>
              <Textarea value={editDesc} onChange={(e) => setEditDesc(e.target.value)} />
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
            <div className="flex items-center gap-2 rounded-btn border border-status-err-border bg-status-err-bg p-3">
              <span className="text-sm text-status-err font-medium">此操作不可撤销</span>
            </div>
            <p className="text-sm text-text-secondary">确定要删除审查要点「{deletingTitle}」吗？删除后相关的审查记录将不受影响。</p>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setDeletingId(null)}>取消</Button>
            <Button variant="danger" onClick={confirmDelete}>确认删除</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
