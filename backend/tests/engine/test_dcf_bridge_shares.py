"""Discounting & terminal value (H.6), EV→equity bridge (H.7, D-09), diluted shares (H.8, D-10)."""

from __future__ import annotations

import pytest
from builders import bridge, cap

from app.engine.bridge import enterprise_from_equity, equity_from_enterprise
from app.engine.dcf import (
    discount_cash_flows,
    discount_factor,
    implied_exit_multiple,
    implied_perpetual_growth,
    terminal_value_gordon,
)
from app.engine.errors import Code, EngineError, MissingInputError
from app.engine.metrics import Status
from app.engine.shares import (
    ConvertibleInstrument,
    InstrumentKind,
    OptionTranche,
    RsuGrant,
    diluted_shares_at_price,
    implied_value_per_share,
)

KA_DCF01_UFCF = [100.0, 110.0, 121.0, 133.1, 146.41]

# --------------------------------------------------------------------------- DCF


def test_ka_dcf_01_discounting_and_gordon_tv() -> None:
    """Every PV equals 100/1.1 = 90.909091 because UFCF grows at exactly WACC.
    ΣPV = 454.545455; TV = 146.41 × 1.02 / 0.08 = 1,866.7275; PV(TV) = 1,159.090909;
    EV = (100/1.1) × (5 + 12.75) = 1,613.636364; TV share = 71.83%."""
    tv = terminal_value_gordon(KA_DCF01_UFCF[-1], 0.10, 0.02)
    assert tv.value == pytest.approx(1866.7275)
    ev = discount_cash_flows(KA_DCF01_UFCF, 0.10, tv.value)
    for f in ev.flows:
        assert f.present_value == pytest.approx(100.0 / 1.1)
    assert ev.sum_pv_flows == pytest.approx(454.545454545)
    assert ev.pv_terminal_value == pytest.approx(1159.090909091)
    assert ev.enterprise_value == pytest.approx((100.0 / 1.1) * 17.75)
    assert ev.enterprise_value == pytest.approx(1613.636363636)
    assert ev.tv_share_of_ev.value == pytest.approx(0.7183098591549295)
    assert ev.issues == ()


def test_discount_factor() -> None:
    assert discount_factor(0.10, 0) == 1.0
    assert discount_factor(0.10, 2) == pytest.approx(1 / 1.21)
    with pytest.raises(EngineError):
        discount_factor(-1.0, 1)


@pytest.mark.parametrize("g", [0.08, 0.085, 0.20])
def test_ka_tv_err_01_growth_at_or_above_wacc_is_rejected(g: float) -> None:
    with pytest.raises(EngineError) as exc:
        terminal_value_gordon(100.0, 0.08, g)
    assert Code.TERMINAL_GROWTH_GE_WACC in exc.value.codes


@pytest.mark.parametrize("final", [0.0, -50.0])
def test_non_positive_final_ufcf_rejected(final: float) -> None:
    with pytest.raises(EngineError) as exc:
        terminal_value_gordon(final, 0.10, 0.02)
    assert exc.value.codes == (Code.TERMINAL_FCF_NON_POSITIVE,)


def test_terminal_growth_warnings() -> None:
    codes = {i.code for i in terminal_value_gordon(100.0, 0.055, 0.05, risk_free_rate=0.04).issues}
    assert codes == {
        Code.TV_SPREAD_NARROW,
        Code.TERMINAL_GROWTH_HIGH,
        Code.TERMINAL_GROWTH_ABOVE_RF,
    }
    neg = terminal_value_gordon(100.0, 0.10, -0.02)
    assert [i.code for i in neg.issues] == [Code.TERMINAL_GROWTH_NEGATIVE]
    assert neg.value == pytest.approx(100.0 * 0.98 / 0.12)


def test_missing_terminal_growth() -> None:
    with pytest.raises(MissingInputError):
        terminal_value_gordon(100.0, 0.10, None)  # type: ignore[arg-type]


def test_high_tv_share_and_negative_ev() -> None:
    ev = discount_cash_flows([1.0] * 5, 0.10, 1000.0)
    assert Code.TV_SHARE_HIGH in {i.code for i in ev.issues}
    neg = discount_cash_flows([-500.0] * 5, 0.10, 100.0)
    assert neg.tv_share_of_ev.status is Status.NOT_MEANINGFUL
    assert Code.ENTERPRISE_VALUE_NON_POSITIVE in {i.code for i in neg.issues}


