"""Property-based invariants (hypothesis) and independent re-computation."""

from __future__ import annotations

from dataclasses import replace

import pytest
from builders import bridge, cap, constant_drivers, dcf_inputs
from hypothesis import given, settings
from hypothesis import strategies as st
from test_mna import ACQ, ALL_STOCK, TGT

from app.engine.dcf import discount_cash_flows, terminal_value_gordon
from app.engine.forecast import ForecastInputs
from app.engine.mna import analyze_deal, new_debt_to_balance
from app.engine.shares import (
    ConvertibleInstrument,
    OptionTranche,
    diluted_shares_at_price,
    implied_value_per_share,
)
from app.engine.valuation import run_dcf

settings.register_profile("engine", max_examples=150, deadline=None, derandomize=True)
settings.load_profile("engine")

rates = st.floats(min_value=0.05, max_value=0.20)
growths = st.floats(min_value=-0.02, max_value=0.035)


@given(w1=rates, w2=rates, g=growths)
def test_ev_strictly_decreases_with_wacc(w1: float, w2: float, g: float) -> None:
    lo, hi = sorted((w1, w2))
    if hi - lo < 1e-6:
        return
    ev = [
        run_dcf(dcf_inputs(wacc_override=w, terminal_growth=g)).enterprise_value for w in (lo, hi)
    ]
    assert ev[0] > ev[1]


@given(g1=growths, g2=growths)
def test_ev_increases_with_terminal_growth(g1: float, g2: float) -> None:
    lo, hi = sorted((g1, g2))
    if hi - lo < 1e-6:
        return
    ev = [run_dcf(dcf_inputs(terminal_growth=g)).enterprise_value for g in (lo, hi)]
    assert ev[1] > ev[0]


@given(k=st.floats(min_value=0.001, max_value=1000.0))
def test_scale_invariance(k: float) -> None:
    """Scaling every monetary input by k scales EV, equity and per-share value by k
    (share count unchanged) and leaves ratios unchanged."""
    base = dcf_inputs()
    f = base.forecast
    scaled = replace(
        base,
        forecast=ForecastInputs(f.base_revenue * k, f.base_nwc * k, f.years),
        bridge=bridge(cash=100.0 * k, debt=300.0 * k, nci=20.0 * k),
        current_share_price=12.0 * k,
    )
    a, b = run_dcf(base), run_dcf(scaled)
    assert b.enterprise_value == pytest.approx(a.enterprise_value * k, rel=1e-9)
    assert b.value_per_share == pytest.approx(a.value_per_share * k, rel=1e-9)
    assert b.valuation.tv_share_of_ev.value == pytest.approx(a.valuation.tv_share_of_ev.value)
    assert b.upside_vs_market.value == pytest.approx(a.upside_vs_market.value, abs=1e-9)


@given(
    cf=st.floats(min_value=1.0, max_value=1e6),
    growth=st.floats(min_value=-0.05, max_value=0.15),
    w=rates,
    g=growths,
)
def test_growing_annuity_closed_form(cf: float, growth: float, w: float, g: float) -> None:
    """Independent check: Σ_{t=1..5} CF(1+γ)^{t-1}/(1+w)^t = CF/(w−γ)·[1 − ((1+γ)/(1+w))^5]."""
    flows = [cf * (1 + growth) ** (t - 1) for t in range(1, 6)]
    tv = terminal_value_gordon(flows[-1], w, g).value
    ev = discount_cash_flows(flows, w, tv)
    if abs(w - growth) > 1e-9:
        closed = cf / (w - growth) * (1 - ((1 + growth) / (1 + w)) ** 5)
    else:
        closed = 5 * cf / (1 + w)
    assert ev.sum_pv_flows == pytest.approx(closed, rel=1e-9)
    assert ev.pv_terminal_value == pytest.approx(flows[-1] * (1 + g) / (w - g) / (1 + w) ** 5)


instrument = st.tuples(
    st.floats(min_value=0.0, max_value=50.0),  # count or face
    st.floats(min_value=0.5, max_value=30.0),  # strike or conversion price
)


@given(
    equity=st.floats(min_value=1.0, max_value=5000.0),
    basic=st.floats(min_value=10.0, max_value=500.0),
    opts=st.lists(instrument, max_size=4),
    convs=st.lists(instrument, max_size=3),
)
def test_implied_per_share_matches_bisection_oracle(
    equity: float, basic: float, opts: list[tuple[float, float]], convs: list[tuple[float, float]]
) -> None:
    """Independent oracle: bisection on f(P) = P − value_per_share_given_price(P)."""
    c = cap(
        basic,
        options=tuple(OptionTranche(f"O{i}", n, k) for i, (n, k) in enumerate(opts)),
        convertibles=tuple(ConvertibleInstrument(f"C{i}", f, k) for i, (f, k) in enumerate(convs)),
    )
    solved = implied_value_per_share(c, equity).value_per_share

    def g(p: float) -> float:
        d = diluted_shares_at_price(c, p)
        return (equity + d.converted_face) / d.diluted_shares

    lo, hi = 1e-9, equity / basic + sum(f for f, _ in convs) / basic + 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if mid - g(mid) > 0:
            hi = mid
        else:
            lo = mid
    assert solved == pytest.approx((lo + hi) / 2, rel=1e-7, abs=1e-9)
    # Self-consistency: TSM at the solved price reproduces the price.
    assert g(solved) == pytest.approx(solved, rel=1e-9)


@given(
    premium=st.floats(min_value=0.0, max_value=0.8),
    pct=st.floats(min_value=0.0, max_value=1.0),
    cost_syn=st.floats(min_value=0.0, max_value=200.0),
)
def test_sources_equal_uses_and_breakeven_is_exact(
    premium: float, pct: float, cost_syn: float
) -> None:
    d = replace(ALL_STOCK, offer_premium=premium, stock_pct=pct, run_rate_cost_synergies=cost_syn)
    d = replace(d, new_debt=new_debt_to_balance(ACQ, TGT, d))
    r = analyze_deal(ACQ, TGT, d)
    assert r.sources_and_uses.total_sources == pytest.approx(r.sources_and_uses.total_uses)
    at_breakeven = analyze_deal(
        ACQ, TGT, replace(d, run_rate_cost_synergies=0.0)
    ).breakeven_synergies_pre_tax
    if at_breakeven >= 0:
        r0 = analyze_deal(ACQ, TGT, replace(d, run_rate_cost_synergies=at_breakeven))
        assert r0.recurring_accretion.value == pytest.approx(0.0, abs=1e-9)


@given(g=st.floats(min_value=-0.2, max_value=0.4), m=st.floats(min_value=0.05, max_value=0.5))
def test_runs_are_deterministic(g: float, m: float) -> None:
    inp = dcf_inputs(
        forecast=ForecastInputs(1000.0, 100.0, constant_drivers(g, m, 0.04, 0.05, 0.1))
    )
    try:
        a = run_dcf(inp)
    except Exception:
        return
    b = run_dcf(inp)
    assert a == b
    assert a.input_hash == b.input_hash
