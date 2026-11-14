import { tokenStore } from "@/auth/tokenStore";

import { createApiClient } from "./client";

/** The application's single API client: same origin, token from the session store. */
export const api = createApiClient({
  baseUrl: window.location.origin,
  getToken: tokenStore.token,
  onUnauthorized: () => {
    tokenStore.clear("unauthorized");
  },
  // Resolved per call (not captured at import), so test doubles such as MSW can intercept it.
  fetch: (input) => globalThis.fetch(input),
});

export { unwrap } from "./client";
export { ApiError, isApiError } from "./errors";
