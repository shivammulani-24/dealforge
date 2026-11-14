/**
 * Maps RECORDED backend responses onto display rows for the design-system page. This file only
 * selects values; it performs no arithmetic (lint-enforced outside src/lib). Each cell carries
 * the basis the backend reports for it.
 */
import type { components } from "@/api/schema";
import type { Basis } from "@/components/ui/Badge";
import type { RowVariant } from "@/components/ui/DataTable";
import type { ValueInput } from "@/components/ui/FinancialValue";
import { recorded } from "@/fixtures";
import { formatFiscalYear, formatUnit, type NumberKind } from "@/lib/format";

type S = components["schemas"];

export interface CellSpec {
  input: ValueInput;
  basis: Basis;
}

export interface RowSpec {
  key: string;
  label: string;
  kind: NumberKind;
  variant?: RowVariant;
  /** One entry per historical year; null = not applicable (rendered empty, not "—"). */
  hist: (CellSpec | null)[];
  /** One entry per forecast year. */
  fc: (CellSpec | null)[];
}

const isBasis = (b: unknown): b is Basis => b === "reported" || b === "derived" || b === "assumed";

/** The basis the backend recorded for an input, from the run's provenance map. */
export function provenanceBasis(provenance: Record<string, unknown>, key: string): Basis {
  const entry = provenance[key];
  const basis =
    typeof entry === "object" && entry !== null ? (entry as Record<string, unknown>).basis : null;
  if (!isBasis(basis)) throw new Error(`No basis recorded in provenance for "${key}".`);
  return basis;
}

function lineItem(period: S["PeriodOut"], code: string): CellSpec {
  const li = period.line_items.find((x) => x.item_code === code);
  return { input: { value: li?.value ?? null }, basis: li?.basis ?? "reported" };
}

function metric(period: S["PeriodAnalysisOut"], name: string): CellSpec {
  const m = period.metrics[name];
  if (m === undefined) throw new Error(`Metric "${name}" missing from the historical analysis.`);
  return {
    input: { metric: m },
    basis: "derived",
  };
}

/**
 * A run's stored inputs are typed as a plain dict in the API (RunOut.inputs); they are the
 * frozen `DcfInputsIn`. src/fixtures/fixtures.test.ts validates the recorded inputs against
 * that schema, which is what makes this cast safe.
 */
export function frozenInputs(run: S["RunOut"]): S["DcfInputsIn"] {
  return run.inputs as unknown as S["DcfInputsIn"];
}

/**
 * A frozen run stores provenance as `{inputs: {...}, scenario: {...}}` (a preview's is the flat
 * inputs map). Returns the per-input map, or an empty map if absent, in which case
 * `provenanceBasis` refuses to guess a basis.
 */
export function runInputProvenance(run: S["RunOut"]): Record<string, unknown> {
  const inputs = (run.provenance as Record<string, unknown>).inputs;
  return typeof inputs === "object" && inputs !== null ? (inputs as Record<string, unknown>) : {};
}

const derived = (value: number | null): CellSpec => ({ input: { value }, basis: "derived" });