def test_negative_interim_fcf_is_discounted_normally() -> None:
    ev = discount_cash_flows([-100.0, -50.0, 20.0, 80.0, 120.0], 0.10, 1500.0)
    expected = sum(cf / 1.1**t for t, cf in enumerate([-100.0, -50.0, 20.0, 80.0, 120.0], 1))
    assert ev.sum_pv_flows == pytest.approx(expected)


def test_exit_multiple_and_implied_growth_cross_checks() -> None:
    assert implied_exit_multiple(1000.0, 125.0).value == pytest.approx(8.0)
    assert implied_exit_multiple(1000.0, -1.0).status is Status.NOT_MEANINGFUL
    tv = terminal_value_gordon(146.41, 0.10, 0.02).value
    assert implied_perpetual_growth(tv, 146.41, 0.10).value == pytest.approx(0.02)


# --------------------------------------------------------------------------- bridge


def test_ka_bridge_01() -> None:
    r = equity_from_enterprise(1613.636363636, bridge(cash=100.0, debt=300.0, nci=20.0), 0.0)
    assert r.equity_value == pytest.approx(1393.636363636)
    assert next(ln.label for ln in r.lines) == "Less: total debt"


def test_bridge_every_claim() -> None:
    b = bridge(
        cash=50.0,
        debt=200.0,
        leases=40.0,
        include_leases=True,
        preferred=30.0,
        nci=20.0,
        other=10.0,
        non_operating=25.0,
    )
    r = equity_from_enterprise(1000.0, b, 15.0)
    # 1000 − 200 − 40 − 15 − 30 − 20 − 10 + 50 + 25
    assert r.equity_value == pytest.approx(760.0)
    assert enterprise_from_equity(760.0, b, 15.0) == pytest.approx(1000.0)


def test_leases_excluded_when_lease_cost_is_in_ebitda() -> None:
    r = equity_from_enterprise(1000.0, bridge(leases=40.0, include_leases=False), 0.0)
    assert r.equity_value == pytest.approx(1000.0)
    assert [i.code for i in r.issues] == [Code.LEASES_EXCLUDED]


def test_zero_cash_zero_debt_equity_equals_ev() -> None:
    assert equity_from_enterprise(500.0, bridge(), 0.0).equity_value == 500.0


def test_claims_exceeding_ev() -> None:
    r = equity_from_enterprise(100.0, bridge(debt=300.0), 0.0)
    assert r.equity_value == pytest.approx(-200.0)
    assert Code.EQUITY_VALUE_NON_POSITIVE in {i.code for i in r.issues}


@pytest.mark.parametrize(
    "kw, code",
    [
        ({"cash": None}, Code.MISSING_INPUT),
        ({"debt": -1.0}, Code.SIGN_CONVENTION),
        ({"include_leases": None}, Code.MISSING_INPUT),
    ],
)
def test_bridge_inputs_must_be_explicit(kw: dict[str, object], code: str) -> None:
    with pytest.raises(EngineError) as exc:
        equity_from_enterprise(1000.0, bridge(**kw), 0.0)  # type: ignore[arg-type]
    assert code in exc.value.codes


# --------------------------------------------------------------------------- shares (D-10)


def test_ka_tsm_01_at_observed_price() -> None:
    """Price 50; basic 100; 4m options @30 → 4 × (1 − 30/50) = 1.6m; 2m @60 → 0; RSUs 1m."""
    c = cap(
        100.0,
        options=(
            OptionTranche("A", 4.0, 30.0),
            OptionTranche("B", 2.0, 60.0, InstrumentKind.WARRANT),
        ),
        rsus=(RsuGrant("RSU", 1.0),),
    )
    d = diluted_shares_at_price(c, 50.0)
    assert d.diluted_shares == pytest.approx(102.6)
    a, b, r = d.lines
    assert (a.included, a.proceeds, a.shares_repurchased, a.net_new_shares) == pytest.approx(
        (True, 120.0, 2.4, 1.6)
    )
    assert (b.included, b.net_new_shares) == (False, 0.0)
    assert r.net_new_shares == 1.0


def test_convertible_at_observed_price() -> None:
    cv = ConvertibleInstrument("2029 notes", 100.0, 8.0)  # 12.5 shares if converted
    d_in = diluted_shares_at_price(cap(100.0, convertibles=(cv,)), 10.0)
    assert d_in.diluted_shares == pytest.approx(112.5)
    assert (d_in.converted_face, d_in.unconverted_face) == (100.0, 0.0)
    d_out = diluted_shares_at_price(cap(100.0, convertibles=(cv,)), 7.0)
    assert d_out.diluted_shares == 100.0
    assert (d_out.converted_face, d_out.unconverted_face) == (0.0, 100.0)


