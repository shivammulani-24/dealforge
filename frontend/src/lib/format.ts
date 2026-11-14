/**
 * DISPLAY-ONLY number formatting (plan sections 1, 6 and 7).
 *
 * This is the only module that turns an API number into text. It rounds, scales a fraction by
 * 100 for a percentage *display*, adds thousands separators, parentheses and units, and renders
 * missing values as "—" and not-meaningful values as "NM". It never derives a financial
 * quantity: no sums, differences, ratios or growth rates. Those come from the API.
 *
 * Rounding: `Intl.NumberFormat` rounds the value's shortest round-trip decimal (what JSON
 * shows) half away from zero, so 1.005 → 1.01 and 1.015 → 1.02, as a decimal hand calculation.
 * Negatives use parentheses, never colour. A value that rounds to zero shows no sign.
 */
/**
 * A backend metric. `MetricOut` (API layer) always sends `reason`; the engine's own `Metric`
 * (inside stored results) may omit it, so both shapes are accepted.
 */
export interface Metric {
  value: number | null;
  status: "ok" | "missing" | "not_meaningful";
  reason?: string | null | undefined;
}

/** How a number is displayed. Decimal places follow plan section 7. */
export type NumberKind =
  | "amount" // currency amounts in the company's scale: 1 dp, e.g. (1,234.5)
  | "per_share" // value per share: 2 dp
  | "percent" // fractions shown as %: 1 dp, e.g. 0.096 → 9.6%
  | "rate" // WACC, discount and growth rates: 2 dp, e.g. 0.0959980 → 9.60%
  | "multiple" // multiples and coverage ratios: 1 dp with x, e.g. 7.9x
  | "ratio" // liquidity ratios: 2 dp with x, e.g. 1.45x
  | "count"; // share counts and other quantities: 1 dp

const DECIMALS: Record<NumberKind, number> = {
  amount: 1,
  per_share: 2,
  percent: 1,
  rate: 2,
  multiple: 1,
  ratio: 2,
  count: 1,
};

const SUFFIX: Record<NumberKind, string> = {
  amount: "",
  per_share: "",
  percent: "%",
  rate: "%",
  multiple: "x",
  ratio: "x",
  count: "",
};

export const MISSING = "—";
export const NOT_MEANINGFUL = "NM";

export type Formatted =
  | { state: "value"; text: string; title: string; negative: boolean }
  | { state: "missing"; text: typeof MISSING; title: string; negative: false }
  | { state: "nm"; text: typeof NOT_MEANINGFUL; title: string; negative: false };

export interface FormatOptions {
  /** Override the default decimal places for the kind. */
  decimals?: number;
  /** Show a "+" on positive values (changes, deltas). */
  signed?: boolean;
  /** Unit text appended to the full-precision title, e.g. "INR crores". */
  unit?: string;
}

const formatters = new Map<number, Intl.NumberFormat>();

function formatter(decimals: number): Intl.NumberFormat {
  let f = formatters.get(decimals);
  if (f === undefined) {
    f = new Intl.NumberFormat("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
      useGrouping: true,
      signDisplay: "never",
    });
    formatters.set(decimals, f);
  }
  return f;
}

function isPercentKind(kind: NumberKind): boolean {
  return kind === "percent" || kind === "rate";
}

/** Full-precision text for the hover title: the shortest string that round-trips the double. */
function fullPrecision(value: number, kind: NumberKind, unit?: string): string {
  const raw = isPercentKind(kind) ? `${String(value)} (fraction)` : String(value);
  return unit === undefined ? raw : `${raw} ${unit}`;
}

/**
 * Format a number for display. `null`/`undefined` render as "—" (missing), never as zero (R3).
 * A non-finite number can't come from JSON; it is shown as missing rather than as text.
 */
export function formatNumber(
  value: number | null | undefined,
  kind: NumberKind,
  options: FormatOptions = {},
): Formatted {
  if (value === null || value === undefined) {
    return { state: "missing", text: MISSING, title: "Missing", negative: false };
  }
  if (!Number.isFinite(value)) {
    return {
      state: "missing",
      text: MISSING,
      title: "Missing: not a finite number",
      negative: false,
    };
  }
  const decimals = options.decimals ?? DECIMALS[kind];
  const shown = isPercentKind(kind) ? value * 100 : value; // display scaling only
  const digits = formatter(decimals).format(shown);
  const isZero = /^[0.,]+$/.test(digits);
  const negative = shown < 0 && !isZero;
  const body = `${digits}${SUFFIX[kind]}`;
  let text = body;
  if (negative) text = `(${body})`;
  else if (options.signed === true && !isZero) text = `+${body}`;
  return { state: "value", text, title: fullPrecision(value, kind, options.unit), negative };
}

/** Format an API `Metric` ({value, status, reason}); the status decides, never the value. */
export function formatMetric(
  metric: Metric,
  kind: NumberKind,
  options: FormatOptions = {},
): Formatted {
  switch (metric.status) {
    case "ok":
      return formatNumber(metric.value, kind, options);
    case "missing":
      return {
        state: "missing",
        text: MISSING,
        title:
          metric.reason === null || metric.reason === undefined
            ? "Missing"
            : `Missing: ${metric.reason}`,
        negative: false,
      };
    case "not_meaningful":
      return {
        state: "nm",
        text: NOT_MEANINGFUL,
        title:
          metric.reason === null || metric.reason === undefined
            ? "Not meaningful"
            : `Not meaningful: ${metric.reason}`,
        negative: false,
      };
  }
}

/** "INR crores", "INR millions", or the currency alone when there is no scale. */
export function formatUnit(currency: string, scale?: string | null): string {
  return scale === undefined || scale === null || scale === "" || scale === "units"
    ? currency
    : `${currency} ${scale}`;
}

/** A per-share unit, e.g. "INR per share". */
export function formatPerShareUnit(currency: string): string {
  return `${currency} per share`;
}

/** Fiscal-year column label: 2025 → "FY2025", with A/E for actual or estimate. */
export function formatFiscalYear(year: number, kind?: "actual" | "estimate"): string {
  const suffix = kind === "actual" ? "A" : kind === "estimate" ? "E" : "";
  return `FY${year}${suffix}`;
}

/** Shorten a content hash for display, keeping the algorithm prefix: sha256:37c66a53… */
export function formatHash(hash: string, keep = 8): string {
  const [algo, digest] = hash.includes(":") ? hash.split(":", 2) : ["", hash];
  const short = (digest ?? "").length > keep ? `${(digest ?? "").slice(0, keep)}…` : (digest ?? "");
  return algo === "" ? short : `${algo ?? ""}:${short}`;
}
