import { useQuery } from "@tanstack/react-query";

import { unwrap } from "@/api/client";
import { useApiClient } from "@/api/context";

export const systemKeys = {
  health: ["health"] as const,
  me: ["auth", "me"] as const,
};

/** GET /api/v1/health: service status and the engine version (unauthenticated). */
export function useHealth() {
  const api = useApiClient();
  return useQuery({
    queryKey: systemKeys.health,
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/health", { signal })),
  });
}

/** GET /api/v1/auth/me: the signed-in user. */
export function useMe(enabled = true) {
  const api = useApiClient();
  return useQuery({
    queryKey: systemKeys.me,
    queryFn: ({ signal }) => unwrap(api.GET("/api/v1/auth/me", { signal })),
    enabled,
  });
}
