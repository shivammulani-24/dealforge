import { act, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { server, TEST_EMAIL, url } from "@/test/msw";
import { renderApp } from "@/test/renderApp";

import { TokenStore } from "./tokenStore";

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});
afterEach(() => {
  server.resetHandlers();
  vi.useRealTimers();
});
afterAll(() => {
  server.close();
});

describe("session expiry (D4-01)", () => {
  it("warns two minutes before expiry, then ends the session and keeps the path", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const start = Date.UTC(2030, 0, 1, 12, 0, 0);
    vi.setSystemTime(start);
    server.use(http.get(url("/auth/me"), () => HttpResponse.json({ id: 1, email: TEST_EMAIL })));
    const store = new TokenStore();
    store.set("short-lived", "2030-01-01T12:10:00.000000Z"); // 10 minutes
    renderApp("/runs", { store });
    expect(await screen.findByText("Saved runs is built in milestone F7")).toBeInTheDocument();
    expect(screen.queryByText(/expires within two minutes/)).not.toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(8 * 60 * 1000 + 1);
    });
    expect(screen.getByText(/Your session expires within two minutes/)).toBeInTheDocument();
    expect(store.token()).toBe("short-lived");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2 * 60 * 1000);
    });
    expect(store.token()).toBeNull();
    expect(store.endReason()).toBe("expired");
    expect(screen.getByTestId("location").textContent).toBe("/login?next=%2Fruns&reason=expired");
    expect(screen.getByText(/Your session expired/)).toBeInTheDocument();
  });
});

describe("long-lived sessions", () => {
  it("does not end a session whose expiry is beyond the browser timer limit", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(Date.UTC(2030, 0, 1));
    server.use(http.get(url("/auth/me"), () => HttpResponse.json({ id: 1, email: TEST_EMAIL })));
    const store = new TokenStore();
    store.set("long-lived", "2099-01-01T00:00:00Z");
    renderApp("/runs", { store });
    expect(await screen.findByText("Saved runs is built in milestone F7")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_147_483_647 + 1000); // the clamped timer fires early
    });
    expect(store.token()).toBe("long-lived");
    expect(screen.queryByText(/expires within two minutes/)).not.toBeInTheDocument();
  });
});
