import type { GovCheckpointPayload, GovFinding, PointRunStatus } from "@/types/ui";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/StatusBadge";
import { cn } from "@/lib/utils";

const SEVERITY_LABEL: Record<string, string> = { critical: "高风险", major: "中风险", minor: "低风险" };
const SEVERITY_VARIANT: Record<string, "err" | "warn" | "default"> = { critical: "err", major: "warn", minor: "default" };
const VERDICT_PANEL_CLASS: Record<string, string> = {
  "合规": "border-status-ok/40 bg-status-ok-bg",
  "不合规": "border-status-err-border bg-status-err-bg",
  "存疑": "border-status-warn/40 bg-status-warn-bg",
};
const VERDICT_HINT_CLASS: Record<string, string> = {
  "合规": "text-status-ok",
  "不合规": "text-status-err",
  "存疑": "text-status-warn",
};
const VERDICT_HINT: Record<string, string> = {
  "合规": "该审核点未发现合规风险",
  "不合规": "该审核点存在合规风险",
  "存疑": "该审核点需要人工复核",
};

export function PointInsight({ checkpoint, finding, pointStatus }: {
  checkpoint: GovCheckpointPayload;
  finding: GovFinding | null;
  pointStatus: PointRunStatus;
}) {
  const verdict = finding?.verdict;

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-base font-semibold text-text-primary">{checkpoint.title}</h3>
        <div className="mt-2 flex items-center gap-2 flex-wrap">
          <Badge variant={SEVERITY_VARIANT[checkpoint.severity] ?? "muted"}>{SEVERITY_LABEL[checkpoint.severity] ?? checkpoint.severity}</Badge>
          <Badge variant="outline">{checkpoint.category}</Badge>
        </div>
      </div>

      {verdict ? (
        <div className={cn("rounded-card border p-4", VERDICT_PANEL_CLASS[verdict.verdict] ?? "border-gray-200 bg-gray-50")}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-medium text-text-muted">审核结论</p>
              <div className="mt-2">
                <StatusBadge status={verdict.verdict} size="lg" emphasis="strong" showIcon />
              </div>
            </div>
            <p className={cn("text-sm font-semibold", VERDICT_HINT_CLASS[verdict.verdict] ?? "text-text-secondary")}>
              {VERDICT_HINT[verdict.verdict] ?? verdict.verdict}
            </p>
          </div>
        </div>
      ) : (
        <div className="rounded-card border border-gray-200 bg-gray-50 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-medium text-text-primary">审核状态</p>
            <StatusBadge status={pointStatus} size="md" showIcon />
          </div>
          <p className="mt-2 text-sm text-text-muted">
            {pointStatus === "completed" ? "已完成，但未返回合规结论。" : "该审核点尚未完成审查。"}
          </p>
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
