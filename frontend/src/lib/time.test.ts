import { describe, expect, it } from "vitest";

import { EXPIRY_WARNING_MS, expirySchedule, minutesLeft, parseIsoUtc } from "./time";

describe("parseIsoUtc", () => {
  it("parses the backend's microsecond UTC timestamps", () => {
    expect(parseIsoUtc("2026-11-10T22:27:44.829369Z")).toBe(
      Date.UTC(2026, 10, 10, 22, 27, 44, 829),
    );
    expect(parseIsoUtc("2026-11-10T22:27:44Z")).toBe(Date.UTC(2026, 10, 10, 22, 27, 44, 0));
    expect(parseIsoUtc("2026-11-10T22:27:44.5+00:00")).toBe(
      Date.UTC(2026, 10, 10, 22, 27, 44, 500),
    );
  });

  it("rejects non-UTC or malformed values", () => {
    for (const s of [
      "",
      "2026-11-10",
      "2026-11-10T22:27:44+05:30",
      "nonsense",
      "2026-13-45T99:99:99Z",
    ]) {
      expect(parseIsoUtc(s)).toBeNull();
    }
  });
});

describe("expiry schedule", () => {
  const now = Date.UTC(2026, 0, 1, 12, 0, 0);
  it("warns two minutes before expiry", () => {
    expect(EXPIRY_WARNING_MS).toBe(120_000);
    expect(expirySchedule(now + 600_000, now)).toEqual({ warnInMs: 480_000, expireInMs: 600_000 });
  });
  it("never schedules in the past", () => {
    expect(expirySchedule(now + 60_000, now)).toEqual({ warnInMs: 0, expireInMs: 60_000 });
    expect(expirySchedule(now - 1, now)).toEqual({ warnInMs: 0, expireInMs: 0 });
  });
  it("rounds minutes left up", () => {
    expect(minutesLeft(now + 61_000, now)).toBe(2);
    expect(minutesLeft(now - 5, now)).toBe(0);
  });
});

describe("timer clamping (browsers fire delays > 2^31 − 1 ms immediately)", () => {
  it("clamps far-future expiries and classifies the clock correctly", async () => {
    const { MAX_TIMER_MS, isExpired, isInWarningWindow } = await import("./time");
    const now = Date.UTC(2026, 0, 1);
    const farFuture = Date.UTC(2099, 0, 1);
    expect(expirySchedule(farFuture, now)).toEqual({
      warnInMs: MAX_TIMER_MS,
      expireInMs: MAX_TIMER_MS,
    });
    expect(isExpired(farFuture, now)).toBe(false);
    expect(isExpired(now, now)).toBe(true);
    expect(isInWarningWindow(now + 120_000, now)).toBe(true);
    expect(isInWarningWindow(now + 120_001, now)).toBe(false);
  });
});
