import { AlertTriangle, CheckCircle2, CircleDashed, Clock3, Loader2, RotateCcw, XCircle, type LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { PointRunStatus, VerdictValue } from "@/types/ui";
import { cn } from "@/lib/utils";

type StatusVariant = "ok" | "warn" | "err" | "default" | "muted";
type StatusBadgeSize = "sm" | "md" | "lg";
type StatusBadgeEmphasis = "subtle" | "strong";
type StatusConfig = { label: string; variant: StatusVariant; icon: LucideIcon; iconClassName?: string };

const STATUS_CONFIG: Record<string, StatusConfig> = {
  "合规": { label: "合规通过", variant: "ok", icon: CheckCircle2 },
  "不合规": { label: "不合规", variant: "err", icon: XCircle },
  "存疑": { label: "存疑待定", variant: "warn", icon: AlertTriangle },
  pending: { label: "等待中", variant: "muted", icon: Clock3 },
  running: { label: "审查中", variant: "default", icon: Loader2, iconClassName: "animate-spin" },
  completed: { label: "已完成", variant: "ok", icon: CheckCircle2 },
  failed: { label: "失败", variant: "err", icon: XCircle },
  waiting_retry: { label: "待重试", variant: "warn", icon: RotateCcw },
};

const SIZE_CLASS: Record<StatusBadgeSize, string> = {
  sm: "gap-1 px-2.5 py-0.5 text-xs",
  md: "gap-1.5 px-3 py-1 text-xs font-semibold",
  lg: "gap-2 px-4 py-1.5 text-sm font-semibold",
};

const ICON_SIZE_CLASS: Record<StatusBadgeSize, string> = {
  sm: "h-3 w-3",
  md: "h-3.5 w-3.5",
  lg: "h-4 w-4",
};

const STRONG_CLASS: Record<StatusVariant, string> = {
  ok: "border border-status-ok/40 bg-status-ok-bg text-status-ok shadow-sm ring-1 ring-status-ok/10",
  warn: "border border-status-warn/40 bg-status-warn-bg text-status-warn shadow-sm ring-1 ring-status-warn/10",
  err: "border border-status-err-border bg-status-err text-white shadow-sm ring-1 ring-status-err/10",
  default: "border border-accent/30 bg-accent text-white shadow-sm ring-1 ring-accent/10",
  muted: "border border-gray-200 bg-gray-100 text-text-muted shadow-sm",
};

export function StatusBadge({
  status,
  size = "sm",
  emphasis = "subtle",
  showIcon = false,
  className,
}: {
  status: VerdictValue | PointRunStatus | string;
  size?: StatusBadgeSize;
  emphasis?: StatusBadgeEmphasis;
  showIcon?: boolean;
  className?: string;
}) {
  const config: StatusConfig = STATUS_CONFIG[status] ?? { label: status, variant: "muted", icon: CircleDashed };
  const Icon = config.icon;
  return (
    <Badge
      variant={config.variant}
      className={cn(
        SIZE_CLASS[size],
        emphasis === "strong" && STRONG_CLASS[config.variant],
        className,
      )}
    >
      {showIcon && <Icon className={cn(ICON_SIZE_CLASS[size], config.iconClassName)} />}
      {config.label}
    </Badge>
  );
}
