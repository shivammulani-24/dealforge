/**
 * Authentication state and flows (D4-01):
 * - login: POST /auth/token, then the token goes to the session store;
 * - register: POST /auth/register, then login;
 * - logout: POST /auth/logout revokes the token server-side, then the client clears it (even if
 *   the server call fails, so the user is never stuck signed in);
 * - expiry: a warning two minutes before `expires_at`, and the session ends at expiry;
 * - any 401 on an authenticated request ends the session (client middleware).
 * When a session ends the query cache is cleared, so no previous user's data stays on screen.
 */
import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";

import type { ApiClient } from "@/api/client";
import { unwrap } from "@/api/client";
import { expirySchedule, isExpired, isInWarningWindow } from "@/lib/time";

import type { Session, TokenStore } from "./tokenStore";

export interface AuthContextValue {
  session: Session | null;
  /** True from two minutes before expiry until the session ends. */
  expiringSoon: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  store: TokenStore;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({
  client,
  store,
  now = Date.now,
  children,
}: {
  client: ApiClient;
  store: TokenStore;
  now?: () => number;
  children: ReactNode;
}) {
  const queryClient = useQueryClient();
  const session = useSyncExternalStore(store.subscribe, store.get, store.get);
  const [warnedFor, setWarnedFor] = useState<string | null>(null);
  // Bumped when a clamped timer fires early, so the timers are re-armed (see MAX_TIMER_MS).
  const [rearm, setRearm] = useState<object>({});

  // Clear cached server data whenever the session ends or changes hands.
  useEffect(() => {
    if (session === null) queryClient.clear();
  }, [session, queryClient]);

  // Expiry timers for the current session.
  useEffect(() => {
    if (session === null) return;
    const { warnInMs, expireInMs } = expirySchedule(session.expiresAtMs, now());
    const warn = window.setTimeout(() => {
      if (isInWarningWindow(session.expiresAtMs, now())) setWarnedFor(session.token);
    }, warnInMs);
    const expire = window.setTimeout(() => {
      if (isExpired(session.expiresAtMs, now())) store.clear("expired");
      else setRearm({}); // fired early because the delay was clamped: re-arm
    }, expireInMs);
    return () => {
      window.clearTimeout(warn);
      window.clearTimeout(expire);
    };
  }, [session, store, now, rearm]);

  const login = useCallback(
    async (email: string, password: string) => {
      const tok = await unwrap(client.POST("/api/v1/auth/token", { body: { email, password } }));
      queryClient.clear();
      store.set(tok.access_token, tok.expires_at);
    },
    [client, queryClient, store],
  );

  const register = useCallback(
    async (email: string, password: string) => {
      await unwrap(client.POST("/api/v1/auth/register", { body: { email, password } }));
      await login(email, password);
    },
    [client, login],
  );

  const logout = useCallback(async () => {
    try {
      if (store.token() !== null) await unwrap(client.POST("/api/v1/auth/logout"));
    } catch {
      // Revocation failed (network or already revoked): still clear locally.
    } finally {
      store.clear("logout");
    }
  }, [client, store]);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      expiringSoon: session !== null && warnedFor === session.token,
      login,
      register,
      logout,
      store,
    }),
    [session, warnedFor, login, register, logout, store],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) throw new Error("useAuth must be used inside <AuthProvider>.");
  return ctx;
}
