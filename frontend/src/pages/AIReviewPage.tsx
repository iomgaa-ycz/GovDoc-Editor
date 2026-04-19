import { RefreshCw } from "lucide-react";
import { useState } from "react";

import { useWorkbench } from "../context/V3WorkbenchContext";
import { useProjectWorkflow } from "../hooks/useProjectWorkflow";
import { useAuditRun } from "../hooks/useAuditRun";
import { parseCheckpointPayload, parseFindingJson, verdictToStatus } from "../adapters/backendToUi";
import {
  Button,
  Card,
  CardHeader,
  EmptyState,
  InlineNotice,
  LogConsole,
  MetricCard,
  PageHero,
  ProgressBar,
  StatPill,
} from "../components/Ui";
import { PointInsight } from "../components/PointInsight";
import { Modal } from "../components/Modal";
import { TenderUploadPanel } from "../components/TenderUploadPanel";
import { CheckpointPicker } from "../components/CheckpointPicker";

export function AIReviewPage() {
  const {
    apiConnected,
    projects,
    activeProject,
    selectedProjectId,
    setSelectedProjectId,
    tenderDocs,
    finalCheckpoints,
    auditProgress,
    logs,
    retryPointRun,
  } = useWorkbench();

  // Task setup state (extracted to useProjectWorkflow)
  const wf = useProjectWorkflow();

  // Audit-run start state (extracted to useAuditRun)
  const auditRun = useAuditRun();

  // Point detail modal
  const [detailPointRunId, setDetailPointRunId] = useState<string | null>(null);

  const tenderDoc = activeProject ? tenderDocs[activeProject.id] : undefined;
  const isRunning = auditProgress?.status === "running" || auditProgress?.status === "pending";

  const completedCount = auditProgress?.point_runs.filter((pr) => pr.status === "completed").length ?? 0;
  const failedCount = auditProgress?.point_runs.filter((pr) => pr.status === "failed").length ?? 0;
  const pendingCount = auditProgress?.point_runs.filter((pr) => pr.status === "pending" || pr.status === "running").length ?? 0;
  const total = auditProgress?.total_count ?? 0;

  // ── Find checkpoint payload for a point run ──

  function getCheckpointForPointRun(prId: string) {
    const pr = auditProgress?.point_runs.find((p) => p.id === prId);
    if (!pr) return null;
    const cp = finalCheckpoints.find((c) => c.id === pr.checkpoint_final_id);
    return cp?.parsed ?? null;
  }

  // ── Render ──

  return (
    <>
      <PageHero
        eyebrow="AI批量审核"
        title="项目审核"
        description="选择项目与审核点，启动 AI 批量审查。"
      />

      {!apiConnected && (
        <InlineNotice tone="warning" message="后端 API 未连通。" />
      )}

      <div className="triple-layout">
        {/* Left: Task setup */}
        <div className="left-column">
          <Card>
            <CardHeader title="任务设置" />
            <div className="modal-form">
              <TenderUploadPanel
                projects={projects}
                activeProject={activeProject}
                selectedProjectId={selectedProjectId}
                setSelectedProjectId={setSelectedProjectId}
                tenderDoc={tenderDoc}
                newProjectName={wf.newProjectName}
                setNewProjectName={wf.setNewProjectName}
                creating={wf.creating}
                handleCreateProject={wf.handleCreateProject}
                tenderFile={wf.tenderFile}
                setTenderFile={wf.setTenderFile}
                uploadingTender={wf.uploadingTender}
                handleUploadTender={wf.handleUploadTender}
              />

              {tenderDoc && !auditProgress && (
                <CheckpointPicker
                  checkpoints={finalCheckpoints}
                  selectedIds={auditRun.selectedCpIds}
                  onToggle={auditRun.toggleCheckpoint}
                  onStart={auditRun.handleStartAudit}
                  startingAudit={auditRun.startingAudit}
                />
              )}
            </div>
          </Card>
        </div>

        {/* Center: Progress */}
        <div className="center-column">
          <Card>
            <CardHeader title="审核进度" />
            {auditProgress ? (
              <>
                <ProgressBar value={total > 0 ? (completedCount / total) * 100 : 0} />
                <div className="metric-grid">
                  <MetricCard label="总计" value={total} tone="blue" />
                  <MetricCard label="已完成" value={completedCount} tone="green" />
                  <MetricCard label="失败" value={failedCount} tone="amber" />
                  <MetricCard label="待处理" value={pendingCount} />
                </div>
              </>
            ) : (
              <EmptyState title="尚未启动" description="请在左侧配置任务后启动审核。" />
            )}
          </Card>

          {logs.length > 0 && (
            <Card>
              <CardHeader title="运行日志" />
              <LogConsole logs={logs} />
            </Card>
          )}
        </div>

        {/* Right: Point status list */}
        <div className="right-column">
          <Card>
            <CardHeader title="审核点进度" />
            {auditProgress && auditProgress.point_runs.length > 0 ? (
              <div className="review-point-list">
                {auditProgress.point_runs.map((pr) => {
                  const cp = finalCheckpoints.find((c) => c.id === pr.checkpoint_final_id);
                  const title = cp?.parsed?.title ?? pr.checkpoint_final_id.slice(0, 8);
                  const status = verdictToStatus(
                    parseFindingJson(pr.finding_json),
                    pr.status,
                  );
                  const statusClass =
                    status === "running" ? "review-point-item--running"
                    : status === "passed" ? "review-point-item--passed"
                    : status === "error" ? "review-point-item--failed"
                    : "";
                  return (
                    <button
                      key={pr.id}
                      className={`review-point-item ${statusClass}`}
                      type="button"
                      onClick={() => setDetailPointRunId(pr.id)}
                    >
                      <div className="review-point-copy">
                        <strong>{title}</strong>
                        <span>
                          <StatPill status={status} />
                        </span>
                      </div>
                      {status === "error" && (
                        <Button
                          size="sm"
                          tone="ghost"
                          icon={RefreshCw}
                          onClick={(e) => { e.stopPropagation(); retryPointRun(pr.id); }}
                        >
                          重试
                        </Button>
                      )}
                    </button>
                  );
                })}
              </div>
            ) : (
              <EmptyState title="无审核点" description="启动审核后这里将显示每个审核点的状态。" />
            )}
          </Card>
        </div>
      </div>

      {/* Point detail modal */}
      <Modal
        open={detailPointRunId != null}
        title="审核点详情"
        width="lg"
        onClose={() => setDetailPointRunId(null)}
      >
        {detailPointRunId && (() => {
          const pr = auditProgress?.point_runs.find((p) => p.id === detailPointRunId);
          const cp = getCheckpointForPointRun(detailPointRunId);
          const finding = parseFindingJson(pr?.finding_json ?? null);
          if (!cp || !pr) return <EmptyState title="无法加载" description="找不到该审核点的数据。" />;
          return <PointInsight checkpoint={cp} finding={finding} pointStatus={pr.status} />;
        })()}
      </Modal>
    </>
  );
}
