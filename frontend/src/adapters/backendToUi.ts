import type {
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
    parts.push(`<table style="width:100%;border-collapse:collapse;">`);
    parts.push(`<thead><tr>`);
    parts.push(`<th style="border:1px solid #ddd;padding:8px;text-align:left;width:35%;">问题</th>`);
    parts.push(`<th style="border:1px solid #ddd;padding:8px;text-align:left;width:30%;">建议</th>`);
    parts.push(`<th style="border:1px solid #ddd;padding:8px;text-align:left;width:35%;">原文出处</th>`);
    parts.push(`</tr></thead><tbody>`);
    for (const f of wp.findings) {
      const cp = f.checkpoint;
      const v = f.verdict;
      // 判定徽章颜色
      const verdictColor: Record<string, string> = {
        "合规": "#16a34a",
        "不合规": "#dc2626",
        "存疑": "#d97706",
      };
      const verdictBg: Record<string, string> = {
        "合规": "#dcfce7",
        "不合规": "#fee2e2",
        "存疑": "#fef3c7",
      };
      const vc = verdictColor[v.verdict] ?? "#666";
      const vbg = verdictBg[v.verdict] ?? "#f3f4f6";
      const verdictBadge = `<span style="display:inline-block;padding:1px 8px;border-radius:4px;color:${vc};background:${vbg};font-weight:600;">${escapeHtml(verdictLabel(v.verdict))}</span>`;
      // 问题列：标题 + 判定徽章 + 严重程度/分类 + 法律依据
      const problemParts: string[] = [
        `<strong>${escapeHtml(cp.title)}</strong>`,
        `<br/><small>${verdictBadge} ${escapeHtml(cp.severity)} | ${escapeHtml(cp.category)}</small>`,
      ];
      if (v.rationale) {
        problemParts.push(`<br/><span style="color:#666;">${escapeHtml(v.rationale)}</span>`);
      }
      if (cp.legal_basis.length > 0) {
        problemParts.push(`<br/><small style="color:#888;">法律依据: ${cp.legal_basis.map(lb => `${escapeHtml(lb.law_name)} ${escapeHtml(lb.article)}`).join("；")}</small>`);
      }
      // 建议列
      const suggestionText = v.suggestion ? escapeHtml(v.suggestion) : "（无）";
      // 原文出处列：evidence_quotes + evidence_refs
      const sourceParts: string[] = [];
      if (v.evidence_quotes.length > 0) {
        for (const q of v.evidence_quotes) {
          sourceParts.push(`<blockquote style="margin:2px 0;padding:4px 8px;border-left:3px solid #ddd;color:#555;">${escapeHtml(q)}</blockquote>`);
        }
      }
      if (f.evidence_refs.length > 0) {
        for (const ref of f.evidence_refs) {
          sourceParts.push(`<blockquote style="margin:2px 0;padding:4px 8px;border-left:3px solid #ddd;color:#555;">${escapeHtml(ref.text)}</blockquote>`);
        }
      }
      if (sourceParts.length === 0) {
        sourceParts.push(`<span style="color:#999;">（无）</span>`);
      }
      parts.push(`<tr>`);
      parts.push(`<td style="border:1px solid #ddd;padding:8px;vertical-align:top;">${problemParts.join("")}</td>`);
      parts.push(`<td style="border:1px solid #ddd;padding:8px;vertical-align:top;">${suggestionText}</td>`);
      parts.push(`<td style="border:1px solid #ddd;padding:8px;vertical-align:top;">${sourceParts.join("")}</td>`);
      parts.push(`</tr>`);
    }
    parts.push(`</tbody></table>`);
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
