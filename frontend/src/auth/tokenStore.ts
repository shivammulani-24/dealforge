/**
 * Session token store (D4-01, approved for the development stage).
 *
 * - Held in memory and mirrored to `sessionStorage` so a reload keeps the session. The browser
 *   drops `sessionStorage` when the tab closes.
 * - Cleared on logout, on any 401 and at expiry.
 * - Never written to `localStorage` (lint-enforced), URLs, logs or error objects.
 *
 * LIM-20: this is readable by injected script. An HttpOnly, Secure, SameSite=Strict cookie with
 * CSRF protection is required before any public deployment.
 */
import { parseIsoUtc } from "@/lib/time";

export const STORAGE_KEY = "dealforge.session.v1";

export interface Session {
  token: string;
  /** ISO-8601 UTC, as returned by POST /auth/token. */
  expiresAt: string;
  expiresAtMs: number;
}

/** Why the last session ended; the login page explains it. */
export type EndReason = "logout" | "expired" | "unauthorized";

type Listener = () => void;

function storage(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null; // storage blocked: memory only
  }
}

function readStored(now: number): Session | null {
  const s = storage();
  if (s === null) return null;
  try {
    const raw = s.getItem(STORAGE_KEY);
    if (raw === null) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (typeof parsed !== "object" || parsed === null) return null;
    const { token, expiresAt } = parsed as Record<string, unknown>;
    if (typeof token !== "string" || token === "" || typeof expiresAt !== "string") return null;
    const expiresAtMs = parseIsoUtc(expiresAt);
    if (expiresAtMs === null || expiresAtMs <= now) {
      s.removeItem(STORAGE_KEY);
      return null;
    }
    return { token, expiresAt, expiresAtMs };
  } catch {
    return null;
  }
}

export class TokenStore {
  private session: Session | null;
  private reason: EndReason | null = null;
  private readonly listeners = new Set<Listener>();

  constructor(now: () => number = Date.now) {
    this.session = readStored(now());
  }

  get = (): Session | null => this.session;

  token = (): string | null => this.session?.token ?? null;

  /** The reason the previous session ended, until a new one starts. */
  endReason = (): EndReason | null => this.reason;

  set(token: string, expiresAt: string): Session {
    const expiresAtMs = parseIsoUtc(expiresAt);
    if (expiresAtMs === null) throw new Error("The server returned an invalid expiry time.");
    this.session = { token, expiresAt, expiresAtMs };
    this.reason = null;
    try {
      storage()?.setItem(STORAGE_KEY, JSON.stringify({ token, expiresAt }));
    } catch {
      // quota or privacy mode: the in-memory session still works for this page load
    }
    this.emit();
    return this.session;
  }

  clear(reason: EndReason): void {
    const had = this.session !== null;
    this.session = null;
    this.reason = reason;
    try {
      storage()?.removeItem(STORAGE_KEY);
    } catch {
      // nothing stored
    }
    if (had) this.emit();
  }

  subscribe = (fn: Listener): (() => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };

  private emit(): void {
    for (const fn of this.listeners) fn();
  }
}

export const tokenStore = new TokenStore();

/** Only same-site relative paths are accepted as a post-login destination (no open redirect). */
export function safeNext(next: string | null | undefined): string {
  if (next === null || next === undefined) return "/";
  if (!next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return "/";
  if (next.startsWith("/login") || next.startsWith("/register")) return "/";
  return next;
}
