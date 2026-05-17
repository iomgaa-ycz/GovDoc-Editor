import { Check, Loader2, AlertCircle, Clock, RefreshCw } from "lucide-react";
import type { AuditPointRun, GovCheckpointPayload } from "@/types/ui";
import { cn } from "@/lib/utils";

type PhaseStep = { label: string; phase: "plan" | "execute" | "summarize" };

const STEPS: PhaseStep[] = [
  { label: "读取审查要点", phase: "plan" },
  { label: "检索招标文书", phase: "plan" },
  { label: "制定审核策略", phase: "plan" },
  { label: "定位证据段落", phase: "execute" },
  { label: "分析证据形成意见", phase: "execute" },
  { label: "汇总审查结果", phase: "summarize" },
];

const PHASE_ORDER = { plan: 0, execute: 1, summarize: 2 };

function getStepStatus(stepIndex: number, currentPhase: string | null, pointStatus: string): "done" | "active" | "pending" | "error" {
  if (pointStatus === "completed") return "done";
  if (pointStatus === "failed") {
    if (!currentPhase) return stepIndex === 0 ? "error" : "pending";
    const phaseIdx = PHASE_ORDER[currentPhase as keyof typeof PHASE_ORDER] ?? -1;
    const stepPhaseIdx = PHASE_ORDER[STEPS[stepIndex].phase];
    if (stepPhaseIdx < phaseIdx) return "done";
    if (stepPhaseIdx === phaseIdx) return "error";
    return "pending";
  }
  if (pointStatus !== "running" || !currentPhase) return "pending";
  const phaseIdx = PHASE_ORDER[currentPhase as keyof typeof PHASE_ORDER] ?? -1;
  const stepPhaseIdx = PHASE_ORDER[STEPS[stepIndex].phase];
  if (stepPhaseIdx < phaseIdx) return "done";
  if (stepPhaseIdx === phaseIdx) {
    const firstOfPhase = STEPS.findIndex((s) => s.phase === STEPS[stepIndex].phase);
    return stepIndex === firstOfPhase ? "active" : "pending";
  }
  return "pending";
}

export function ProgressTimeline({ pointRun, checkpoint, onRetry }: {
  pointRun: AuditPointRun;
  checkpoint: GovCheckpointPayload | null;
  onRetry?: () => void;
}) {
  return (
    <div className="rounded-card border bg-surface-card p-5">
      <h3 className="text-sm font-semibold text-text-primary mb-1">{checkpoint?.title ?? "审查进度"}</h3>
      {pointRun.started_at && (
        <p className="text-xs text-text-muted mb-4">开始于 {new Date(pointRun.started_at).toLocaleTimeString("zh-CN")}</p>
      )}
      <div className="space-y-0">
        {STEPS.map((step, i) => {
          const status = getStepStatus(i, pointRun.current_phase, pointRun.status);
          const isLast = i === STEPS.length - 1;
          return (
            <div key={i} className="flex gap-3">
              <div className="flex flex-col items-center">
                <div className={cn(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full",
                  status === "done" && "bg-status-ok",
                  status === "active" && "bg-accent",
                  status === "error" && "bg-status-err",
                  status === "pending" && "border-2 border-gray-200 bg-white",
                )}>
                  {status === "done" && <Check className="h-3.5 w-3.5 text-white" />}
                  {status === "active" && <Loader2 className="h-3.5 w-3.5 text-white animate-spin" />}
                  {status === "error" && <AlertCircle className="h-3.5 w-3.5 text-white" />}
                  {status === "pending" && <Clock className="h-3 w-3 text-gray-300" />}
                </div>
                {!isLast && <div className={cn("w-0.5 flex-1 min-h-[24px]", status === "done" ? "bg-status-ok" : "bg-gray-200")} />}
              </div>
              <div className="pb-4">
                <p className={cn("text-sm font-medium",
                  status === "done" && "text-text-primary",
                  status === "active" && "text-accent",
                  status === "error" && "text-status-err",
                  status === "pending" && "text-text-muted",
                )}>{step.label}</p>
                {status === "active" && <p className="text-xs text-text-muted mt-0.5">正在处理中...</p>}
              </div>
            </div>
          );
        })}
      </div>
      {pointRun.status === "failed" && onRetry && (
        <button onClick={onRetry} className="mt-2 flex items-center gap-1.5 text-sm text-accent hover:underline">
          <RefreshCw className="h-3.5 w-3.5" /> 点击重试
        </button>
      )}
    </div>
  );
}
