"""Comparable-company analysis (H.9, D-03, D-11)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import numpy as np
import pytest
from builders import bridge, cap

from app.engine.comps import (
    MultipleKind,
    PeerInputs,
    PeriodType,
    analyze_comps,
    compute_peer,
    implied_valuation,
    percentile_inc,
)
from app.engine.ebitda import EbitdaBasis, EbitdaFigures
from app.engine.errors import Code, EngineError
from app.engine.metrics import Status, missing, ok
from app.engine.shares import ConvertibleInstrument, OptionTranche

END = date(2025, 3, 31)


def peer(name: str, mcap: float, ebit: float, da: float = 0.0, **kw: object) -> PeerInputs:
    """Peer with price 10 and mcap/10 basic shares; zero bridge unless overridden (EV = mcap)."""
    base = PeerInputs(
        name=name,
        share_price=10.0,
        price_currency="USD",
        reporting_currency="USD",
        share_capital=cap(mcap / 10.0),
        bridge=bridge(),
        revenue=mcap / 2.0,
        ebitda=EbitdaFigures(ebit=ebit, da=da),
        net_income=mcap / 20.0,
        period_type=PeriodType.LTM,
        period_end=END,
    )
    return replace(base, **kw)  # type: ignore[arg-type]


def test_ka_comp_01_peer_ev_and_multiples() -> None:
    """Price 25 × 40 = 1,000 market cap; + debt 300 + NCI 50 − cash 150 = EV 1,200.
    Revenue 600 → 2.0x; EBITDA 120 + 30 = 150 → 8.0x; NI 80 → P/E 12.5x."""
    p = PeerInputs(
        name="Peer A (SYNTHETIC)",
        share_price=25.0,
        price_currency="USD",
        reporting_currency="USD",
        share_capital=cap(40.0),
        bridge=bridge(cash=150.0, debt=300.0, nci=50.0),
        revenue=600.0,
        ebitda=EbitdaFigures(ebit=120.0, da=30.0),
        net_income=80.0,
        period_type=PeriodType.LTM,
        period_end=END,
    )
    r = compute_peer(p, EbitdaBasis.STANDARDIZED)
    assert r.market_cap == pytest.approx(1000.0)
    assert r.enterprise_value == pytest.approx(1200.0)
    assert r.multiples[MultipleKind.EV_REVENUE].value == pytest.approx(2.0)
    assert r.multiples[MultipleKind.EV_EBITDA].value == pytest.approx(8.0)
    assert r.multiples[MultipleKind.PE].value == pytest.approx(12.5)


def ka_comp02_peers() -> list[PeerInputs]:
    return [
        peer("P1", 800.0, 100.0),
        peer("P2", 1000.0, 100.0),
        peer("P3", 1200.0, 100.0),
        peer("P4", 1400.0, 100.0),
        peer("P5 loss-making", 900.0, -50.0, 10.0),  # EBITDA −40 → NM
        peer("P6", 3000.0, 100.0, included=False, exclusion_reason="one-off disposal gain"),
    ]


def test_ka_comp_02_statistics_and_exclusions() -> None:
    a = analyze_comps(
        ka_comp02_peers(),
        period_type=PeriodType.LTM,
        ebitda_basis=EbitdaBasis.STANDARDIZED,
        target_period_end=END,
    )
    s = a.stats[MultipleKind.EV_EBITDA]
    assert s.values == pytest.approx((8.0, 10.0, 12.0, 14.0))
    assert s.n == 4
    assert (s.median, s.mean, s.p25, s.p75) == pytest.approx((11.0, 11.0, 9.5, 12.5))
    assert (s.minimum, s.maximum) == (8.0, 14.0)
    left = dict(s.left_out)
    assert left["P5 loss-making"].startswith("not_meaningful")
    assert left["P6"] == "excluded by analyst: one-off disposal gain"
    assert Code.POTENTIAL_OUTLIER not in {i.code for i in a.issues}

    target_ebitda = ok(200.0)
    iv = implied_valuation(s, target_ebitda, bridge=bridge(), share_capital=cap(100.0))
    assert [pt.enterprise_value for pt in iv.points] == pytest.approx([1900.0, 2200.0, 2500.0])
    assert [pt.value_per_share for pt in iv.points] == pytest.approx([19.0, 22.0, 25.0])


def test_percentile_matches_numpy_and_excel_inc() -> None:
    rng = np.random.default_rng(7)
    for _ in range(50):
        xs = sorted(rng.uniform(1, 40, size=int(rng.integers(1, 15))).tolist())
        for q in (0.0, 0.25, 0.5, 0.75, 1.0):
            assert percentile_inc(xs, q) == pytest.approx(float(np.percentile(xs, q * 100)))
    with pytest.raises(ValueError):
        percentile_inc([], 0.5)
    with pytest.raises(ValueError):
        percentile_inc([1.0], 1.5)


def test_ebitda_basis_is_never_mixed() -> None:
    peers = [
        peer("P1", 800.0, 100.0, ebitda=EbitdaFigures(80.0, 20.0, adjusted=120.0)),
        peer("P2", 1000.0, 100.0),  # no adjusted EBITDA disclosed
    ]
    a = analyze_comps(
        peers, period_type=PeriodType.LTM, ebitda_basis=EbitdaBasis.ADJUSTED, target_period_end=END
    )
    p2 = a.peers[1].multiples[MultipleKind.EV_EBITDA]
    assert p2.status is Status.MISSING  # not silently replaced by standardised EBITDA
    s = a.stats[MultipleKind.EV_EBITDA]
    assert s.values == pytest.approx((800.0 / 120.0,))
    assert Code.LOW_PEER_COUNT in {i.code for i in a.issues}


def test_period_type_mismatch_is_an_error() -> None:
    peers = [peer("P1", 800.0, 100.0), peer("P2", 900.0, 100.0, period_type=PeriodType.NTM)]
    with pytest.raises(EngineError) as exc:
        analyze_comps(
            peers,
            period_type=PeriodType.LTM,
            ebitda_basis=EbitdaBasis.STANDARDIZED,
            target_period_end=END,
        )
    assert exc.value.codes == (Code.PERIOD_TYPE_MISMATCH,)


def test_misaligned_fiscal_year_and_multi_currency_are_flagged() -> None:
    peers = [
        peer("P1", 800.0, 100.0, period_end=date(2024, 9, 30)),  # 182 days earlier
        peer("P2", 900.0, 100.0, price_currency="INR", reporting_currency="INR"),
        peer("P3", 1000.0, 100.0),
    ]
    a = analyze_comps(
        peers,
        period_type=PeriodType.LTM,
        ebitda_basis=EbitdaBasis.STANDARDIZED,
        target_period_end=END,
    )
    codes = [i.code for i in a.issues]
    assert Code.FISCAL_PERIOD_MISALIGNED in codes
    assert Code.CURRENCY_MISMATCH in codes  # info: multiples still comparable
    assert a.stats[MultipleKind.EV_EBITDA].n == 3


def test_price_and_financials_in_different_currencies_rejected() -> None:
    with pytest.raises(EngineError) as exc:
        compute_peer(
            peer("ADR", 800.0, 100.0, price_currency="USD", reporting_currency="INR"),
            EbitdaBasis.STANDARDIZED,
        )
    assert exc.value.codes == (Code.CURRENCY_MISMATCH,)


def test_exclusion_without_reason_rejected() -> None:
    with pytest.raises(EngineError) as exc:
        compute_peer(
            peer("P", 800.0, 100.0, included=False, exclusion_reason="  "), EbitdaBasis.STANDARDIZED
        )
    assert exc.value.codes == (Code.EXCLUSION_REASON_REQUIRED,)


def test_outliers_flagged_not_excluded() -> None:
    a = analyze_comps(
        [peer("Hot", 8000.0, 100.0), peer("P2", 1000.0, 100.0), peer("P3", 1100.0, 100.0)],
        period_type=PeriodType.LTM,
        ebitda_basis=EbitdaBasis.STANDARDIZED,
        target_period_end=END,
    )
    assert Code.POTENTIAL_OUTLIER in {i.code for i in a.issues}
    assert a.stats[MultipleKind.EV_EBITDA].n == 3


def test_net_cash_peer_with_negative_ev_is_nm() -> None:
    p = peer("Cash shell", 100.0, 10.0, bridge=bridge(cash=500.0))
    r = compute_peer(p, EbitdaBasis.STANDARDIZED)
    assert r.enterprise_value == pytest.approx(-400.0)
    assert r.multiples[MultipleKind.EV_EBITDA].status is Status.NOT_MEANINGFUL
    assert r.multiples[MultipleKind.PE].is_ok  # equity multiple still meaningful


def test_missing_revenue_and_loss_pe() -> None:
    r = compute_peer(
        peer("P", 800.0, 100.0, revenue=None, net_income=-5.0), EbitdaBasis.STANDARDIZED
    )
    assert r.multiples[MultipleKind.EV_REVENUE].status is Status.MISSING
    assert r.multiples[MultipleKind.PE].status is Status.NOT_MEANINGFUL


def test_peer_dilution_and_convertibles_in_ev() -> None:
    """Options 10 @5 at price 10 → +5 shares; convertible 100 @8 converts (+12.5 shares)
    and is removed from debt. Market cap = 10 × (100 + 5 + 12.5) = 1,175; EV = 1,175 + 200."""
    c = cap(
        100.0,
        options=(OptionTranche("A", 10.0, 5.0),),
        convertibles=(ConvertibleInstrument("N", 100.0, 8.0),),
    )
    r = compute_peer(
        peer("P", 1000.0, 100.0, share_capital=c, bridge=bridge(debt=200.0)),
        EbitdaBasis.STANDARDIZED,
    )
    assert r.diluted_shares == pytest.approx(117.5)
    assert r.enterprise_value == pytest.approx(1375.0)


def test_pe_route_and_target_metric_validation() -> None:
    a = analyze_comps(
        ka_comp02_peers(),
        period_type=PeriodType.LTM,
        ebitda_basis=EbitdaBasis.STANDARDIZED,
        target_period_end=END,
    )
    pe = a.stats[MultipleKind.PE]  # every included peer has P/E = 20x
    iv = implied_valuation(pe, ok(50.0), bridge=bridge(debt=999.0), share_capital=cap(100.0))
    assert iv.points[1].enterprise_value is None
    assert iv.points[1].equity_value == pytest.approx(1000.0)  # bridge not applied for P/E
    assert iv.points[1].value_per_share == pytest.approx(10.0)
    with_conv = implied_valuation(
        pe,
        ok(50.0),
        bridge=bridge(),
        share_capital=cap(100.0, convertibles=(ConvertibleInstrument("N", 10.0, 1.0),)),
    )
    assert Code.PE_CONVERTIBLES_IGNORED in {i.code for i in with_conv.issues}
    for bad in (ok(-10.0), ok(0.0), missing("net income")):
        with pytest.raises(EngineError) as exc:
            implied_valuation(pe, bad, bridge=bridge(), share_capital=cap(100.0))
        assert exc.value.codes == (Code.TARGET_METRIC_NOT_MEANINGFUL,)


def test_no_meaningful_values() -> None:
    a = analyze_comps(
        [peer("L", 900.0, -50.0, 10.0)],
        period_type=PeriodType.LTM,
        ebitda_basis=EbitdaBasis.STANDARDIZED,
        target_period_end=END,
    )
    s = a.stats[MultipleKind.EV_EBITDA]
    assert s.n == 0 and s.median is None
    assert Code.NO_VALID_PEERS in {i.code for i in a.issues}
    with pytest.raises(EngineError):
        implied_valuation(s, ok(100.0), bridge=bridge(), share_capital=cap(100.0))
    with pytest.raises(EngineError):
        analyze_comps(
            [],
            period_type=PeriodType.LTM,
            ebitda_basis=EbitdaBasis.STANDARDIZED,
            target_period_end=END,
        )
