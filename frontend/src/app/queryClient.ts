import { QueryClient } from "@tanstack/react-query";

import { isApiError } from "@/api/errors";

/**
 * Server state lives in TanStack Query (no global state library).
 * - Queries retry once, and only for network or 5xx failures; a 4xx is an answer, not a glitch.
 * - Mutations are never retried automatically (plan section 1: POST is never auto-retried).
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: (failureCount, error) =>
          failureCount < 1 && !(isApiError(error) && error.status >= 400 && error.status < 500),
        refetchOnWindowFocus: false,
        staleTime: 30_000,
      },
      mutations: { retry: false },
    },
  });
}
