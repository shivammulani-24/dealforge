"""Validation helpers, Metric semantics, date conventions (D-07), EBITDA definitions (D-03)."""

from __future__ import annotations

import math
from datetime import date

import pytest

from app.engine.dates import ValuationDates, add_years, build_schedule
from app.engine.ebitda import (
    EbitdaAdjustment,
    EbitdaBasis,
    EbitdaFigures,
    reconcile_ebitda,
    select_ebitda,
    standardized_ebitda,
)
from app.engine.errors import Code, EngineError, MissingInputError, Severity
from app.engine.metrics import Metric, Status, safe_ratio
from app.engine.validation import Checker, approx_equal, require

# --------------------------------------------------------------------------- validation


def test_missing_is_never_zero() -> None:
    with pytest.raises(MissingInputError) as exc:
        require("revenue", None)
    assert exc.value.codes == (Code.MISSING_INPUT,)
    assert "revenue" in str(exc.value)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_rejected(bad: float) -> None:
    with pytest.raises(EngineError) as exc:
        require("x", bad)
    assert exc.value.codes == (Code.NON_FINITE_INPUT,)


@pytest.mark.parametrize("bad", [True, "1.0", [1.0]])
def test_non_numbers_rejected(bad: object) -> None:
    with pytest.raises(EngineError) as exc:
        require("x", bad)
    assert exc.value.codes == (Code.INVALID_TYPE,)


def test_checker_reports_every_error_at_once() -> None:
    c = Checker()
    c.number("a", None)
    c.non_negative("b", -1.0)
    c.in_range("c", 2.0, 0.0, 1.0)
    with pytest.raises(EngineError) as exc:
        c.raise_if_errors()
    assert exc.value.codes == (Code.MISSING_INPUT, Code.SIGN_CONVENTION, Code.OUT_OF_RANGE)
    assert not isinstance(exc.value, MissingInputError)  # mixed errors → plain EngineError


def test_approx_equal_tolerance() -> None:
    assert approx_equal(100.4, 100.0)  # within 0.5 unit
    assert approx_equal(1004.0, 1000.0)  # within 0.5%
    assert not approx_equal(1006.0, 1000.0)


# --------------------------------------------------------------------------- metrics


def test_safe_ratio_states() -> None:
    assert safe_ratio(1.0, 4.0, num_name="n", den_name="d") == Metric(0.25, Status.OK)
    assert safe_ratio(None, 4.0, num_name="n", den_name="d").status is Status.MISSING
    assert safe_ratio(1.0, 0.0, num_name="n", den_name="d").status is Status.NOT_MEANINGFUL
    assert safe_ratio(1.0, -2.0, num_name="n", den_name="d").status is Status.NOT_MEANINGFUL
    signed = safe_ratio(1.0, -2.0, num_name="n", den_name="d", require_positive_denominator=False)
    assert signed.value == -0.5
    assert (
        safe_ratio(1.0, 0.0, num_name="n", den_name="d", require_positive_denominator=False).status
        is Status.NOT_MEANINGFUL
    )


def test_metric_invariant() -> None:
    with pytest.raises(ValueError):
        Metric(None, Status.OK)
    with pytest.raises(ValueError):
        Metric(1.0, Status.MISSING)


# --------------------------------------------------------------------------- dates (D-07)


def test_dates_are_kept_separate_and_forecast_periods_labelled() -> None:
    s = build_schedule(ValuationDates(date(2025, 3, 31), date(2025, 3, 31), date(2025, 4, 15)), 5)
    assert s.statement_date == s.valuation_date == date(2025, 3, 31)
    assert s.market_data_date == date(2025, 4, 15)
    assert s.market_data_gap_days == 15
    assert [p.label for p in s.periods] == ["FY2026", "FY2027", "FY2028", "FY2029", "FY2030"]
    assert [p.t for p in s.periods] == [1, 2, 3, 4, 5]
    assert s.periods[0].end_date == date(2026, 3, 31)
    assert [i.code for i in s.issues] == [Code.MARKET_DATA_DATE_DIFFERS]
    assert "end-of-year" in s.convention


def test_same_day_market_data_has_no_issue() -> None:
    d = date(2024, 12, 31)
    assert build_schedule(ValuationDates(d, d, d), 5).issues == ()


def test_stale_market_data_warns() -> None:
    s = build_schedule(ValuationDates(date(2025, 3, 31), date(2025, 3, 31), date(2025, 9, 30)), 5)
    assert s.issues[0].code == Code.MARKET_DATA_STALE
    assert s.issues[0].severity is Severity.WARNING


