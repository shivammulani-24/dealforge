"""Five-year driver-based operating forecast (spec section H.3, decision D-16).

For each forecast year t = 1..5::

    Revenue_t = Revenue_{t-1} × (1 + g_t)          Revenue_0 = last fiscal year (LFY) actual
    EBITDA_t  = Revenue_t × EBITDA margin_t
    D&A_t     = Revenue_t × D&A %_t
    EBIT_t    = EBITDA_t − D&A_t
    CapEx_t   = Revenue_t × CapEx %_t
    NWC_t     = Revenue_t × NWC %_t                NWC_0 = LFY actual operating NWC
    ΔNWC_t    = NWC_t − NWC_{t-1}                  (positive = cash absorbed)

Taxes and free cash flow are computed in :mod:`fcf`; this module is pure operating build-up.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import Code, Issue, warning
from .validation import Checker

HORIZON_YEARS = 5

#: Growth above this in any single year is flagged as extreme (not rejected).
EXTREME_GROWTH_THRESHOLD = 0.50
#: Year-1 NWC % differing from LFY NWC % by more than this triggers a step-change warning.
NWC_STEP_THRESHOLD = 0.02


@dataclass(frozen=True, slots=True)
class ForecastYearDrivers:
    revenue_growth: float
    ebitda_margin: float
    da_pct_revenue: float
    capex_pct_revenue: float
    nwc_pct_revenue: float  # may be negative (e.g. businesses funded by customer prepayments)


@dataclass(frozen=True, slots=True)
class ForecastInputs:
    base_revenue: float  # LFY actual revenue
    base_nwc: float  # LFY actual operating NWC (signed)
    years: tuple[ForecastYearDrivers, ...]


@dataclass(frozen=True, slots=True)
class ForecastYear:
    t: int
    revenue: float
    ebitda: float
    da: float
    ebit: float
    capex: float
    nwc: float
    change_in_nwc: float


@dataclass(frozen=True, slots=True)
class Forecast:
    years: tuple[ForecastYear, ...]
    issues: tuple[Issue, ...]


def validate_forecast_inputs(inp: ForecastInputs) -> tuple[Issue, ...]:
    c = Checker()
    c.positive("base_revenue", inp.base_revenue)
    c.number("base_nwc", inp.base_nwc)
    if len(inp.years) != HORIZON_YEARS:
        c.error(
            Code.HORIZON_NOT_SUPPORTED,
            f"The forecast must have exactly {HORIZON_YEARS} years (D-16); got {len(inp.years)}.",
            "years",
        )
    for i, y in enumerate(inp.years, start=1):
        p = f"years[{i}]"
        c.in_range(f"{p}.revenue_growth", y.revenue_growth, -1.0, 10.0, low_inclusive=False)
        c.in_range(
            f"{p}.ebitda_margin",
            y.ebitda_margin,
            -1.0,
            1.0,
            low_inclusive=False,
            high_inclusive=False,
        )
        c.in_range(f"{p}.da_pct_revenue", y.da_pct_revenue, 0.0, 1.0)
        c.in_range(f"{p}.capex_pct_revenue", y.capex_pct_revenue, 0.0, 1.0)
        c.in_range(
            f"{p}.nwc_pct_revenue",
            y.nwc_pct_revenue,
            -1.0,
            1.0,
            low_inclusive=False,
            high_inclusive=False,
        )
    c.raise_if_errors()

    issues: list[Issue] = []
    for i, y in enumerate(inp.years, start=1):
        if y.revenue_growth > EXTREME_GROWTH_THRESHOLD:
            issues.append(
                warning(
                    Code.EXTREME_GROWTH,
                    f"Year {i} revenue growth {y.revenue_growth:.1%} exceeds "
                    f"{EXTREME_GROWTH_THRESHOLD:.0%}.",
                    f"years[{i}].revenue_growth",
                )
            )
        if y.ebitda_margin < 0:
            issues.append(
                warning(
                    Code.NEGATIVE_EBITDA_MARGIN,
                    f"Year {i} EBITDA margin is negative ({y.ebitda_margin:.1%}).",
                    f"years[{i}].ebitda_margin",
                )
            )
    last = inp.years[-1]
    if last.capex_pct_revenue < last.da_pct_revenue:
        issues.append(
            warning(
                Code.CAPEX_BELOW_DA_TERMINAL,
                f"Final-year CapEx ({last.capex_pct_revenue:.1%} of revenue) is below D&A "
                f"({last.da_pct_revenue:.1%}). The terminal value then assumes the asset base "
                "shrinks forever while revenue keeps growing.",
                f"years[{HORIZON_YEARS}].capex_pct_revenue",
            )
        )
    base_pct = inp.base_nwc / inp.base_revenue
    first = inp.years[0].nwc_pct_revenue
    if abs(first - base_pct) > NWC_STEP_THRESHOLD:
        rev1 = inp.base_revenue * (1 + inp.years[0].revenue_growth)
        step = rev1 * first - inp.base_nwc
        issues.append(
            warning(
                Code.NWC_STEP_CHANGE,
                f"Year-1 NWC is {first:.1%} of revenue vs {base_pct:.1%} in the last actual year; "
                f"this alone moves year-1 ΔNWC to {step:,.2f}.",
                "years[1].nwc_pct_revenue",
            )
        )
    return tuple(issues)


def build_forecast(inp: ForecastInputs) -> Forecast:
    issues = validate_forecast_inputs(inp)
    out: list[ForecastYear] = []
    prev_rev, prev_nwc = inp.base_revenue, inp.base_nwc
    for t, d in enumerate(inp.years, start=1):
        revenue = prev_rev * (1.0 + d.revenue_growth)
        ebitda = revenue * d.ebitda_margin
        da = revenue * d.da_pct_revenue
        nwc = revenue * d.nwc_pct_revenue
        out.append(
            ForecastYear(
                t=t,
                revenue=revenue,
                ebitda=ebitda,
                da=da,
                ebit=ebitda - da,
                capex=revenue * d.capex_pct_revenue,
                nwc=nwc,
                change_in_nwc=nwc - prev_nwc,
            )
        )
        prev_rev, prev_nwc = revenue, nwc
    return Forecast(tuple(out), issues)
