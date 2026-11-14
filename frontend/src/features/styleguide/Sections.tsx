/** Design-system reference sections: foundations, number formats, components and states. */
import { type ReactNode, useState } from "react";

import { ApiError } from "@/api/errors";
import { BasisBadge, BasisLegend, StatusIndicator, Tag } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Table, TableScroll, Td, Th, Tr } from "@/components/ui/DataTable";
import {
  EmptyState,
  ErrorPanel,
  IssueList,
  SkeletonRows,
  StaleOverlay,
  SyntheticBanner,
  UpdatingIndicator,
} from "@/components/ui/Feedback";
import { FinancialValue, type ValueInput } from "@/components/ui/FinancialValue";
import { HeatGrid } from "@/components/ui/HeatGrid";
import { InputCell } from "@/components/ui/InputCell";
import { KpiStrip, KpiTile } from "@/components/ui/Kpi";
import { Panel } from "@/components/ui/Panel";
import { TextField } from "@/components/ui/TextField";
import { recorded } from "@/fixtures";
import { formatPerShareUnit, formatUnit, type Metric, type NumberKind } from "@/lib/format";
import type { ParseResult } from "@/lib/parse";
import { colors } from "@/styles/tokens";

import { buildKpis, frozenInputs } from "./data";

export function Section({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="flex scroll-mt-4 flex-col gap-3">
      <div>
        <h2 id={`${id}-title`} className="text-section font-semibold text-slate-900">
          {title}
        </h2>
        {description === undefined ? null : (
          <p className="max-w-3xl text-table text-slate-600">{description}</p>
        )}
      </div>
      {children}
    </section>
  );
}

// --- Colour ----------------------------------------------------------------------------------

interface Swatch {
  name: string;
  hex: string;
  cls: string;
  use: string;
  dark?: boolean;
}

// Class names are literal so Tailwind can see them; hex values come from the token module.
const SWATCHES: Swatch[] = [
  {
    name: "navy-900",
    hex: colors.navy[900],
    cls: "bg-navy-900",
    use: "Rail and header",
    dark: true,
  },
  { name: "white", hex: colors.white, cls: "bg-white", use: "Content canvas" },
  { name: "slate-50", hex: colors.slate[50], cls: "bg-slate-50", use: "Table header, stripes" },
  { name: "slate-200", hex: colors.slate[200], cls: "bg-slate-200", use: "Borders and rules" },
  {
    name: "slate-600",
    hex: colors.slate[600],
    cls: "bg-slate-600",
    use: "Secondary text",
    dark: true,
  },
  {
    name: "slate-900",
    hex: colors.slate[900],
    cls: "bg-slate-900",
    use: "Primary text, outputs",
    dark: true,
  },
  {
    name: "accent",
    hex: colors.accent.DEFAULT,
    cls: "bg-accent",
    use: "Interactive, assumed inputs",
    dark: true,
  },
  {
    name: "accent-subtle",
    hex: colors.accent.subtle,
    cls: "bg-accent-subtle",
    use: "Unsaved draft cells",
  },
  {
    name: "status-ok",
    hex: colors.status.ok,
    cls: "bg-status-ok",
    use: "Status only: OK",
    dark: true,
  },
  {
    name: "status-warn",
    hex: colors.status.warn,
    cls: "bg-status-warn",
    use: "Status only: warning",
    dark: true,
  },
  {
    name: "status-error",
    hex: colors.status.error,
    cls: "bg-status-error",
    use: "Status only: error",
    dark: true,
  },
];

export function ColourSection() {
  return (
    <Section
      id="colour"
      title="Colour"
      description="A closed palette: only these colours exist as utilities. Status colours are for status alone. Negative numbers use parentheses, never red or green."
    >
      <ul className="grid grid-cols-4 gap-3 xl:grid-cols-6">
        {SWATCHES.map((s) => (
          <li key={s.name} className="overflow-hidden rounded border border-slate-200 bg-white">
            <div className={`flex h-12 items-end px-2 pb-1 ${s.cls}`}>
              <span
                className={`df-code text-[11px] ${s.dark === true ? "text-white" : "text-slate-700"}`}
              >
                {s.hex}
              </span>
            </div>
            <div className="px-2 py-1.5">
              <p className="text-table font-medium">{s.name}</p>
              <p className="text-label text-slate-500">{s.use}</p>
            </div>
          </li>
        ))}
      </ul>
    </Section>
  );
}

