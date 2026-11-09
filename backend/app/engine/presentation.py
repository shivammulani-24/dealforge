"""Display ratios derived from a DCF result (Phase 4 plan §4.5, decision D4-06).

These are **not** part of ``run_dcf``'s result: they are computed on read, never written into a
frozen run's ``result_json``, and therefore never change a run's fingerprint. They are outside
ENGINE_VERSION's scope (plan §4.13).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .metrics import Metric, safe_ratio
from .valuation import DcfResult


@dataclass(frozen=True, slots=True)
class YearMargins:
    t: int
    ebit_margin: Metric  # EBIT_t / Revenue_t
    ufcf_margin: Metric  # UFCF_t / Revenue_t


def margins_from_values(
    revenues: Sequence[float], ebits: Sequence[float], ufcfs: Sequence[float]
) -> tuple[YearMargins, ...]:
    """Per-year margins; revenue ≤ 0 gives NM. Works on stored result values as well."""
    if not len(revenues) == len(ebits) == len(ufcfs):
        raise ValueError("revenues, ebits and ufcfs must have the same length")
    return tuple(
        YearMargins(
            t,
            safe_ratio(e, r, num_name="ebit", den_name="revenue"),
            safe_ratio(u, r, num_name="ufcf", den_name="revenue"),
        )
        for t, (r, e, u) in enumerate(zip(revenues, ebits, ufcfs, strict=True), start=1)
    )


def margins(result: DcfResult) -> tuple[YearMargins, ...]:
    return margins_from_values(
        [y.revenue for y in result.forecast.years],
        [y.ebit for y in result.forecast.years],
        [u.ufcf for u in result.ufcf],
    )
