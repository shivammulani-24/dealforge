"""Historical analysis (spec H.2): metrics, NM/missing handling, consistency checks."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.engine.errors import Code, EngineError
from app.engine.historical import HistoricalPeriod, analyze_historicals
from app.engine.metrics import Status

FY23 = HistoricalPeriod(
    fiscal_year=2023,
    revenue=1000.0,
    cogs=600.0,
    opex=250.0,
    ebit=150.0,
    da=40.0,
    pretax_income=140.0,
    tax_expense=35.0,
    net_income=105.0,
    cfo=160.0,
    capex=50.0,
    accounts_receivable=120.0,
    inventory=80.0,
    other_current_operating_assets=10.0,
    accounts_payable=90.0,
    other_current_operating_liabilities=20.0,
    cash=100.0,
    total_debt=300.0,
    interest_expense=10.0,
    total_assets=1000.0,
    total_liabilities=600.0,
    total_equity=400.0,
)
# FY2024: profits up, but receivables and inventory balloon → cash flow falls (question 6).
FY24 = replace(
    FY23,
    fiscal_year=2024,
    revenue=1200.0,
    cogs=720.0,
    opex=300.0,
    ebit=180.0,
    da=45.0,
    pretax_income=170.0,
    tax_expense=42.5,
    net_income=127.5,
    cfo=100.0,
    capex=70.0,
    accounts_receivable=200.0,
    inventory=110.0,
    accounts_payable=100.0,
    total_assets=1200.0,
    total_liabilities=700.0,
    total_equity=500.0,
)


def v(analysis, fy: int, name: str) -> float:  # type: ignore[no-untyped-def]
    m = analysis.metric(fy, name)
    assert m.status is Status.OK, (name, m)
    return m.value


def test_ka_hist_01_metrics_hand_calculated() -> None:
    a = analyze_historicals([FY23, FY24])
    assert a.metric(2023, "revenue_growth").status is Status.NOT_MEANINGFUL  # no prior year
    assert v(a, 2023, "gross_profit") == pytest.approx(400.0)
    assert v(a, 2023, "gross_margin") == pytest.approx(0.40)
    assert v(a, 2023, "ebitda") == pytest.approx(190.0)  # 150 + 40
    assert v(a, 2023, "ebitda_margin") == pytest.approx(0.19)
    assert v(a, 2023, "ebit_margin") == pytest.approx(0.15)
    assert v(a, 2023, "effective_tax_rate") == pytest.approx(0.25)
    assert v(a, 2023, "simple_fcf") == pytest.approx(110.0)  # 160 − 50
    assert v(a, 2023, "fcf_conversion") == pytest.approx(110.0 / 105.0)
    assert v(a, 2023, "nwc") == pytest.approx(100.0)  # 120 + 80 + 10 − 90 − 20
    assert v(a, 2023, "net_debt") == pytest.approx(200.0)
    assert v(a, 2023, "net_debt_to_ebitda") == pytest.approx(200.0 / 190.0)
    assert v(a, 2023, "interest_coverage") == pytest.approx(15.0)
    assert v(a, 2023, "capex_to_da") == pytest.approx(1.25)
    assert v(a, 2024, "revenue_growth") == pytest.approx(0.20)
    assert v(a, 2024, "nwc") == pytest.approx(200.0)
    assert v(a, 2024, "change_in_nwc") == pytest.approx(100.0)


def test_ka_hist_02_rising_profit_falling_cash_is_flagged() -> None:
    """Net income 105 → 127.5 (+21%) while FCF 110 → 30, because NWC absorbed 100."""
    a = analyze_historicals([FY23, FY24])
    div = [i for i in a.issues if i.code == Code.EARNINGS_CASH_DIVERGENCE]
    assert len(div) == 1
    assert "absorbed 100.00" in div[0].message
    assert v(a, 2024, "fcf_conversion") == pytest.approx(30.0 / 127.5)


def test_clean_data_has_no_consistency_warnings() -> None:
    codes = {i.code for i in analyze_historicals([FY23, FY24]).issues}
    assert codes == {Code.EARNINGS_CASH_DIVERGENCE}


def test_missing_items_propagate_as_missing_not_zero() -> None:
    p = replace(FY23, cogs=None, capex=None, accounts_receivable=None, cash=None)
    a = analyze_historicals([p])
    for name in (
        "gross_profit",
        "gross_margin",
        "simple_fcf",
        "fcf_conversion",
        "capex_pct_revenue",
        "nwc",
        "nwc_pct_revenue",
        "net_debt",
        "net_debt_to_ebitda",
    ):
        m = a.metric(2023, name)
        assert m.status is Status.MISSING, name
        assert m.value is None
    assert "cogs" in (a.metric(2023, "gross_profit").reason or "")
    # Unaffected metrics are still computed
    assert a.metric(2023, "ebitda").value == pytest.approx(190.0)


def test_optional_nwc_lines_are_disclosed_when_absent() -> None:
    p = replace(FY23, other_current_operating_assets=None, other_current_operating_liabilities=None)
    a = analyze_historicals([p])
    assert a.metric(2023, "nwc").value == pytest.approx(110.0)  # 120 + 80 − 90
    assert Code.NWC_PARTIAL in {i.code for i in a.issues}


def test_negative_ebit_and_losses() -> None:
    p = replace(
        FY23, ebit=-50.0, opex=450.0, pretax_income=-60.0, tax_expense=0.0, net_income=-60.0
    )
    a = analyze_historicals([p])
    assert a.metric(2023, "ebit_margin").value == pytest.approx(-0.05)
    assert a.metric(2023, "effective_tax_rate").status is Status.NOT_MEANINGFUL
    assert a.metric(2023, "fcf_conversion").status is Status.NOT_MEANINGFUL
    assert a.metric(2023, "ebitda").value == pytest.approx(-10.0)
    assert a.metric(2023, "net_debt_to_ebitda").status is Status.NOT_MEANINGFUL


def test_zero_revenue_gives_nm_ratios() -> None:
    p = replace(FY23, revenue=0.0, cogs=0.0, opex=0.0, ebit=0.0)
    a = analyze_historicals([p, replace(FY24, fiscal_year=2024)])
    assert a.metric(2023, "gross_margin").status is Status.NOT_MEANINGFUL
    assert a.metric(2024, "revenue_growth").status is Status.NOT_MEANINGFUL  # growth from zero


def test_zero_debt_zero_cash_and_zero_interest() -> None:
    p = replace(FY23, cash=0.0, total_debt=0.0, interest_expense=0.0)
    a = analyze_historicals([p])
    assert a.metric(2023, "net_debt").value == 0.0
    assert a.metric(2023, "interest_coverage").status is Status.NOT_MEANINGFUL


def test_unusual_tax_rate_is_flagged() -> None:
    p = replace(FY23, tax_expense=84.0, net_income=56.0)  # 60%
    assert Code.UNUSUAL_TAX_RATE in {i.code for i in analyze_historicals([p]).issues}


def test_reconciliation_and_balance_sheet_checks() -> None:
    p = replace(FY23, ebit=170.0, net_income=90.0, total_equity=300.0)
    codes = {i.code for i in analyze_historicals([p]).issues}
    assert {
        Code.EBIT_RECONCILIATION,
        Code.NET_INCOME_RECONCILIATION,
        Code.BALANCE_SHEET_IMBALANCE,
    } <= codes


def test_gap_in_years_is_flagged_and_growth_not_computed() -> None:
    a = analyze_historicals([FY23, replace(FY24, fiscal_year=2025)])
    assert Code.PERIODS_NOT_CONTIGUOUS in {i.code for i in a.issues}
    assert a.metric(2025, "revenue_growth").status is Status.NOT_MEANINGFUL
    assert a.metric(2025, "change_in_nwc").status is Status.NOT_MEANINGFUL


def test_periods_are_sorted() -> None:
    a = analyze_historicals([FY24, FY23])
    assert [p.fiscal_year for p in a.periods] == [2023, 2024]


@pytest.mark.parametrize(
    "periods, code",
    [
        ([], Code.NO_PERIODS),
        ([FY23, FY23], Code.DUPLICATE_PERIOD),
        ([replace(FY23, capex=-50.0)], Code.SIGN_CONVENTION),
        ([replace(FY23, revenue=float("nan"))], Code.NON_FINITE_INPUT),
    ],
)
def test_invalid_period_sets(periods: list[HistoricalPeriod], code: str) -> None:
    with pytest.raises(EngineError) as exc:
        analyze_historicals(periods)
    assert code in exc.value.codes
