/**
 * String-exact input parsing (plan section 6).
 *
 * Typing "18.5" in a percentage field must send 0.185: the same double as the JSON literal
 * `0.185`. Dividing by 100 would not do that (1.1 / 100 === 0.011000000000000001), so the
 * decimal point is shifted ON THE STRING and the result is converted once with `Number()`,
 * which rounds the exact decimal to the nearest double, exactly as a JSON parser does.
 *
 * Accepted: optional sign, digits with an optional fraction ("18", "18.5", ".5", "-0.25"),
 * thousands separators in correct groups ("1,234.5"), and for percentages a trailing "%".
 * Rejected: empty input, exponents, spaces inside the number, misplaced commas, a bare sign or
 * dot. A blank field is reported as `empty` so the caller can mark the value MISSING; it is
 * never turned into zero (R3).
 */

export type ParseResult =
  | { ok: true; value: number; /** the exact decimal string that was converted */ exact: string }
  | { ok: false; reason: "empty" | "invalid" };

const PLAIN = /^([+-]?)(\d*)(?:\.(\d*))?$/;
const GROUPED = /^([+-]?)(\d{1,3}(?:,\d{3})+)(?:\.(\d*))?$/;

interface Parts {
  sign: "" | "-";
  int: string;
  frac: string;
}

function split(text: string): Parts | null {
  const m = PLAIN.exec(text) ?? GROUPED.exec(text);
  if (m === null) return null;
  const int = (m[2] ?? "").replaceAll(",", "");
  const frac = m[3] ?? "";
  if (int === "" && frac === "") return null; // "", "+", ".", "-."
  return { sign: m[1] === "-" ? "-" : "", int, frac };
}

/** Move the decimal point `places` positions to the left, on the digit string only. */
export function shiftDecimalLeft(int: string, frac: string, places: number): string {
  const digits = `${int}${frac}`;
  const point = int.length - places;
  const body =
    point <= 0
      ? `0.${"0".repeat(-point)}${digits}`
      : `${digits.slice(0, point)}.${digits.slice(point)}`;
  return body.endsWith(".") ? body.slice(0, -1) : body;
}

function done(sign: "" | "-", body: string): ParseResult {
  const exact = `${sign}${body}`;
  return { ok: true, value: Number(exact), exact };
}

/** Parse a plain decimal such as "1,234.5" or "-0.25". */
export function parseDecimal(input: string): ParseResult {
  const text = input.trim();
  if (text === "") return { ok: false, reason: "empty" };
  const parts = split(text);
  if (parts === null) return { ok: false, reason: "invalid" };
  const int = parts.int === "" ? "0" : parts.int; // ".5" → "0.5"
  const body = parts.frac === "" ? int : `${int}.${parts.frac}`;
  return done(parts.sign, body);
}

/** Parse a percentage as typed ("18.5" or "18.5%") into its fraction (0.185), string-exactly. */
export function parsePercent(input: string): ParseResult {
  const text = input.trim().replace(/%$/, "").trimEnd();
  if (text === "") return { ok: false, reason: "empty" };
  const parts = split(text);
  if (parts === null) return { ok: false, reason: "invalid" };
  return done(parts.sign, shiftDecimalLeft(parts.int, parts.frac, 2));
}
