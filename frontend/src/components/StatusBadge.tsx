import { Badge } from "@/components/ui/badge";
import type { PointRunStatus, VerdictValue } from "@/types/ui";

const STATUS_CONFIG: Record<string, { label: string; variant: "ok" | "warn" | "err" | "default" | "muted" }> = {
  "合规": { label: "合规通过", variant: "ok" },
  "不合规": { label: "不合规", variant: "err" },
  "存疑": { label: "存疑待定", variant: "warn" },
  pending: { label: "等待中", variant: "muted" },
  running: { label: "审查中", variant: "default" },
  completed: { label: "已完成", variant: "ok" },
  failed: { label: "失败", variant: "err" },
  waiting_retry: { label: "待重试", variant: "warn" },
};

export function StatusBadge({ status }: { status: VerdictValue | PointRunStatus | string }) {
  const config = STATUS_CONFIG[status] ?? { label: status, variant: "muted" as const };
  return <Badge variant={config.variant}>{config.label}</Badge>;
}
