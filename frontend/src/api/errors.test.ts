import { describe, expect, it } from "vitest";

import { recorded } from "@/fixtures";

import { ApiError, isApiError } from "./errors";

describe("ApiError.fromResponse", () => {
  it("parses a recorded calculation envelope (engine issues with field and code)", () => {
    const e = ApiError.fromResponse(422, recorded.errorCalculation.body);
    expect(e.errorType).toBe("calculation");
    expect(e.engineVersion).toBe("0.1.0");
    expect(e.codes).toEqual(["TERMINAL_GROWTH_GE_WACC"]);
    expect(e.errors[0]).toMatchObject({ field: "terminal_growth", severity: "error", loc: null });
    expect(e.message).toMatch(/Terminal growth \(20\.00%\) must be below WACC/);
    expect(isApiError(e)).toBe(true);
  });

  it("parses a recorded validation envelope (Pydantic loc paths)", () => {
    const e = ApiError.fromResponse(422, recorded.errorValidation.body);
    expect(e.errorType).toBe("validation");
    expect(e.errors.map((x) => x.loc)).toEqual([
      ["body", "name"],
      ["body", "currency"],
    ]);
  });

  it("keeps Retry-After for 503 DATABASE_BUSY", () => {
    const e = ApiError.fromResponse(
      503,
      {
        error_type: "unavailable",
        status: 503,
        errors: [{ code: "DATABASE_BUSY", message: "busy" }],
      },
      new Headers({ "Retry-After": "1" }),
    );
    expect(e).toMatchObject({ errorType: "unavailable", retryAfter: 1, status: 503 });
    expect(
      ApiError.fromResponse(503, {}, new Headers({ "Retry-After": "soon" })).retryAfter,
    ).toBeNull();
  });

  it("degrades safely on unexpected bodies", () => {
    for (const body of [null, "Internal Server Error", [], { error_type: 42 }, { errors: "x" }]) {
      const e = ApiError.fromResponse(500, body);
      expect(e.errorType).toBe("unknown");
      expect(e.message).toBe("The server returned HTTP 500.");
      expect(e.codes).toEqual([]);
    }
    const odd = ApiError.fromResponse(409, {
      error_type: "conflict",
      errors: [{ code: 7, loc: ["body", 3, {}], message: null }],
    });
    expect(odd.errors[0]).toMatchObject({
      code: null,
      loc: ["body", 3],
      message: "Unknown error.",
    });
  });

  it("builds a network error", () => {
    const e = ApiError.network();
    expect(e).toMatchObject({ status: 0, errorType: "network", codes: ["NETWORK_ERROR"] });
    expect(isApiError(new Error("x"))).toBe(false);
  });
});
