import { RefreshCw } from "lucide-react";
import { useState } from "react";

import { useWorkbench } from "../context/V3WorkbenchContext";
import {
  parseCheckpointPayload,
  parseFindingJson,
  verdictToStatus,
} from "../adapters/backendToUi";
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
    activeAuditRun,
    auditRuns,
    auditProgress,
    selectedAuditRunId,
    setSelectedAuditRunId,
    selectedPointRunId,
    setSelectedPointRunId,
    finalCheckpoints,
    retryPointRun,
  } = useWorkbench();

  const pointRuns = auditProgress?.point_runs ?? [];
  const activePr = pointRuns.find((pr) => pr.id === selectedPointRunId);

  const [retryingId, setRetryingId] = useState<string | null>(null);

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

  function getCheckpoint(pr: { checkpoint_final_id: string }) {
    const cp = finalCheckpoints.find((c) => c.id === pr.checkpoint_final_id);
    return cp?.parsed ?? null;
  }

  return (
    <>
      <PageHero
        eyebrow="审核点结果"
        title="审核结果详情"
        description="查看每个审核点的 AI 审查结果与人工反馈。"
        actions={
          <div className="hero-side">
            <SelectInput
              value={selectedAuditRunId ?? ""}
              onChange={(e) => setSelectedAuditRunId(e.target.value || null)}
              style={{ minWidth: 200 }}
            >
              <option value="">选择审核运行</option>
              {auditRuns.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.id.slice(0, 8)}... ({r.status})
                </option>
              ))}
            </SelectInput>
          </div>
        }
      />

      {pointRuns.length === 0 ? (
        <EmptyState
          title="暂无审核结果"
          description="请先完成一次审核运行。"
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
                  const title = cp?.title ?? pr.checkpoint_final_id.slice(0, 8);
                  const finding = parseFindingJson(pr.finding_json);
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
              if (!cp) return <EmptyState title="无法加载" description="找不到该审核点数据。" />;
              return (
                <>
                  <PointInsight checkpoint={cp} finding={finding} pointStatus={activePr.status} />
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
