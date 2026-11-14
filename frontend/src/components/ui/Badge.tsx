import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

import { Icon, type IconName } from "./Icon";

export type Basis = "reported" | "derived" | "assumed";

const BASIS: Record<Basis, { letter: string; label: string; meaning: string; className: string }> =
  {
    reported: {
      letter: "R",
      label: "Reported",
      meaning: "From a source document (filing, import or market data)",
      className: "border-slate-500 text-slate-700 bg-white",
    },
    derived: {
      letter: "D",
      label: "Derived",
      meaning: "Calculated by the backend engine from other values",
      className: "border-slate-600 bg-slate-600 text-white",
    },
    assumed: {
      letter: "A",
      label: "Assumed",
      meaning: "Entered by the analyst, with a rationale",
      className: "border-accent text-accent bg-white",
    },
  };

export const BASIS_ORDER: readonly Basis[] = ["reported", "derived", "assumed"];

/** R / D / A marker (R2): R slate outline · D slate filled · A blue outline. */
export function BasisBadge({ basis }: { basis: Basis }) {
  const b = BASIS[basis];
  return (
    <abbr
      title={`${b.label}: ${b.meaning}`}
      aria-label={b.label}
      data-basis={basis}
      className={cn(
        "inline-flex h-4 w-4 shrink-0 select-none items-center justify-center rounded-sm border text-[10px] font-semibold leading-none no-underline",
        b.className,
      )}
    >
      {b.letter}
    </abbr>
  );
}

/** The legend that sits in each table footer (plan section 7). */
export function BasisLegend({ only }: { only?: readonly Basis[] }) {
  const items = only ?? BASIS_ORDER;
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1" aria-label="Basis legend">
      {items.map((basis) => (
        <li key={basis} className="flex items-center gap-1.5 text-label text-slate-600">
          <BasisBadge basis={basis} />
          <span>{BASIS[basis].label}</span>
        </li>
      ))}
    </ul>
  );
}

export type Tone = "ok" | "warn" | "error" | "info" | "neutral";

const TONES: Record<Tone, { icon: IconName; className: string }> = {
  ok: { icon: "check", className: "text-status-ok" },
  warn: { icon: "warning", className: "text-status-warn" },
  error: { icon: "error", className: "text-status-error" },
  info: { icon: "info", className: "text-accent" },
  neutral: { icon: "info", className: "text-slate-500" },
};

/**
 * Status indicator: icon + text, so status is never conveyed by colour alone (plan section 7).
 * Status colours are used for status only.
 */
export function StatusIndicator({ tone, children }: { tone: Tone; children: ReactNode }) {
  const t = TONES[tone];
  return (
    <span className="inline-flex items-center gap-1.5 text-table" data-tone={tone}>
      <Icon name={t.icon} size={14} className={cn("shrink-0", t.className)} />
      <span className="text-slate-800">{children}</span>
    </span>
  );
}

/** A compact outlined tag for metadata (engine version, run state, codes). */
export function Tag({
  children,
  tone = "neutral",
  mono = false,
}: {
  children: ReactNode;
  tone?: Tone;
  mono?: boolean;
}) {
  const cls: Record<Tone, string> = {
    ok: "border-status-ok text-status-ok bg-status-ok-subtle",
    warn: "border-status-warn text-status-warn bg-status-warn-subtle",
    error: "border-status-error text-status-error bg-status-error-subtle",
    info: "border-accent-line text-accent bg-accent-subtle",
    neutral: "border-slate-300 text-slate-700 bg-white",
  };
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center whitespace-nowrap rounded-sm border px-1.5 text-label font-medium",
        mono ? "font-mono" : "uppercase tracking-wide",
        cls[tone],
      )}
    >
      {children}
    </span>
  );
}
