/**
 * Heat-shaded sensitivity grid: a TABLE, not a chart (plan section 7). Every number is the
 * backend's: the cell value, `change_abs` and `change_pct` (A9). The base cell is outlined;
 * invalid cells show their code; `change_pct` shows "NM" when the base is zero or negative.
 * Shading (lib/heat) uses `change_abs`, so it works even when every percentage is NM.
 */
import type { components } from "@/api/schema";
import { formatNumber, type NumberKind } from "@/lib/format";
import { heatTones, type HeatTone } from "@/lib/heat";
import { cn } from "@/lib/cn";

import { FinancialValue } from "./FinancialValue";

type Grid = components["schemas"]["SensitivityOut"];

/** Short axis names for the grid's corner cell. */
const SHORT_LABEL: Record<string, string> = { wacc: "WACC", terminal_growth: "g" };

const VARIABLE_LABEL: Record<string, string> = {
  wacc: "WACC",
  terminal_growth: "Terminal growth",
  revenue_growth_shift: "Revenue growth shift",
  ebitda_margin_shift: "EBITDA margin shift",
  capex_pct_shift: "Capex % shift",
  tax_rate: "Tax rate",
};

const OUTPUT: Record<string, { label: string; kind: NumberKind } | undefined> = {
  value_per_share: { label: "Value per share", kind: "per_share" },
  enterprise_value: { label: "Enterprise value", kind: "amount" },
  equity_value: { label: "Equity value", kind: "amount" },
};

const TONE_CLASS: Record<HeatTone, string> = {
  base: "bg-white",
  invalid: "bg-slate-50",
  flat: "bg-white",
  "up-1": "bg-heat-up-1",
  "up-2": "bg-heat-up-2",
  "up-3": "bg-heat-up-3",
  "down-1": "bg-heat-down-1",
  "down-2": "bg-heat-down-2",
  "down-3": "bg-heat-down-3",
};

export function variableLabel(v: string): string {
  return VARIABLE_LABEL[v] ?? v;
}

export function HeatGrid({ grid, unit }: { grid: Grid; unit: string }) {
  // `output` is typed as a plain string in the response; an unknown output is shown as an amount.
  const out = OUTPUT[grid.output] ?? { label: grid.output, kind: "amount" as const };
  const tones = heatTones(grid.cells, [grid.base_row, grid.base_col]);
  const rowLabel = variableLabel(grid.row_variable);
  const colLabel = variableLabel(grid.col_variable);
  return (
    <div className="flex flex-col gap-2">
      <div
        className="overflow-x-auto"
        role="region"
        aria-label={`${out.label} sensitivity`}
        tabIndex={0}
      >
        <table className="border-separate border-spacing-0 text-table">
          <caption className="sr-only">
            {out.label} ({unit}) by {rowLabel} (rows) and {colLabel} (columns)
          </caption>
          <thead>
            <tr>
              <th
                scope="col"
                className="df-label h-row border-b border-r border-slate-300 bg-slate-50 px-3 text-left normal-case"
              >
                {SHORT_LABEL[grid.row_variable] ?? rowLabel} ↓ ·{" "}
                {SHORT_LABEL[grid.col_variable] ?? colLabel} →
              </th>
              {grid.col_values.map((c, j) => (
                <th
                  key={c}
                  scope="col"
                  className={cn(
                    "df-label df-num h-row border-b border-slate-300 bg-slate-50 px-3",
                    j === grid.base_col && "text-slate-900",
                  )}
                >
                  {formatNumber(c, "rate").text}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grid.cells.map((row, i) => (
              <tr key={grid.row_values[i]}>
                <th
                  scope="row"
                  className={cn(
                    "df-num border-b border-r border-slate-200 bg-slate-50 px-3 text-label font-semibold",
                    i === grid.base_row ? "text-slate-900" : "text-slate-600",
                  )}
                >
                  {formatNumber(grid.row_values[i], "rate").text}
                </th>
                {row.map((cell, j) => {
                  const tone = tones[i]?.[j] ?? "invalid";
                  const isBase = tone === "base";
                  return (
                    <td
                      key={`${String(i)}-${String(j)}`}
                      data-tone={tone}
                      data-base={isBase || undefined}
                      className={cn(
                        "min-w-[112px] border-b border-r border-slate-200 px-3 py-1.5 align-top",
                        TONE_CLASS[tone],
                        isBase && "outline outline-2 -outline-offset-2 outline-slate-900",
                      )}
                    >
                      {cell.status === "invalid" ? (
                        <span className="flex flex-col items-end" title={cell.codes.join(", ")}>
                          <span className="text-slate-500">Invalid</span>
                          <code className="df-code text-[10px] text-slate-500">
                            {cell.codes[0] ?? ""}
                          </code>
                        </span>
                      ) : (
                        <span className="flex flex-col items-end">
                          <FinancialValue
                            value={cell.value}
                            kind={out.kind}
                            basis="derived"
                            unit={unit}
                            className="font-medium"
                          />
                          <span className="flex gap-2 text-label text-slate-600">
                            <FinancialValue
                              value={cell.change_abs}
                              kind={out.kind}
                              basis="derived"
                              signed
                            />
                            <FinancialValue
                              metric={cell.change_pct}
                              kind="percent"
                              basis="derived"
                              signed
                            />
                          </span>
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul
        className="flex flex-wrap gap-x-4 gap-y-1 text-label text-slate-600"
        aria-label="Grid legend"
      >
        <li className="flex items-center gap-1.5">
          <span className="h-3 w-4 border-2 border-slate-900 bg-white" aria-hidden="true" /> Base
          (equals the frozen run)
        </li>
        <li className="flex items-center gap-1.5">
          <span className="h-3 w-4 bg-heat-up-3" aria-hidden="true" /> Higher than base
        </li>
        <li className="flex items-center gap-1.5">
          <span className="h-3 w-4 bg-heat-down-3" aria-hidden="true" /> Lower than base
        </li>
        <li>
          Second line: change vs base ({unit === "" ? "absolute" : unit}) and %; NM when the base ≤
          0
        </li>
      </ul>
    </div>
  );
}
