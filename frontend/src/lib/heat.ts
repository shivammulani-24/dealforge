/**
 * Heat shading for the sensitivity grid (plan sections 3.6 and 4.3). DISPLAY ONLY.
 *
 * Shading is driven by the backend's `change_abs`, so it still works when `change_pct` is NM
 * (base ≤ 0). The only computation here maps each change onto one of three intensity bands
 * relative to the largest absolute change in the grid; no financial value is derived.
 * Direction uses blue (up) and slate (down): never red/green (plan section 7).
 */

export type HeatTone = "base" | "invalid" | "flat" | `up-${1 | 2 | 3}` | `down-${1 | 2 | 3}`;

export interface HeatCellInput {
  change_abs: number | null;
  status: "ok" | "invalid";
}

function band(ratio: number): 1 | 2 | 3 {
  if (ratio > 2 / 3) return 3;
  if (ratio > 1 / 3) return 2;
  return 1;
}

/** Tone for every cell of a grid; `base` is the [row, col] of the base cell. */
export function heatTones(cells: HeatCellInput[][], base: [number, number]): HeatTone[][] {
  let maxAbs = 0;
  for (const row of cells) {
    for (const c of row) {
      if (c.status === "ok" && c.change_abs !== null)
        maxAbs = Math.max(maxAbs, Math.abs(c.change_abs));
    }
  }
  return cells.map((row, i) =>
    row.map((c, j): HeatTone => {
      if (i === base[0] && j === base[1]) return "base";
      if (c.status !== "ok" || c.change_abs === null) return "invalid";
      if (c.change_abs === 0 || maxAbs === 0) return "flat";
      const level = band(Math.abs(c.change_abs) / maxAbs);
      return c.change_abs > 0 ? `up-${level}` : `down-${level}`;
    }),
  );
}
