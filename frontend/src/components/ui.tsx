import clsx from "clsx";
import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { ACTION_LABEL, LEVEL_NAME } from "../format";

export function Card({ children, className, title, action }: { children: ReactNode; className?: string; title?: ReactNode; action?: ReactNode }) {
  return (
    <section className={clsx("rounded-xl border border-slate-200 bg-white shadow-sm", className)}>
      {title && (
        <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          {action}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Button({ children, onClick, variant = "primary", disabled, className, type = "button", title }: {
  children: ReactNode; onClick?: () => void; variant?: "primary" | "secondary" | "ghost" | "danger";
  disabled?: boolean; className?: string; type?: "button" | "submit"; title?: string;
}) {
  return (
    <button type={type} onClick={onClick} disabled={disabled} title={title}
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && "bg-brand-700 text-white hover:bg-brand-900",
        variant === "secondary" && "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
        variant === "ghost" && "text-slate-600 hover:bg-slate-100",
        variant === "danger" && "bg-rose-600 text-white hover:bg-rose-700",
        className,
      )}>
      {children}
    </button>
  );
}

const ACTION_STYLE: Record<string, string> = {
  APPROVE: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  APPROVE_PARTIAL: "bg-teal-50 text-teal-700 ring-teal-600/20",
  REJECT: "bg-rose-50 text-rose-700 ring-rose-600/20",
  HOLD: "bg-amber-50 text-amber-800 ring-amber-600/20",
  ESCALATE: "bg-violet-50 text-violet-700 ring-violet-600/20",
};

export function ActionBadge({ action, large }: { action: string; large?: boolean }) {
  return (
    <span className={clsx("inline-flex items-center rounded-md font-semibold ring-1 ring-inset",
      large ? "px-3 py-1 text-base" : "px-2 py-0.5 text-xs", ACTION_STYLE[action] ?? "bg-slate-100 text-slate-700 ring-slate-300")}>
      {ACTION_LABEL[action] ?? action}
    </span>
  );
}

const LEVEL_STYLE = ["bg-slate-100 text-slate-600", "bg-sky-100 text-sky-800", "bg-emerald-100 text-emerald-800"];

export function TrustBadge({ level }: { level: number }) {
  return (
    <span className={clsx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", LEVEL_STYLE[level])}>
      {["🎒", "🧑‍💼", "🎓"][level]} {LEVEL_NAME[level]}
    </span>
  );
}

export function CodeChip({ label }: { label: string }) {
  return <span className="inline-flex rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-700">{label}</span>;
}

export function ConfidenceBar({ value }: { value: number }) {
  const color = value >= 0.8 ? "bg-emerald-500" : value >= 0.5 ? "bg-amber-400" : "bg-rose-400";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-200">
        <div className={clsx("h-full rounded-full", color)} style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      <span className="text-xs tabular-nums text-slate-500">{Math.round(value * 100)}%</span>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-500">
      <Loader2 className="h-4 w-4 animate-spin" /> {label}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
      <p className="font-medium text-slate-700">{title}</p>
      {children && <div className="mt-2 text-sm text-slate-500">{children}</div>}
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  return <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error instanceof Error ? error.message : String(error)}</div>;
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="font-serif text-2xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
