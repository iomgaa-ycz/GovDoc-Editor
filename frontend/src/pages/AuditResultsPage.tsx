import { RefreshCw, Send } from "lucide-react";
import { useEffect, useState } from "react";

import { useWorkbench } from "@/context/V3WorkbenchContext";
import { parseFindingJson, verdictToStatus } from "@/adapters/backendToUi";
import { listComments, createComment } from "@/api/v3";
import type { Comment } from "@/types/ui";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
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

  const pointRuns = auditProgress?.point_runs ?? [];
  const activePr = pointRuns.find((pr) => pr.id === selectedPointRunId);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [feedbackText, setFeedbackText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!selectedPointRunId) return;
    listComments("AuditPointRun", selectedPointRunId).then(setComments).catch(() => {});
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
          <div className="w-80 shrink-0 border-r bg-surface-card overflow-auto">
            <div className="p-4 border-b">
              <p className="text-sm font-medium text-text-primary">审核要点列表</p>
              <p className="text-xs text-text-muted">{pointRuns.length} 个审核点</p>
            </div>
            <ScrollArea className="h-[calc(100vh-120px)]">
              {pointRuns.map((pr) => {
                const cp = finalCheckpoints.find((c) => c.id === pr.checkpoint_final_id);
                const title = cp?.parsed?.title ?? pr.checkpoint_final_id.slice(0, 8);
                const finding = parseFindingJson(pr.finding_json);
                return (
                  <button key={pr.id} className={cn("flex w-full items-center justify-between px-4 py-3 text-left border-b hover:bg-surface transition-colors", pr.id === selectedPointRunId && "bg-accent-light border-l-2 border-l-accent")} onClick={() => setSelectedPointRunId(pr.id)}>
                    <span className="text-sm truncate mr-2">{title}</span>
                    <StatusBadge status={finding?.verdict?.verdict ?? pr.status} />
                  </button>
                );
              })}
            </ScrollArea>
          </div>

          <div className="flex-1 overflow-auto p-7 space-y-5">
            {activePr ? (() => {
              const cp = finalCheckpoints.find((c) => c.id === activePr.checkpoint_final_id);
              const finding = parseFindingJson(activePr.finding_json);
              if (!cp?.parsed) return <EmptyState title="无法加载" description="找不到该审核点数据。" />;
              return (
                <>
                  <PointInsight checkpoint={cp.parsed} finding={finding} pointStatus={activePr.status} />
                  {(activePr.status === "failed" || activePr.status === "waiting_retry") && (
                    <Button variant="secondary" disabled={retryingId === activePr.id} onClick={() => handleRetry(activePr.id)}>
                      <RefreshCw className={cn("h-4 w-4", retryingId === activePr.id && "animate-spin")} />
                      {retryingId === activePr.id ? "正在重试..." : "重试此审核点"}
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
              );
            })() : (
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
