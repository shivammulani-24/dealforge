"""End-to-end DCF, sensitivity grids and scenarios."""

from __future__ import annotations

from dataclasses import replace

import pytest
from builders import bridge, cap, constant_drivers, dcf_inputs, wacc_assumptions

from app.engine.errors import Code, EngineError, MissingInputError, error
from app.engine.forecast import ForecastInputs
from app.engine.hashing import canonical_json, fingerprint
from app.engine.metrics import Status
from app.engine.scenarios import apply_overrides, run_scenarios
from app.engine.sensitivity import (
    DcfOutput,
    DcfVariable,
    centered_axis,
    dcf_sensitivity,
)
from app.engine.shares import ConvertibleInstrument, OptionTranche
from app.engine.valuation import market_capital_structure, run_dcf
from app.engine.version import ENGINE_VERSION

# --------------------------------------------------------------------------- end to end


def test_ka_dcf_02_full_pipeline_reproduces_component_answers() -> None:
    """Drivers built so UFCF = KA-DCF-01's flows; bridge = KA-BRIDGE-01."""
    r = run_dcf(dcf_inputs())
    assert [u.ufcf for u in r.ufcf] == pytest.approx([100.0, 110.0, 121.0, 133.1, 146.41])
    assert r.wacc == 0.10
    assert r.terminal.value == pytest.approx(1866.7275)
    assert r.enterprise_value == pytest.approx(1613.636363636)
    assert r.bridge.equity_value == pytest.approx(1393.636363636)
    assert r.value_per_share == pytest.approx(13.93636363636)
    assert r.valuation.tv_share_of_ev.value == pytest.approx(0.71830986)
    # TV / EBITDA_5 = 1,866.7275 / (0.21 × 1,610.51)
    assert r.implied_exit_multiple.value == pytest.approx(1866.7275 / (0.21 * 1610.51))
    assert r.upside_vs_market.value == pytest.approx(13.93636363636 / 12.0 - 1.0)
    assert r.engine_version == ENGINE_VERSION
    assert r.schedule.periods[-1].label == "FY2030"
    assert [i.code for i in r.issues] == [Code.WACC_OVERRIDDEN]


def test_perpetuity_identity() -> None:
    """No growth, CapEx = D&A, ΔNWC = 0, g = 0  ⇒  EV = NOPAT / WACC = 112.5 / 10% = 1,125."""
    f = ForecastInputs(1000.0, 100.0, constant_drivers(0.0, 0.20, 0.05, 0.05, 0.10))
    r = run_dcf(dcf_inputs(forecast=f, terminal_growth=0.0))
    assert [u.ufcf for u in r.ufcf] == pytest.approx([112.5] * 5)
    assert r.enterprise_value == pytest.approx(1125.0)


def test_capm_wacc_path_uses_market_values_on_market_data_date() -> None:
    """Price 50 × 20 shares = E 1,000; debt 250 → KA-WACC-01's 9.38%."""
    inp = dcf_inputs(
        wacc_override=None,
        wacc_assumptions=wacc_assumptions(),
        current_share_price=50.0,
        share_capital=cap(20.0),
        bridge=bridge(cash=100.0, debt=250.0),
    )
    cs = market_capital_structure(inp)
    assert (cs.equity_value, cs.debt_value, cs.preferred_value) == (1000.0, 250.0, 0.0)
    r = run_dcf(inp)
    assert r.wacc == pytest.approx(0.0938)
    assert r.wacc_build is not None
    assert Code.DEBT_AT_BOOK in {i.code for i in r.issues}


def test_wacc_debt_includes_debt_like_leases_and_unconverted_convertibles() -> None:
    inp = dcf_inputs(
        wacc_override=None,
        wacc_assumptions=wacc_assumptions(),
        current_share_price=10.0,
        share_capital=cap(100.0, convertibles=(ConvertibleInstrument("N", 50.0, 20.0),)),
        bridge=bridge(debt=200.0, leases=30.0, include_leases=True),
    )
    assert market_capital_structure(inp).debt_value == pytest.approx(280.0)


def test_dcf_with_options_and_convertibles_is_self_consistent() -> None:
    c = cap(
        100.0,
        options=(OptionTranche("A", 5.0, 8.0),),
        convertibles=(ConvertibleInstrument("N", 50.0, 10.0),),
    )
    r = run_dcf(dcf_inputs(share_capital=c))
    p = r.value_per_share
    # Equity before conversion = 1,393.64 − 50 (convertible face) = 1,343.64
    assert r.bridge.equity_value == pytest.approx(1343.636363636)
    assert r.per_share.circular is True
    assert r.per_share.equity_value_to_common / r.per_share.dilution.diluted_shares == (
        pytest.approx(p)
    )
    assert Code.DILUTION_SOLVED in {i.code for i in r.issues}


