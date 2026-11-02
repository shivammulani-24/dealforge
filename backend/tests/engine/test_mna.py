"""Accretion/dilution (H.11, D-13)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from builders import bridge, cap

from app.engine.errors import Code, EngineError, MissingInputError
from app.engine.metrics import Status
from app.engine.mna import (
    AcquirerInputs,
    DealInputs,
    TargetInputs,
    accretion_sensitivity,
    analyze_deal,
    new_debt_to_balance,
)
from app.engine.shares import ConvertibleInstrument

# Acquirer: price 50, 100 shares, NI 500 → EPS 5.00, P/E 10x.
ACQ = AcquirerInputs(
    share_price=50.0,
    diluted_shares=100.0,
    net_income=500.0,
    ebitda=900.0,
    total_debt=0.0,
    cash_available=100.0,
)
# Target: price 20, 50 shares, NI 100. At a 30% premium: offer 26, equity price 1,300, P/E 13x.
TGT = TargetInputs(
    share_price=20.0,
    share_capital=cap(50.0),
    net_income=100.0,
    ebitda=200.0,
    bridge=bridge(),
    interest_expense=None,
    refinance_debt=False,
)
ALL_STOCK = DealInputs(
    offer_premium=0.30,
    stock_pct=1.0,
    cash_used=0.0,
    new_debt=0.0,
    new_debt_rate=0.06,
    interest_rate_on_cash=0.0,
    tax_rate=0.25,
    stock_issue_discount=0.0,
    advisory_fees=0.0,
    financing_fees=0.0,
    financing_fee_amortization_years=None,
    run_rate_cost_synergies=0.0,
    revenue_synergies=0.0,
    revenue_synergy_margin=0.0,
    synergy_phase_in_year1=1.0,
    integration_costs_year1=0.0,
)


def test_ka_ma_01_all_stock_buying_higher_pe_is_dilutive() -> None:
    r = analyze_deal(ACQ, TGT, ALL_STOCK)
    assert r.offer_price == pytest.approx(26.0)
    assert r.equity_purchase_price == pytest.approx(1300.0)
    assert r.pe_paid.value == pytest.approx(13.0)
    assert r.new_shares_issued == pytest.approx(26.0)
    assert r.recurring_net_income == pytest.approx(600.0)
    assert r.pro_forma_shares == pytest.approx(126.0)
    assert r.recurring_eps == pytest.approx(600.0 / 126.0) == pytest.approx(4.761904761904762)
    assert r.recurring_accretion.value == pytest.approx(-0.047619047619)
    assert r.breakeven_synergies_pre_tax == pytest.approx(40.0)  # (5 × 126 − 600) / 0.75
    assert r.acquirer_ownership == pytest.approx(100.0 / 126.0)
    su = r.sources_and_uses
    assert su.total_uses == pytest.approx(su.total_sources) == pytest.approx(1300.0)


def test_ka_ma_02_breakeven_synergies_give_zero_accretion() -> None:
    r = analyze_deal(ACQ, TGT, replace(ALL_STOCK, run_rate_cost_synergies=40.0))
    assert r.recurring_net_income == pytest.approx(630.0)
    assert r.recurring_eps == pytest.approx(5.0)
    assert r.recurring_accretion.value == pytest.approx(0.0, abs=1e-12)


def ka_ma03() -> DealInputs:
    return replace(ALL_STOCK, stock_pct=0.5, new_debt=650.0, run_rate_cost_synergies=40.0)


def test_ka_ma_03_debt_and_stock_mix() -> None:
    """13 new shares; after-tax interest 650 × 6% × 0.75 = 29.25; synergies 40 × 0.75 = 30.
    PF NI = 500 + 100 + 30 − 29.25 = 600.75; 113 shares → EPS 5.316372 → +6.33%."""
    r = analyze_deal(ACQ, TGT, ka_ma03())
    assert r.new_shares_issued == pytest.approx(13.0)
    lines = {ln.label: ln.amount for ln in r.recurring_bridge}
    assert lines["Interest on new debt, after tax"] == pytest.approx(-29.25)
    assert lines["Run-rate synergies, after tax"] == pytest.approx(30.0)
    assert r.recurring_net_income == pytest.approx(600.75)
    assert r.recurring_eps == pytest.approx(5.316371681)
    assert r.recurring_accretion.value == pytest.approx(0.0632743363)
    assert r.pro_forma_leverage.value == pytest.approx(650.0 / 1140.0)


def test_ka_ma_04_fees_are_one_time_and_sources_must_balance() -> None:
    d = replace(ka_ma03(), advisory_fees=20.0, cash_used=20.0)
    r = analyze_deal(ACQ, TGT, d)
    assert r.sources_and_uses.total_uses == pytest.approx(1320.0)
    assert r.recurring_eps == pytest.approx(5.316371681)  # advisory fees not recurring
    assert r.year1_eps == pytest.approx((600.75 - 20.0) / 113.0)
    with pytest.raises(EngineError) as exc:
        analyze_deal(ACQ, TGT, replace(d, new_debt=640.0))
    assert exc.value.codes == (Code.SU_IMBALANCE,)


def test_financing_fees_are_funded_and_amortised_once() -> None:
    d = replace(
        ka_ma03(), financing_fees=10.0, financing_fee_amortization_years=5.0, new_debt=660.0
    )
    r = analyze_deal(ACQ, TGT, d)
    lines = {ln.label: ln.amount for ln in r.recurring_bridge}
    assert lines["Financing fee amortisation, after tax"] == pytest.approx(-10.0 / 5.0 * 0.75)
    assert lines["Interest on new debt, after tax"] == pytest.approx(-660.0 * 0.06 * 0.75)
    with pytest.raises(MissingInputError):
        analyze_deal(ACQ, TGT, replace(d, financing_fee_amortization_years=None))


def test_year1_vs_run_rate_with_phase_in_and_integration_costs() -> None:
    d = replace(ka_ma03(), synergy_phase_in_year1=0.5, integration_costs_year1=20.0)
    r = analyze_deal(ACQ, TGT, d)
    assert r.recurring_net_income == pytest.approx(600.75)  # unaffected by one-time items
    # 570.75 ex-synergies + 40 × 50% × 0.75 − 20 × 0.75 = 570.75 + 15 − 15
    assert r.year1_net_income == pytest.approx(570.75)
    assert r.year1_accretion.value < r.recurring_accretion.value


def test_revenue_synergies_use_contribution_margin() -> None:
    d = replace(ALL_STOCK, revenue_synergies=100.0, revenue_synergy_margin=0.40)
    r = analyze_deal(ACQ, TGT, d)
    assert r.run_rate_synergies_pre_tax == pytest.approx(40.0)  # not 100
    assert r.recurring_accretion.value == pytest.approx(0.0, abs=1e-12)


def test_cash_deal_forgone_interest() -> None:
    acq = replace(ACQ, cash_available=2000.0)
    d = replace(ALL_STOCK, stock_pct=0.0, cash_used=1300.0, interest_rate_on_cash=0.04)
    r = analyze_deal(acq, TGT, d)
    # 500 + 100 − 1,300 × 4% × 0.75 = 561; no new shares → EPS 5.61 → +12.2%
    assert r.new_shares_issued == 0.0
    assert r.recurring_eps == pytest.approx(5.61)


def test_insufficient_cash() -> None:
    d = replace(ALL_STOCK, stock_pct=0.0, cash_used=1300.0)
    with pytest.raises(EngineError) as exc:
        analyze_deal(ACQ, TGT, d)
    assert Code.INSUFFICIENT_CASH in exc.value.codes


def test_refinancing_at_same_rate_is_eps_neutral() -> None:
    """Target debt 200 at 6% (interest 12). Refinancing with new 6% debt removes 12 × 0.75 from
    the target and adds 200 × 6% × 0.75 — the same 9 — so EPS is unchanged: no double count."""
    tgt = replace(TGT, bridge=bridge(debt=200.0), interest_expense=12.0)
    keep = analyze_deal(ACQ, tgt, ka_ma03())
    refi = analyze_deal(ACQ, replace(tgt, refinance_debt=True), replace(ka_ma03(), new_debt=850.0))
    assert refi.sources_and_uses.total_uses == pytest.approx(1500.0)
    assert refi.recurring_eps == pytest.approx(keep.recurring_eps)
    assert keep.enterprise_value_paid == pytest.approx(1500.0)
    with pytest.raises(MissingInputError):
        analyze_deal(
            ACQ,
            replace(tgt, refinance_debt=True, interest_expense=None),
            replace(ka_ma03(), new_debt=850.0),
        )


def test_target_convertible_converts_at_offer_price() -> None:
    """Face 100 @20 converts at the 26 offer → +5 shares; equity price 26 × 55 = 1,430.
    Its 4% coupon disappears: + 100 × 4% × 0.75 = 3. All stock: 28.6 new shares;
    PF NI 603 / 128.6 shares."""
    cv = ConvertibleInstrument("Target notes", 100.0, 20.0, coupon_rate=0.04)
    tgt = replace(TGT, share_capital=cap(50.0, convertibles=(cv,)))
    r = analyze_deal(ACQ, tgt, ALL_STOCK)
    assert r.equity_purchase_price == pytest.approx(1430.0)
    assert r.new_shares_issued == pytest.approx(28.6)
    assert r.recurring_net_income == pytest.approx(603.0)
    assert r.recurring_eps == pytest.approx(603.0 / 128.6)
    assert Code.CONVERTIBLE_CONVERTED in {i.code for i in r.issues}
    with pytest.raises(MissingInputError):
        analyze_deal(
            ACQ,
            replace(tgt, share_capital=cap(50.0, convertibles=(replace(cv, coupon_rate=None),))),
            ALL_STOCK,
        )


def test_out_of_the_money_convertible_stays_debt() -> None:
    cv = ConvertibleInstrument("Target notes", 100.0, 30.0)  # coupon not needed: not converted
    tgt = replace(TGT, share_capital=cap(50.0, convertibles=(cv,)))
    r = analyze_deal(ACQ, tgt, ALL_STOCK)
    assert r.equity_purchase_price == pytest.approx(1300.0)
    assert r.enterprise_value_paid == pytest.approx(1400.0)


def test_acquirer_with_losses_gives_nm_accretion() -> None:
    r = analyze_deal(replace(ACQ, net_income=-50.0), TGT, ALL_STOCK)
    assert r.recurring_accretion.status is Status.NOT_MEANINGFUL
    assert Code.ACQUIRER_EPS_NON_POSITIVE in {i.code for i in r.issues}
    assert r.recurring_eps_change == pytest.approx(50.0 / 126.0 - (-0.5))


def test_warnings_for_premium_and_leverage() -> None:
    d = replace(ALL_STOCK, offer_premium=0.80, stock_pct=0.0, new_debt=1800.0)
    r = analyze_deal(replace(ACQ, ebitda=100.0, total_debt=500.0), TGT, d)
    codes = {i.code for i in r.issues}
    assert {Code.UNUSUAL_PREMIUM, Code.HIGH_PRO_FORMA_LEVERAGE} <= codes


@pytest.mark.parametrize(
    "kw",
    [
        {"stock_pct": 1.2},
        {"tax_rate": 0.9},
        {"offer_premium": -1.0},
        {"new_debt": -5.0},
        {"synergy_phase_in_year1": 1.5},
        {"revenue_synergy_margin": None},
    ],
)
def test_invalid_deal_inputs(kw: dict[str, object]) -> None:
    with pytest.raises(EngineError):
        analyze_deal(ACQ, TGT, replace(ALL_STOCK, **kw))  # type: ignore[arg-type]


def test_debt_plug_and_accretion_grid() -> None:
    d = replace(ka_ma03(), new_debt=0.0)
    assert new_debt_to_balance(ACQ, TGT, d) == pytest.approx(650.0)
    grid = accretion_sensitivity(ACQ, TGT, ka_ma03(), (0.2, 0.3, 0.4), (0.0, 0.5, 1.0))
    assert grid.base_value == pytest.approx(0.0632743363)
    for col in range(3):  # higher premium → lower accretion
        vals = [grid.cells[r][col].value for r in range(3)]
        assert vals == sorted(vals, reverse=True)
    with pytest.raises(EngineError) as exc:
        new_debt_to_balance(ACQ, TGT, replace(d, stock_pct=1.0, cash_used=50.0))
    assert exc.value.codes == (Code.NEGATIVE_DEBT_PLUG,)
