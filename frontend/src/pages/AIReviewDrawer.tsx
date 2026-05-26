import { FileText, Loader2, Plus, X } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import {
  createAuditRun,
  createProject,
  listCheckpoints,
  listProjects,
  uploadTenderDoc,
} from "@/api/v3";
import { FileDropzone } from "@/components/FileDropzone";
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
  GovCheckpointPayload,
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

function selectedFileLabel(file: File | null): string {
  if (!file) return "";
  return `${file.name} · ${(file.size / 1024).toFixed(1)} KB`;
}

export function AIReviewDrawer({ open, onClose, onCreated }: AIReviewDrawerProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [checkpoints, setCheckpoints] = useState<ParsedCheckpoint[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [newProjectName, setNewProjectName] = useState("");
  const [tenderFile, setTenderFile] = useState<File | null>(null);
  const [selectedCheckpointIds, setSelectedCheckpointIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [creatingProject, setCreatingProject] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId),
    [projects, selectedProjectId],
  );

  useEffect(() => {
    if (!open) return;
    let active = true;
    setLoading(true);
    setError(null);
    Promise.all([listProjects(), listCheckpoints()])
      .then(([nextProjects, nextCheckpoints]) => {
        if (!active) return;
        setProjects(nextProjects);
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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProjectId || !tenderFile || selectedCheckpointIds.length === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      const tenderDoc = await uploadTenderDoc(selectedProjectId, tenderFile);
      await createAuditRun(selectedProjectId, tenderDoc.id, [], selectedCheckpointIds);
      onCreated();
      onClose();
      setTenderFile(null);
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
            <p className="text-sm text-text-muted">选择项目、上传文书并勾选审查要点</p>
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
                {tenderFile ? (
                  <div className="flex items-center gap-3 rounded-card border bg-surface px-3 py-3">
                    <FileText className="h-4 w-4 shrink-0 text-accent" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-text-primary">
                        {selectedFileLabel(tenderFile)}
                      </p>
                      <p className="text-xs text-text-muted">提交时将上传为主招标文书</p>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setTenderFile(null)}
                    >
                      移除
                    </Button>
                  </div>
                ) : (
                  <FileDropzone
                    title="点击选择或拖入招标文书"
                    subtitle="支持 .docx, .pdf"
                    accept=".docx,.pdf"
                    onSelect={(files) => setTenderFile(files[0] ?? null)}
                  />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex-row items-center justify-between space-y-0">
                <CardTitle>审查要点</CardTitle>
                <span className="text-sm text-text-muted">
                  已选 {selectedCheckpointIds.length} / {checkpoints.length}
                </span>
              </CardHeader>
              <CardContent>
                {checkpoints.length === 0 ? (
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
              !tenderFile ||
              selectedCheckpointIds.length === 0
            }
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            开始审查（{selectedCheckpointIds.length} 个要点）
          </Button>
        </footer>
      </form>
    </div>
  );
}

export default AIReviewDrawer;
