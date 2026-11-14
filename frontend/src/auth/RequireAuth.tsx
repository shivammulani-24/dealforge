import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "./AuthProvider";

/**
 * Protected routes. Without a session the user goes to /login?next=<path>[&reason=…], and comes
 * back to the same screen after logging in (plan section 1).
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { session, store } = useAuth();
  const location = useLocation();
  if (session !== null) return <>{children}</>;
  const params = new URLSearchParams({ next: `${location.pathname}${location.search}` });
  const reason = store.endReason();
  if (reason !== null) params.set("reason", reason);
  return <Navigate to={`/login?${params.toString()}`} replace />;
}