// --- Typography and spacing ------------------------------------------------------------------

export function TypographySection() {
  const rows: { name: string; cls: string; spec: string; sample: ReactNode }[] = [
    {
      name: "Page title",
      cls: "text-title font-semibold",
      spec: "Inter 20/28 · 600",
      sample: "Ardent valuation",
    },
    {
      name: "Section header",
      cls: "text-section font-semibold",
      spec: "Inter 15/22 · 600",
      sample: "Operating summary",
    },
    {
      name: "Body",
      cls: "text-body",
      spec: "Inter 14/20 · 400",
      sample: "Draft values are previewed without saving.",
    },
    {
      name: "Table",
      cls: "text-table",
      spec: "Inter 13/20 · tabular",
      sample: "1,234.5   (400.0)   9.60%",
    },
    { name: "Column label", cls: "df-label", spec: "Inter 11/16 · 600 · caps", sample: "FY2025A" },
    {
      name: "KPI value",
      cls: "text-kpi font-semibold",
      spec: "Inter 20/26 · 600",
      sample: "31.22",
    },
    {
      name: "Code and hash",
      cls: "df-code",
      spec: "IBM Plex Mono 12",
      sample: "sha256:37c66a53…  TERMINAL_GROWTH_GE_WACC",
    },
  ];
  return (
    <Section
      id="typography"
      title="Typography"
      description="Inter with tabular figures, so digits align in every column; IBM Plex Mono for hashes and codes. Self-hosted: no external font requests."
    >
      <Panel bodyClassName="p-0">
        <Table>
          <tbody>
            {rows.map((r) => (
              <Tr key={r.name}>
                <Td first className="w-44 text-slate-600">
                  {r.name}
                </Td>
                <Td className="w-48 text-label text-slate-500">{r.spec}</Td>
                <Td className={r.cls}>{r.sample}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      </Panel>
    </Section>
  );
}

export function SpacingSection() {
  const steps: { label: string; cls: string }[] = [
    { label: "4", cls: "w-1" },
    { label: "8", cls: "w-2" },
    { label: "12", cls: "w-3" },
    { label: "16", cls: "w-4" },
    { label: "24", cls: "w-6" },
    { label: "32", cls: "w-8" },
  ];
  const surfaces: { name: string; cls: string; note: string }[] = [
    { name: "Canvas", cls: "bg-white border border-slate-200", note: "Page background" },
    { name: "Panel", cls: "bg-white border border-slate-300", note: "1 px border, no shadow" },
    { name: "Subtle", cls: "bg-slate-50 border border-slate-200", note: "Headers, empty states" },
    {
      name: "Forecast header",
      cls: "bg-slate-100 border border-slate-200",
      note: "Shaded E columns",
    },
    { name: "Draft", cls: "bg-accent-subtle border border-accent-line", note: "Unsaved input" },
    { name: "Rail", cls: "bg-navy-900", note: "Navigation" },
  ];
  return (
    <Section
      id="spacing"
      title="Spacing and surfaces"
      description="A 4 px grid. Compact 28 px table rows; 48 px header; 224 px rail (56 px compact). No gradients and no decorative shadows."
    >
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel title="Spacing scale" meta="px">
          <ul className="flex items-end gap-5">
            {steps.map((s) => (
              <li key={s.label} className="flex flex-col items-center gap-1">
                <span className={`block h-6 bg-accent ${s.cls}`} aria-hidden="true" />
                <span className="text-label text-slate-600">{s.label}</span>
              </li>
            ))}
            <li className="flex flex-col items-center gap-1">
              <span
                className="block h-row w-10 border border-slate-300 bg-slate-50"
                aria-hidden="true"
              />
              <span className="text-label text-slate-600">row 28</span>
            </li>
          </ul>
        </Panel>
        <Panel title="Surfaces">
          <ul className="grid grid-cols-3 gap-3">
            {surfaces.map((s) => (
              <li key={s.name} className="flex flex-col gap-1">
                <span className={`block h-10 rounded ${s.cls}`} aria-hidden="true" />
                <span className="text-table font-medium">{s.name}</span>
                <span className="text-label text-slate-500">{s.note}</span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </Section>
  );
}

// --- Number formats --------------------------------------------------------------------------

interface FormatExample {
  rule: string;
  source: string;
  raw: string;
  input: ValueInput;
  kind: NumberKind;
  signed?: boolean;
}

function examples(): FormatExample[] {
  const run = recorded.run.body;
  const r = run.result;
  const neg = recorded.sensitivityNegative.body;
  const negBase = neg.cells[neg.base_row]?.[neg.base_col];
  const ana = recorded.historicalAnalysis.body.periods;
  const firstYear = ana[0];
  const lastYear = ana.at(-1);
  const debt = r.bridge.lines.find((l) => l.label.includes("total debt"));
  const grid = recorded.sensitivityWaccG.body;
  const up = grid.cells.at(0)?.at(-1);
  const down = grid.cells.at(-1)?.at(0);
  const m = (x: Metric | undefined): ValueInput =>
    x === undefined ? { value: null } : { metric: x };
  const rawOf = (v: unknown) => JSON.stringify(v);
  const growthNm = firstYear?.metrics.revenue_growth;
  const reportedMissing = ana.find((p) => p.ebitda.reported.status === "missing");
  const reported = reportedMissing?.ebitda.reported;
  const margin = lastYear?.metrics.ebitda_margin;
  const current = lastYear?.metrics.current_ratio;
  return [
    {
      rule: "Amount, 1 dp, thousands separator",
      source: "result.valuation.enterprise_value",
      raw: rawOf(r.valuation.enterprise_value),
      input: { value: r.valuation.enterprise_value },
      kind: "amount",
    },
    {
      rule: "Negative in parentheses",
      source: "result.bridge.lines[total debt].amount",
      raw: rawOf(debt?.amount ?? null),
      input: { value: debt?.amount ?? null },
      kind: "amount",
    },
    {
      rule: "Per share, 2 dp",
      source: "result.per_share.value_per_share",
      raw: rawOf(r.per_share.value_per_share),
      input: { value: r.per_share.value_per_share },
      kind: "per_share",
    },
    {
      rule: "Negative per share",
      source: "negative-base run, base cell",
      raw: rawOf(negBase?.value ?? null),
      input: { value: negBase?.value ?? null },
      kind: "per_share",
    },
    {
      rule: "Percentage, 1 dp",
      source: "FY2025 metrics.ebitda_margin",
      raw: rawOf(margin?.value ?? null),
      input: m(margin),
      kind: "percent",
    },
    {
      rule: "Rate (WACC, g), 2 dp",
      source: "result.wacc",
      raw: rawOf(r.wacc),
      input: { value: r.wacc },
      kind: "rate",
    },
    {
      rule: "Multiple, 1 dp",
      source: "result.implied_exit_multiple",
      raw: rawOf(r.implied_exit_multiple.value),
      input: m(r.implied_exit_multiple),
      kind: "multiple",
    },
    {
      rule: "Liquidity ratio, 2 dp",
      source: "FY2025 metrics.current_ratio",
      raw: rawOf(current?.value ?? null),
      input: m(current),
      kind: "ratio",
    },
    {
      rule: "Change, signed",
      source: "sensitivity cell change_abs (up)",
      raw: rawOf(up?.change_abs ?? null),
      input: { value: up?.change_abs ?? null },
      kind: "per_share",
      signed: true,
    },
    {
      rule: "Change, negative",
      source: "sensitivity cell change_abs (down)",
      raw: rawOf(down?.change_abs ?? null),
      input: { value: down?.change_abs ?? null },
      kind: "per_share",
      signed: true,
    },
    {
      rule: "Missing → “—” (reason on hover)",
      source: `FY${String(reportedMissing?.fiscal_year ?? "")} ebitda.reported`,
      raw: rawOf(reported ?? null),
      input: m(reported),
      kind: "amount",
    },
    {
      rule: "Not meaningful → “NM”",
      source: "FY2023 metrics.revenue_growth",
      raw: rawOf(growthNm ?? null),
      input: m(growthNm),
      kind: "percent",
    },
    {
      rule: "% change NM when base ≤ 0 (A9)",
      source: "negative-base run, change_pct",
      raw: rawOf(negBase?.change_pct ?? null),
      input: m(negBase?.change_pct),
      kind: "percent",
      signed: true,
    },
  ];
}

export function NumberFormatSection() {
  return (
    <Section
      id="numbers"
      title="Financial number formats"
      description="lib/format.ts is the only number transformer and it is display only: rounding, % scaling for display, parentheses and units. Raw values are recorded API responses; hover a displayed value for full precision."
    >
      <Panel
        bodyClassName="p-0"
        footer="Right-aligned, tabular figures. A value that rounds to zero shows no sign. Missing values are never shown as 0 (R3)."
      >
        <TableScroll label="Number format examples">
          <Table>
            <thead>
              <tr>
                <Th first>Rule</Th>
                <Th>API field</Th>
                <Th>Raw JSON value</Th>
                <Th numeric>Displayed</Th>
              </tr>
            </thead>
            <tbody>
              {examples().map((e) => (
                <Tr key={e.rule}>
                  <Td first>{e.rule}</Td>
                  <Td className="df-code text-slate-500">{e.source}</Td>
                  <Td className="df-code max-w-[340px] truncate text-slate-600" title={e.raw}>
                    {e.raw}
                  </Td>
                  <Td numeric>
                    <FinancialValue
                      {...e.input}
                      kind={e.kind}
                      basis="derived"
                      {...(e.signed === true ? { signed: true } : {})}
                    />
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </TableScroll>
      </Panel>
    </Section>
  );
}

// --- Badges, status, controls ----------------------------------------------------------------

export function BadgeSection() {
  const reportedRevenue = recorded.financials.body.periods
    .at(-1)
    ?.line_items.find((li) => li.item_code === "revenue");
  return (
    <Section
      id="badges"
      title="Basis markers and status"
      description="Every financial value declares its basis (R2): it cannot render without one. Status is always icon plus text, never colour alone."
    >
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel title="Basis (R / D / A)" footer={<BasisLegend />}>
          <ul className="flex flex-col gap-2 text-table">
            <li className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2">
                <BasisBadge basis="reported" /> Reported · from a source document
              </span>
              <FinancialValue
                value={reportedRevenue?.value ?? null}
                kind="amount"
                basis="reported"
              />
            </li>
            <li className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2">
                <BasisBadge basis="derived" /> Derived · calculated by the engine
              </span>
              <FinancialValue value={recorded.run.body.result.wacc} kind="rate" basis="derived" />
            </li>
            <li className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2">
                <BasisBadge basis="assumed" /> Assumed · analyst input, in blue
              </span>
              <FinancialValue
                value={frozenInputs(recorded.run.body).terminal_growth}
                kind="rate"
                basis="assumed"
              />
            </li>
          </ul>
        </Panel>
        <Panel title="Status indicators">
          <ul className="flex flex-col gap-2">
            <li>
              <StatusIndicator tone="ok">Verified identical</StatusIndicator>
            </li>
            <li>
              <StatusIndicator tone="warn">Driver outside historical range</StatusIndicator>
            </li>
            <li>
              <StatusIndicator tone="error">Terminal growth must be below WACC</StatusIndicator>
            </li>
            <li>
              <StatusIndicator tone="info">
                Market data dated after the valuation date
              </StatusIndicator>
            </li>
          </ul>
        </Panel>
        <Panel title="Tags">
          <div className="flex flex-wrap gap-2">
            <Tag tone="info">Frozen</Tag>
            <Tag tone="ok">Engine compatible</Tag>
            <Tag tone="warn">Engine changed</Tag>
            <Tag tone="error">Invalid</Tag>
            <Tag>Draft</Tag>
            <Tag mono>engine 0.1.0</Tag>
            <Tag mono>run #1</Tag>
          </div>
          <div className="mt-3">
            <SyntheticBanner subject="Shown wherever a company is synthetic (R4)." />
          </div>
        </Panel>
      </div>
    </Section>
  );
}

export function ControlsSection() {
  const [sent, setSent] = useState<ParseResult | null>(null);
  const validation = recorded.errorValidation.body.errors.find(
    (e) => e.code === "string_pattern_mismatch",
  );
  return (
    <Section
      id="controls"
      title="Buttons and inputs"
      description="One accent colour for interactive elements. Mutation buttons are disabled while pending, so a double click can't send twice. Financial inputs are blue (assumed) and parsed string-exactly."
    >
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel title="Buttons">
          <div className="flex flex-wrap items-center gap-2">
            <Button>Save scenario</Button>
            <Button variant="secondary">Discard</Button>
            <Button variant="ghost">View provenance</Button>
            <Button disabled>Disabled</Button>
            <Button pending pendingLabel="Freezing…">
              Freeze run
            </Button>
            <Button size="sm" variant="secondary">
              Small
            </Button>
          </div>
        </Panel>
        <Panel title="Form fields">
          <div className="flex flex-col gap-3">
            <TextField label="Company name" defaultValue="Ardent Precision Components" />
            <TextField
              label="Currency"
              defaultValue="inr"
              error={typeof validation?.message === "string" ? validation.message : undefined}
              hint="Server validation message, recorded from the API."
            />
          </div>
        </Panel>
        <Panel title="Financial input cells">
          <div className="flex flex-col gap-3 text-table">
            <div className="flex items-center justify-between gap-3">
              <span>Saved value</span>
              <InputCell label="Revenue growth FY2026E" kind="percent" initial="8.0" />
            </div>
            <div className="flex items-center justify-between gap-3">
              <span>Unsaved draft</span>
              <InputCell
                label="EBITDA margin FY2026E"
                kind="percent"
                initial="18.5"
                draft
                onParsed={setSent}
              />
            </div>
            <div className="flex items-center justify-between gap-3">
              <span>Invalid</span>
              <InputCell label="Capex % FY2026E" kind="percent" initial="5..0" />
            </div>
            <p className="text-label text-slate-500" data-testid="parse-demo">
              Draft cell sends{" "}
              <code className="df-code">
                {sent === null
                  ? "0.185"
                  : sent.ok
                    ? JSON.stringify(sent.value)
                    : `(${sent.reason})`}
              </code>{" "}
              — string-shifted, never divided by 100.
            </p>
          </div>
        </Panel>
      </div>
    </Section>
  );
}

// --- Sensitivity grid ------------------------------------------------------------------------

export function SensitivitySection() {
  const k = buildKpis();
  const unit = formatPerShareUnit(k.currency);
  return (
    <Section
      id="sensitivity"
      title="Sensitivity grid"
      description="Heat-shaded table from a frozen run (R1). Values, absolute and % changes are the backend's (A9); shading uses the absolute change, so it still works when % is NM."
    >
      <div className="flex flex-col gap-4">
        <Panel title="WACC × terminal growth" meta={`value per share · ${unit} · 5 × 5`}>
          <HeatGrid grid={recorded.sensitivityWaccG.body} unit={unit} />
        </Panel>
        <Panel title="Invalid cells" meta="a wide g step reaches g ≥ WACC">
          <HeatGrid grid={recorded.sensitivityInvalid.body} unit={unit} />
        </Panel>
        <Panel title="Negative base" meta="base value per share < 0, so every % change is NM">
          <HeatGrid grid={recorded.sensitivityNegative.body} unit={unit} />
        </Panel>
      </div>
    </Section>
  );
}

// --- States ----------------------------------------------------------------------------------

export function StatesSection() {
  const calc = recorded.errorCalculation;
  const calcError = ApiError.fromResponse(calc.$recorded.operation.status, calc.body);
  const k = buildKpis();
  const unit = formatUnit(k.currency, recorded.run.body.context.company.scale);
  return (
    <Section
      id="states"
      title="Loading, empty, error and stale states"
      description="Errors are rendered from the backend's envelope. Calculation errors list each engine issue; previous results are greyed out and labelled stale."
    >
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel title="Calculation error" meta="recorded 422 from a draft preview">
          <ErrorPanel error={calcError} />
        </Panel>
        <Panel title="Stale results" meta="inputs currently invalid">
          <StaleOverlay stale>
            <KpiStrip label="Stale valuation summary" columns={3}>
              <KpiTile
                label="Enterprise value"
                unit={unit}
                value={{ value: k.enterpriseValue, kind: "amount", basis: "derived" }}
              />
              <KpiTile
                label="Equity value"
                unit={unit}
                value={{ value: k.equityValue, kind: "amount", basis: "derived" }}
              />
              <KpiTile
                label="Value per share"
                unit={formatPerShareUnit(k.currency)}
                value={{ value: k.valuePerShare, kind: "per_share", basis: "derived" }}
              />
            </KpiStrip>
          </StaleOverlay>
        </Panel>
        <Panel title="Network error" meta="retry is explicit; POST is never auto-retried">
          <ErrorPanel error={ApiError.network()} onRetry={() => undefined} />
        </Panel>
        <Panel title="Engine warnings" meta="recorded preview">
          <IssueList issues={recorded.preview.body.warnings} />
        </Panel>
        <Panel title="Loading" actions={<UpdatingIndicator />}>
          <SkeletonRows rows={4} label="Loading example" />
        </Panel>
        <Panel title="Empty">
          <EmptyState title="No saved runs yet" action={<Button size="sm">Freeze a run</Button>}>
            Freeze a scenario to create an immutable, verifiable valuation run.
          </EmptyState>
        </Panel>
      </div>
    </Section>
  );
}

export function TableSection() {
  const lines = buildKpis().bridgeLines;
  const run = recorded.run.body;
  const unit = formatUnit(run.context.company.currency, run.context.company.scale);
  return (
    <Section
      id="tables"
      title="Tables"
      description="Compact 28 px rows, sticky header and first column, subtotals bold with a rule above, and the basis legend in the footer. Wide tables scroll inside their container; the page never scrolls sideways."
    >
      <Panel
        title="Enterprise value to equity bridge"
        meta={unit}
        bodyClassName="p-0"
        footer={<BasisLegend only={["derived"]} />}
      >
        <Table>
          <thead>
            <tr>
              <Th first>Bridge item</Th>
              <Th numeric>{unit}</Th>
            </tr>
          </thead>
          <tbody>
            <Tr>
              <Td first>Enterprise value</Td>
              <Td numeric>
                <FinancialValue
                  value={run.result.bridge.enterprise_value}
                  kind="amount"
                  basis="derived"
                  showBasis
                />
              </Td>
            </Tr>
            {lines.map((l) => (
              <Tr key={l.label}>
                <Td first className="text-slate-700">
                  {l.label}
                </Td>
                <Td numeric>
                  <FinancialValue value={l.amount} kind="amount" basis="derived" showBasis />
                </Td>
              </Tr>
            ))}
            <Tr variant="subtotal">
              <Td first subtotal>
                Equity value
              </Td>
              <Td numeric subtotal>
                <FinancialValue
                  value={run.result.bridge.equity_value}
                  kind="amount"
                  basis="derived"
                  showBasis
                />
              </Td>
            </Tr>
          </tbody>
        </Table>
      </Panel>
    </Section>
  );
}
