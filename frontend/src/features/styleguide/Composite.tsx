/**
 * A representative composition of the design system (not an application screen): KPI strip,
 * chart, side panels and a wide statement table, laid out exactly as screens will be. Every
 * number is a recorded backend value; the live panel talks to the running backend.
 */
import { useHealth, useMe } from "@/api/queries/system";
import { UfcfBars } from "@/components/charts/UfcfBars";
import { BasisBadge, BasisLegend, StatusIndicator, Tag } from "@/components/ui/Badge";
import { RowLabel, Table, TableScroll, Td, Th, Tr } from "@/components/ui/DataTable";
import { SkeletonRows } from "@/components/ui/Feedback";
import { FinancialValue } from "@/components/ui/FinancialValue";
import { KpiStrip, KpiTile } from "@/components/ui/Kpi";
import { Panel, SidePanelLayout } from "@/components/ui/Panel";
import { recorded } from "@/fixtures";
import { formatHash, formatPerShareUnit } from "@/lib/format";

import { buildKpis, buildSummary, type CellSpec } from "./data";

function Cell({
  spec,
  kind,
}: {
  spec: CellSpec | null;
  kind: Parameters<typeof FinancialValue>[0]["kind"];
}) {
  if (spec === null) return <span className="sr-only">not applicable</span>;
  // R2: every value on screen carries its basis marker.
  return <FinancialValue {...spec.input} kind={kind} basis={spec.basis} showBasis />;
}

/** Live check that the typed client reaches the backend (health + the signed-in user). */
export function BackendPanel() {
  const health = useHealth();
  const me = useMe();
  const fixtureEngine = recorded.run.$recorded.engine_version;
  return (
    <Panel title="Backend connection" meta="live · typed client" bodyClassName="px-4 py-3">
      {health.isPending || me.isPending ? (
        <SkeletonRows rows={3} label="Contacting the backend" />
      ) : (
        <dl
          className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 text-table"
          data-testid="backend-panel"
        >
          <dt className="text-slate-500">Health</dt>
          <dd data-testid="health-status">
            {health.isError ? (
              <StatusIndicator tone="error">Unreachable</StatusIndicator>
            ) : (
              <StatusIndicator tone="ok">{health.data.status}</StatusIndicator>
            )}
          </dd>
          <dt className="text-slate-500">Engine</dt>
          <dd className="flex flex-wrap items-center gap-2" data-testid="engine-version">
            {health.data === undefined ? "—" : <Tag mono>{health.data.engine_version}</Tag>}
            {health.data === undefined ? null : health.data.engine_version === fixtureEngine ? (
              <StatusIndicator tone="ok">matches recorded data</StatusIndicator>
            ) : (
              <StatusIndicator tone="warn">recorded on {fixtureEngine}</StatusIndicator>
            )}
          </dd>
          <dt className="text-slate-500">Signed in</dt>
          <dd className="truncate" data-testid="me-email">
            {me.isError ? (
              <StatusIndicator tone="error">{me.error.message}</StatusIndicator>
            ) : (
              me.data.email
            )}
          </dd>
          <dt className="text-slate-500">Client</dt>
          <dd className="text-slate-700">
            <code className="df-code">openapi-fetch</code> over types generated from{" "}
            <code className="df-code">docs/openapi.json</code>
          </dd>
        </dl>
      )}
    </Panel>
  );
}

export function RecordedPanel() {
  const run = recorded.run.body;
  return (
    <Panel title="Recorded data" meta="fixtures" bodyClassName="px-4 py-3">
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 text-table">
        <dt className="text-slate-500">Company</dt>
        <dd className="truncate">{run.context.company.name}</dd>
        <dt className="text-slate-500">Scenario</dt>
        <dd className="truncate">
          {run.context.project.name} · {run.context.scenario.name}
        </dd>
        <dt className="text-slate-500">Run</dt>
        <dd className="flex flex-wrap items-center gap-2">
          <Tag tone="info">Frozen</Tag>
          <code className="df-code" title={run.input_hash}>
            {formatHash(run.input_hash)}
          </code>
        </dd>
        <dt className="text-slate-500">Source</dt>
        <dd className="text-slate-700">
          Recorded from the API by <code className="df-code">scripts/record-fixtures.mjs</code>;
          validated against <code className="df-code">docs/openapi.json</code> in tests.
        </dd>
      </dl>
    </Panel>
  );
}

export function Composite() {
  const s = buildSummary();
  const k = buildKpis();
  return (
    <div className="flex flex-col gap-4">
      <KpiStrip label="Valuation summary">
        <KpiTile
          label="WACC"
          unit="rate"
          value={{ value: k.wacc, kind: "rate", basis: "derived" }}
        />
        <KpiTile
          label="Terminal growth"
          unit="rate"
          value={{ value: k.terminalGrowth, kind: "rate", basis: k.terminalGrowthBasis }}
        />
        <KpiTile
          label="Enterprise value"
          unit={k.amountUnit}
          value={{ value: k.enterpriseValue, kind: "amount", basis: "derived", unit: k.amountUnit }}
        />
        <KpiTile
          label="Equity value"
          unit={k.amountUnit}
          value={{ value: k.equityValue, kind: "amount", basis: "derived", unit: k.amountUnit }}
        />
        <KpiTile
          label="Value per share"
          unit={formatPerShareUnit(k.currency)}
          value={{ value: k.valuePerShare, kind: "per_share", basis: "derived" }}
        />
      </KpiStrip>

      <SidePanelLayout
        main={
          <Panel
            title="Unlevered free cash flow"
            meta={s.unit}
            actions={<BasisBadge basis="derived" />}
          >
            <UfcfBars points={s.chart} unit={s.unit} height={300} />
          </Panel>
        }
        side={
          <div className="flex flex-col gap-4">
            <BackendPanel />
            <RecordedPanel />
          </div>
        }
      />

      <Panel
        title="Operating summary"
        meta={`${s.unit} · historical (A) and forecast (E)`}
        bodyClassName="p-0"
        footer={<BasisLegend />}
      >
        <TableScroll label="Operating summary, historical and forecast">
          <Table>
            <thead>
              <tr>
                <Th first className="min-w-[220px]">
                  {s.unit}
                </Th>
                {s.histLabels.map((l) => (
                  <Th key={l} numeric>
                    {l}
                  </Th>
                ))}
                {s.fcLabels.map((l, j) => (
                  <Th key={l} numeric forecast divider={j === 0}>
                    {l}
                  </Th>
                ))}
              </tr>
            </thead>
            <tbody>
              {s.rows.map((row) => {
                const subtotal = row.variant === "subtotal";
                return (
                  <Tr key={row.key} variant={row.variant ?? "default"}>
                    <Td first subtotal={subtotal}>
                      <RowLabel>{row.label}</RowLabel>
                    </Td>
                    {row.hist.map((c, j) => (
                      <Td key={`h${String(j)}`} numeric subtotal={subtotal}>
                        <Cell spec={c} kind={row.kind} />
                      </Td>
                    ))}
                    {row.fc.map((c, j) => (
                      <Td key={`f${String(j)}`} numeric subtotal={subtotal} divider={j === 0}>
                        <Cell spec={c} kind={row.kind} />
                      </Td>
                    ))}
                  </Tr>
                );
              })}
            </tbody>
          </Table>
        </TableScroll>
      </Panel>
    </div>
  );
}
