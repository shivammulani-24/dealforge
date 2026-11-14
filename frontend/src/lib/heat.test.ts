import { describe, expect, it } from "vitest";

import { recorded } from "@/fixtures";

import { cn } from "./cn";
import { heatTones } from "./heat";

describe("heatTones", () => {
  it("marks the base, invalid and flat cells and bands the rest by |change_abs|", () => {
    const tones = heatTones(
      [
        [
          { status: "ok", change_abs: 3 },
          { status: "ok", change_abs: 0 },
          { status: "invalid", change_abs: null },
        ],
        [
          { status: "ok", change_abs: -1 },
          { status: "ok", change_abs: 0 },
          { status: "ok", change_abs: -2.5 },
        ],
      ],
      [1, 1],
    );
    expect(tones).toEqual([
      ["up-3", "flat", "invalid"],
      ["down-1", "base", "down-3"],
    ]);
  });

  it("is flat when nothing moves", () => {
    expect(heatTones([[{ status: "ok", change_abs: 0 }]], [5, 5])).toEqual([["flat"]]);
  });

  it("still shades a negative-base grid, where every % change is NM (A9)", () => {
    const g = recorded.sensitivityNegative.body;
    const tones = heatTones(g.cells, [g.base_row, g.base_col]).flat();
    expect(g.cells.flat().every((c) => c.change_pct.status === "not_meaningful")).toBe(true);
    expect(tones.filter((t) => t.startsWith("up-") || t.startsWith("down-")).length).toBe(8);
    expect(tones.filter((t) => t === "base")).toHaveLength(1);
  });

  it("marks recorded invalid cells as invalid", () => {
    const g = recorded.sensitivityInvalid.body;
    const tones = heatTones(g.cells, [g.base_row, g.base_col]);
    g.cells.forEach((row, i) => {
      row.forEach((c, j) => {
        if (c.status === "invalid") expect(tones[i]![j]).toBe("invalid");
      });
    });
  });
});

describe("cn", () => {
  it("joins truthy class names only", () => {
    expect(cn("a", false, null, undefined, "", "b")).toBe("a b");
  });
});
