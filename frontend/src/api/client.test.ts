import { afterEach, describe, expect, it, vi } from "vitest";

import { recorded } from "@/fixtures";

import { createApiClient, unwrap } from "./client";
import { ApiError } from "./errors";

const TOKEN = "tok_must_never_leak_1234567890";

function setup(
  responder: (req: Request) => Response | Promise<Response>,
  token: string | null = TOKEN,
) {
  const seen: Request[] = [];
  const onUnauthorized = vi.fn();
  const client = createApiClient({
    baseUrl: "http://localhost:3000",
    getToken: () => token,
    onUnauthorized,
    fetch: async (input) => {
      const req = input instanceof Request ? input : new Request(input);
      seen.push(req);
      return responder(req);
    },
  });
  return { client, seen, onUnauthorized };
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => {
  vi.restoreAllMocks();
});

describe("typed client", () => {
  it("adds the bearer token and returns typed data", async () => {
    const { client, seen } = setup(() => json(recorded.health.body));
    const data = await unwrap(client.GET("/api/v1/health"));
    expect(data.engine_version).toBe("0.1.0");
    expect(seen[0]!.headers.get("Authorization")).toBe(`Bearer ${TOKEN}`);
    expect(seen[0]!.url).toBe("http://localhost:3000/api/v1/health");
  });

  it("sends no Authorization header without a session", async () => {
    const { client, seen } = setup(() => json(recorded.health.body), null);
    await unwrap(client.GET("/api/v1/health"));
    expect(seen[0]!.headers.has("Authorization")).toBe(false);
  });

  it("reports a 401 on an authenticated request (session-expired flow)", async () => {
    const { client, onUnauthorized } = setup(() =>
      json(
        { error_type: "authentication", status: 401, errors: [{ message: "Token expired" }] },
        401,
      ),
    );
    await expect(unwrap(client.GET("/api/v1/auth/me"))).rejects.toMatchObject({
      errorType: "authentication",
      status: 401,
    });
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("leaves a 401 on an unauthenticated request (wrong password) to the caller", async () => {
    const { client, onUnauthorized } = setup(
      () =>
        json({ error_type: "authentication", status: 401, errors: [{ message: "Invalid" }] }, 401),
      null,
    );
    await expect(
      unwrap(client.POST("/api/v1/auth/token", { body: { email: "a@b.co", password: "x" } })),
    ).rejects.toBeInstanceOf(ApiError);
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it("turns the backend envelope into an ApiError", async () => {
    const { client } = setup(() => json(recorded.errorCalculation.body, 422));
    const err = await unwrap(
      client.POST("/api/v1/scenarios/{scenario_id}/preview", {
        params: { path: { scenario_id: 1 } },
      }),
    ).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).codes).toEqual(["TERMINAL_GROWTH_GE_WACC"]);
  });

  it("maps a network failure to a network ApiError and re-throws aborts", async () => {
    const down = setup(() => {
      throw new TypeError("Failed to fetch");
    });
    await expect(unwrap(down.client.GET("/api/v1/health"))).rejects.toMatchObject({
      errorType: "network",
    });
    const aborted = setup(() => {
      throw new DOMException("The operation was aborted.", "AbortError");
    });
    await expect(unwrap(aborted.client.GET("/api/v1/health"))).rejects.toMatchObject({
      name: "AbortError",
    });
  });

  it("returns undefined data for 204 (logout)", async () => {
    const { client } = setup(() => new Response(null, { status: 204 }));
    await expect(unwrap(client.POST("/api/v1/auth/logout"))).resolves.toBeUndefined();
  });

  it("never exposes the token in errors or console output (D4-01)", async () => {
    const spies = (["log", "info", "warn", "error", "debug"] as const).map((m) =>
      vi.spyOn(console, m).mockImplementation(() => undefined),
    );
    const failures = [
      setup(() => json(recorded.errorValidation.body, 422)),
      setup(() => json({ error_type: "authentication", status: 401, errors: [] }, 401)),
      setup(() => new Response("<html>oops</html>", { status: 500 })),
      setup(() => {
        throw new TypeError("network down");
      }),
    ];
    for (const { client } of failures) {
      const err = await unwrap(client.GET("/api/v1/auth/me")).catch((e: unknown) => e);
      expect(err).toBeInstanceOf(ApiError);
      const e = err as ApiError;
      const surface = [
        e.message,
        e.stack ?? "",
        JSON.stringify(e),
        JSON.stringify(e.errors),
        String(e),
      ];
      for (const text of surface) expect(text).not.toContain(TOKEN);
    }
    for (const spy of spies) {
      for (const call of spy.mock.calls) expect(JSON.stringify(call)).not.toContain(TOKEN);
    }
  });
});
