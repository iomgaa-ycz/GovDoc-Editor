import { cn } from "@/lib/utils";

const TONE_STYLES = {
  blue: "border-l-accent",
  green: "border-l-status-ok",
  amber: "border-l-status-warn",
  red: "border-l-status-err",
  slate: "border-l-text-muted",
} as const;

export function MetricCard({ label, value, tone = "blue" }: {
  label: string;
  value: string | number;
  tone?: keyof typeof TONE_STYLES;
}) {
  return (
    <div className={cn("rounded-card border bg-surface-card p-4 border-l-4", TONE_STYLES[tone])}>
      <p className="text-sm text-text-muted">{label}</p>
      <p className="text-2xl font-bold text-text-primary mt-1">{value}</p>
    </div>
  );
}
