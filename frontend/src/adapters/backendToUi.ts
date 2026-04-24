import type {
  CheckpointItem,
  GovCheckpointPayload,
  GovFinding,
  WorkpaperPayload,
  AuditPointRun,
  LogEntry,
} from "../types/ui";

/* ── Checkpoint payload parsing ── */

export function parseCheckpointPayload(
  raw: string,
): GovCheckpointPayload | null {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function checkpointToDisplay(
  item: CheckpointItem,
): GovCheckpointPayload & { _id: string; _kind: "draft" | "final" } {
  const payload = parseCheckpointPayload(item.payload_json);
  return {
    ...(payload ?? {
      id: item.id,
      category: "其他违法违规" as const,
      title: "(解析失败)",
      description: "",
      legal_basis: [],
      severity: "minor" as const,
      retrieval_hint: "",
    }),
    _id: item.id,
    _kind: item.kind,
  };
}

/* ── Finding display helpers ── */

export function parseFindingJson(
  raw: string | null,
): GovFinding | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function verdictToStatus(
  finding: GovFinding | null,
  pointStatus: string,
): "pending" | "running" | "passed" | "failed" | "uncertain" | "error" {
  if (pointStatus === "pending") return "pending";
  if (pointStatus === "running") return "running";
  if (pointStatus === "failed" || pointStatus === "waiting_retry") return "error";
  // completed
  if (!finding) return "failed";
  const v = finding.verdict?.verdict;
  if (v === "合规") return "passed";
  if (v === "不合规") return "failed";
  if (v === "存疑") return "uncertain";
  return "failed";
}

export function severityToRisk(
  severity: string,
): "high" | "medium" | "low" {
  if (severity === "critical") return "high";
  if (severity === "major") return "medium";
  return "low";
}

export function verdictLabel(verdict: string): string {
  if (verdict === "合规") return "合规通过";
  if (verdict === "不合规") return "不合规";
  if (verdict === "存疑") return "存疑待定";
  return verdict;
}

/* ── Workpaper HTML → summary text ── */

export function extractSummaryFromHtml(html: string): string {
  const div = document.createElement("div");
  div.innerHTML = html;
  // Try to find the summary section: text after <h3>总结</h3>
  const headings = div.querySelectorAll("h3");
  for (const h of headings) {
    if (h.textContent?.trim() === "总结") {
      const next = h.nextElementSibling;
      if (next) return next.textContent?.trim() ?? "";
    }
  }
  return "";
}

/* ── Workpaper JSON → HTML ── */

export function workpaperToHtml(wp: WorkpaperPayload): string {
  const parts: string[] = [];

  parts.push(`<h2>审查工作底稿</h2>`);

  if (wp.summary) {
    parts.push(`<h3>总结</h3>`);
    parts.push(`<p>${escapeHtml(wp.summary)}</p>`);
  }

  if (wp.findings.length > 0) {
    parts.push(`<h3>审查发现 (${wp.findings.length})</h3>`);
    for (const f of wp.findings) {
      const cp = f.checkpoint;
      const v = f.verdict;
      parts.push(
        `<blockquote><strong>${escapeHtml(cp.title)}</strong> — ${escapeHtml(v.verdict)}</blockquote>`,
      );
      parts.push(`<p><strong>分类:</strong> ${escapeHtml(cp.category)} | <strong>严重程度:</strong> ${escapeHtml(cp.severity)}</p>`);
      if (v.rationale) {
        parts.push(`<p><strong>判断理由:</strong> ${escapeHtml(v.rationale)}</p>`);
      }
      if (v.evidence_quotes.length > 0) {
        parts.push(`<p><strong>证据引用:</strong></p><ul>`);
        for (const q of v.evidence_quotes) {
          parts.push(`<li>${escapeHtml(q)}</li>`);
        }
        parts.push(`</ul>`);
      }
      if (v.suggestion) {
        parts.push(`<p><strong>建议:</strong> ${escapeHtml(v.suggestion)}</p>`);
      }
      if (f.evidence_refs.length > 0) {
        parts.push(`<p><strong>命中材料:</strong></p><ul>`);
        for (const ref of f.evidence_refs) {
          parts.push(`<li>${escapeHtml(ref.text)}</li>`);
        }
        parts.push(`</ul>`);
      }
      if (cp.legal_basis.length > 0) {
        parts.push(`<p><strong>法律依据:</strong></p><ul>`);
        for (const lb of cp.legal_basis) {
          parts.push(`<li>${escapeHtml(lb.law_name)} ${escapeHtml(lb.article)}: ${escapeHtml(lb.quote)}</li>`);
        }
        parts.push(`</ul>`);
      }
      parts.push(`<hr/>`);
    }
  }

  return parts.join("\n");
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* ── Point run → log entry ── */

let logCounter = 0;

export function pointRunToLog(
  pr: AuditPointRun,
  checkpointTitle: string,
): LogEntry {
  const now = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  const level =
    pr.status === "completed"
      ? "success"
      : pr.status === "failed"
        ? "error"
        : "info";
  const message =
    pr.status === "completed"
      ? `✓ ${checkpointTitle} — 完成`
      : pr.status === "failed"
        ? `✗ ${checkpointTitle} — 失败${pr.error ? `: ${pr.error}` : ""}`
        : `→ ${checkpointTitle} — ${pr.status}`;
  return { id: `log-${++logCounter}`, time: now, level, message };
}
