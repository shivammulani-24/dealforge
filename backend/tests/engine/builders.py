"""Explicit input builders for tests. Every number a test depends on is visible at the call site
or documented here; nothing is defaulted silently inside the engine."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from app.engine.bridge import BridgeInputs
from app.engine.dates import ValuationDates
from app.engine.forecast import ForecastInputs, ForecastYearDrivers
from app.engine.shares import (
    ConvertibleInstrument,
    OptionTranche,
    RsuGrant,
    ShareCapitalInputs,
)
from app.engine.valuation import DcfInputs
from app.engine.wacc import DebtValueBasis, WaccAssumptions

STATEMENT_DATE = date(2025, 3, 31)


def dates(market: date = STATEMENT_DATE) -> ValuationDates:
    return ValuationDates(STATEMENT_DATE, STATEMENT_DATE, market)


def bridge(
    *,
    cash: float = 0.0,
    debt: float = 0.0,
    leases: float = 0.0,
    include_leases: bool = False,
    preferred: float = 0.0,
    nci: float = 0.0,
    other: float = 0.0,
    non_operating: float = 0.0,
) -> BridgeInputs:
    return BridgeInputs(
        cash=cash,
        total_debt=debt,
        lease_liabilities=leases,
        include_leases_in_debt=include_leases,
        preferred_equity=preferred,
        non_controlling_interest=nci,
        other_debt_like_claims=other,
        non_operating_assets=non_operating,
    )


def cap(
    basic: float = 100.0,
    options: tuple[OptionTranche, ...] = (),
    rsus: tuple[RsuGrant, ...] = (),
    convertibles: tuple[ConvertibleInstrument, ...] = (),
) -> ShareCapitalInputs:
    return ShareCapitalInputs(basic, options, rsus, convertibles)


def constant_drivers(
    g: float, m: float, d: float, c: float, n: float
) -> tuple[ForecastYearDrivers, ...]:
    return tuple(ForecastYearDrivers(g, m, d, c, n) for _ in range(5))


def ka_dcf02_forecast() -> ForecastInputs:
    """Drivers chosen by hand so that UFCF = 100, 110, 121, 133.1, 146.41 (see test_valuation).

    Revenue_0 = 1,000, g = 10%, EBITDA margin 21%, D&A 5%, CapEx 5%, NWC 32% (NWC_0 = 320).
    Year 1: revenue 1,100; EBIT = 0.16 × 1,100 = 176; NOPAT = 132; + D&A 55 − CapEx 55
            − ΔNWC (352 − 320 = 32) = 100.
    UFCF is proportional to revenue, so it grows at exactly 10%.
    """
    return ForecastInputs(1000.0, 320.0, constant_drivers(0.10, 0.21, 0.05, 0.05, 0.32))


def wacc_assumptions(**kw: object) -> WaccAssumptions:
    base = WaccAssumptions(
        risk_free_rate=0.04,
        levered_beta=1.2,
        equity_risk_premium=0.055,
        pre_tax_cost_of_debt=0.06,
        size_premium=0.0,
        debt_value_basis=DebtValueBasis.BOOK,
    )
    return replace(base, **kw)  # type: ignore[arg-type]


def dcf_inputs(**kw: object) -> DcfInputs:
    """KA-DCF-02 base case: WACC fixed at 10%, g = 2%, debt 300, cash 100, NCI 20, 100 shares."""
    base = DcfInputs(
        dates=dates(),
        forecast=ka_dcf02_forecast(),
        tax_rate=0.25,
        terminal_growth=0.02,
        bridge=bridge(cash=100.0, debt=300.0, nci=20.0),
        share_capital=cap(100.0),
        current_share_price=12.0,
        wacc_assumptions=None,
        wacc_override=0.10,
        is_financial_institution=False,
    )
    return replace(base, **kw)  # type: ignore[arg-type]
