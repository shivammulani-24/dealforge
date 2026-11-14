/**
 * Typed HTTP client (D4-08): `openapi-fetch` over the types generated from docs/openapi.json.
 *
 * One middleware adds `Authorization: Bearer …` and reports a 401 on an authenticated request,
 * so the session-expired flow runs no matter which screen made the call. A 401 on an
 * unauthenticated request (a wrong password on /auth/token) is left to the caller.
 */
import createClient, { type Middleware } from "openapi-fetch";

import { ApiError } from "./errors";
import type { paths } from "./schema";

export type ApiClient = ReturnType<typeof createClient<paths>>;

export interface ClientOptions {
  baseUrl: string;
  getToken: () => string | null;
  onUnauthorized: () => void;
  fetch?: typeof globalThis.fetch;
}

export function createApiClient(options: ClientOptions): ApiClient {
  const auth: Middleware = {
    onRequest({ request }) {
      const token = options.getToken();
      if (token !== null) request.headers.set("Authorization", `Bearer ${token}`);
      return request;
    },
    onResponse({ request, response }) {
      if (response.status === 401 && request.headers.has("Authorization")) {
        options.onUnauthorized();
      }
      return response;
    },
  };
  const client = createClient<paths>({
    baseUrl: options.baseUrl,
    ...(options.fetch === undefined ? {} : { fetch: options.fetch }),
  });
  client.use(auth);
  return client;
}

interface Result<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/**
 * Await an openapi-fetch call and return its typed data, or throw an `ApiError` built from the
 * backend's envelope. Network failures become `ApiError` with `errorType: "network"`; an
 * aborted request (query cancellation) is re-thrown unchanged.
 */
export async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  let result: Result<T>;
  try {
    result = await call;
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw ApiError.network();
  }
  if (!result.response.ok) {
    throw ApiError.fromResponse(result.response.status, result.error, result.response.headers);
  }
  return result.data as T;
}
