"""Liquidity ratios and checks (Phase 4 plan §5, D4-02). Known answers KA-LIQ-01…06."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.engine.errors import Code, EngineError
from app.engine.historical import HistoricalPeriod, analyze_historicals, liquidity_ratios
from app.engine.metrics import Status
from app.importers.csv_financials import parse_financials_csv

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "ardent_precision_synthetic.csv"

# FY2025 of the synthetic sample (INR crores)
FY25 = HistoricalPeriod(
    fiscal_year=2025,
    cash=150.0,
    accounts_receivable=250.0,
    inventory=175.0,
    other_current_operating_assets=25.0,
    accounts_payable=125.0,
    other_current_operating_liabilities=25.0,
    total_current_assets=600.0,
    total_current_liabilities=300.0,
    marketable_securities=0.0,
    total_assets=1700.0,
    total_liabilities=850.0,
)


def ratios(p: HistoricalPeriod) -> dict[str, object]:
    return liquidity_ratios(p)  # type: ignore[return-value]


def test_ka_liq_01_sample_years() -> None:
    """Hand-computed: FY2025 600/300, (150+0+250)/300, (150+0)/300; FY2024 and FY2023 below."""
    expected = {
        2023: (480 / 260, 320 / 260, 120 / 260),
        2024: (540 / 280, 360 / 280, 135 / 280),
        2025: (2.0, 400 / 300, 0.5),
    }
    preview = parse_financials_csv(
        SAMPLE.read_bytes(),
        file_name=SAMPLE.name,
        currency="INR",
        file_scale="crores",
        company_currency="INR",
        company_scale="crores",
        fiscal_year_end_month=3,
    )
    assert preview.ok and preview.analysis is not None
    for fy, (cur, quick, cash) in expected.items():
        m = {p.fiscal_year: p.metrics for p in preview.analysis.periods}[fy]
        assert m["current_ratio"].value == pytest.approx(cur, rel=1e-12)
        assert m["quick_ratio"].value == pytest.approx(quick, rel=1e-12)
        assert m["cash_ratio"].value == pytest.approx(cash, rel=1e-12)
    # 6 dp values quoted in the plan
    assert round(480 / 260, 6) == 1.846154 and round(360 / 280, 6) == 1.285714
    codes = {i.code for i in preview.analysis.issues}
    assert not codes & {
        Code.LIQUIDITY_COMPONENTS_EXCEED_CA,
        Code.OPERATING_PAYABLES_EXCEED_CL,
        Code.CURRENT_ASSETS_EXCEED_TOTAL,
        Code.CURRENT_LIABILITIES_EXCEED_TOTAL,
    }


def test_ka_liq_02_missing_marketable_securities_makes_quick_and_cash_missing() -> None:
    r = liquidity_ratios(replace(FY25, marketable_securities=None))
    assert r["current_ratio"].value == 2.0
    for name in ("quick_ratio", "cash_ratio"):
        assert r[name].status is Status.MISSING and r[name].value is None
        assert "marketable_securities" in (r[name].reason or "")


def test_ka_liq_03_zero_current_liabilities_is_not_meaningful() -> None:
    r = liquidity_ratios(replace(FY25, total_current_liabilities=0.0))
    for name in ("current_ratio", "quick_ratio", "cash_ratio"):
        assert r[name].status is Status.NOT_MEANINGFUL, name
        assert "zero" in (r[name].reason or "")


def test_ka_liq_04_explicit_zeros_are_data_not_missing() -> None:
    r = liquidity_ratios(
        replace(FY25, cash=0.0, marketable_securities=0.0, accounts_receivable=0.0)
    )
    assert r["quick_ratio"].status is Status.OK and r["quick_ratio"].value == 0.0
    assert r["cash_ratio"].status is Status.OK and r["cash_ratio"].value == 0.0


def test_ka_liq_05_components_exceeding_current_assets_are_flagged() -> None:
    a = analyze_historicals([replace(FY25, cash=400.0)])  # 400+0+250+175+25 = 850 > 600
    hits = [i for i in a.issues if i.code == Code.LIQUIDITY_COMPONENTS_EXCEED_CA]
    assert len(hits) == 1 and "850.00" in hits[0].message
    assert "other_current_operating_assets" in hits[0].message  # included components listed


def test_ka_liq_06_missing_current_assets() -> None:
    a = analyze_historicals([replace(FY25, total_current_assets=None)])
    m = a.periods[0].metrics
    assert m["current_ratio"].status is Status.MISSING
    assert m["quick_ratio"].value == pytest.approx(400 / 300)  # does not need TCA
    assert m["cash_ratio"].value == pytest.approx(0.5)
    assert Code.LIQUIDITY_CHECK_SKIPPED in {i.code for i in a.issues}  # disclosed


def test_partial_component_sum_uses_only_present_items() -> None:
    # inventory missing: lower bound 150+0+250+25 = 425 ≤ 600 → no warning, nothing assumed 0
    a = analyze_historicals([replace(FY25, inventory=None)])
    assert Code.LIQUIDITY_COMPONENTS_EXCEED_CA not in {i.code for i in a.issues}
    b = analyze_historicals([replace(FY25, inventory=None, cash=500.0)])  # 500+0+250+25 = 775
    hit = next(i for i in b.issues if i.code == Code.LIQUIDITY_COMPONENTS_EXCEED_CA)
    assert "inventory" not in hit.message


def test_other_liquidity_consistency_checks() -> None:
    payables = analyze_historicals([replace(FY25, accounts_payable=400.0)])  # 400+25 > 300
    assert Code.OPERATING_PAYABLES_EXCEED_CL in {i.code for i in payables.issues}
    totals = analyze_historicals(
        [replace(FY25, total_current_assets=1800.0, total_current_liabilities=900.0)]
    )
    codes = {i.code for i in totals.issues}
    assert {Code.CURRENT_ASSETS_EXCEED_TOTAL, Code.CURRENT_LIABILITIES_EXCEED_TOTAL} <= codes


def test_no_liquidity_data_at_all_adds_no_noise() -> None:
    p = replace(
        FY25, total_current_assets=None, total_current_liabilities=None, marketable_securities=None
    )
    a = analyze_historicals([p])
    assert Code.LIQUIDITY_CHECK_SKIPPED not in {i.code for i in a.issues}
    assert all(
        a.periods[0].metrics[n].status is Status.MISSING
        for n in ("current_ratio", "quick_ratio", "cash_ratio")
    )


@pytest.mark.parametrize(
    "item", ["total_current_assets", "total_current_liabilities", "marketable_securities"]
)
def test_new_items_follow_the_sign_convention(item: str) -> None:
    with pytest.raises(EngineError) as exc:
        analyze_historicals([replace(FY25, **{item: -1.0})])
    assert Code.SIGN_CONVENTION in exc.value.codes


opt = st.one_of(st.none(), st.floats(min_value=0, max_value=1e6))


@given(cash=opt, ms=opt, ar=opt, tca=opt, tcl=opt)
def test_ratios_are_numeric_only_when_every_input_is_present(cash, ms, ar, tca, tcl) -> None:  # type: ignore[no-untyped-def]
    p = replace(
        FY25,
        cash=cash,
        marketable_securities=ms,
        accounts_receivable=ar,
        total_current_assets=tca,
        total_current_liabilities=tcl,
    )
    r = liquidity_ratios(p)
    needs = {
        "current_ratio": (tca, tcl),
        "quick_ratio": (cash, ms, ar, tcl),
        "cash_ratio": (cash, ms, tcl),
    }
    for name, inputs in needs.items():
        if any(v is None for v in inputs):
            assert r[name].status is Status.MISSING and r[name].value is None
        elif tcl == 0:
            assert r[name].status is Status.NOT_MEANINGFUL
        else:
            assert r[name].status is Status.OK and r[name].value is not None
