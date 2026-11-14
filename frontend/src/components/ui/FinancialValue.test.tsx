import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ErrorBoundary } from "@/app/ErrorBoundary";
import { recorded } from "@/fixtures";

import { BasisBadge, BasisLegend } from "./Badge";
import { FinancialValue, type FinancialValueProps } from "./FinancialValue";

describe("FinancialValue", () => {
  it("renders the formatted value with full precision and basis on hover", () => {
    render(
      <FinancialValue
        value={recorded.run.body.result.wacc}
        kind="rate"
        basis="derived"
        showBasis
      />,
    );
    const el = screen.getByText("9.60%").parentElement!;
    expect(el).toHaveAttribute("title", "0.0959980079681275 (fraction)");
    expect(el).toHaveAttribute("data-basis", "derived");
    expect(screen.getByLabelText("Derived")).toHaveTextContent("D");
  });

  it("shows assumed values in the input colour", () => {
    render(<FinancialValue value={0.025} kind="rate" basis="assumed" />);
    expect(screen.getByText("2.50%").parentElement!).toHaveClass("text-accent");
  });

  it("renders missing as — with the reason, never as 0 (R3)", () => {
    const p = recorded.historicalAnalysis.body.periods[0]!;
    render(<FinancialValue metric={p.ebitda.reported} kind="amount" basis="reported" />);
    const el = screen.getByText("—").parentElement!;
    expect(el).toHaveAttribute("data-state", "missing");
    expect(el).toHaveAttribute("title", "Missing: missing input: reported EBITDA");
    expect(el.textContent).not.toMatch(/0/);
  });

  it("renders null as —", () => {
    render(<FinancialValue value={null} kind="amount" basis="reported" />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("cannot render without a basis (R2)", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined); // React logs caught errors
    const noBasis = { value: 1, kind: "amount" } as unknown as FinancialValueProps;
    render(
      <ErrorBoundary>
        <FinancialValue {...noBasis} />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/must declare its basis/);
    const badBasis = {
      value: 1,
      kind: "amount",
      basis: "estimated",
    } as unknown as FinancialValueProps;
    expect(() => render(<FinancialValue {...badBasis} />)).toThrow(/must declare its basis/);
  });

  it("legend and badges cover R, D and A", () => {
    render(
      <>
        <BasisLegend />
        <BasisBadge basis="assumed" />
      </>,
    );
    const legend = screen.getByRole("list", { name: "Basis legend" });
    expect(legend).toHaveTextContent("ReportedDDerivedAAssumed".replace(/^/, "R"));
  });
});
