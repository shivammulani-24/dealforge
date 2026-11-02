"""Unlevered free cash flow — free cash flow to the firm (FCFF) (spec section H.4, D-06).

::

    Taxes on EBIT = max(EBIT, 0) × T
    NOPAT         = EBIT − Taxes on EBIT
    UFCF          = NOPAT + D&A − CapEx − ΔNWC

For EBIT ≥ 0 this is exactly ``EBIT × (1 − T) + D&A − CapEx − ΔNWC``.

Why unlevered: interest is deliberately absent. UFCF is the cash available to *all* capital
providers (debt and equity) before any financing flows; the cost of financing enters through
the discount rate (WACC). Deducting interest here as well would count financing twice.

D-06: when EBIT < 0 the MVP charges zero tax rather than a negative tax (a refund). Tax-loss
carry-forwards (NOL tax shields) are **not modelled** — a conservative simplification that is
flagged with ``NEGATIVE_EBIT_NO_TAX_CREDIT``.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import Code, Issue, warning
from .forecast import Forecast
from .validation import Checker


@dataclass(frozen=True, slots=True)
class UfcfLine:
    t: int
    ebit: float
    taxes_on_ebit: float
    nopat: float
    da: float
    capex: float
    change_in_nwc: float
    ufcf: float
    issues: tuple[Issue, ...]


def validate_tax_rate(c: Checker, tax_rate: object, field: str = "tax_rate") -> float | None:
    return c.in_range(field, tax_rate, 0.0, 0.60)


def compute_ufcf(
    ebit: float,
    da: float,
    capex: float,
    change_in_nwc: float,
    tax_rate: float,
    *,
    t: int = 0,
) -> UfcfLine:
    c = Checker()
    c.number("ebit", ebit)
    c.non_negative("da", da)
    c.non_negative("capex", capex)
    c.number("change_in_nwc", change_in_nwc)
    validate_tax_rate(c, tax_rate)
    c.raise_if_errors()

    taxes = max(ebit, 0.0) * tax_rate
    nopat = ebit - taxes
    ufcf = nopat + da - capex - change_in_nwc
    issues: list[Issue] = []
    label = f"Year {t}" if t else "Period"
    if ebit < 0:
        issues.append(
            warning(
                Code.NEGATIVE_EBIT_NO_TAX_CREDIT,
                f"{label}: EBIT is negative ({ebit:,.2f}); tax set to zero, no credit for losses "
                "and no NOL carry-forward modelled (D-06).",
            )
        )
    if ufcf < 0:
        issues.append(
            warning(
                Code.NEGATIVE_UFCF, f"{label}: unlevered free cash flow is negative ({ufcf:,.2f})."
            )
        )
    return UfcfLine(t, ebit, taxes, nopat, da, capex, change_in_nwc, ufcf, tuple(issues))


def forecast_ufcf(forecast: Forecast, tax_rate: float) -> tuple[UfcfLine, ...]:
    return tuple(
        compute_ufcf(y.ebit, y.da, y.capex, y.change_in_nwc, tax_rate, t=y.t)
        for y in forecast.years
    )
