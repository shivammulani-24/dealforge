/**
 * Unlevered free cash flow by forecast year (plan section 7: few series, slate and blue, axes
 * labelled with units, no 3D). Every plotted value is a backend output (`result.ufcf[].ufcf`);
 * year labels come from the backend's `schedule.periods`. Tick and tooltip text go through
 * lib/format, so the chart shows exactly what a table would.
 */
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatNumber } from "@/lib/format";
import { colors } from "@/styles/tokens";

export interface UfcfPoint {
  label: string;
  ufcf: number;
}

export function UfcfBars({
  points,
  unit,
  height = 220,
}: {
  points: UfcfPoint[];
  unit: string;
  height?: number;
}) {
  return (
    <figure className="m-0" aria-label={`Unlevered free cash flow by year, ${unit}`}>
      <div style={{ height }} className="w-full min-w-0" data-chart="ufcf">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={points} margin={{ top: 8, right: 8, bottom: 4, left: 8 }}>
            <CartesianGrid vertical={false} stroke={colors.slate[200]} />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={{ stroke: colors.slate[300] }}
              tick={{ fill: colors.slate[600], fontSize: 11 }}
            />
            <YAxis
              width={56}
              tickLine={false}
              axisLine={false}
              tick={{ fill: colors.slate[600], fontSize: 11 }}
              tickFormatter={(v: number) => formatNumber(v, "amount", { decimals: 0 }).text}
              label={{
                value: unit,
                angle: -90,
                position: "insideLeft",
                fill: colors.slate[500],
                fontSize: 11,
              }}
            />
            <Tooltip
              cursor={{ fill: colors.slate[100] }}
              formatter={(v) => [
                typeof v === "number" ? formatNumber(v, "amount").text : "—",
                `UFCF (${unit})`,
              ]}
              contentStyle={{
                border: `1px solid ${colors.slate[200]}`,
                borderRadius: 3,
                fontSize: 12,
              }}
            />
            <Bar
              dataKey="ufcf"
              fill={colors.accent.DEFAULT}
              maxBarSize={40}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 text-label text-slate-500">
        Derived (D): backend UFCF per forecast year. Bars are not computed in the browser.
      </figcaption>
    </figure>
  );
}
