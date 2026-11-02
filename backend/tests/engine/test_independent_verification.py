"""Engine vs an independent, exact (Fraction-based) re-computation.

``verification/independent.py`` never imports the engine; here both are run on the same inputs
and every intermediate figure must agree to a relative 1e-12.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import date
from fractions import Fraction
from pathlib import Path

import pytest
from builders import bridge, cap, dates, dcf_inputs, wacc_assumptions
from test_mna import ACQ, ALL_STOCK, TGT

from app.engine.forecast import ForecastInputs, ForecastYearDrivers
from app.engine.mna import analyze_deal
from app.engine.shares import OptionTranche, RsuGrant
from app.engine.valuation import run_dcf
from app.engine.wacc import CapitalStructure, compute_wacc
from verification import independent as ind

BACKEND = Path(__file__).resolve().parents[2]
REL = 1e-12


def close(engine_value: float, exact: Fraction) -> bool:
    return engine_value == pytest.approx(float(exact), rel=REL, abs=1e-12)


def ka_dcf03_inputs():  # type: ignore[no-untyped-def]
    years = tuple(
        ForecastYearDrivers(
            float(ind.GROWTH[i]),
            float(ind.EBITDA_MARGIN[i]),
            float(ind.DA_PCT[i]),
            float(ind.CAPEX_PCT[i]),
            float(ind.NWC_PCT[i]),
        )
        for i in range(5)
    )
    return dcf_inputs(
        dates=dates(market=date(2025, 4, 30)),
        forecast=ForecastInputs(float(ind.BASE_REVENUE), float(ind.BASE_NWC), years),
        tax_rate=float(ind.TAX),
        terminal_growth=float(ind.TERMINAL_G),
        bridge=bridge(
            cash=150.0,
            debt=400.0,
            leases=50.0,
            include_leases=True,
            nci=30.0,
            other=20.0,
            non_operating=40.0,
        ),
        share_capital=cap(
            100.0, options=(OptionTranche("ESOP", 5.0, 12.0),), rsus=(RsuGrant("RSU", 1.0),)
        ),
        current_share_price=20.0,
        wacc_override=None,
        wacc_assumptions=wacc_assumptions(
            risk_free_rate=0.045,
            levered_beta=1.1,
            equity_risk_premium=0.055,
            pre_tax_cost_of_debt=0.07,
        ),
    )


def test_ka_dcf_03_every_intermediate_matches_exact_recomputation() -> None:
    exact = ind.dcf_check()
    r = run_dcf(ka_dcf03_inputs())
    for y, u, row in zip(r.forecast.years, r.ufcf, exact.rows, strict=True):
        for got, key in (
            (y.revenue, "revenue"),
            (y.ebitda, "ebitda"),
            (y.da, "da"),
            (y.ebit, "ebit"),
            (u.taxes_on_ebit, "tax"),
            (u.nopat, "nopat"),
            (y.capex, "capex"),
            (y.nwc, "nwc"),
            (y.change_in_nwc, "dnwc"),
            (u.ufcf, "ufcf"),
        ):
            assert close(got, row[key]), (y.t, key)
    for f, row in zip(r.valuation.flows, exact.rows, strict=True):
        assert close(f.discount_factor, row["df"])
        assert close(f.present_value, row["pv"])
    assert r.wacc_build is not None
    assert close(r.wacc_build.cost_of_equity, exact.ke)
    assert close(r.wacc_build.after_tax_cost_of_debt, exact.kd_at)
    assert close(r.wacc, exact.wacc)
    assert close(r.terminal.value, exact.tv)
    assert close(r.valuation.pv_terminal_value, exact.pv_tv)
    assert close(r.valuation.sum_pv_flows, exact.sum_pv)
    assert close(r.enterprise_value, exact.ev)
    assert close(r.bridge.equity_value, exact.equity_pre)
    assert close(r.per_share.dilution.diluted_shares, exact.diluted_implied)
    assert close(r.value_per_share, exact.per_share)
    assert r.valuation.tv_share_of_ev.value is not None
    assert close(r.valuation.tv_share_of_ev.value, exact.tv_share)
    assert r.implied_exit_multiple.value is not None
    assert close(r.implied_exit_multiple.value, exact.exit_multiple)
    assert r.per_share.circular is True


def test_wacc_and_market_dilution_match_exact() -> None:
    exact = ind.dcf_check()
    cs = CapitalStructure(float(exact.e_mkt), float(exact.d_mkt), 0.0)
    assert close(compute_wacc(ka_dcf03_inputs().wacc_assumptions, cs, 0.25).wacc, exact.wacc)
    ka = compute_wacc(wacc_assumptions(), CapitalStructure(1000.0, 250.0, 0.0), 0.25)
    assert close(
        ka.wacc, Fraction(1000, 1250) * Fraction("0.106") + Fraction(250, 1250) * Fraction("0.045")
    )


@pytest.mark.parametrize("syn", [Fraction(0), Fraction(40), Fraction(17)])
def test_all_stock_accretion_matches_exact(syn: Fraction) -> None:
    exact = ind.all_stock_check(syn)
    r = analyze_deal(ACQ, TGT, replace(ALL_STOCK, run_rate_cost_synergies=float(syn)))
    assert close(r.offer_price, exact.offer)
    assert close(r.equity_purchase_price, exact.equity_price)
    assert close(r.new_shares_issued, exact.new_shares)
    assert close(r.recurring_net_income, exact.pf_ni)
    assert close(r.pro_forma_shares, exact.pf_shares)
    assert close(r.recurring_eps, exact.pf_eps)
    assert r.recurring_accretion.value is not None
    assert close(r.recurring_accretion.value, exact.accretion)
    assert close(r.breakeven_synergies_pre_tax, exact.breakeven)


def test_verification_module_is_independent_of_engine() -> None:
    tree = ast.parse((BACKEND / "verification" / "independent.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("app"), node.module
        if isinstance(node, ast.Import):
            assert all(not a.name.startswith("app") for a in node.names)


def test_published_verification_document_is_up_to_date() -> None:
    doc = BACKEND.parent / "docs" / "verification" / "independent-verification.md"
    assert doc.read_text(encoding="utf-8") == ind.render(), (
        "Regenerate: cd backend && python -m verification.independent "
        "> ../docs/verification/independent-verification.md"
    )
