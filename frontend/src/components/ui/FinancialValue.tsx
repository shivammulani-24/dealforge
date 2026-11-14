/**
 * The ONLY way a financial number reaches the screen (plan section 6).
 *
 * - The text comes from lib/format (display only); the hover title carries full precision.
 * - `basis` is required (R2): TypeScript requires the prop and a runtime guard throws if it is
 *   missing or invalid, so a value can never render without one (component-tested).
 * - Missing renders "—" and NM renders "NM", each with the backend's reason as a tooltip (R3).
 * - Assumed values are blue (banking "input" colour); everything else is near-black.
 */
import {
  formatMetric,
  formatNumber,
  type FormatOptions,
  type Formatted,
  type Metric,
  type NumberKind,
} from "@/lib/format";
import { cn } from "@/lib/cn";

import { type Basis, BasisBadge, BASIS_ORDER } from "./Badge";

export type ValueInput = { value: number | null } | { metric: Metric };

export type FinancialValueProps = ValueInput & {
  kind: NumberKind;
  basis: Basis;
  /** Show the R/D/A badge next to the value (tables often show it once per row instead). */
  showBasis?: boolean;
  className?: string;
} & FormatOptions;

export function assertBasis(basis: unknown): asserts basis is Basis {
  if (!(BASIS_ORDER as readonly unknown[]).includes(basis)) {
    throw new Error(
      `A financial value must declare its basis (reported, derived or assumed); got ${String(basis)}.`,
    );
  }
}

export function formatValueInput(
  input: ValueInput,
  kind: NumberKind,
  options: FormatOptions,
): Formatted {
  return "metric" in input
    ? formatMetric(input.metric, kind, options)
    : formatNumber(input.value, kind, options);
}

export function FinancialValue(props: FinancialValueProps) {
  assertBasis(props.basis);
  const { kind, basis, showBasis = false, className, decimals, signed, unit } = props;
  const options: FormatOptions = {
    ...(decimals === undefined ? {} : { decimals }),
    ...(signed === undefined ? {} : { signed }),
    ...(unit === undefined ? {} : { unit }),
  };
  const f = formatValueInput(props, kind, options);
  return (
    <span
      className={cn(
        "df-num inline-flex items-center justify-end gap-1.5",
        f.state === "value" && basis === "assumed" ? "text-accent" : "text-slate-900",
        f.state !== "value" && "text-slate-500",
        className,
      )}
      title={f.title}
      data-state={f.state}
      data-basis={basis}
    >
      <span>{f.text}</span>
      {showBasis ? <BasisBadge basis={basis} /> : null}
    </span>
  );
}