export function buildSummary() {
  const fin = recorded.financials.body;
  const ana = recorded.historicalAnalysis.body;
  const run = recorded.run.body;
  const result = run.result;
  const prov = runInputProvenance(run);

  const histPeriods = fin.periods;
  const anaPeriods = ana.periods;
  const fcYears = result.forecast.years;
  const ufcf = result.ufcf;
  const pres = run.presentation.years;
  const drivers = frozenInputs(run).forecast.years;
  const periodLabels = result.schedule.periods;

  const driver = (key: "revenue_growth" | "ebitda_margin"): (CellSpec | null)[] =>
    fcYears.map((y, i) => ({
      input: { value: drivers[i]?.[key] ?? null },
      basis: provenanceBasis(prov, `forecast.years[${String(y.t)}].${key}`),
    }));

  const none = histPeriods.map(() => null);
  const noneFc = fcYears.map(() => null);

  const rows: RowSpec[] = [
    {
      key: "revenue",
      label: "Revenue",
      kind: "amount",
      hist: histPeriods.map((p) => lineItem(p, "revenue")),
      fc: fcYears.map((y) => derived(y.revenue)),
    },
    {
      key: "revenue_growth",
      label: "Revenue growth",
      kind: "percent",
      hist: anaPeriods.map((p) => metric(p, "revenue_growth")),
      fc: driver("revenue_growth"),
    },
    {
      key: "ebitda",
      label: "EBITDA (standardised)",
      kind: "amount",
      hist: anaPeriods.map((p) => ({
        input: { metric: p.ebitda.standardized },
        basis: "derived",
      })),
      fc: fcYears.map((y) => derived(y.ebitda)),
    },
    {
      key: "ebitda_margin",
      label: "EBITDA margin",
      kind: "percent",
      hist: anaPeriods.map((p) => metric(p, "ebitda_margin")),
      fc: driver("ebitda_margin"),
    },
    {
      key: "reported_ebitda",
      label: "EBITDA (as reported)",
      kind: "amount",
      hist: anaPeriods.map((p) => ({ input: { metric: p.ebitda.reported }, basis: "reported" })),
      fc: noneFc,
    },
    {
      key: "da",
      label: "D&A",
      kind: "amount",
      hist: histPeriods.map((p) => lineItem(p, "da")),
      fc: fcYears.map((y) => derived(y.da)),
    },
    {
      key: "ebit",
      label: "EBIT",
      kind: "amount",
      variant: "subtotal",
      hist: histPeriods.map((p) => lineItem(p, "ebit")),
      fc: fcYears.map((y) => derived(y.ebit)),
    },
    {
      key: "ebit_margin",
      label: "EBIT margin",
      kind: "percent",
      hist: anaPeriods.map((p) => metric(p, "ebit_margin")),
      fc: pres.map((y) => ({ input: { metric: y.ebit_margin }, basis: "derived" })),
    },
    {
      key: "taxes",
      label: "Taxes on EBIT",
      kind: "amount",
      hist: none,
      fc: ufcf.map((y) => derived(y.taxes_on_ebit)),
    },
    {
      key: "capex",
      label: "Capital expenditure",
      kind: "amount",
      hist: histPeriods.map((p) => lineItem(p, "capex")),
      fc: ufcf.map((y) => derived(y.capex)),
    },
    {
      key: "change_in_nwc",
      label: "Change in operating NWC",
      kind: "amount",
      hist: anaPeriods.map((p) => metric(p, "change_in_nwc")),
      fc: ufcf.map((y) => derived(y.change_in_nwc)),
    },
    {
      key: "ufcf",
      label: "Unlevered free cash flow",
      kind: "amount",
      variant: "subtotal",
      hist: none,
      fc: ufcf.map((y) => derived(y.ufcf)),
    },
    {
      key: "ufcf_margin",
      label: "UFCF margin",
      kind: "percent",
      hist: none,
      fc: pres.map((y) => ({ input: { metric: y.ufcf_margin }, basis: "derived" })),
    },
    {
      key: "current_ratio",
      label: "Current ratio",
      kind: "ratio",
      hist: anaPeriods.map((p) => metric(p, "current_ratio")),
      fc: noneFc,
    },
  ];

  return {
    company: run.context.company,
    scenario: run.context.scenario,
    project: run.context.project,
    unit: formatUnit(fin.currency, fin.scale),
    histLabels: histPeriods.map((p) => formatFiscalYear(p.fiscal_year, "actual")),
    fcLabels: periodLabels.map((p) => `${p.label}E`),
    rows,
    chart: ufcf.map((y, i) => ({ label: `${periodLabels[i]?.label ?? ""}E`, ufcf: y.ufcf })),
  };
}

/** KPIs straight from the frozen run's stored result and inputs. */
export function buildKpis() {
  const run = recorded.run.body;
  const r = run.result;
  const currency = run.context.company.currency;
  return {
    currency,
    amountUnit: formatUnit(currency, run.context.company.scale),
    wacc: r.wacc,
    terminalGrowth: frozenInputs(run).terminal_growth,
    terminalGrowthBasis: provenanceBasis(runInputProvenance(run), "terminal_growth"),
    enterpriseValue: r.valuation.enterprise_value,
    equityValue: r.bridge.equity_value,
    valuePerShare: r.per_share.value_per_share,
    impliedExitMultiple: r.implied_exit_multiple,
    tvShare: r.valuation.tv_share_of_ev,
    bridgeLines: r.bridge.lines,
  };
}
