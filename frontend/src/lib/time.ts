/**
 * Session-timing helpers (D4-01). Kept in src/lib because they are the only arithmetic the
 * auth layer needs, and src/lib is the only place arithmetic is allowed.
 */

/** Warn this long before the token expires (plan section 1: two minutes). */
export const EXPIRY_WARNING_MS = 2 * 60 * 1000;

/**
 * Parse the backend's ISO-8601 UTC timestamp ("2026-11-10T22:27:44.829369Z") to epoch ms.
 * Fractions beyond milliseconds are truncated so every engine parses the same instant.
 * Returns null when the string is not a valid UTC timestamp.
 */
export function parseIsoUtc(iso: string): number | null {
  const m = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]00:00)$/.exec(iso);
  if (m === null) return null;
  const ms = (m[2] ?? "").padEnd(3, "0").slice(0, 3);
  const t = Date.parse(`${m[1] ?? ""}.${ms}Z`);
  return Number.isNaN(t) ? null : t;
}

/**
 * Browsers fire a timer IMMEDIATELY when its delay exceeds 2^31 − 1 ms (~24.8 days), so every
 * delay is clamped to this and a timer that fires early re-checks the clock and re-arms.
 */
export const MAX_TIMER_MS = 2_147_483_647;

export interface ExpirySchedule {
  /** ms from `now` until the warning should show (0 if already due). */
  warnInMs: number;
  /** ms from `now` until the session expires (0 if already expired). */
  expireInMs: number;
}

/** Timer delays (clamped to MAX_TIMER_MS) for the warning and the expiry. */
export function expirySchedule(expiresAtMs: number, nowMs: number): ExpirySchedule {
  const left = Math.max(0, expiresAtMs - nowMs);
  return {
    warnInMs: Math.min(MAX_TIMER_MS, Math.max(0, left - EXPIRY_WARNING_MS)),
    expireInMs: Math.min(MAX_TIMER_MS, left),
  };
}

export function isExpired(expiresAtMs: number, nowMs: number): boolean {
  return nowMs >= expiresAtMs;
}

export function isInWarningWindow(expiresAtMs: number, nowMs: number): boolean {
  return nowMs >= expiresAtMs - EXPIRY_WARNING_MS;
}

/** Whole minutes left, rounded up, for "expires in 2 minutes" text. */
export function minutesLeft(expiresAtMs: number, nowMs: number): number {
  return Math.max(0, Math.ceil((expiresAtMs - nowMs) / 60000));
}
