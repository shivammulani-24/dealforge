import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import type { ApiClient } from "@/api/client";
import { ApiClientProvider } from "@/api/context";
import { AuthProvider } from "@/auth/AuthProvider";
import { LoginPage, RegisterPage } from "@/auth/AuthPages";
import { RequireAuth } from "@/auth/RequireAuth";
import type { TokenStore } from "@/auth/tokenStore";
import { SkeletonRows } from "@/components/ui/Feedback";

import { AppShell } from "./AppShell";
import { ErrorBoundary } from "./ErrorBoundary";
import { NotFoundPage, PlannedScreen } from "./pages";

// The design-system page is code-split, so its recorded fixtures never load with the app.
const StyleGuidePage = lazy(() => import("@/features/styleguide/StyleGuidePage"));

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<PlannedScreen title="Dashboard" milestone="F2" />} />
        <Route path="companies/*" element={<PlannedScreen title="Companies" milestone="F2" />} />
        <Route path="runs/*" element={<PlannedScreen title="Saved runs" milestone="F7" />} />
        <Route
          path="style-guide"
          element={
            <Suspense fallback={<SkeletonRows rows={8} label="Loading the design system" />}>
              <StyleGuidePage />
            </Suspense>
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export function App({
  client,
  store,
  queryClient,
}: {
  client: ApiClient;
  store: TokenStore;
  queryClient: QueryClient;
}) {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <AuthProvider client={client} store={store}>
            <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
              <AppRoutes />
            </BrowserRouter>
          </AuthProvider>
        </ApiClientProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
