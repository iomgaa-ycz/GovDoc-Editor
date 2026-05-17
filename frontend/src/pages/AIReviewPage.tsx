import { Check, ChevronRight, Loader2, Plus } from "lucide-react";
import { useState } from "react";

import { useWorkbench } from "@/context/V3WorkbenchContext";
import { useProjectWorkflow } from "@/hooks/useProjectWorkflow";
import { useAuditRun } from "@/hooks/useAuditRun";
import { parseFindingJson } from "@/adapters/backendToUi";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { MetricCard } from "@/components/MetricCard";
import { StatusBadge } from "@/components/StatusBadge";
import { FileDropzone } from "@/components/FileDropzone";
import { EmptyState } from "@/components/EmptyState";
import { ProgressTimeline } from "@/components/ProgressTimeline";
import { PointInsight } from "@/components/PointInsight";

export function AIReviewPage() {
  const {
    projects, activeProject, selectedProjectId, setSelectedProjectId,
    auditInputDocs, finalCheckpoints, auditProgress, retryPointRun,
  } = useWorkbench();

  const wf = useProjectWorkflow();
  const auditRun = useAuditRun();
  const [detailPrId, setDetailPrId] = useState<string | null>(null);
  const [selectedTimelinePrId, setSelectedTimelinePrId] = useState<string | null>(null);

  const inputDocs = activeProject ? auditInputDocs[activeProject.id] : undefined;
  const mainDoc = inputDocs?.mainDoc;
  const isRunning = auditProgress != null;
  const pointRuns = auditProgress?.point_runs ?? [];
  const progress = auditProgress ? (auditProgress.total_count > 0 ? (auditProgress.processed_count / auditProgress.total_count) * 100 : 0) : 0;
  const completedCount = pointRuns.filter((p) => p.status === "completed").length;
  const failedCount = pointRuns.filter((p) => p.status === "failed").length;
  const runningCount = pointRuns.filter((p) => p.status === "running").length;
  const selectedTimelinePr = pointRuns.find((p) => p.id === selectedTimelinePrId) ?? pointRuns.find((p) => p.status === "running") ?? pointRuns[0];

  if (isRunning) {
    return (
      <>
        <div className="flex flex-col h-screen">
          <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
            <div className="flex items-center gap-2">
              <span className="text-base font-semibold text-text-primary">AI 审核</span>
              <Badge variant="default">审核进行中</Badge>
            </div>
            <span className="text-xs text-text-muted">已完成 {auditProgress.processed_count}/{auditProgress.total_count}</span>
          </header>
          <div className="flex-1 space-y-5 p-7 overflow-auto">
            <div>
              <h2 className="text-lg font-semibold">{activeProject?.name ?? "审核任务"}</h2>
              <p className="text-sm text-text-muted">共 {auditProgress.total_count} 个审核要点，已处理 {auditProgress.processed_count} 个</p>
            </div>
            <Card>
              <CardContent className="p-4 space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-text-secondary">审核进度</span>
                  <span className="font-medium">{Math.round(progress)}%</span>
                </div>
                <Progress value={progress} />
                <div className="grid grid-cols-4 gap-3">
                  <MetricCard label="总审核点" value={auditProgress.total_count} tone="blue" />
                  <MetricCard label="已完成" value={completedCount} tone="green" />
                  <MetricCard label="审查中" value={runningCount} tone="amber" />
                  <MetricCard label="失败" value={failedCount} tone="red" />
                </div>
              </CardContent>
            </Card>
            <div className="grid grid-cols-2 gap-5">
              <Card>
                <CardHeader><CardTitle>审核要点</CardTitle></CardHeader>
                <CardContent className="p-0">
                  <div className="max-h-[400px] overflow-auto">
                    {pointRuns.map((pr) => {
                      const cp = finalCheckpoints.find((c) => c.id === pr.checkpoint_final_id);
                      const title = cp?.parsed?.title ?? pr.checkpoint_final_id.slice(0, 8);
                      return (
                        <button key={pr.id} className={cn("flex w-full items-center justify-between px-4 py-3 text-left border-b last:border-0 hover:bg-surface transition-colors", pr.id === selectedTimelinePr?.id && "bg-accent-light")} onClick={() => setSelectedTimelinePrId(pr.id)}>
                          <div className="flex items-center gap-2 min-w-0">
                            <span className={cn("h-2 w-2 shrink-0 rounded-full", pr.status === "completed" && "bg-status-ok", pr.status === "running" && "bg-accent", pr.status === "failed" && "bg-status-err", pr.status === "pending" && "bg-gray-300")} />
                            <span className="text-sm truncate">{title}</span>
                          </div>
                          <StatusBadge status={pr.status} />
                        </button>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
              {selectedTimelinePr && (
                <ProgressTimeline
                  pointRun={selectedTimelinePr}
                  checkpoint={finalCheckpoints.find((c) => c.id === selectedTimelinePr.checkpoint_final_id)?.parsed ?? null}
                  onRetry={selectedTimelinePr.status === "failed" ? () => retryPointRun(selectedTimelinePr.id) : undefined}
                />
              )}
            </div>
          </div>
        </div>
        <Dialog open={detailPrId != null} onOpenChange={(o: boolean) => { if (!o) setDetailPrId(null); }}>
          <DialogContent className="max-w-3xl">
            <DialogHeader><DialogTitle>审核点详情</DialogTitle></DialogHeader>
            {detailPrId && (() => {
              const pr = pointRuns.find((p) => p.id === detailPrId);
              const cp = pr ? finalCheckpoints.find((c) => c.id === pr.checkpoint_final_id)?.parsed ?? null : null;
              if (!cp || !pr) return <EmptyState title="无法加载" description="找不到该审核点的数据。" />;
              return <div className="p-5"><PointInsight checkpoint={cp} finding={parseFindingJson(pr.finding_json ?? null)} pointStatus={pr.status} /></div>;
            })()}
          </DialogContent>
        </Dialog>
      </>
    );
  }

  const step = !selectedProjectId || !activeProject ? 1 : !mainDoc ? 2 : 3;

  return (
    <div className="flex flex-col">
      <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
        <span className="text-base font-semibold text-text-primary">AI 审核</span>
      </header>
      <div className="space-y-6 p-7">
        <div>
          <h2 className="text-lg font-semibold">新建审查任务</h2>
          <p className="text-sm text-text-muted">上传招标文件，选择审查要点，启动 AI 自动审核</p>
        </div>
        <div className="flex items-center gap-3">
          {[{ n: 1, label: "选择或创建项目" }, { n: 2, label: "上传招标文件" }, { n: 3, label: "选择审查要点" }].map((s, i) => (
            <div key={s.n} className="flex items-center gap-3">
              <div className={cn("flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium", step > s.n ? "bg-accent text-white" : step === s.n ? "bg-accent text-white" : "border border-gray-300 text-text-muted")}>
                {step > s.n ? <Check className="h-4 w-4" /> : s.n}
              </div>
              <span className={cn("text-sm", step >= s.n ? "text-text-primary font-medium" : "text-text-muted")}>{s.label}</span>
              {i < 2 && <ChevronRight className="h-4 w-4 text-text-muted" />}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-6">
          <div className="space-y-6">
            <Card>
              <CardHeader><CardTitle>第一步：选择或创建项目</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">选择现有项目</label>
                  <select className="flex h-9 w-full rounded-btn border bg-white px-3 py-1 text-sm" value={selectedProjectId ?? ""} onChange={(e) => setSelectedProjectId(e.target.value || null)}>
                    <option value="">选择项目...</option>
                    {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">或创建新项目</label>
                  <div className="flex gap-2">
                    <Input placeholder="输入项目名称" value={wf.newProjectName} onChange={(e) => wf.setNewProjectName(e.target.value)} />
                    <Button variant="secondary" disabled={!wf.newProjectName || wf.creating} onClick={wf.handleCreateProject}>
                      <Plus className="h-4 w-4" /> 创建
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
            {activeProject && (
              <Card>
                <CardHeader><CardTitle>第二步：上传招标文件</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  {mainDoc ? (
                    <div className="flex items-center gap-2 rounded-card border p-3 bg-status-ok-bg">
                      <Check className="h-4 w-4 text-status-ok" />
                      <span className="text-sm">{mainDoc.filename}</span>
                    </div>
                  ) : (
                    <FileDropzone title="点击选择或拖入招标文件" subtitle="支持 .docx, .pdf" accept=".docx,.pdf" onSelect={(files) => { if (files[0]) wf.setMainTenderFile(files[0]); }} />
                  )}
                  {wf.mainTenderFile && !mainDoc && (
                    <div className="flex items-center justify-between">
                      <span className="text-sm">{wf.mainTenderFile.name}</span>
                      <Button size="sm" disabled={wf.uploadingTender} onClick={wf.handleUploadTender}>
                        {wf.uploadingTender ? <Loader2 className="h-4 w-4 animate-spin" /> : "上传"}
                      </Button>
                    </div>
                  )}
                  {wf.uploadError && <p className="text-sm text-status-err">{wf.uploadError}</p>}
                </CardContent>
              </Card>
            )}
          </div>
          <Card>
            <CardHeader><CardTitle>第三步：选择审查要点</CardTitle></CardHeader>
            <CardContent>
              {mainDoc ? (
                <div className="space-y-3">
                  <div className="max-h-[360px] overflow-auto space-y-1">
                    {finalCheckpoints.map((cp) => (
                      <label key={cp.id} className="flex items-center gap-3 rounded-btn p-2 hover:bg-surface cursor-pointer">
                        <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-accent" checked={auditRun.selectedCpIds.includes(cp.id)} onChange={() => auditRun.toggleCheckpoint(cp.id)} />
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-text-primary truncate">{cp.parsed.title}</p>
                          <p className="text-xs text-text-muted truncate">{cp.parsed.category}</p>
                        </div>
                      </label>
                    ))}
                    {finalCheckpoints.length === 0 && <p className="text-sm text-text-muted py-4 text-center">暂无审查要点，请先在审核点库中创建。</p>}
                  </div>
                  <Button className="w-full" disabled={auditRun.selectedCpIds.length === 0 || auditRun.startingAudit} onClick={auditRun.handleStartAudit}>
                    {auditRun.startingAudit ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                    开始审核（{auditRun.selectedCpIds.length} 个要点）
                  </Button>
                </div>
              ) : (
                <EmptyState title="请先完成前两步" description="选择项目并上传招标文件后，即可选择审查要点。" />
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