def test_implied_no_price_dependent_instruments_is_direct() -> None:
    r = implied_value_per_share(cap(100.0, rsus=(RsuGrant("RSU", 5.0),)), 1000.0)
    assert r.circular is False
    assert r.value_per_share == pytest.approx(1000.0 / 105.0)
    assert "direct" in r.method


def test_ka_sh_02_options_in_the_money_closed_form() -> None:
    """E 1,000, basic 100, 10m options @5. P = (1,000 + 10 × 5) / (100 + 10) = 9.545455.
    Check by TSM at P: 10 × (1 − 5/9.545455) = 4.761905 new shares; 1,000 / 104.761905 = P."""
    c = cap(100.0, options=(OptionTranche("A", 10.0, 5.0),))
    r = implied_value_per_share(c, 1000.0)
    assert r.circular is True
    assert r.value_per_share == pytest.approx(1050.0 / 110.0)
    assert r.dilution.diluted_shares == pytest.approx(104.76190476190476)
    assert 1000.0 / r.dilution.diluted_shares == pytest.approx(r.value_per_share)


def test_options_out_of_the_money_at_implied_value() -> None:
    r = implied_value_per_share(cap(100.0, options=(OptionTranche("A", 10.0, 12.0),)), 1000.0)
    assert r.value_per_share == pytest.approx(10.0)
    assert r.dilution.lines[0].included is False


def test_option_exactly_at_the_money_adds_nothing() -> None:
    r = implied_value_per_share(cap(100.0, options=(OptionTranche("A", 10.0, 10.0),)), 1000.0)
    assert r.value_per_share == pytest.approx(10.0)


def test_ka_sh_03_convertible_converts_at_implied_value() -> None:
    """Equity before conversion 1,000 (face 100 already deducted as debt). Conversion price 8
    → 12.5 shares. P = (1,000 + 100) / 112.5 = 9.777778 > 8 → consistent: converts."""
    cv = ConvertibleInstrument("Notes", 100.0, 8.0)
    r = implied_value_per_share(cap(100.0, convertibles=(cv,)), 1000.0)
    assert r.value_per_share == pytest.approx(1100.0 / 112.5)
    assert r.equity_value_to_common == pytest.approx(1100.0)
    assert Code.CONVERTIBLE_CONVERTED in {i.code for i in r.issues}


def test_convertible_stays_debt_when_out_of_the_money() -> None:
    cv = ConvertibleInstrument("Notes", 100.0, 12.0)
    r = implied_value_per_share(cap(100.0, convertibles=(cv,)), 1000.0)
    assert r.value_per_share == pytest.approx(10.0)
    assert r.equity_value_to_common == pytest.approx(1000.0)


def test_ka_sh_04_mixed_instruments() -> None:
    """Options 10 @5 + convertible 100 @8 + basic 100, E 1,000:
    P = (1,000 + 50 + 100) / (100 + 10 + 12.5) = 9.387755."""
    c = cap(
        100.0,
        options=(OptionTranche("A", 10.0, 5.0),),
        convertibles=(ConvertibleInstrument("Notes", 100.0, 8.0),),
    )
    r = implied_value_per_share(c, 1000.0)
    assert r.value_per_share == pytest.approx(1150.0 / 122.5)


def test_non_positive_equity_value() -> None:
    c = cap(100.0, options=(OptionTranche("A", 10.0, 5.0),))
    r = implied_value_per_share(c, -50.0)
    assert r.value_per_share == pytest.approx(-0.5)
    assert Code.EQUITY_VALUE_NON_POSITIVE in {i.code for i in r.issues}


@pytest.mark.parametrize(
    "c",
    [
        cap(0.0),
        cap(100.0, options=(OptionTranche("A", -1.0, 5.0),)),
        cap(100.0, convertibles=(ConvertibleInstrument("N", 100.0, 0.0),)),
        cap(None),  # type: ignore[arg-type]
    ],
)
def test_invalid_share_capital(c) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(EngineError):
        diluted_shares_at_price(c, 10.0)
    with pytest.raises(EngineError):
        diluted_shares_at_price(cap(100.0), 0.0)
