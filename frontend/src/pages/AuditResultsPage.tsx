import { RefreshCw, Send } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useWorkbench } from "@/context/V3WorkbenchContext";
import { parseFindingJson } from "@/adapters/backendToUi";
import { listComments, createComment } from "@/api/v3";
import type { Comment } from "@/types/ui";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { PointInsight } from "@/components/PointInsight";

export function AuditResultsPage() {
  const {
    auditRuns, auditProgress, selectedAuditRunId, setSelectedAuditRunId,
    selectedPointRunId, setSelectedPointRunId, finalCheckpoints, retryPointRun,
  } = useWorkbench();

  const selectedAuditProgress =
    auditProgress?.audit_run_id === selectedAuditRunId ? auditProgress : null;
  const pointRuns = selectedAuditProgress?.point_runs ?? [];
  const checkpointById = useMemo(
    () => new Map(finalCheckpoints.map((checkpoint) => [checkpoint.id, checkpoint])),
    [finalCheckpoints],
  );
  const pointRunViews = useMemo(() => pointRuns.map((pr) => {
    const checkpoint = checkpointById.get(pr.checkpoint_final_id)?.parsed ?? null;
    const finding = parseFindingJson(pr.finding_json);
    const verdict = finding?.verdict?.verdict;
    return {
      pr,
      checkpoint,
      finding,
      verdict,
      title: checkpoint?.title ?? "（已失效）",
    };
  }), [checkpointById, pointRuns]);
  const activePointRunView = pointRunViews.find((item) => item.pr.id === selectedPointRunId);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [feedbackText, setFeedbackText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (auditRuns.length === 0) return;
    if (selectedAuditRunId && auditRuns.some((r) => r.id === selectedAuditRunId)) return;
    setSelectedAuditRunId(auditRuns[0].id);
  }, [auditRuns, selectedAuditRunId, setSelectedAuditRunId]);

  useEffect(() => {
    setComments([]);
    if (!selectedPointRunId) return;
    let cancelled = false;
    listComments("AuditPointRun", selectedPointRunId).then((nextComments) => {
      if (!cancelled) setComments(nextComments);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [selectedPointRunId]);

  async function handleRetry(prId: string) {
    setRetryingId(prId);
    try { await retryPointRun(prId); } finally { setRetryingId(null); }
  }

  async function handleSubmitFeedback() {
    if (!selectedPointRunId || !feedbackText.trim()) return;
    setSubmitting(true);
    try {
      const c = await createComment("AuditPointRun", selectedPointRunId, "reviewer", feedbackText);
      setComments((prev) => [c, ...prev]);
      setFeedbackText("");
    } finally { setSubmitting(false); }
  }

  return (
    <div className="flex flex-col h-screen">
      <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
        <span className="text-base font-semibold text-text-primary">审核结果</span>
        <Select value={selectedAuditRunId ?? ""} onValueChange={(v: string) => setSelectedAuditRunId(v || null)}>
          <SelectTrigger className="w-56"><SelectValue placeholder="选择审核运行" /></SelectTrigger>
          <SelectContent>
            {auditRuns.map((r) => (
              <SelectItem key={r.id} value={r.id}>{r.project_name || r.id.slice(0, 8)} ({r.status})</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </header>

      {pointRuns.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <EmptyState title="暂无审核结果" description="请先完成一次审核运行。" />
        </div>
      ) : (
        <div className="flex flex-1 overflow-hidden">
          <div className="flex w-96 shrink-0 flex-col overflow-hidden border-r bg-surface-card">
            <div className="shrink-0 border-b p-4">
              <p className="text-sm font-medium text-text-primary">审核要点列表</p>
              <p className="text-xs text-text-muted">{pointRuns.length} 个审核点</p>
            </div>
            <div className="audit-points-scrollbar min-h-0 flex-1">
              {pointRunViews.map(({ pr, title, verdict }) => {
                return (
                  <button
                    key={pr.id}
                    className={cn(
                      "grid min-h-[68px] w-full grid-cols-[minmax(0,1fr)_7rem] items-center gap-3 border-b border-l-4 border-l-transparent px-5 py-3 pr-6 text-left transition-colors hover:bg-surface",
                      verdict === "合规" && "border-l-status-ok/70 bg-status-ok-bg/40 hover:bg-status-ok-bg",
                      verdict === "不合规" && "border-l-status-err bg-status-err-bg hover:bg-red-50",
                      verdict === "存疑" && "border-l-status-warn bg-status-warn-bg hover:bg-amber-50",
                      pr.id === selectedPointRunId && "ring-1 ring-inset ring-accent",
                    )}
                    onClick={() => setSelectedPointRunId(pr.id)}
                  >
                    <span className="min-w-0 truncate text-sm leading-5">{title}</span>
                    <StatusBadge status={verdict ?? pr.status} size="sm" emphasis={verdict ? "strong" : "subtle"} showIcon={!!verdict} className="w-full justify-center" />
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex-1 overflow-auto p-7 space-y-5">
            {activePointRunView ? (
              activePointRunView.checkpoint ? (
                <>
                  <PointInsight checkpoint={activePointRunView.checkpoint} finding={activePointRunView.finding} pointStatus={activePointRunView.pr.status} />
                  {(activePointRunView.pr.status === "failed" || activePointRunView.pr.status === "waiting_retry") && (
                    <Button variant="secondary" disabled={retryingId === activePointRunView.pr.id} onClick={() => handleRetry(activePointRunView.pr.id)}>
                      <RefreshCw className={cn("h-4 w-4", retryingId === activePointRunView.pr.id && "animate-spin")} />
                      {retryingId === activePointRunView.pr.id ? "正在重试..." : "重试此审核点"}
                    </Button>
                  )}
                  <Separator />
                  <div>
                    <h4 className="text-sm font-medium text-text-primary mb-3">人工反馈</h4>
                    <div className="flex gap-2 mb-4">
                      <Textarea placeholder="输入审查意见或修改建议..." value={feedbackText} onChange={(e) => setFeedbackText(e.target.value)} className="flex-1" />
                      <Button size="icon" disabled={!feedbackText.trim() || submitting} onClick={handleSubmitFeedback}><Send className="h-4 w-4" /></Button>
                    </div>
                    {comments.map((c) => (
                      <div key={c.id} className="border-b py-2.5 last:border-0">
                        <p className="text-sm text-text-primary">{c.text}</p>
                        <p className="text-xs text-text-muted mt-1">{c.author} · {new Date(c.created_at).toLocaleString("zh-CN")}</p>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <EmptyState title="审核点数据已失效" description="该审核点对应的审查标准已被删除或重新导入，无法显示详细结果。请使用当前审查标准重新发起审核。" />
              )
            ) : (
              <div className="flex-1 flex items-center justify-center h-full">
                <EmptyState title="请选择审核点" description="点击左侧列表查看详细审查结果。" />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
