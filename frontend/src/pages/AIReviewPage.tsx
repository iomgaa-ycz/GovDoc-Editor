import { useState } from "react";

import { useWorkbench } from "../context/V3WorkbenchContext";
import { useProjectWorkflow } from "../hooks/useProjectWorkflow";
import { useAuditRun } from "../hooks/useAuditRun";
import { parseFindingJson } from "../adapters/backendToUi";
import { Card, CardHeader, EmptyState, InlineNotice, PageHero } from "../components/Ui";
import { PointInsight } from "../components/PointInsight";
import { Modal } from "../components/Modal";
import { TenderUploadPanel } from "../components/TenderUploadPanel";
import { CheckpointPicker } from "../components/CheckpointPicker";
import { AuditProgressPanel } from "../components/AuditProgressPanel";

export function AIReviewPage() {
  const {
    apiConnected,
    projects,
    activeProject,
    selectedProjectId,
    setSelectedProjectId,
    auditInputDocs,
    finalCheckpoints,
    auditProgress,
    logs,
    retryPointRun,
  } = useWorkbench();

  const wf = useProjectWorkflow();
  const auditRun = useAuditRun();
  const [detailPointRunId, setDetailPointRunId] = useState<string | null>(null);

  const inputDocs = activeProject ? auditInputDocs[activeProject.id] : undefined;
  const mainDoc = inputDocs?.mainDoc;
  const supplementaryDocs = inputDocs?.supplementaryDocs ?? [];
  const hasPendingUpload = Boolean(wf.mainTenderFile || wf.supplementaryFiles.length > 0);

  return (
    <>
      <PageHero
        eyebrow="AI批量审核"
        title="项目审核"
        description="选择项目与审核点，启动 AI 批量审查。"
      />

      {!apiConnected && <InlineNotice tone="warning" message="后端 API 未连通。" />}

      <div className="triple-layout">
        <div className="left-column">
          <Card>
            <CardHeader title="任务设置" />
            <div className="modal-form">
              <TenderUploadPanel
                projects={projects}
                activeProject={activeProject}
                selectedProjectId={selectedProjectId}
                setSelectedProjectId={setSelectedProjectId}
                mainDoc={mainDoc}
                supplementaryDocs={supplementaryDocs}
                newProjectName={wf.newProjectName}
                setNewProjectName={wf.setNewProjectName}
                creating={wf.creating}
                handleCreateProject={wf.handleCreateProject}
                mainTenderFile={wf.mainTenderFile}
                setMainTenderFile={wf.setMainTenderFile}
                supplementaryFiles={wf.supplementaryFiles}
                setSupplementaryFiles={wf.setSupplementaryFiles}
                uploadingTender={wf.uploadingTender}
                handleUploadTender={wf.handleUploadTender}
                uploadError={wf.uploadError}
              />

              {mainDoc && !hasPendingUpload && !auditProgress && (
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

        <AuditProgressPanel
          auditProgress={auditProgress}
          logs={logs}
          finalCheckpoints={finalCheckpoints}
          retryPointRun={retryPointRun}
          onPointRunClick={setDetailPointRunId}
        />
      </div>

      <Modal
        open={detailPointRunId != null}
        title="审核点详情"
        width="lg"
        onClose={() => setDetailPointRunId(null)}
      >
        {detailPointRunId && (() => {
          const pr = auditProgress?.point_runs.find((p) => p.id === detailPointRunId);
          const cp = pr ? finalCheckpoints.find((c) => c.id === pr.checkpoint_final_id)?.parsed ?? null : null;
          if (!cp || !pr) return <EmptyState title="无法加载" description="找不到该审核点的数据。" />;
          return <PointInsight checkpoint={cp} finding={parseFindingJson(pr.finding_json ?? null)} pointStatus={pr.status} />;
        })()}
      </Modal>
    </>
  );
}
