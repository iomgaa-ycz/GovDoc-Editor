import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { useWorkbench } from "../context/V3WorkbenchContext";
import {
  parseCheckpointPayload,
  parseFindingJson,
  verdictToStatus,
} from "../adapters/backendToUi";
import { listComments, createComment } from "../api/v3";
import type { Comment } from "../types/ui";
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

  const [comments, setComments] = useState<Comment[]>([]);
  const [feedbackText, setFeedbackText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!selectedPointRunId) return;
    listComments("AuditPointRun", selectedPointRunId).then(setComments).catch(() => {});
  }, [selectedPointRunId]);

  async function handleSubmitFeedback() {
    if (!selectedPointRunId || !feedbackText.trim()) return;
    setSubmitting(true);
    try {
      const comment = await createComment("AuditPointRun", selectedPointRunId, "reviewer", feedbackText);
      setComments((prev) => [comment, ...prev]);
      setFeedbackText("");
    } finally {
      setSubmitting(false);
    }
  }

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
                  placeholder="输入审查意见或修改建议"
                  value={feedbackText}
                  onChange={(e) => setFeedbackText(e.target.value)}
                />
                <Button
                  tone="primary"
                  onClick={handleSubmitFeedback}
                  busy={submitting}
                  disabled={!feedbackText.trim() || submitting}
                  style={{ width: "100%" }}
                >
                  提交反馈
                </Button>
                {comments.map((c) => (
                  <div key={c.id} style={{ padding: "8px 0", borderBottom: "1px solid var(--border-light)" }}>
                    <p style={{ margin: 0, fontSize: 13 }}>{c.text}</p>
                    <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{c.author} · {c.created_at}</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
