import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useWorkbench } from "../context/V3WorkbenchContext";
import {
  parseFindingJson,
  verdictToStatus,
} from "../adapters/backendToUi";
import { formatAuditRunOptionLabel } from "../utils/auditRunLabel";
import { AuditRunCurrentInfo } from "../components/AuditRunCurrentInfo";
import {
  Button,
  Card,
  CardHeader,
  EmptyState,
  PageHero,
  SelectInput,
  StatPill,
  TextArea,
} from "../components/Ui";
import { PointInsight } from "../components/PointInsight";

export function AuditResultsPage() {
  const {
    auditRuns,
    auditProgress,
    selectedAuditRunId,
    setSelectedAuditRunId,
    loadAuditRunProgress,
    selectedPointRunId,
    setSelectedPointRunId,
    finalCheckpoints,
    projects,
    auditInputDocs,
    retryPointRun,
  } = useWorkbench();

  const pointRuns =
    selectedAuditRunId && auditProgress?.audit_run_id === selectedAuditRunId
      ? auditProgress.point_runs
      : [];
  const activePr = pointRuns.find((pr) => pr.id === selectedPointRunId);
  const selectedAuditRun = auditRuns.find((r) => r.id === selectedAuditRunId);

  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [loadingRunId, setLoadingRunId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [requestedRunId, setRequestedRunId] = useState<string | null>(null);

  async function handleRetry(prId: string) {
    setRetryingId(prId);
    try {
      await retryPointRun(prId);
    } finally {
      setRetryingId(null);
    }
  }

  // Feedback state (local only — V3 has no feedback API yet)
  const [feedbackNotes, setFeedbackNotes] = useState("");

  const handleSelectRun = useCallback(async (id: string) => {
    const nextId = id || null;
    setSelectedAuditRunId(nextId);
    setSelectedPointRunId(null);
    setFeedbackNotes("");
    setLoadError(null);
    setRequestedRunId(nextId);

    if (!nextId) {
      setLoadingRunId(null);
      return;
    }

    setLoadingRunId(nextId);
    try {
      await loadAuditRunProgress(nextId);
    } catch {
      setLoadError("审核结果加载失败，请重新选择或稍后重试。");
    } finally {
      setLoadingRunId((current) => (current === nextId ? null : current));
    }
  }, [loadAuditRunProgress, setSelectedAuditRunId, setSelectedPointRunId]);

  function getCheckpoint(pr: { checkpoint_final_id: string }) {
    const cp = finalCheckpoints.find((c) => c.id === pr.checkpoint_final_id);
    return cp?.parsed ?? null;
  }

  const isLoadingSelectedRun = Boolean(selectedAuditRunId && loadingRunId === selectedAuditRunId);

  useEffect(() => {
    if (!selectedAuditRunId) return;
    if (auditProgress?.audit_run_id === selectedAuditRunId) return;
    if (loadingRunId === selectedAuditRunId || loadError || requestedRunId === selectedAuditRunId) return;
    void handleSelectRun(selectedAuditRunId);
  }, [
    selectedAuditRunId,
    auditProgress?.audit_run_id,
    loadingRunId,
    loadError,
    requestedRunId,
    handleSelectRun,
  ]);

  return (
    <>
      <PageHero
        eyebrow="审核点结果"
        title="审核结果详情"
        description="查看每个审核点的 AI 审查结果与人工反馈。"
        actions={
          <div className="audit-run-select">
            <SelectInput
              value={selectedAuditRunId ?? ""}
              onChange={(e) => handleSelectRun(e.target.value)}
              style={{ minWidth: 0 }}
            >
              <option value="">选择审核运行</option>
              {auditRuns.map((r) => (
                <option key={r.id} value={r.id}>
                  {formatAuditRunOptionLabel({ run: r, projects, auditInputDocs })}
                </option>
              ))}
            </SelectInput>
          </div>
        }
      />

      <AuditRunCurrentInfo
        run={selectedAuditRun}
        projects={projects}
        auditInputDocs={auditInputDocs}
      />

      {!selectedAuditRunId ? (
        <EmptyState
          title="请选择审核运行"
          description="选择一次已创建的审核运行后，可查看每个审核点的结果。"
        />
      ) : isLoadingSelectedRun ? (
        <EmptyState
          title="正在加载审核结果"
          description="正在读取该次审核运行的审核点结果。"
        />
      ) : loadError ? (
        <EmptyState
          title="加载失败"
          description={loadError}
        />
      ) : pointRuns.length === 0 ? (
        <EmptyState
          title="暂无审核点结果"
          description="该审核运行暂时没有可展示的审核点结果。"
        />
      ) : (
        <div className="triple-layout--results triple-layout">
          {/* Left: point list */}
          <div className="left-column">
            <Card>
              <CardHeader title="审核点列表" />
              <div className="result-point-list">
                {pointRuns.map((pr) => {
                  const cp = getCheckpoint(pr);
                  const finding = parseFindingJson(pr.finding_json);
                  const title =
                    cp?.title ?? finding?.checkpoint?.title ?? pr.checkpoint_final_id.slice(0, 8);
                  const status = verdictToStatus(finding, pr.status);
                  return (
                    <button
                      key={pr.id}
                      className={`result-point-item${pr.id === selectedPointRunId ? " is-active" : ""}`}
                      type="button"
                      onClick={() => setSelectedPointRunId(pr.id)}
                    >
                      <div>
                        <strong>{title}</strong>
                        <span><StatPill status={status} /></span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </Card>
          </div>

          {/* Center: insight detail */}
          <div className="center-column">
            {activePr ? (() => {
              const cp = getCheckpoint(activePr);
              const finding = parseFindingJson(activePr.finding_json);
              const checkpoint = cp ?? finding?.checkpoint;
              if (!checkpoint) return <EmptyState title="无法加载" description="找不到该审核点数据。" />;
              return (
                <>
                  <PointInsight checkpoint={checkpoint} finding={finding} pointStatus={activePr.status} />
                  {(activePr.status === "failed" || activePr.status === "waiting_retry") && (
                    <div style={{ marginTop: 12 }}>
                      <Button
                        tone="secondary"
                        icon={RefreshCw}
                        busy={retryingId === activePr.id}
                        disabled={retryingId === activePr.id}
                        onClick={() => handleRetry(activePr.id)}
                      >
                        {retryingId === activePr.id ? "正在重试..." : "重试此审核点"}
                      </Button>
                    </div>
                  )}
                </>
              );
            })() : (
              <EmptyState title="请选择审核点" description="点击左侧列表查看详细审查结果。" />
            )}
          </div>

          {/* Right: feedback */}
          <div className="right-column">
            <Card>
              <CardHeader title="人工反馈" />
              <div className="feedback-panel">
                <TextArea
                  placeholder="输入反馈意见（本地暂存，暂不支持提交）"
                  value={feedbackNotes}
                  onChange={(e) => setFeedbackNotes(e.target.value)}
                />
                <Button tone="secondary" disabled style={{ width: "100%" }}>
                  保存反馈（开发中）
                </Button>
                <p style={{ color: "var(--text-muted)", fontSize: 12, lineHeight: 1.6 }}>
                  V3 后端暂未提供 feedback API，此功能将在后续版本开放。
                </p>
              </div>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
