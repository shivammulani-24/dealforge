"""Valuation-date conventions (decision D-07, refined).

Four kinds of date are kept separate and are never silently treated as interchangeable:

=========================  ============================================================
``statement_date``         Balance-sheet date of the last historical fiscal year (LFY).
                           Cash, debt, NWC and share counts are measured here.
``valuation_date``         The date the enterprise value is struck at. MVP convention:
                           **must equal ``statement_date``** (no stub period).
forecast periods           Fiscal years t = 1..N ending one, two, ... years after the
                           statement date; cash flows arrive at each year end
                           (end-of-year discounting, discount exponent = t).
``market_data_date``       Date of the share price, risk-free rate, beta and ERP used for
                           WACC and market capitalisation. May differ from the valuation
                           date; the gap is always reported.
=========================  ============================================================
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from .errors import Code, Issue, info, warning
from .validation import Checker

#: Market data more than this many days away from the valuation date triggers a warning.
MARKET_DATA_STALE_DAYS = 92


def add_years(d: date, years: int) -> date:
    """Same month/day ``years`` later; 29 Feb maps to 28 Feb in non-leap years."""
    y = d.year + years
    last_day = calendar.monthrange(y, d.month)[1]
    return date(y, d.month, min(d.day, last_day))


@dataclass(frozen=True, slots=True)
class ValuationDates:
    statement_date: date
    valuation_date: date
    market_data_date: date


@dataclass(frozen=True, slots=True)
class ForecastPeriod:
    t: int  # 1..N; also the discounting exponent under end-of-year convention
    label: str  # e.g. "FY2026" (fiscal years are labelled by the calendar year they end in)
    end_date: date


@dataclass(frozen=True, slots=True)
class DateSchedule:
    statement_date: date
    valuation_date: date
    market_data_date: date
    market_data_gap_days: int  # market_data_date − valuation_date (signed)
    periods: tuple[ForecastPeriod, ...]
    convention: str
    issues: tuple[Issue, ...]


CONVENTION_TEXT = (
    "Valuation date = last fiscal year-end balance-sheet date; forecast cash flows are "
    "discounted from each fiscal year-end (end-of-year convention, exponent t = 1..N); "
    "market data (price, risk-free rate, beta, ERP) is dated separately."
)


def build_schedule(dates: ValuationDates, horizon_years: int) -> DateSchedule:
    c = Checker()
    for name in ("statement_date", "valuation_date", "market_data_date"):
        if not isinstance(getattr(dates, name), date):
            c.error(Code.INVALID_TYPE, f"'{name}' must be a date.", name)
    c.raise_if_errors()

    if dates.valuation_date != dates.statement_date:
        c.error(
            Code.STUB_PERIOD_NOT_SUPPORTED,
            f"Valuation date {dates.valuation_date.isoformat()} differs from the statement date "
            f"{dates.statement_date.isoformat()}. The MVP values the company at the last fiscal "
            "year-end (D-07); stub periods are a planned enhancement.",
            "valuation_date",
        )
    gap = (dates.market_data_date - dates.valuation_date).days
    if dates.market_data_date < dates.statement_date:
        c.error(
            Code.MARKET_DATA_BEFORE_STATEMENTS,
            f"Market data date {dates.market_data_date.isoformat()} precedes the statement date "
            f"{dates.statement_date.isoformat()}; the price would not reflect those statements.",
            "market_data_date",
        )
    c.raise_if_errors()

    issues: list[Issue] = []
    if abs(gap) > MARKET_DATA_STALE_DAYS:
        issues.append(
            warning(
                Code.MARKET_DATA_STALE,
                f"Market data is dated {gap} days after the valuation date "
                f"(> {MARKET_DATA_STALE_DAYS}). Price-based inputs (market cap, WACC weights, "
                "TSM dilution) reflect information not available at the valuation date.",
                "market_data_date",
            )
        )
    elif gap != 0:
        issues.append(
            info(
                Code.MARKET_DATA_DATE_DIFFERS,
                f"Market data is dated {gap} days after the valuation date.",
                "market_data_date",
            )
        )

    periods = tuple(
        ForecastPeriod(
            t=t,
            label=f"FY{add_years(dates.statement_date, t).year}",
            end_date=add_years(dates.statement_date, t),
        )
        for t in range(1, horizon_years + 1)
    )
    return DateSchedule(
        statement_date=dates.statement_date,
        valuation_date=dates.valuation_date,
        market_data_date=dates.market_data_date,
        market_data_gap_days=gap,
        periods=periods,
        convention=CONVENTION_TEXT,
        issues=tuple(issues),
    )
