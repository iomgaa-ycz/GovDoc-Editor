import { Check, ChevronRight, FileText, Loader2, Paperclip, Plus, Upload, X } from "lucide-react";
import { useMemo, useState } from "react";

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
import { MetricCard } from "@/components/MetricCard";
import { StatusBadge } from "@/components/StatusBadge";
import { FileDropzone } from "@/components/FileDropzone";
import { EmptyState } from "@/components/EmptyState";
import { ProgressTimeline } from "@/components/ProgressTimeline";
import { PointInsight } from "@/components/PointInsight";

export function AIReviewPage() {
  const {
    projects, activeProject, selectedProjectId, setSelectedProjectId,
    auditInputDocs, finalCheckpoints, auditProgress, retryPointRun, resetProjectDocs,
  } = useWorkbench();

  const wf = useProjectWorkflow();
  const auditRun = useAuditRun();
  const [selectedTimelinePrId, setSelectedTimelinePrId] = useState<string | null>(null);

  const inputDocs = activeProject ? auditInputDocs[activeProject.id] : undefined;
  const mainDoc = inputDocs?.mainDoc;
  const supplementaryDocs = inputDocs?.supplementaryDocs ?? [];
  const isRunning = auditProgress != null;
  const pointRuns = auditProgress?.point_runs ?? [];
  const progress = auditProgress ? (auditProgress.total_count > 0 ? (auditProgress.processed_count / auditProgress.total_count) * 100 : 0) : 0;
  const completedCount = pointRuns.filter((p) => p.status === "completed").length;
  const failedCount = pointRuns.filter((p) => p.status === "failed").length;
  const runningCount = pointRuns.filter((p) => p.status === "running").length;
  const checkpointById = useMemo(
    () => new Map(finalCheckpoints.map((checkpoint) => [checkpoint.id, checkpoint])),
    [finalCheckpoints],
  );
  const pointRunViews = useMemo(() => pointRuns.map((pr) => {
    const checkpoint = checkpointById.get(pr.checkpoint_final_id)?.parsed ?? null;
    const finding = parseFindingJson(pr.finding_json ?? null);
    const verdict = finding?.verdict?.verdict;
    return {
      pr,
      checkpoint,
      finding,
      verdict,
      displayStatus: verdict ?? pr.status,
      title: checkpoint?.title ?? pr.checkpoint_final_id.slice(0, 8),
    };
  }), [checkpointById, pointRuns]);
  const selectedTimeline =
    pointRunViews.find((item) => item.pr.id === selectedTimelinePrId)
    ?? pointRunViews.find((item) => item.pr.status === "running")
    ?? pointRunViews[0];

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
                    {pointRunViews.map(({ pr, title, verdict, displayStatus }) => {
                      return (
                        <button
                          key={pr.id}
                          className={cn(
                            "flex w-full items-center justify-between gap-3 border-b border-l-4 border-l-transparent px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-surface",
                            verdict === "合规" && "border-l-status-ok/70 bg-status-ok-bg/40 hover:bg-status-ok-bg",
                            verdict === "不合规" && "border-l-status-err bg-status-err-bg hover:bg-red-50",
                            verdict === "存疑" && "border-l-status-warn bg-status-warn-bg hover:bg-amber-50",
                            pr.id === selectedTimeline?.pr.id && "ring-1 ring-inset ring-accent",
                          )}
                          onClick={() => setSelectedTimelinePrId(pr.id)}
                        >
                          <div className="flex min-w-0 flex-1 items-center gap-2">
                            <span className={cn(
                              "h-2.5 w-2.5 shrink-0 rounded-full",
                              verdict === "合规" && "bg-status-ok",
                              verdict === "不合规" && "bg-status-err",
                              verdict === "存疑" && "bg-status-warn",
                              !verdict && pr.status === "completed" && "bg-status-ok",
                              !verdict && pr.status === "running" && "bg-accent",
                              !verdict && pr.status === "failed" && "bg-status-err",
                              !verdict && pr.status === "pending" && "bg-gray-300",
                            )} />
                            <span className="text-sm truncate">{title}</span>
                          </div>
                          <StatusBadge status={displayStatus} size={verdict ? "md" : "sm"} emphasis={verdict ? "strong" : "subtle"} showIcon={!!verdict} className="shrink-0" />
                        </button>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
              {selectedTimeline && (
                <div className="space-y-4">
                  {selectedTimeline.checkpoint && (selectedTimeline.finding || selectedTimeline.pr.status === "completed") && (
                    <div className="rounded-card border bg-surface-card p-5">
                      <PointInsight checkpoint={selectedTimeline.checkpoint} finding={selectedTimeline.finding} pointStatus={selectedTimeline.pr.status} />
                    </div>
                  )}
                  <ProgressTimeline
                    pointRun={selectedTimeline.pr}
                    checkpoint={selectedTimeline.checkpoint}
                    onRetry={selectedTimeline.pr.status === "failed" ? () => retryPointRun(selectedTimeline.pr.id) : undefined}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
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
                <CardHeader><CardTitle>第二步：上传招标文书</CardTitle></CardHeader>
                <CardContent className="space-y-4">
                  {/* 主招标文书 */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-text-secondary">主招标文书</label>
                    {mainDoc ? (
                      <div className="flex items-center gap-2 rounded-card border border-green-300 bg-green-50 p-3">
                        <Check className="h-4 w-4 shrink-0 text-green-600" />
                        <span className="min-w-0 flex-1 truncate text-sm">{mainDoc.filename}</span>
                        <button type="button" className="text-xs text-red-500 hover:text-red-700" onClick={() => resetProjectDocs(activeProject.id)}>移除</button>
                      </div>
                    ) : wf.mainTenderFile ? (
                      <div className="flex items-center gap-2 rounded-card border p-3">
                        <FileText className="h-4 w-4 shrink-0 text-text-muted" />
                        <span className="min-w-0 flex-1 truncate text-sm">{wf.mainTenderFile.name}</span>
                        <button type="button" className="text-xs text-red-500 hover:text-red-700" onClick={() => wf.setMainTenderFile(null)}>移除</button>
                      </div>
                    ) : (
                      <FileDropzone title="点击选择或拖入招标文书" subtitle="支持 .docx, .pdf" accept=".docx,.pdf" onSelect={(files) => { if (files[0]) wf.setMainTenderFile(files[0]); }} />
                    )}
                  </div>

                  {/* 补充文件（主文件选择后才显示） */}
                  {(wf.mainTenderFile || mainDoc) && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-medium text-text-secondary">补充文件（可选）</label>
                        {(wf.supplementaryFiles.length > 0 || supplementaryDocs.length > 0) && (
                          <span className="flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-600">
                            <Paperclip className="h-3 w-3" />
                            {wf.supplementaryFiles.length + supplementaryDocs.length} 个文件
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-text-muted">变更公告、答疑纪要、补充通知等</p>

                      {/* 已上传的附件 */}
                      {supplementaryDocs.map((doc) => (
                        <div key={doc.id} className="flex items-center gap-2 rounded-card border bg-gray-50 px-3 py-2">
                          <FileText className="h-4 w-4 shrink-0 text-text-muted" />
                          <span className="min-w-0 flex-1 truncate text-sm">{doc.filename}</span>
                        </div>
                      ))}

                      {/* 待上传的附件列表 */}
                      {wf.supplementaryFiles.map((f, i) => (
                        <div key={`pending-${i}`} className="flex items-center gap-2 rounded-card border bg-gray-50 px-3 py-2">
                          <FileText className="h-4 w-4 shrink-0 text-text-muted" />
                          <span className="min-w-0 flex-1 truncate text-sm">{f.name}</span>
                          <button type="button" className="text-text-muted hover:text-red-500" onClick={() => wf.removeSupplementaryFile(i)}>
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ))}

                      {/* 添加更多附件 */}
                      {!mainDoc && (
                        <FileDropzone title="添加补充文件" subtitle="支持 .docx, .pdf，可多选" accept=".docx,.pdf" multiple onSelect={(files) => wf.addSupplementaryFiles(files)} />
                      )}
                    </div>
                  )}

                  {/* 确认上传按钮 */}
                  {wf.mainTenderFile && !mainDoc && (
                    <Button className="w-full" disabled={wf.uploadingTender} onClick={wf.handleUploadTender}>
                      {wf.uploadingTender ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                      确认上传{wf.supplementaryFiles.length > 0 ? `（含 ${wf.supplementaryFiles.length} 个附件）` : ""}
                    </Button>
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
