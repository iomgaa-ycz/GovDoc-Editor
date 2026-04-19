import {
  AlertTriangle,
  CheckCircle2,
  FileUp,
  Info,
  LoaderCircle,
  Pencil,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import {
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type PropsWithChildren,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";

import type { LogEntry } from "../types/ui";

export function PageHero(props: {
  eyebrow: string;
  title: string;
  description?: string;
  tag?: string;
  actions?: ReactNode;
}) {
  return (
    <section className="page-hero">
      <div>
        {props.eyebrow ? <p className="eyebrow">{props.eyebrow}</p> : null}
        <h2>{props.title}</h2>
        {props.description ? <p className="hero-description">{props.description}</p> : null}
      </div>
      <div className="hero-side">
        {props.tag ? <span className="hero-tag">{props.tag}</span> : null}
        {props.actions}
      </div>
    </section>
  );
}

export function Card(props: PropsWithChildren<{ className?: string }>) {
  return (
    <section className={`card${props.className ? ` ${props.className}` : ""}`}>
      {props.children}
    </section>
  );
}

export function CardHeader(props: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="card-header">
      <div>
        <h3>{props.title}</h3>
        {props.description ? <p>{props.description}</p> : null}
      </div>
      {props.actions ? <div className="card-actions">{props.actions}</div> : null}
    </div>
  );
}

export function Button(
  props: PropsWithChildren<
    ButtonHTMLAttributes<HTMLButtonElement> & {
      tone?: "primary" | "secondary" | "ghost" | "danger";
      size?: "md" | "sm";
      busy?: boolean;
      icon?: LucideIcon;
    }
  >,
) {
  const {
    tone = "primary",
    size = "md",
    busy = false,
    icon: Icon,
    children,
    className,
    ...buttonProps
  } = props;

  return (
    <button
      className={`button button--${tone} button--${size}${className ? ` ${className}` : ""}`}
      {...buttonProps}
    >
      {busy ? (
        <LoaderCircle className="spin" size={16} />
      ) : Icon ? (
        <Icon size={16} />
      ) : null}
      <span>{children}</span>
    </button>
  );
}

export type ReviewStatus = "pending" | "running" | "passed" | "failed" | "error";

export function StatPill(props: {
  status: ReviewStatus | "completed" | "idle";
  children?: ReactNode;
}) {
  return (
    <span className={`status-pill status-pill--${props.status}`}>
      {props.children ?? props.status}
    </span>
  );
}

export function Field(
  props: PropsWithChildren<{ label: string; hint?: string; className?: string }>,
) {
  return (
    <label className={`field${props.className ? ` ${props.className}` : ""}`}>
      <span className="field-label">{props.label}</span>
      {props.children}
      {props.hint ? <span className="field-hint">{props.hint}</span> : null}
    </label>
  );
}

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className="text-input" {...props} />;
}

export function SelectInput(
  props: SelectHTMLAttributes<HTMLSelectElement> & PropsWithChildren,
) {
  return (
    <select className="text-input" {...props}>
      {props.children}
    </select>
  );
}

export function TextArea(
  props: TextareaHTMLAttributes<HTMLTextAreaElement>,
) {
  return <textarea className="text-area" {...props} />;
}

export function FileDropzone(props: {
  title: string;
  subtitle: string;
  accept?: string;
  multiple?: boolean;
  onSelect: (files: File[]) => void;
}) {
  return (
    <label className="dropzone">
      <input
        className="sr-only"
        type="file"
        accept={props.accept}
        multiple={props.multiple}
        onChange={(event) => {
          props.onSelect(Array.from(event.target.files || []));
          event.target.value = "";
        }}
      />
      <div className="dropzone-icon">
        <FileUp size={18} />
      </div>
      <div>
        <strong>{props.title}</strong>
        <p>{props.subtitle}</p>
      </div>
    </label>
  );
}

export function ProgressBar(props: { value: number }) {
  return (
    <div className="progress-track">
      <div
        className="progress-fill"
        style={{ width: `${Math.min(100, Math.max(0, props.value))}%` }}
      />
    </div>
  );
}

export function MetricCard(props: {
  label: string;
  value: string | number;
  tone?: "blue" | "green" | "amber" | "slate";
}) {
  return (
    <article className={`metric-card${props.tone ? ` metric-card--${props.tone}` : ""}`}>
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </article>
  );
}

export function EmptyState(props: { title: string; description: string }) {
  return (
    <div className="empty-state">
      <Info size={18} />
      <div>
        <strong>{props.title}</strong>
        <p>{props.description}</p>
      </div>
    </div>
  );
}

export function InlineNotice(props: {
  tone: "info" | "success" | "warning";
  message: string;
}) {
  const iconMap: Record<typeof props.tone, LucideIcon> = {
    info: Info,
    success: CheckCircle2,
    warning: AlertTriangle,
  };
  const Icon = iconMap[props.tone];
  return (
    <div className={`inline-notice inline-notice--${props.tone}`}>
      <Icon size={16} />
      <span>{props.message}</span>
    </div>
  );
}

export function LogConsole(props: { logs: LogEntry[] }) {
  return (
    <div className="log-console">
      {props.logs.map((entry) => (
        <div key={entry.id} className={`log-entry log-entry--${entry.level}`}>
          <span>{entry.time}</span>
          <p>{entry.message}</p>
        </div>
      ))}
    </div>
  );
}

export function IconAction(props: {
  label: string;
  icon: "edit" | "delete";
  onClick: () => void;
}) {
  return (
    <button
      className="icon-button"
      type="button"
      onClick={props.onClick}
      aria-label={props.label}
    >
      {props.icon === "edit" ? <Pencil size={14} /> : <Trash2 size={14} />}
    </button>
  );
}
