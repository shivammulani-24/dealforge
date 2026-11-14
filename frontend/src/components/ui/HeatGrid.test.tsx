import { render, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { recorded } from "@/fixtures";
import { formatMetric, formatNumber } from "@/lib/format";

import { HeatGrid } from "./HeatGrid";

describe("HeatGrid", () => {
  it("display trace: every cell shows exactly format(apiValue) for value, change_abs and change_pct", () => {
    const g = recorded.sensitivityWaccG.body;
    const { container } = render(<HeatGrid grid={g} unit="INR per share" />);
    const tds = [...container.querySelectorAll("tbody td")];
    expect(tds).toHaveLength(25);
    g.cells.flat().forEach((cell, k) => {
      const td = tds[k]!;
      const expected = [
        formatNumber(cell.value, "per_share").text,
        formatNumber(cell.change_abs, "per_share", { signed: true }).text,
        formatMetric(cell.change_pct, "percent", { signed: true }).text,
      ];
      expect(td.textContent).toBe(expected.join(""));
    });
  });

  it("outlines exactly one base cell, which equals the frozen run's value", () => {
    const g = recorded.sensitivityWaccG.body;
    const { container } = render(<HeatGrid grid={g} unit="INR per share" />);
    const base = container.querySelectorAll("[data-base]");
    expect(base).toHaveLength(1);
    expect(base[0]!.textContent).toContain(
      formatNumber(recorded.run.body.result.per_share.value_per_share, "per_share").text,
    );
    expect(g.base_matches_run).toBe(true);
  });

  it("shows invalid cells with their code", () => {
    const g = recorded.sensitivityInvalid.body;
    const { container } = render(<HeatGrid grid={g} unit="INR per share" />);
    const invalid = [...container.querySelectorAll('[data-tone="invalid"]')];
    expect(invalid.length).toBe(g.cells.flat().filter((c) => c.status === "invalid").length);
    for (const td of invalid)
      expect(within(td as HTMLElement).getByText("TERMINAL_GROWTH_GE_WACC")).toBeInTheDocument();
  });

  it("shows NM for every % change on a negative base, with absolute changes still given (A9)", () => {
    const g = recorded.sensitivityNegative.body;
    const { container } = render(<HeatGrid grid={g} unit="INR per share" />);
    const tds = [...container.querySelectorAll("tbody td")];
    tds.forEach((td, k) => {
      const cell = g.cells.flat()[k]!;
      expect(td.textContent).toContain("NM");
      expect(td.textContent).toContain(
        formatNumber(cell.change_abs, "per_share", { signed: true }).text,
      );
    });
  });
});