@pytest.mark.parametrize(
    "kw, code",
    [
        ({"is_financial_institution": True}, Code.FINANCIAL_INSTITUTION_NOT_SUPPORTED),
        ({"wacc_override": None}, Code.MISSING_INPUT),  # neither WACC source
        ({"wacc_assumptions": wacc_assumptions()}, Code.INVALID_TYPE),  # both
        ({"wacc_override": 0.0}, Code.INVALID_WACC),
        ({"wacc_override": -0.05}, Code.INVALID_WACC),
        ({"wacc_override": 1.5}, Code.INVALID_WACC),
        ({"terminal_growth": 0.10}, Code.TERMINAL_GROWTH_GE_WACC),
        ({"terminal_growth": 0.12}, Code.TERMINAL_GROWTH_GE_WACC),
        ({"tax_rate": 0.75}, Code.OUT_OF_RANGE),
        ({"current_share_price": 0.0}, Code.OUT_OF_RANGE),
    ],
)
def test_invalid_valuations_are_rejected(kw: dict[str, object], code: str) -> None:
    with pytest.raises(EngineError) as exc:
        run_dcf(dcf_inputs(**kw))
    assert code in exc.value.codes


def test_capm_path_requires_market_price() -> None:
    with pytest.raises(MissingInputError):
        run_dcf(
            dcf_inputs(
                wacc_override=None, wacc_assumptions=wacc_assumptions(), current_share_price=None
            )
        )


def test_missing_market_price_makes_upside_missing_not_zero() -> None:
    r = run_dcf(dcf_inputs(current_share_price=None))
    assert r.upside_vs_market.status is Status.MISSING


def test_negative_final_fcf_blocks_terminal_value() -> None:
    f = ForecastInputs(1000.0, 100.0, constant_drivers(0.05, -0.10, 0.05, 0.05, 0.10))
    with pytest.raises(EngineError) as exc:
        run_dcf(dcf_inputs(forecast=f))
    assert Code.TERMINAL_FCF_NON_POSITIVE in exc.value.codes


def test_loss_making_early_years_still_value() -> None:
    years = list(constant_drivers(0.30, 0.25, 0.04, 0.06, 0.05))
    years[0] = replace(years[0], ebitda_margin=-0.20)
    years[1] = replace(years[1], ebitda_margin=-0.05)
    f = ForecastInputs(500.0, 25.0, tuple(years))
    r = run_dcf(dcf_inputs(forecast=f))
    assert r.ufcf[0].ufcf < 0 and r.ufcf[0].taxes_on_ebit == 0.0
    codes = {i.code for i in r.issues}
    assert {
        Code.NEGATIVE_EBIT_NO_TAX_CREDIT,
        Code.NEGATIVE_UFCF,
        Code.NEGATIVE_EBITDA_MARGIN,
    } <= codes
    assert r.enterprise_value > 0


def test_peer_range_cross_check() -> None:
    r = run_dcf(dcf_inputs(peer_ev_ebitda_range=(7.0, 12.0)))  # implied ≈ 5.5x
    assert Code.TV_MULTIPLE_INCONSISTENT in {i.code for i in r.issues}


def test_reproducible_and_fingerprinted() -> None:
    a, b = run_dcf(dcf_inputs()), run_dcf(dcf_inputs())
    assert a.input_hash == b.input_hash and a.input_hash.startswith("sha256:")
    assert canonical_json(a) == canonical_json(b)
    c = run_dcf(dcf_inputs(terminal_growth=0.021))
    assert c.input_hash != a.input_hash
    assert fingerprint(dcf_inputs()) == a.input_hash


def test_canonical_json_rejects_nan() -> None:
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})


# --------------------------------------------------------------------------- sensitivity


def test_wacc_by_growth_grid_base_cell_equals_base_run() -> None:
    inp = dcf_inputs()
    base = run_dcf(inp)
    g = dcf_sensitivity(
        inp,
        DcfVariable.WACC,
        centered_axis(0.10, 0.01, 2),
        DcfVariable.TERMINAL_GROWTH,
        centered_axis(0.02, 0.01, 2),
    )
    assert g.base_value == base.value_per_share  # exact, not approximate
    assert g.cells[g.base_row][g.base_col].value == base.value_per_share
    # WACC 8% with g 4%... fine; but WACC 8% row with g = 0.04 is valid, and
    # every cell must be monotone: higher WACC → lower value; higher g → higher value.
    for r in range(len(g.row_values) - 1):
        for col in range(len(g.col_values)):
            a, b = g.cells[r][col].value, g.cells[r + 1][col].value
            if a is not None and b is not None:
                assert a > b
    for row in g.cells:
        vals = [cell.value for cell in row if cell.value is not None]
        assert vals == sorted(vals)


