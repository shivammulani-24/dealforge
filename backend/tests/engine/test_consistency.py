"""LIM-12 (forecast drivers vs history) and LIM-13 (D&A vs operating costs)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from builders import constant_drivers
from test_historical import FY23, FY24

from app.engine.consistency import driver_history_warnings, historical_ranges
from app.engine.errors import Code
from app.engine.forecast import ForecastInputs
from app.engine.historical import analyze_historicals

# History: growth 20% (FY24 only); EBITDA margin 19.0% / 18.75%; D&A 4.0% / 3.75%;
# CapEx 5.0% / 5.83%; NWC 10.0% / 16.67%.
HIST = analyze_historicals([FY23, FY24])


def test_ranges_use_only_meaningful_values() -> None:
    r = historical_ranges(HIST)
    assert r["revenue_growth"].observations == 1  # FY23 growth is NM, not 0
    assert r["revenue_growth"].minimum == pytest.approx(0.20)
    assert (r["ebitda_margin"].minimum, r["ebitda_margin"].maximum) == pytest.approx((0.1875, 0.19))
    assert r["nwc_pct_revenue"].maximum == pytest.approx(200 / 1200)


def test_drivers_inside_tolerance_raise_nothing() -> None:
    f = ForecastInputs(1200.0, 200.0, constant_drivers(0.15, 0.22, 0.04, 0.05, 0.15))
    assert driver_history_warnings(f, HIST) == ()


def test_drivers_outside_tolerance_are_flagged_per_year() -> None:
    years = list(constant_drivers(0.15, 0.22, 0.04, 0.05, 0.15))
    years[2] = replace(years[2], ebitda_margin=0.30)  # 30% vs max 19% + 10pp = 29%
    years[4] = replace(years[4], revenue_growth=0.05)  # 5% vs min 20% − 10pp = 10%
    issues = driver_history_warnings(ForecastInputs(1200.0, 200.0, tuple(years)), HIST)
    assert [(i.code, i.field) for i in issues] == [
        (Code.DRIVER_OUTSIDE_HISTORY, "years[5].revenue_growth"),
        (Code.DRIVER_OUTSIDE_HISTORY, "years[3].ebitda_margin"),
    ]
    assert "18.8%–19.0%" in issues[1].message


def test_boundary_is_inclusive() -> None:
    years = list(constant_drivers(0.15, 0.22, 0.04, 0.05, 0.15))
    years[0] = replace(years[0], ebitda_margin=0.19 + 0.10)
    issues = driver_history_warnings(ForecastInputs(1200.0, 200.0, tuple(years)), HIST)
    assert issues == ()


def test_missing_history_is_disclosed_not_compared_with_zero() -> None:
    hist = analyze_historicals([replace(FY23, capex=None)])  # single year: no growth either
    f = ForecastInputs(1000.0, 100.0, constant_drivers(0.9, 0.2, 0.04, 0.9, 0.1))
    issues = driver_history_warnings(f, hist)
    no_history = {i.field for i in issues if i.code == Code.DRIVER_NO_HISTORY}
    assert no_history == {"revenue_growth", "capex_pct_revenue"}
    assert all(
        i.code != Code.DRIVER_OUTSIDE_HISTORY or "capex" not in (i.field or "") for i in issues
    )


def test_negative_tolerance_rejected() -> None:
    with pytest.raises(ValueError):
        driver_history_warnings(
            ForecastInputs(1.0, 0.0, constant_drivers(0, 0, 0, 0, 0)), HIST, -0.1
        )


# --------------------------------------------------------------------------- LIM-13


def test_da_above_operating_costs_is_flagged() -> None:
    p = replace(FY23, da=900.0)  # COGS 600 + OpEx 250 = 850
    codes = [i.code for i in analyze_historicals([p]).issues]
    assert Code.DA_EXCEEDS_OPERATING_COSTS in codes


def test_da_check_passes_on_clean_data() -> None:
    codes = {i.code for i in analyze_historicals([FY23]).issues}
    assert Code.DA_EXCEEDS_OPERATING_COSTS not in codes
    assert Code.DA_CHECK_SKIPPED not in codes


@pytest.mark.parametrize("missing", ["da", "cogs", "opex"])
def test_da_check_skipped_and_disclosed_when_inputs_missing(missing: str) -> None:
    issues = analyze_historicals([replace(FY23, **{missing: None})]).issues
    skipped = [i for i in issues if i.code == Code.DA_CHECK_SKIPPED]
    assert len(skipped) == 1 and missing in skipped[0].message
    assert Code.DA_EXCEEDS_OPERATING_COSTS not in {i.code for i in issues}
