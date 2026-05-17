import type { GovCheckpointPayload, GovFinding, PointRunStatus } from "@/types/ui";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/StatusBadge";

const SEVERITY_LABEL: Record<string, string> = { critical: "高风险", major: "中风险", minor: "低风险" };
const SEVERITY_VARIANT: Record<string, "err" | "warn" | "default"> = { critical: "err", major: "warn", minor: "default" };

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
          {verdict && <StatusBadge status={verdict.verdict} />}
          <Badge variant={SEVERITY_VARIANT[checkpoint.severity] ?? "muted"}>{SEVERITY_LABEL[checkpoint.severity] ?? checkpoint.severity}</Badge>
          <Badge variant="outline">{checkpoint.category}</Badge>
        </div>
      </div>

      {!finding && pointStatus !== "completed" && (
        <p className="text-sm text-text-muted">该审核点尚未完成审查。</p>
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
