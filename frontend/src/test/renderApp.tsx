import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";

import { createApiClient } from "@/api/client";
import { ApiClientProvider } from "@/api/context";
import { AppRoutes } from "@/app/App";
import { createQueryClient } from "@/app/queryClient";
import { AuthProvider } from "@/auth/AuthProvider";
import { TokenStore } from "@/auth/tokenStore";

import { ORIGIN } from "./msw";

/** Shows the current location so tests can assert redirects. */
function LocationProbe() {
  const l = useLocation();
  return <output data-testid="location">{`${l.pathname}${l.search}`}</output>;
}

/** The real routes and providers, on a memory router, with a fresh store and client. */
export function renderApp(path: string, options: { store?: TokenStore; now?: () => number } = {}) {
  const store = options.store ?? new TokenStore();
  const client = createApiClient({
    baseUrl: ORIGIN,
    getToken: store.token,
    onUnauthorized: () => {
      store.clear("unauthorized");
    },
    fetch: (input) => globalThis.fetch(input),
  });
  const queryClient = createQueryClient();
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <AuthProvider client={client} store={store} {...(options.now ? { now: options.now } : {})}>
          <MemoryRouter
            initialEntries={[path]}
            future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
          >
            <AppRoutes />
            <LocationProbe />
          </MemoryRouter>
        </AuthProvider>
      </ApiClientProvider>
    </QueryClientProvider>,
  );
  return { ...utils, store, client, queryClient };
}
