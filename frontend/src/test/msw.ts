import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { recorded } from "@/fixtures";

export const ORIGIN = window.location.origin;
export const url = (path: string) => `${ORIGIN}/api/v1${path}`;

export const TEST_TOKEN = "tok_secret_value_9f8e7d6c";
export const TEST_EMAIL = "analyst@example.com";

/** An expiry far in the future, in the backend's microsecond ISO format. */
export const FAR_EXPIRY = "2099-01-01T00:00:00.000000Z";

/** Default handlers: a healthy backend with one known user. Values are recorded fixtures. */
export const handlers = [
  http.get(url("/health"), () => HttpResponse.json(recorded.health.body)),
  http.get(url("/auth/me"), ({ request }) =>
    request.headers.get("Authorization") === `Bearer ${TEST_TOKEN}`
      ? HttpResponse.json({ id: 1, email: TEST_EMAIL })
      : HttpResponse.json(
          {
            error_type: "authentication",
            status: 401,
            errors: [{ code: "UNAUTHORIZED", message: "Invalid or revoked token.", detail: null }],
          },
          { status: 401 },
        ),
  ),
  http.post(url("/auth/token"), async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string };
    if (body.password !== "correct-password-1") {
      return HttpResponse.json(
        {
          error_type: "authentication",
          status: 401,
          errors: [{ code: "UNAUTHORIZED", message: "Invalid email or password.", detail: null }],
        },
        { status: 401 },
      );
    }
    return HttpResponse.json({
      access_token: TEST_TOKEN,
      token_type: "bearer",
      expires_at: FAR_EXPIRY,
    });
  }),
  http.post(url("/auth/logout"), () => new HttpResponse(null, { status: 204 })),
];

export const server = setupServer(...handlers);