def test_stub_period_rejected() -> None:
    with pytest.raises(EngineError) as exc:
        build_schedule(ValuationDates(date(2025, 3, 31), date(2025, 6, 30), date(2025, 6, 30)), 5)
    assert Code.STUB_PERIOD_NOT_SUPPORTED in exc.value.codes


def test_market_data_before_statements_rejected() -> None:
    with pytest.raises(EngineError) as exc:
        build_schedule(ValuationDates(date(2025, 3, 31), date(2025, 3, 31), date(2025, 1, 1)), 5)
    assert Code.MARKET_DATA_BEFORE_STATEMENTS in exc.value.codes


def test_non_date_rejected() -> None:
    with pytest.raises(EngineError):
        build_schedule(ValuationDates("2025-03-31", date(2025, 3, 31), date(2025, 3, 31)), 5)  # type: ignore[arg-type]


def test_leap_day_rolls_to_28_feb() -> None:
    assert add_years(date(2024, 2, 29), 1) == date(2025, 2, 28)
    assert add_years(date(2024, 2, 29), 4) == date(2028, 2, 29)


# --------------------------------------------------------------------------- EBITDA (D-03)


def test_ka_ebitda_01_three_definitions_reconcile() -> None:
    """₹ crore: EBIT 800 + D&A 200 = 1,000 standardised = reported; adjusted 1,150 =
    1,000 + SBC 100 + restructuring 50."""
    fig = EbitdaFigures(
        ebit=800.0,
        da=200.0,
        reported=1000.0,
        reported_source="FY2025 annual report p.42",
        adjusted=1150.0,
        adjusted_source="FY2025 investor presentation slide 9",
        adjustments=(
            EbitdaAdjustment("Share-based compensation", 100.0, "note 31"),
            EbitdaAdjustment("Restructuring costs", 50.0, "note 12"),
        ),
    )
    rec = reconcile_ebitda(fig)
    assert rec.standardized.value == 1000.0
    assert rec.reported.value == 1000.0
    assert rec.adjusted.value == 1150.0
    assert rec.adjustments_total == 150.0
    assert rec.adjustments_base is EbitdaBasis.REPORTED
    assert rec.issues == ()
    assert select_ebitda(fig, EbitdaBasis.STANDARDIZED).value == 1000.0
    assert select_ebitda(fig, EbitdaBasis.ADJUSTED).value == 1150.0


def test_adjusted_ebitda_that_does_not_reconcile_is_flagged() -> None:
    fig = EbitdaFigures(
        ebit=800.0,
        da=200.0,
        reported=1000.0,
        adjusted=1150.0,
        adjustments=(EbitdaAdjustment("SBC", 120.0),),
    )
    codes = [i.code for i in reconcile_ebitda(fig).issues]
    assert codes == [Code.ADJUSTED_EBITDA_UNRECONCILED]


def test_adjusted_without_adjustments_is_flagged() -> None:
    rec = reconcile_ebitda(EbitdaFigures(ebit=800.0, da=200.0, adjusted=1150.0))
    assert [i.code for i in rec.issues] == [Code.ADJUSTMENTS_NOT_DISCLOSED]
    assert rec.reported.status is Status.MISSING


def test_adjustments_without_adjusted_figure_are_flagged() -> None:
    rec = reconcile_ebitda(
        EbitdaFigures(ebit=800.0, da=200.0, adjustments=(EbitdaAdjustment("SBC", 1.0),))
    )
    assert [i.code for i in rec.issues] == [Code.ADJUSTMENTS_WITHOUT_ADJUSTED]
    assert rec.adjustments_base is EbitdaBasis.STANDARDIZED


def test_reported_ebitda_differing_from_standardised_is_disclosed() -> None:
    rec = reconcile_ebitda(EbitdaFigures(ebit=800.0, da=200.0, reported=1040.0))
    assert [i.code for i in rec.issues] == [Code.REPORTED_VS_STANDARDIZED_EBITDA]
    assert rec.issues[0].severity is Severity.INFO


def test_select_never_substitutes_another_basis() -> None:
    fig = EbitdaFigures(ebit=800.0, da=200.0)
    adj = select_ebitda(fig, EbitdaBasis.ADJUSTED)
    rep = select_ebitda(fig, EbitdaBasis.REPORTED)
    assert adj.status is Status.MISSING and adj.value is None
    assert rep.status is Status.MISSING
    assert select_ebitda(EbitdaFigures(None, 200.0), EbitdaBasis.STANDARDIZED).status is (
        Status.MISSING
    )


def test_negative_da_violates_sign_convention() -> None:
    with pytest.raises(EngineError) as exc:
        standardized_ebitda(800.0, -200.0)
    assert exc.value.codes == (Code.SIGN_CONVENTION,)
