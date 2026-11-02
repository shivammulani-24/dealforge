"""Forecast (H.3), unlevered FCF (H.4, D-06) and WACC (H.5, D-08)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from builders import constant_drivers, wacc_assumptions

from app.engine.errors import Code, EngineError, MissingInputError
from app.engine.fcf import compute_ufcf, forecast_ufcf
from app.engine.forecast import ForecastInputs, ForecastYearDrivers, build_forecast
from app.engine.wacc import (
    CapitalStructure,
    DebtValueBasis,
    compute_wacc,
    cost_of_equity,
    relever_beta,
    unlever_beta,
)

# --------------------------------------------------------------------------- forecast


def ka_fc01() -> ForecastInputs:
    y1 = ForecastYearDrivers(0.10, 0.20, 0.05, 0.06, 0.10)
    y2 = replace(y1, revenue_growth=0.08)
    return ForecastInputs(1000.0, 100.0, (y1, y2, y2, y2, y2))


def test_ka_fc_01_forecast_build() -> None:
    f = build_forecast(ka_fc01())
    y1, y2 = f.years[0], f.years[1]
    assert (y1.revenue, y2.revenue) == pytest.approx((1100.0, 1188.0))
    assert (y1.ebitda, y2.ebitda) == pytest.approx((220.0, 237.6))
    assert (y1.da, y2.da) == pytest.approx((55.0, 59.4))
    assert (y1.ebit, y2.ebit) == pytest.approx((165.0, 178.2))
    assert (y1.capex, y2.capex) == pytest.approx((66.0, 71.28))
    assert (y1.nwc, y2.nwc) == pytest.approx((110.0, 118.8))
    assert (y1.change_in_nwc, y2.change_in_nwc) == pytest.approx((10.0, 8.8))
    u = forecast_ufcf(f, 0.25)
    assert (u[0].nopat, u[1].nopat) == pytest.approx((123.75, 133.65))
    assert (u[0].ufcf, u[1].ufcf) == pytest.approx((102.75, 112.97))
    assert f.issues == ()


def test_forecast_requires_exactly_five_years() -> None:
    with pytest.raises(EngineError) as exc:
        build_forecast(
            ForecastInputs(1000.0, 100.0, constant_drivers(0.05, 0.2, 0.05, 0.05, 0.1)[:4])
        )
    assert exc.value.codes == (Code.HORIZON_NOT_SUPPORTED,)


@pytest.mark.parametrize(
    "field, value",
    [
        ("revenue_growth", -1.0),  # revenue cannot fall by 100% or more
        ("ebitda_margin", 1.0),
        ("ebitda_margin", -1.5),
        ("da_pct_revenue", -0.01),
        ("capex_pct_revenue", 1.5),
        ("nwc_pct_revenue", 1.0),
        ("revenue_growth", None),
        ("revenue_growth", float("inf")),
    ],
)
def test_invalid_drivers_rejected(field: str, value: object) -> None:
    years = list(constant_drivers(0.05, 0.2, 0.05, 0.05, 0.1))
    years[2] = replace(years[2], **{field: value})
    with pytest.raises(EngineError):
        build_forecast(ForecastInputs(1000.0, 100.0, tuple(years)))


@pytest.mark.parametrize("base", [0.0, -10.0, None])
def test_base_revenue_must_be_positive(base: object) -> None:
    with pytest.raises(EngineError):
        build_forecast(ForecastInputs(base, 100.0, constant_drivers(0.05, 0.2, 0.05, 0.05, 0.1)))  # type: ignore[arg-type]


def test_forecast_warnings() -> None:
    years = list(constant_drivers(0.05, 0.2, 0.06, 0.04, 0.25))  # CapEx < D&A in final year
    years[0] = replace(years[0], revenue_growth=0.80, ebitda_margin=-0.05)
    f = build_forecast(ForecastInputs(1000.0, 100.0, tuple(years)))  # NWC 10% → 25%
    codes = {i.code for i in f.issues}
    assert codes == {
        Code.EXTREME_GROWTH,
        Code.NEGATIVE_EBITDA_MARGIN,
        Code.CAPEX_BELOW_DA_TERMINAL,
        Code.NWC_STEP_CHANGE,
    }


def test_negative_nwc_business_is_allowed() -> None:
    f = build_forecast(
        ForecastInputs(1000.0, -100.0, constant_drivers(0.10, 0.2, 0.05, 0.05, -0.10))
    )
    # Growing a negative-NWC business releases cash: ΔNWC is negative.
    assert f.years[0].change_in_nwc == pytest.approx(-10.0)


# --------------------------------------------------------------------------- UFCF


def test_ka_ufcf_01() -> None:
    u = compute_ufcf(ebit=200.0, da=50.0, capex=70.0, change_in_nwc=10.0, tax_rate=0.25)
    assert u.taxes_on_ebit == pytest.approx(50.0)
    assert u.nopat == pytest.approx(150.0)
    assert u.ufcf == pytest.approx(120.0)
    assert u.issues == ()


def test_ka_ufcf_02_negative_ebit_gets_no_tax_credit() -> None:
    u = compute_ufcf(ebit=-40.0, da=30.0, capex=20.0, change_in_nwc=-5.0, tax_rate=0.25)
    assert u.taxes_on_ebit == 0.0
    assert u.nopat == pytest.approx(-40.0)
    assert u.ufcf == pytest.approx(-25.0)  # symmetric tax would wrongly give −15
    assert [i.code for i in u.issues] == [Code.NEGATIVE_EBIT_NO_TAX_CREDIT, Code.NEGATIVE_UFCF]


def test_ufcf_ignores_interest_by_construction() -> None:
    import inspect

    assert "interest" not in inspect.signature(compute_ufcf).parameters


def test_zero_tax_rate_and_zero_ebit() -> None:
    assert compute_ufcf(100.0, 10.0, 10.0, 0.0, 0.0).ufcf == pytest.approx(100.0)
    assert compute_ufcf(0.0, 10.0, 10.0, 0.0, 0.25).issues == ()


@pytest.mark.parametrize(
    "kw",
    [
        {"tax_rate": 0.7},
        {"tax_rate": -0.1},
        {"capex": -1.0},
        {"da": -1.0},
        {"ebit": None},
    ],
)
def test_ufcf_invalid_inputs(kw: dict[str, object]) -> None:
    base: dict[str, object] = {
        "ebit": 100.0,
        "da": 10.0,
        "capex": 10.0,
        "change_in_nwc": 0.0,
        "tax_rate": 0.25,
    }
    base.update(kw)
    with pytest.raises(EngineError):
        compute_ufcf(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- WACC


def test_ka_wacc_01() -> None:
    """Ke = 4% + 1.2 × 5.5% = 10.6%; E 1,000, D 250; Kd 6% × 0.75 = 4.5%;
    WACC = 0.8 × 10.6% + 0.2 × 4.5% = 9.38%."""
    r = compute_wacc(wacc_assumptions(), CapitalStructure(1000.0, 250.0, 0.0), 0.25)
    assert r.cost_of_equity == pytest.approx(0.106)
    assert r.after_tax_cost_of_debt == pytest.approx(0.045)
    assert (r.weight_equity, r.weight_debt, r.weight_preferred) == pytest.approx((0.8, 0.2, 0.0))
    assert r.wacc == pytest.approx(0.0938)
    assert [i.code for i in r.issues] == [Code.DEBT_AT_BOOK]


def test_zero_debt_wacc_equals_cost_of_equity() -> None:
    r = compute_wacc(wacc_assumptions(), CapitalStructure(1000.0, 0.0, 0.0), 0.25)
    assert r.wacc == pytest.approx(r.cost_of_equity) == pytest.approx(0.106)
    assert r.issues == ()  # no book-debt flag when there is no debt


def test_wacc_with_preferred_and_size_premium() -> None:
    a = wacc_assumptions(
        cost_of_preferred=0.08, size_premium=0.01, debt_value_basis=DebtValueBasis.MARKET
    )
    r = compute_wacc(a, CapitalStructure(700.0, 200.0, 100.0), 0.25)
    # Ke = 4% + 6.6% + 1% = 11.6%; WACC = .7×11.6% + .2×4.5% + .1×8% = 8.12% + 0.9% + 0.8%
    assert r.wacc == pytest.approx(0.0982)
    assert Code.SIZE_PREMIUM_APPLIED in {i.code for i in r.issues}


def test_preferred_without_cost_is_missing() -> None:
    with pytest.raises(MissingInputError):
        compute_wacc(wacc_assumptions(), CapitalStructure(700.0, 200.0, 100.0), 0.25)


def test_target_capital_structure() -> None:
    r = compute_wacc(
        wacc_assumptions(target_debt_to_capital=0.30), CapitalStructure(1000.0, 250.0, 0.0), 0.25
    )
    assert r.wacc == pytest.approx(0.7 * 0.106 + 0.3 * 0.045)
    assert Code.TARGET_STRUCTURE_USED in {i.code for i in r.issues}


def test_cost_of_equity_below_debt_is_flagged() -> None:
    a = wacc_assumptions(levered_beta=0.1, pre_tax_cost_of_debt=0.12)
    codes = {i.code for i in compute_wacc(a, CapitalStructure(1000.0, 250.0, 0.0), 0.25).issues}
    assert {Code.COST_OF_EQUITY_BELOW_DEBT, Code.UNUSUAL_BETA} <= codes


@pytest.mark.parametrize(
    "kw, cs, code",
    [
        ({"levered_beta": -3.0}, (1000.0, 0.0, 0.0), Code.INVALID_WACC),  # Ke < 0 → WACC < 0
        ({"risk_free_rate": 0.29, "levered_beta": 30.0}, (1000.0, 0.0, 0.0), Code.INVALID_WACC),
        ({}, (0.0, 250.0, 0.0), Code.OUT_OF_RANGE),  # equity must be positive
        ({}, (1000.0, -1.0, 0.0), Code.SIGN_CONVENTION),
        ({"equity_risk_premium": None}, (1000.0, 0.0, 0.0), Code.MISSING_INPUT),
        ({"target_debt_to_capital": 1.0}, (1000.0, 0.0, 0.0), Code.OUT_OF_RANGE),
    ],
)
def test_invalid_wacc_inputs(
    kw: dict[str, object], cs: tuple[float, float, float], code: str
) -> None:
    with pytest.raises(EngineError) as exc:
        compute_wacc(wacc_assumptions(**kw), CapitalStructure(*cs), 0.25)
    assert code in exc.value.codes


def test_extreme_wacc_warns() -> None:
    r = compute_wacc(
        wacc_assumptions(levered_beta=4.0, equity_risk_premium=0.07),
        CapitalStructure(1000.0, 0.0, 0.0),
        0.25,
    )
    assert r.wacc == pytest.approx(0.32)
    assert {Code.EXTREME_WACC, Code.UNUSUAL_BETA} <= {i.code for i in r.issues}


def test_ka_beta_01_hamada_round_trip() -> None:
    bu = unlever_beta(1.2, 0.25, 0.25)
    assert bu == pytest.approx(1.2 / 1.1875) == pytest.approx(1.0105263157894737)
    assert relever_beta(bu, 0.25, 0.25) == pytest.approx(1.2)
    assert unlever_beta(1.2, 0.0, 0.25) == 1.2
    with pytest.raises(EngineError):
        unlever_beta(1.2, -0.1, 0.25)


def test_cost_of_equity_formula() -> None:
    assert cost_of_equity(0.04, 1.2, 0.055, 0.0) == pytest.approx(0.106)


def test_target_structure_leaving_no_equity_rejected() -> None:
    a = wacc_assumptions(target_debt_to_capital=0.95, cost_of_preferred=0.08)
    with pytest.raises(EngineError) as exc:
        compute_wacc(a, CapitalStructure(100.0, 0.0, 100.0), 0.25)  # preferred weight 50%
    assert Code.OUT_OF_RANGE in exc.value.codes
