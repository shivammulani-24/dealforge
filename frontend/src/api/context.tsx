import { createContext, type ReactNode, useContext } from "react";

import type { ApiClient } from "./client";

const ApiClientContext = createContext<ApiClient | null>(null);

/**
 * Provides the typed API client to every query and mutation hook, so hooks never reach for a
 * module-level singleton: the client (with its token source) is chosen once, by the app root.
 */
export function ApiClientProvider({
  client,
  children,
}: {
  client: ApiClient;
  children: ReactNode;
}) {
  return <ApiClientContext.Provider value={client}>{children}</ApiClientContext.Provider>;
}

export function useApiClient(): ApiClient {
  const client = useContext(ApiClientContext);
  if (client === null) throw new Error("useApiClient must be used inside <ApiClientProvider>.");
  return client;
}
