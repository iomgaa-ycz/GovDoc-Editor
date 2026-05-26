import { FileCheck, FileText, FolderOpen, Info, Loader2, Plus, X } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { getDocument } from "@/api/documents";
import {
  createAuditRun,
  createProject,
  listCheckpoints,
  listCheckpointLibraries,
  listProjects,
} from "@/api/v3";
import FilePickerModal from "@/components/FilePickerModal";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import type {
  CheckpointItem,
  CheckpointLibrary,
  GovCheckpointPayload,
  GovDocument,
  Project,
} from "@/types/ui";

export interface AIReviewDrawerProps {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

type ParsedCheckpoint = CheckpointItem & { parsed: GovCheckpointPayload };

function parseCheckpoint(item: CheckpointItem): ParsedCheckpoint | null {
  try {
    return { ...item, parsed: JSON.parse(item.payload_json) as GovCheckpointPayload };
  } catch {
    return null;
  }
}

function formatFileSize(bytes: number): string {
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function deduplicateDocuments(documents: GovDocument[]): GovDocument[] {
  return [...new Map(documents.map((document) => [document.id, document])).values()];
}

export function AIReviewDrawer({ open, onClose, onCreated }: AIReviewDrawerProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [checkpoints, setCheckpoints] = useState<ParsedCheckpoint[]>([]);
  const [checkpointLibraries, setCheckpointLibraries] = useState<CheckpointLibrary[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [newProjectName, setNewProjectName] = useState("");
  const [mainDoc, setMainDoc] = useState<GovDocument | null>(null);
  const [suppDocs, setSuppDocs] = useState<GovDocument[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerMode, setPickerMode] = useState<"single" | "multi">("single");
  const [pickerTarget, setPickerTarget] = useState<"main" | "supp">("main");
  const [selectionMode, setSelectionMode] = useState<"library" | "manual">("library");
  const [selectedLibraryId, setSelectedLibraryId] = useState<string | null>(null);
  const [selectedCheckpointIds, setSelectedCheckpointIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [creatingProject, setCreatingProject] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId),
    [projects, selectedProjectId],
  );
  const selectedLibraryCount =
    checkpointLibraries.find((library) => library.id === selectedLibraryId)?.checkpoint_count ?? 0;

  useEffect(() => {
    if (!open) return;
    let active = true;
    setLoading(true);
    setError(null);
    Promise.all([listProjects(), listCheckpoints(), listCheckpointLibraries()])
      .then(([nextProjects, nextCheckpoints, nextLibraries]) => {
        if (!active) return;
        setProjects(nextProjects);
        setCheckpointLibraries(nextLibraries);
        setCheckpoints(
          nextCheckpoints
            .map(parseCheckpoint)
            .filter((checkpoint): checkpoint is ParsedCheckpoint => checkpoint != null),
        );
        setSelectedProjectId((current) =>
          current && nextProjects.some((project) => project.id === current)
            ? current
            : nextProjects[0]?.id ?? null,
        );
        setSelectedLibraryId((current) =>
          current && nextLibraries.some((library) => library.id === current)
            ? current
            : nextLibraries[0]?.id ?? null,
        );
        setSelectionMode(nextLibraries.length > 0 ? "library" : "manual");
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "加载数据失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [open]);

  async function handleCreateProject() {
    const name = newProjectName.trim();
    if (!name) return;
    setCreatingProject(true);
    setError(null);
    try {
      const project = await createProject(name, "reviewer");
      setProjects((current) => [
        project,
        ...current.filter((item) => item.id !== project.id),
      ]);
      setSelectedProjectId(project.id);
      setNewProjectName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建项目失败");
    } finally {
      setCreatingProject(false);
    }
  }

  function toggleCheckpoint(checkpointId: string) {
    setSelectedCheckpointIds((current) =>
      current.includes(checkpointId)
        ? current.filter((id) => id !== checkpointId)
        : [...current, checkpointId],
    );
  }

  function openPicker(target: "main" | "supp", mode: "single" | "multi"): void {
    setPickerTarget(target);
    setPickerMode(mode);
    setPickerOpen(true);
  }

  async function handlePickerConfirm(selectedIds: string[]): Promise<void> {
    if (selectedIds.length === 0) return;
    setError(null);
    try {
      if (pickerTarget === "main") {
        setMainDoc(await getDocument(selectedIds[0]));
      } else {
        const selected = await Promise.all(selectedIds.map((id) => getDocument(id)));
        setSuppDocs((current) => deduplicateDocuments([...current, ...selected]));
      }
      setPickerOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "选择文件失败");
    }
  }

  function removeSupplementaryDoc(documentId: string): void {
    setSuppDocs((current) => current.filter((document) => document.id !== documentId));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const usingLibrary = selectionMode === "library";
    if (!selectedProjectId || !mainDoc) return;
    if (usingLibrary && (!selectedLibraryId || selectedLibraryCount === 0)) return;
    if (!usingLibrary && selectedCheckpointIds.length === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      await createAuditRun(
        selectedProjectId,
        mainDoc.id,
        suppDocs.map((document) => document.id),
        usingLibrary ? [] : selectedCheckpointIds,
        usingLibrary ? selectedLibraryId : null,
      );
      onCreated();
      onClose();
      setMainDoc(null);
      setSuppDocs([]);
      setSelectedCheckpointIds([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建审查任务失败");
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <form
        className="absolute right-0 top-0 flex h-full w-[640px] max-w-full flex-col bg-white shadow-xl"
        onSubmit={handleSubmit}
      >
        <header className="flex items-center justify-between border-b px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">新建审查任务</h2>
            <p className="text-sm text-text-muted">选择项目、文件并选择审核点库或手动勾选要点</p>
          </div>
          <Button type="button" variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
            <span className="sr-only">关闭</span>
          </Button>
        </header>

        <ScrollArea className="flex-1">
          <div className="space-y-5 p-6">
            {error && (
              <div className="rounded-card border border-status-err-border bg-status-err-bg px-4 py-3 text-sm text-status-err">
                {error}
              </div>
            )}

            <Card>
              <CardHeader>
                <CardTitle>选择项目</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-text-primary">现有项目</label>
                  <Select
                    value={selectedProjectId ?? undefined}
                    onValueChange={(value: string) => setSelectedProjectId(value)}
                    disabled={loading || projects.length === 0}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={loading ? "加载项目中..." : "选择项目"} />
                    </SelectTrigger>
                    <SelectContent>
                      {projects.map((project) => (
                        <SelectItem key={project.id} value={project.id}>
                          {project.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {selectedProject && (
                    <p className="text-xs text-text-muted">
                      当前项目：{selectedProject.name}
                    </p>
                  )}
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-text-primary">创建新项目</label>
                  <div className="flex gap-2">
                    <Input
                      placeholder="输入项目名称"
                      value={newProjectName}
                      onChange={(event) => setNewProjectName(event.target.value)}
                    />
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={!newProjectName.trim() || creatingProject}
                      onClick={handleCreateProject}
                    >
                      {creatingProject ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Plus className="h-4 w-4" />
                      )}
                      创建
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>招标文书</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {mainDoc ? (
                  <div
                    className="flex items-center gap-3 rounded-card border px-3 py-3"
                    style={{ borderColor: "#86EFAC", backgroundColor: "#F0FDF4" }}
                  >
                    <FileCheck className="h-4 w-4 shrink-0 text-green-600" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-green-950">
                        {mainDoc.filename}
                      </p>
                      <p className="text-xs text-green-700">{formatFileSize(mainDoc.file_size)}</p>
                    </div>
                    <button
                      type="button"
                      className="text-xs font-medium text-green-700 underline-offset-2 hover:underline"
                      onClick={() => openPicker("main", "single")}
                    >
                      更换
                    </button>
                  </div>
                ) : (
                  <Button
                    type="button"
                    variant="secondary"
                    className="w-full justify-center"
                    onClick={() => openPicker("main", "single")}
                  >
                    <FolderOpen className="h-4 w-4" />
                    选择招标文书
                  </Button>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>补充文件（可选）</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {suppDocs.length > 0 && (
                  <div className="space-y-2">
                    {suppDocs.map((document) => (
                      <div
                        key={document.id}
                        className="flex items-center gap-2 rounded-card border bg-surface px-3 py-2"
                      >
                        <FileText className="h-4 w-4 shrink-0 text-text-muted" />
                        <span className="min-w-0 flex-1 truncate text-sm text-text-primary">
                          {document.filename}
                        </span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => removeSupplementaryDoc(document.id)}
                        >
                          <X className="h-3.5 w-3.5" />
                          <span className="sr-only">移除</span>
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
                <Button
                  type="button"
                  variant="secondary"
                  className="w-full justify-center"
                  onClick={() => openPicker("supp", "multi")}
                >
                  <FolderOpen className="h-4 w-4" />
                  从文件库添加
                </Button>
              </CardContent>
            </Card>

            <div className="flex items-center gap-1.5 rounded-md bg-amber-50 px-3 py-2">
              <Info className="h-3.5 w-3.5 text-amber-600" />
              <span className="text-xs text-amber-900">没有找到需要的文件？请先到「文件管理」页面上传</span>
            </div>

            <Card>
              <CardHeader className="flex-row items-center justify-between space-y-0">
                <CardTitle>审查范围</CardTitle>
                <span className="text-sm text-text-muted">
                  {selectionMode === "library" ? selectedLibraryCount : selectedCheckpointIds.length} 个要点
                </span>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    className={cn(
                      "rounded-btn border px-3 py-2 text-sm font-medium",
                      selectionMode === "library" ? "border-accent bg-accent-light text-accent" : "hover:bg-surface",
                    )}
                    onClick={() => setSelectionMode("library")}
                    disabled={checkpointLibraries.length === 0}
                  >
                    按审核点库
                  </button>
                  <button
                    type="button"
                    className={cn(
                      "rounded-btn border px-3 py-2 text-sm font-medium",
                      selectionMode === "manual" ? "border-accent bg-accent-light text-accent" : "hover:bg-surface",
                    )}
                    onClick={() => setSelectionMode("manual")}
                  >
                    手动选择
                  </button>
                </div>

                {selectionMode === "library" ? (
                  checkpointLibraries.length === 0 ? (
                    <div className="rounded-card border border-dashed py-10 text-center text-sm text-text-muted">
                      暂无审核点库，请先在审核点库页面创建并入库。
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-text-primary">审核点库</label>
                      <Select
                        value={selectedLibraryId ?? undefined}
                        onValueChange={(value: string) => setSelectedLibraryId(value)}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="选择审核点库" />
                        </SelectTrigger>
                        <SelectContent>
                          {checkpointLibraries.map((library) => (
                            <SelectItem key={library.id} value={library.id}>
                              {library.name}（{library.checkpoint_count}）
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {selectedLibraryId && (
                        <p className="text-xs text-text-muted">
                          发起后将固定使用该库当前可用审核点；之后库内容变化不会影响本次任务。
                        </p>
                      )}
                    </div>
                  )
                ) : checkpoints.length === 0 ? (
                  <div className="rounded-card border border-dashed py-10 text-center text-sm text-text-muted">
                    暂无审查要点，请先在审核点库中导入或创建。
                  </div>
                ) : (
                  <div className="max-h-[360px] space-y-1 overflow-auto pr-1">
                    {checkpoints.map((checkpoint) => {
                      const checked = selectedCheckpointIds.includes(checkpoint.id);
                      return (
                        <label
                          key={checkpoint.id}
                          className={cn(
                            "flex cursor-pointer items-start gap-3 rounded-btn border px-3 py-2.5 transition-colors",
                            checked
                              ? "border-accent bg-accent-light"
                              : "border-transparent hover:bg-surface",
                          )}
                        >
                          <input
                            type="checkbox"
                            className="mt-0.5 h-4 w-4 rounded border-gray-300 text-accent"
                            checked={checked}
                            onChange={() => toggleCheckpoint(checkpoint.id)}
                          />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-medium text-text-primary">
                              {checkpoint.parsed.title}
                            </span>
                            <span className="block truncate text-xs text-text-muted">
                              {checkpoint.parsed.category} · {checkpoint.parsed.severity}
                            </span>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </ScrollArea>

        <footer className="flex items-center justify-between border-t px-6 py-4">
          <Button type="button" variant="secondary" onClick={onClose}>
            取消
          </Button>
          <Button
            type="submit"
            disabled={
              submitting ||
              !selectedProjectId ||
              !mainDoc ||
              (selectionMode === "library"
                ? !selectedLibraryId || selectedLibraryCount === 0
                : selectedCheckpointIds.length === 0)
            }
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            开始审查（{selectionMode === "library" ? selectedLibraryCount : selectedCheckpointIds.length} 个要点）
          </Button>
        </footer>
      </form>

      <FilePickerModal
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onConfirm={handlePickerConfirm}
        mode={pickerMode}
        initialSelected={pickerTarget === "main" ? (mainDoc ? [mainDoc.id] : []) : suppDocs.map((document) => document.id)}
      />
    </div>
  );
}

export default AIReviewDrawer;
