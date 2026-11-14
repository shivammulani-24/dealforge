import fc from "fast-check";
import { describe, expect, it } from "vitest";

import { parseDecimal, parsePercent, shiftDecimalLeft } from "./parse";

describe("parsePercent (string-exact, never divides)", () => {
  it.each([
    ["18.5", 0.185, "0.185"],
    ["1.1", 0.011, "0.011"],
    ["8", 0.08, "0.08"],
    ["0.5", 0.005, "0.005"],
    [".5", 0.005, "0.005"],
    ["100", 1, "1.00"],
    ["125.75", 1.2575, "1.2575"],
    ["-2.5", -0.025, "-0.025"],
    ["+3", 0.03, "0.03"],
    ["18.5%", 0.185, "0.185"],
    ["  7.0 % ", 0.07, "0.070"],
    ["1,234.5", 12.345, "12.345"],
  ])("%s → %s", (input, value, exact) => {
    const r = parsePercent(input);
    expect(r).toEqual({ ok: true, value, exact });
  });

  it("gives the JSON-literal double where division would not", () => {
    expect(1.1 / 100).not.toBe(0.011); // the bug this module exists to avoid
    const r = parsePercent("1.1");
    expect(r.ok && r.value).toBe(0.011);
    expect(r.ok && r.value).toBe(JSON.parse("0.011"));
  });

  it.each(["", "   ", "%"])("reports %j as empty (missing), never zero", (input) => {
    expect(parsePercent(input)).toEqual({ ok: false, reason: "empty" });
  });

  it.each([
    "abc",
    "1e3",
    "1.2.3",
    "5..0",
    "-",
    ".",
    "1 000",
    "12,34",
    "1,2345",
    "--1",
    "0x10",
    "∞",
  ])("rejects %j", (input) => {
    expect(parsePercent(input)).toEqual({ ok: false, reason: "invalid" });
  });

  it("property: equals the correctly rounded decimal n × 10⁻², for 10,000 inputs", () => {
    const decimal = fc
      .tuple(
        fc.constantFrom("", "-", "+"),
        fc.stringMatching(/^\d{1,12}$/),
        fc.option(fc.stringMatching(/^\d{1,12}$/), { nil: undefined }),
      )
      .map(([sign, int, frac]) => `${sign}${int}${frac === undefined ? "" : `.${frac}`}`);
    fc.assert(
      fc.property(decimal, (s) => {
        const r = parsePercent(s);
        // Number("…e-2") is the exact decimal rounded once to the nearest double: the oracle.
        return r.ok && Object.is(r.value, Number(`${s}e-2`));
      }),
      { numRuns: 10_000 },
    );
  });
});

describe("parseDecimal", () => {
  it.each([
    ["1,234.5", 1234.5],
    ["-0.25", -0.25],
    [".5", 0.5],
    ["42", 42],
    ["42.", 42],
    ["0", 0],
  ])("%s → %s", (input, value) => {
    const r = parseDecimal(input);
    expect(r.ok && r.value).toBe(value);
  });

  it("keeps a blank field missing and rejects junk", () => {
    expect(parseDecimal("")).toEqual({ ok: false, reason: "empty" });
    expect(parseDecimal("1e5")).toEqual({ ok: false, reason: "invalid" });
  });

  it("property: equals Number() of the same decimal string, for 10,000 inputs", () => {
    fc.assert(
      fc.property(fc.stringMatching(/^-?\d{1,15}(\.\d{1,15})?$/), (s) => {
        const r = parseDecimal(s);
        return r.ok && Object.is(r.value, Number(s));
      }),
      { numRuns: 10_000 },
    );
  });
});

describe("shiftDecimalLeft", () => {
  it("moves the point on the string only", () => {
    expect(shiftDecimalLeft("18", "5", 2)).toBe("0.185");
    expect(shiftDecimalLeft("1234", "", 2)).toBe("12.34");
    expect(shiftDecimalLeft("100", "", 2)).toBe("1.00");
    expect(shiftDecimalLeft("", "5", 2)).toBe("0.005");
    expect(shiftDecimalLeft("12", "", 0)).toBe("12");
  });
});
