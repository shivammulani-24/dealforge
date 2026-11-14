import { describe, expect, it } from "vitest";

import { recorded } from "@/fixtures";

import {
  formatFiscalYear,
  formatHash,
  formatMetric,
  formatNumber,
  formatPerShareUnit,
  formatUnit,
  MISSING,
  NOT_MEANINGFUL,
} from "./format";

describe("formatNumber", () => {
  it.each([
    [3558.790701488767, "amount", "3,558.8"],
    [-400, "amount", "(400.0)"],
    [0, "amount", "0.0"],
    [31.215006617818556, "per_share", "31.22"],
    [-17.140686123873596, "per_share", "(17.14)"],
    [0.2, "percent", "20.0%"],
    [0.0959980079681275, "rate", "9.60%"],
    [-0.025, "rate", "(2.50%)"],
    [7.884836607796121, "multiple", "7.9x"],
    [2, "ratio", "2.00x"],
    [1234567.891, "amount", "1,234,567.9"],
  ] as const)("%s as %s → %s", (value, kind, text) => {
    expect(formatNumber(value, kind).text).toBe(text);
  });

  it("keeps full precision in the hover title, with the unit", () => {
    const f = formatNumber(3558.790701488767, "amount", { unit: "INR crores" });
    expect(f.title).toBe("3558.790701488767 INR crores");
    expect(formatNumber(0.0959980079681275, "rate").title).toBe("0.0959980079681275 (fraction)");
  });

  it("never shows a sign on a value that rounds to zero", () => {
    expect(formatNumber(-0.00001, "amount").text).toBe("0.0");
    expect(formatNumber(-0.00001, "amount").negative).toBe(false);
    expect(formatNumber(-0, "per_share").text).toBe("0.00");
    expect(formatNumber(0.00001, "amount", { signed: true }).text).toBe("0.0");
  });

  it("shows + on signed positives and parentheses on negatives", () => {
    expect(formatNumber(2.6513821240346083, "per_share", { signed: true }).text).toBe("+2.65");
    expect(formatNumber(-2.300915809426396, "per_share", { signed: true }).text).toBe("(2.30)");
    expect(formatNumber(0.0849, "percent", { signed: true }).text).toBe("+8.5%");
  });

  it("rounds the decimal the API sent, half away from zero (not the binary expansion)", () => {
    expect(formatNumber(1.005, "per_share").text).toBe("1.01");
    expect(formatNumber(1.015, "per_share").text).toBe("1.02");
    expect(formatNumber(-1.005, "per_share").text).toBe("(1.01)");
    expect(formatNumber(0.00125, "rate").text).toBe("0.13%");
  });

  it("honours a decimals override", () => {
    expect(formatNumber(3558.79, "amount", { decimals: 0 }).text).toBe("3,559");
  });

  it("renders null and undefined as missing, never as zero (R3)", () => {
    for (const v of [null, undefined]) {
      const f = formatNumber(v, "amount");
      expect(f).toMatchObject({ state: "missing", text: MISSING });
      expect(f.text).not.toContain("0");
    }
  });

  it("treats non-finite numbers as missing rather than printing them", () => {
    for (const v of [Number.NaN, Number.POSITIVE_INFINITY]) {
      expect(formatNumber(v, "amount")).toMatchObject({ state: "missing", text: MISSING });
    }
  });

  it("does not change the value it is given (display only)", () => {
    const v = 0.0959980079681275;
    formatNumber(v, "rate");
    expect(v).toBe(0.0959980079681275);
  });
});

describe("formatMetric", () => {
  it("formats ok metrics by value", () => {
    expect(formatMetric({ value: 0.2, status: "ok", reason: null }, "percent").text).toBe("20.0%");
  });

  it("uses the status, not the value, for missing and NM, with the backend's reason", () => {
    const first = recorded.historicalAnalysis.body.periods[0]!;
    const nm = formatMetric(first.metrics.revenue_growth!, "percent");
    expect(nm).toMatchObject({ state: "nm", text: NOT_MEANINGFUL });
    expect(nm.title).toBe("Not meaningful: no immediately preceding fiscal year");
    const missing = formatMetric(first.ebitda.reported, "amount");
    expect(missing).toMatchObject({ state: "missing", text: MISSING });
    expect(missing.title).toBe("Missing: missing input: reported EBITDA");
  });

  it("accepts an omitted or null reason", () => {
    expect(formatMetric({ value: null, status: "missing" }, "amount").title).toBe("Missing");
    expect(
      formatMetric({ value: null, status: "not_meaningful", reason: null }, "amount").title,
    ).toBe("Not meaningful");
  });

  it("renders the A9 NM change from a negative-base grid", () => {
    const g = recorded.sensitivityNegative.body;
    const cell = g.cells[0]![0]!;
    expect(formatMetric(cell.change_pct, "percent", { signed: true }).text).toBe("NM");
    expect(formatMetric(cell.change_pct, "percent").title).toBe(
      "Not meaningful: base value is zero or negative",
    );
  });
});

describe("labels", () => {
  it("formats units, years and hashes", () => {
    expect(formatUnit("INR", "crores")).toBe("INR crores");
    expect(formatUnit("USD", null)).toBe("USD");
    expect(formatUnit("USD", "units")).toBe("USD");
    expect(formatUnit("USD", "")).toBe("USD");
    expect(formatUnit("USD")).toBe("USD");
    expect(formatPerShareUnit("INR")).toBe("INR per share");
    expect(formatFiscalYear(2025, "actual")).toBe("FY2025A");
    expect(formatFiscalYear(2026, "estimate")).toBe("FY2026E");
    expect(formatFiscalYear(2026)).toBe("FY2026");
    expect(formatHash("sha256:37c66a5382d863399822cc79")).toBe("sha256:37c66a53…");
    expect(formatHash("abcdef")).toBe("abcdef");
    expect(formatHash("0123456789abcdef", 4)).toBe("0123…");
  });
});
