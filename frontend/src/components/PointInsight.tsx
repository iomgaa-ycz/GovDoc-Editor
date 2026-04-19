import { CheckCircle2, ShieldAlert } from "lucide-react";

import type { GovCheckpointPayload, GovFinding } from "../types/ui";
import {
  severityToRisk,
  verdictLabel,
  verdictToStatus,
} from "../adapters/backendToUi";
import { Card, CardHeader, EmptyState, StatPill, type ReviewStatus } from "./Ui";

export function PointInsight(props: {
  checkpoint: GovCheckpointPayload;
  finding: GovFinding | null;
  pointStatus?: string;
  compact?: boolean;
}) {
  const { checkpoint, finding, pointStatus } = props;
  const status = verdictToStatus(finding, pointStatus ?? "pending");

  if (!finding) {
    const isRetryable = status === "error";
    return (
      <div className={`insight-layout${props.compact ? " insight-layout--compact" : ""}`}>
        <Card>
          <CardHeader title={checkpoint.title} description={checkpoint.description} />
          <EmptyState
            title={
              isRetryable
                ? "该审核点执行失败，可点击重试"
                : "当前项目还没有生成这个审核点的审查结果"
            }
            description={
              isRetryable
                ? "AI 审查过程中发生了错误，请尝试重试此审核点。"
                : "请先运行项目审查，或切换到已有审核运行后再查看结构化分析。"
            }
          />
        </Card>
      </div>
    );
  }

  const riskLevel = severityToRisk(checkpoint.severity);
  const riskIcon = finding.verdict.verdict === "合规" ? (
    <CheckCircle2 size={16} />
  ) : (
    <ShieldAlert size={16} />
  );

  return (
    <div className={`insight-layout${props.compact ? " insight-layout--compact" : ""}`}>
      <Card>
        <CardHeader
          title={checkpoint.title}
          description={checkpoint.description}
          actions={
            <div className="insight-head-actions">
              <StatPill status={status as ReviewStatus} />
              <span className={`risk-pill risk-pill--${riskLevel}`}>
                {riskIcon}
                <span>{verdictLabel(finding.verdict.verdict)}</span>
              </span>
            </div>
          }
        />

        <div className="insight-columns">
          <div className="detail-section">
            <h4>判断理由</h4>
            <p>{finding.verdict.rationale}</p>
            <div className="detail-callout">
              <strong>AI 输出结论</strong>
              <p>{finding.verdict.suggestion || finding.verdict.verdict}</p>
            </div>
          </div>

          <div className="detail-section">
            <h4>证据引用</h4>
            <div className="evidence-list">
              {finding.verdict.evidence_quotes.map((quote, i) => (
                <article key={`eq-${i}`} className="evidence-card">
                  <p>{quote}</p>
                </article>
              ))}
              {finding.evidence_refs.map((ref, i) => (
                <article key={`er-${i}`} className="evidence-card">
                  <span className="evidence-source">{ref.chunk_id}</span>
                  <p>{ref.text}</p>
                </article>
              ))}
              {finding.verdict.evidence_quotes.length === 0 && finding.evidence_refs.length === 0 && (
                <p style={{ color: "var(--text-muted)" }}>无证据引用</p>
              )}
            </div>
          </div>
        </div>

        <div className="insight-columns">
          <div className="detail-section">
            <h4>命中材料</h4>
            <div className="evidence-list">
              {finding.evidence_refs.map((ref, i) => (
                <article key={`hit-${i}`} className="evidence-card">
                  <span className="evidence-source">{ref.chunk_id}</span>
                  <p>{ref.text}</p>
                </article>
              ))}
              {finding.evidence_refs.length === 0 && (
                <p style={{ color: "var(--text-muted)" }}>无命中材料</p>
              )}
            </div>
          </div>

          <div className="detail-section">
            <h4>法律依据</h4>
            <ul className="bullet-list">
              {checkpoint.legal_basis.map((lb, i) => (
                <li key={`lb-${i}`}>
                  {lb.law_name} {lb.article}: {lb.quote}
                </li>
              ))}
              {checkpoint.legal_basis.length === 0 && (
                <p style={{ color: "var(--text-muted)" }}>无法律依据</p>
              )}
            </ul>
          </div>
        </div>
      </Card>
    </div>
  );
}
