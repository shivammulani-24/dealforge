import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

import { FinancialValue, type FinancialValueProps } from "./FinancialValue";

/**
 * Slim KPI tiles (label, value, unit): not oversized cards. The strip shows 5 per row at
 * >= 1280 px and wraps to two rows at 1024–1279 px (D4-09).
 */
export function KpiStrip({
  children,
  label,
  columns = 5,
}: {
  children: ReactNode;
  label: string;
  /** 5 (default) wraps to 3 + 2 at 1024–1279 px; 3 stays on one row. */
  columns?: 3 | 5;
}) {
  return (
    <dl
      aria-label={label}
      // Each tile draws its own top and left hairline; the outer ones are clipped by the
      // container, so a wrapped strip never shows an empty grey slot.
      className={cn(
        "grid overflow-hidden rounded border border-slate-200 bg-white",
        columns === 5 ? "grid-cols-3 xl:grid-cols-5" : "grid-cols-3",
      )}
    >
      {children}
    </dl>
  );
}

export function KpiTile({
  label,
  unit,
  value,
}: {
  label: string;
  unit: string;
  value: FinancialValueProps;
}) {
  return (
    <div className="-ml-px -mt-px min-w-0 border-l border-t border-slate-200 px-4 py-2.5">
      <dt className="df-label truncate">{label}</dt>
      <dd className="mt-0.5 flex items-baseline justify-between gap-2">
        <FinancialValue {...value} className="text-kpi font-semibold" />
        <span className="truncate text-label text-slate-500">{unit}</span>
      </dd>
    </div>
  );
}
