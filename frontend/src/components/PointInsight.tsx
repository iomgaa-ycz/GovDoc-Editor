import { CircleCheck, CircleX, TriangleAlert, type LucideIcon } from "lucide-react";

import type { GovCheckpointPayload, GovFinding, PointRunStatus } from "@/types/ui";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/StatusBadge";

const SEVERITY_LABEL: Record<string, string> = { critical: "高风险", major: "中风险", minor: "低风险" };
const SEVERITY_VARIANT: Record<string, "err" | "warn" | "default"> = { critical: "err", major: "warn", minor: "default" };

const VERDICT_PANEL: Record<string, {
  bg: string; border: string; text: string; icon: LucideIcon; hint: string;
}> = {
  "合规": {
    bg: "bg-status-ok-bg", border: "border-status-ok/40", text: "text-status-ok",
    icon: CircleCheck, hint: "该审核点未发现合规风险",
  },
  "不合规": {
    bg: "bg-status-err-bg", border: "border-status-err-border", text: "text-status-err",
    icon: CircleX, hint: "该审核点存在合规风险",
  },
  "存疑": {
    bg: "bg-status-warn-bg", border: "border-status-warn/40", text: "text-status-warn",
    icon: TriangleAlert, hint: "该审核点需要人工复核",
  },
};

export function PointInsight({ checkpoint, finding, pointStatus }: {
  checkpoint: GovCheckpointPayload;
  finding: GovFinding | null;
  pointStatus: PointRunStatus;
}) {
  const verdict = finding?.verdict;
  const panel = verdict ? VERDICT_PANEL[verdict.verdict] : null;

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-base font-semibold text-text-primary">{checkpoint.title}</h3>
        <div className="mt-2 flex items-center gap-2 flex-wrap">
          <Badge variant={SEVERITY_VARIANT[checkpoint.severity] ?? "muted"}>{SEVERITY_LABEL[checkpoint.severity] ?? checkpoint.severity}</Badge>
          <Badge variant="outline">{checkpoint.category}</Badge>
        </div>
      </div>

      {panel && verdict ? (
        <div className={cn("flex items-center justify-between rounded-card border p-4", panel.bg, panel.border)}>
          <div className="flex items-center gap-3">
            <panel.icon className={cn("h-5 w-5 shrink-0", panel.text)} />
            <div>
              <p className="text-xs text-text-muted">审核结论</p>
              <p className={cn("text-base font-bold", panel.text)}>{verdict.verdict}</p>
            </div>
          </div>
          <p className={cn("text-sm font-semibold", panel.text)}>{panel.hint}</p>
        </div>
      ) : (
        <div className="flex items-center justify-between rounded-card border border-gray-200 bg-gray-50 p-4">
          <p className="text-sm font-medium text-text-primary">审核状态</p>
          <StatusBadge status={pointStatus} />
        </div>
      )}

      {verdict && (
        <>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="text-sm font-medium text-text-primary mb-2">审查意见</h4>
              <p className="text-sm text-text-secondary leading-relaxed">{verdict.rationale}</p>
            </div>
            <div>
              <h4 className="text-sm font-medium text-text-primary mb-2">整改建议</h4>
              <p className="text-sm text-text-secondary leading-relaxed">{verdict.suggestion}</p>
            </div>
          </div>

          {verdict.evidence_quotes.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-text-primary mb-2">原文引用</h4>
              <div className="space-y-2">
                {verdict.evidence_quotes.map((q, i) => (
                  <blockquote key={i} className="border-l-2 border-accent pl-3 text-sm text-text-secondary italic">"{q}"</blockquote>
                ))}
              </div>
            </div>
          )}

          {checkpoint.legal_basis.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-text-primary mb-2">法条依据</h4>
              <div className="space-y-2">
                {checkpoint.legal_basis.map((lb, i) => (
                  <div key={i} className="rounded-btn bg-accent-light px-3 py-2">
                    <p className="text-sm font-medium text-accent">{lb.law_name} {lb.article}</p>
                    {lb.quote && <p className="text-xs text-text-secondary mt-0.5">{lb.quote}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
