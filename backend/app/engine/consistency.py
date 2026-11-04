"""Forecast assumptions vs historical evidence (LIM-12, spec H.3).

Each forecast driver is compared with the range the company actually achieved. A driver more
than ``tolerance`` (default 10 percentage points) outside the historical [min, max] range is
flagged, so an unrealistic assumption is visible next to the evidence. Missing or NM historical
values are left out of the range; if no historical value exists at all, that is disclosed
instead of comparing against nothing.

Warnings only: management plans, turnarounds and acquisitions can justify a break from history,
but the analyst should have to explain it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import Code, Issue, info, warning
from .forecast import ForecastInputs
from .historical import HistoricalAnalysis

DEFAULT_TOLERANCE = 0.10

#: forecast driver field → historical metric name
DRIVER_METRICS: dict[str, str] = {
    "revenue_growth": "revenue_growth",
    "ebitda_margin": "ebitda_margin",
    "da_pct_revenue": "da_pct_revenue",
    "capex_pct_revenue": "capex_pct_revenue",
    "nwc_pct_revenue": "nwc_pct_revenue",
}


@dataclass(frozen=True, slots=True)
class HistoricalRange:
    driver: str
    minimum: float | None
    maximum: float | None
    observations: int


def historical_ranges(history: HistoricalAnalysis) -> dict[str, HistoricalRange]:
    out: dict[str, HistoricalRange] = {}
    for driver, metric in DRIVER_METRICS.items():
        vals = [
            p.metrics[metric].value
            for p in history.periods
            if metric in p.metrics and p.metrics[metric].is_ok
        ]
        nums = [v for v in vals if v is not None]
        out[driver] = HistoricalRange(
            driver, min(nums) if nums else None, max(nums) if nums else None, len(nums)
        )
    return out


def driver_history_warnings(
    forecast: ForecastInputs,
    history: HistoricalAnalysis,
    tolerance: float = DEFAULT_TOLERANCE,
) -> tuple[Issue, ...]:
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")
    issues: list[Issue] = []
    for driver, rng in historical_ranges(history).items():
        if rng.minimum is None or rng.maximum is None:
            issues.append(
                info(
                    Code.DRIVER_NO_HISTORY,
                    f"No meaningful historical {driver.replace('_', ' ')} to compare the "
                    "forecast with.",
                    driver,
                )
            )
            continue
        lo, hi = rng.minimum - tolerance, rng.maximum + tolerance
        for t, year in enumerate(forecast.years, start=1):
            v = getattr(year, driver)
            if v < lo or v > hi:
                issues.append(
                    warning(
                        Code.DRIVER_OUTSIDE_HISTORY,
                        f"Year {t} {driver.replace('_', ' ')} {v:.1%} is more than "
                        f"{tolerance * 100:.0f}pp outside the historical range "
                        f"{rng.minimum:.1%}–{rng.maximum:.1%} ({rng.observations} years).",
                        f"years[{t}].{driver}",
                    )
                )
    return tuple(issues)