def test_invalid_cells_are_marked_not_numbers() -> None:
    g = dcf_sensitivity(
        dcf_inputs(), DcfVariable.WACC, (0.03, 0.10), DcfVariable.TERMINAL_GROWTH, (0.02, 0.04)
    )
    bad = g.cells[0][1]  # WACC 3% vs g 4%
    assert bad.status == "invalid" and bad.value is None
    assert Code.TERMINAL_GROWTH_GE_WACC in bad.codes


def test_operating_shift_grid() -> None:
    inp = dcf_inputs()
    g = dcf_sensitivity(
        inp,
        DcfVariable.REVENUE_GROWTH_SHIFT,
        centered_axis(0.0, 0.02, 1),
        DcfVariable.EBITDA_MARGIN_SHIFT,
        centered_axis(0.0, 0.02, 1),
        DcfOutput.ENTERPRISE_VALUE,
    )
    assert g.base_value == pytest.approx(1613.636363636)
    assert g.cells[1][2].value > g.cells[1][1].value  # +2pp margin raises EV
    assert g.cells[1][0].value < g.cells[1][1].value


def test_margin_shift_that_breaks_validation_is_invalid_cell() -> None:
    g = dcf_sensitivity(
        dcf_inputs(),
        DcfVariable.EBITDA_MARGIN_SHIFT,
        (0.0, 0.85),
        DcfVariable.TAX_RATE,
        (0.25, 0.30),
        DcfOutput.EQUITY_VALUE,
    )
    assert g.cells[1][0].status == "invalid"  # 21% + 85% margin > 100%
    assert g.cells[0][1].status == "ok"


def test_capex_shift() -> None:
    g = dcf_sensitivity(
        dcf_inputs(),
        DcfVariable.CAPEX_PCT_SHIFT,
        (0.0, 0.01),
        DcfVariable.TERMINAL_GROWTH,
        (0.02,),
    )
    assert g.cells[1][0].value < g.cells[0][0].value


@pytest.mark.parametrize(
    "rows, cols, code",
    [
        ((0.09, 0.11), (0.02,), Code.BASE_NOT_IN_AXIS),
        ((), (0.02,), Code.INVALID_AXIS),
        ((0.10, 0.10), (0.02,), Code.INVALID_AXIS),
    ],
)
def test_bad_axes(rows: tuple[float, ...], cols: tuple[float, ...], code: str) -> None:
    with pytest.raises(EngineError) as exc:
        dcf_sensitivity(dcf_inputs(), DcfVariable.WACC, rows, DcfVariable.TERMINAL_GROWTH, cols)
    assert exc.value.codes == (code,)


def test_same_variable_on_both_axes_rejected() -> None:
    with pytest.raises(EngineError):
        dcf_sensitivity(dcf_inputs(), DcfVariable.WACC, (0.10,), DcfVariable.WACC, (0.10,))


def test_centered_axis() -> None:
    assert centered_axis(0.02, 0.005, 2)[2] == 0.02
    with pytest.raises(EngineError):
        centered_axis(0.02, 0.0, 2)


# --------------------------------------------------------------------------- scenarios


def test_scenarios_apply_audited_overrides() -> None:
    base = dcf_inputs()
    runs = run_scenarios(
        base,
        [
            ("Base", {}),
            ("Downside", {"forecast.years[5].ebitda_margin": 0.18, "terminal_growth": 0.015}),
            ("Upside", {"wacc_override": 0.09}),
        ],
    )
    b, d, u = (s.result.value_per_share for s in runs)
    assert d < b < u
    assert runs[1].overrides == (
        ("forecast.years[5].ebitda_margin", 0.18),
        ("terminal_growth", 0.015),
    )
    resolved = apply_overrides(base, {"forecast.years[5].ebitda_margin": 0.18})
    assert resolved.forecast.years[4].ebitda_margin == 0.18
    assert resolved.forecast.years[3].ebitda_margin == 0.21
    assert base.forecast.years[4].ebitda_margin == 0.21  # base untouched (immutable)


@pytest.mark.parametrize(
    "path",
    [
        "terminal_grwth",
        "forecast.years[6].ebitda_margin",
        "forecast.years[1]",
        "bridge",
        "dates.statement_date",
        "wacc_assumptions.levered_beta",
    ],
)
def test_bad_override_paths_rejected(path: str) -> None:
    with pytest.raises(EngineError):
        apply_overrides(dcf_inputs(), {path: 0.1})


def test_grid_whose_base_case_is_invalid_is_rejected() -> None:
    from app.engine.sensitivity import two_way_grid

    def evaluate(r: float, c: float) -> float:
        raise EngineError([error("X", "bad")])

    with pytest.raises(EngineError) as exc:
        two_way_grid(
            evaluate,
            (1.0,),
            (2.0,),
            row_base=1.0,
            col_base=2.0,
            row_name="a",
            col_name="b",
            output="o",
        )
    assert exc.value.codes == (Code.BASE_NOT_IN_AXIS,)
