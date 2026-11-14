import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import { ApiClientProvider } from "@/api/context";
import { createQueryClient } from "@/app/queryClient";
import { recorded } from "@/fixtures";
import { formatNumber } from "@/lib/format";
import { ORIGIN, server, TEST_EMAIL, TEST_TOKEN } from "@/test/msw";

import StyleGuidePage from "./StyleGuidePage";

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});
afterAll(() => {
  server.close();
});

function renderPage() {
  const client = createApiClient({
    baseUrl: ORIGIN,
    getToken: () => TEST_TOKEN,
    onUnauthorized: () => undefined,
    fetch: (input) => globalThis.fetch(input),
  });
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <ApiClientProvider client={client}>
        <MemoryRouter>
          <StyleGuidePage />
        </MemoryRouter>
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

describe("design-system page", () => {
  it("talks to the backend through the typed client", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("me-email")).toHaveTextContent(TEST_EMAIL);
    });
    expect(screen.getByTestId("engine-version")).toHaveTextContent("0.1.0");
    expect(screen.getByTestId("engine-version")).toHaveTextContent("matches recorded data");
  });

  it("gives every financial value a basis and never prints NaN, undefined or a bare 0 for missing", () => {
    const { container } = renderPage();
    const values = [...container.querySelectorAll("[data-state]")];
    expect(values.length).toBeGreaterThan(150);
    for (const v of values)
      expect(["reported", "derived", "assumed"]).toContain(v.getAttribute("data-basis"));
    // The value text is the first child; a basis badge may follow it.
    for (const v of container.querySelectorAll('[data-state="missing"]')) {
      expect(v.firstElementChild?.textContent).toBe("—");
    }
    expect(container.textContent).not.toMatch(/NaN|undefined|Infinity/);
  });

  it("display trace: KPIs show exactly format(apiValue) from the frozen run", () => {
    const { container } = renderPage();
    const r = recorded.run.body.result;
    const strip = container.querySelector('dl[aria-label="Valuation summary"]');
    if (strip === null) throw new Error("KPI strip not rendered");
    for (const [v, kind] of [
      [r.wacc, "rate"],
      [r.valuation.enterprise_value, "amount"],
      [r.bridge.equity_value, "amount"],
      [r.per_share.value_per_share, "per_share"],
    ] as const) {
      expect(strip.textContent).toContain(formatNumber(v, kind).text);
    }
  });

  it("labels the synthetic data (R4) and shows each section", () => {
    renderPage();
    expect(screen.getAllByText(/SYNTHETIC – not real data/).length).toBeGreaterThan(0);
    for (const h of [
      "Colour",
      "Typography",
      "Financial number formats",
      "Sensitivity grid",
      "Tables",
    ]) {
      expect(screen.getByRole("heading", { name: h })).toBeInTheDocument();
    }
  });
});
