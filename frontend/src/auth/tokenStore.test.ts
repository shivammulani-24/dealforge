import { afterEach, describe, expect, it, vi } from "vitest";

import { safeNext, STORAGE_KEY, TokenStore } from "./tokenStore";

const FUTURE = "2099-01-01T00:00:00.123456Z";
const PAST = "2000-01-01T00:00:00Z";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TokenStore", () => {
  it("holds the session in memory and mirrors it to sessionStorage only", () => {
    const local = vi.spyOn(Storage.prototype, "setItem");
    const store = new TokenStore();
    const s = store.set("tok-1", FUTURE);
    expect(s).toMatchObject({
      token: "tok-1",
      expiresAt: FUTURE,
      expiresAtMs: Date.UTC(2099, 0, 1, 0, 0, 0, 123),
    });
    expect(store.token()).toBe("tok-1");
    expect(JSON.parse(window.sessionStorage.getItem(STORAGE_KEY)!)).toEqual({
      token: "tok-1",
      expiresAt: FUTURE,
    });
    // Every write went to sessionStorage, none to localStorage (D4-01).
    for (const call of local.mock.contexts) expect(call).toBe(window.sessionStorage);
    expect(window.localStorage.length).toBe(0);
  });

  it("restores a valid session after a reload", () => {
    new TokenStore().set("tok-2", FUTURE);
    expect(new TokenStore().token()).toBe("tok-2");
  });

  it("drops an expired or malformed stored session", () => {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ token: "old", expiresAt: PAST }));
    expect(new TokenStore().get()).toBeNull();
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBeNull();
    for (const raw of [
      "not json",
      "null",
      "42",
      JSON.stringify({ token: "", expiresAt: FUTURE }),
      JSON.stringify({ token: "x" }),
    ]) {
      window.sessionStorage.setItem(STORAGE_KEY, raw);
      expect(new TokenStore().get()).toBeNull();
    }
  });

  it("clears on logout, records why, and notifies subscribers", () => {
    const store = new TokenStore();
    const fn = vi.fn();
    const unsubscribe = store.subscribe(fn);
    store.set("tok-3", FUTURE);
    expect(store.endReason()).toBeNull();
    store.clear("expired");
    expect(store.get()).toBeNull();
    expect(store.endReason()).toBe("expired");
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(fn).toHaveBeenCalledTimes(2);
    store.clear("logout"); // no session: no extra notification
    expect(fn).toHaveBeenCalledTimes(2);
    unsubscribe();
    store.set("tok-4", FUTURE);
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it("rejects an invalid expiry from the server", () => {
    expect(() => new TokenStore().set("tok", "tomorrow")).toThrow(/invalid expiry/);
  });

  it("keeps working in memory when storage is blocked", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    const store = new TokenStore();
    expect(store.get()).toBeNull();
    store.set("tok-5", FUTURE);
    expect(store.token()).toBe("tok-5");
    store.clear("logout");
    expect(store.token()).toBeNull();
  });
});

describe("safeNext", () => {
  it.each([
    ["/style-guide", "/style-guide"],
    ["/runs/7?tab=audit", "/runs/7?tab=audit"],
    [null, "/"],
    [undefined, "/"],
    ["https://evil.example/", "/"],
    ["//evil.example", "/"],
    ["/\\evil.example", "/"],
    ["javascript:alert(1)", "/"],
    ["/login?next=/x", "/"],
    ["/register", "/"],
  ])("%j → %j", (next, expected) => {
    expect(safeNext(next)).toBe(expected);
  });
});
