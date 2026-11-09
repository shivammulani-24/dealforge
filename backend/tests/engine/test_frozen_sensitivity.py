"""Frozen-run sensitivity (Phase 4 plan §4.3, A1, A2, A9) and presentation margins (D4-06)."""

from __future__ import annotations

from fractions import Fraction

import pytest
from builders import bridge, dcf_inputs
from test_independent_verification import ka_dcf03_inputs

from app.engine.errors import Code, EngineError
from app.engine.hashing import canonical_json
from app.engine.metrics import Status
from app.engine.presentation import margins, margins_from_values
from app.engine.sensitivity import (
    AxisSpec,
    BaseMismatchError,
    DcfOutput,
    DcfVariable,
    FrozenBase,
    change_vs_base,
    frozen_run_grid,
)
from app.engine.valuation import DcfInputs, DcfResult, run_dcf

UFCF = [Fraction(100), Fraction(110), Fraction(121), Fraction("133.1"), Fraction("146.41")]
W = [Fraction("0.095"), Fraction("0.10"), Fraction("0.105")]
G = [Fraction("0.015"), Fraction("0.02"), Fraction("0.025")]


def exact_vps(w: Fraction, g: Fraction, debt: int) -> Fraction:
    """Independent exact KA-DCF-02 value per share (does not use the engine)."""
    ev = sum(c / (1 + w) ** (t + 1) for t, c in enumerate(UFCF))
    ev += UFCF[-1] * (1 + g) / (w - g) / (1 + w) ** 5
    return (ev - debt + 100 - 20) / 100


def base(r: DcfResult) -> FrozenBase:
    return FrozenBase(r.wacc, r.enterprise_value, r.equity_value, r.value_per_share)


def grid(inp: DcfInputs, **kw: object):  # type: ignore[no-untyped-def]
    row = kw.get("row", AxisSpec(DcfVariable.WACC, 0.005, 1))
    col = kw.get("col", AxisSpec(DcfVariable.TERMINAL_GROWTH, 0.005, 1))
    out = kw.get("output", DcfOutput.VALUE_PER_SHARE)
    return frozen_run_grid(inp, base(run_dcf(inp)), row, col, out)  # type: ignore[arg-type]


def test_ka_sens_01_matches_exact_recomputation() -> None:
    g = grid(dcf_inputs())
    assert (g.base_row, g.base_col, g.base_matches_run) == (1, 1, True)
    b = exact_vps(Fraction("0.10"), Fraction("0.02"), 300)
    for i, w in enumerate(W):
        for j, gg in enumerate(G):
            cell = g.cells[i][j]
            v = exact_vps(w, gg, 300)
            assert cell.status == "ok"
            assert cell.value == pytest.approx(float(v), rel=1e-12)
            assert cell.change_abs == pytest.approx(float(v - b), rel=1e-9, abs=1e-12)
            assert cell.change_pct.value == pytest.approx(float((v - b) / b), rel=1e-9, abs=1e-12)
    # values quoted in the plan (6 dp)
    assert round(g.cells[0][1].value, 6) == 15.056602
    assert round(g.cells[0][1].change_abs, 6) == 1.120239
    assert round(g.cells[0][1].change_pct.value, 6) == 0.080382
    assert g.cells[1][1].change_abs == 0.0 and g.cells[1][1].change_pct.value == 0.0


def test_ka_sens_02_percentage_is_nm_when_base_is_negative() -> None:
    inp = dcf_inputs(bridge=bridge(cash=100.0, debt=2000.0, nci=20.0))
    g = grid(inp)
    assert round(g.base_value, 6) == -3.063636
    ref = grid(dcf_inputs())
    for i in range(3):
        for j in range(3):
            c, r = g.cells[i][j], ref.cells[i][j]
            assert c.change_pct.status is Status.NOT_MEANINGFUL
            assert c.change_pct.reason == "base value is zero or negative"
            assert c.change_abs == pytest.approx(r.change_abs, abs=1e-9)  # same as KA-SENS-01
            assert c.value == pytest.approx(r.value - 17.0, abs=1e-9)
    assert round(g.cells[0][1].value, 6) == -1.943398


def test_change_vs_base_rules() -> None:
    assert change_vs_base(12.0, 10.0) == (2.0, change_vs_base(12.0, 10.0)[1])
    assert change_vs_base(12.0, 10.0)[1].value == pytest.approx(0.2)
    zero_abs, zero_pct = change_vs_base(5.0, 0.0)
    assert zero_abs == 5.0 and zero_pct.status is Status.NOT_MEANINGFUL
    neg_abs, neg_pct = change_vs_base(-1.0, -3.0)
    assert neg_abs == 2.0 and neg_pct.status is Status.NOT_MEANINGFUL
    none_abs, none_pct = change_vs_base(None, 10.0)
    assert none_abs is None and none_pct.status is Status.MISSING


def test_invalid_cells_carry_codes_and_no_changes() -> None:
    g = grid(dcf_inputs(), col=AxisSpec(DcfVariable.TERMINAL_GROWTH, 0.04, 2))  # g up to 10%
    bad = g.cells[1][4]  # WACC 10% vs g 10%
    assert bad.status == "invalid" and bad.value is None
    assert Code.TERMINAL_GROWTH_GE_WACC in bad.codes
    assert bad.change_abs is None and bad.change_pct.status is Status.MISSING


def test_ka_dcf03_grid_uses_frozen_capm_wacc_as_base() -> None:
    r = run_dcf(ka_dcf03_inputs())
    g = grid(
        ka_dcf03_inputs(),
        row=AxisSpec(DcfVariable.WACC, 0.005, 3),
        col=AxisSpec(DcfVariable.TERMINAL_GROWTH, 0.005, 3),
    )
    assert g.row_values[3] == r.wacc and g.base_value == r.value_per_share
    assert g.cells[3][3].value == r.value_per_share  # exact, not approximate


@pytest.mark.parametrize("output", list(DcfOutput))
def test_every_output_reproduces_its_stored_base(output: DcfOutput) -> None:
    g = grid(dcf_inputs(), output=output)
    assert g.cells[g.base_row][g.base_col].value == g.base_value


def test_operating_shift_and_tax_axes() -> None:
    g = grid(
        dcf_inputs(),
        row=AxisSpec(DcfVariable.REVENUE_GROWTH_SHIFT, 0.01, 1),
        col=AxisSpec(DcfVariable.EBITDA_MARGIN_SHIFT, 0.01, 1),
    )
    assert g.row_values[1] == 0.0 and g.col_values[1] == 0.0
    t = grid(
        dcf_inputs(),
        row=AxisSpec(DcfVariable.TAX_RATE, 0.05, 1),
        col=AxisSpec(DcfVariable.CAPEX_PCT_SHIFT, 0.005, 1),
    )
    assert t.row_values == (0.20, 0.25, 0.30)


@pytest.mark.parametrize(
    "row, col",
    [
        (AxisSpec(DcfVariable.WACC, 0.0001, 1), AxisSpec(DcfVariable.TERMINAL_GROWTH, 0.005, 1)),
        (AxisSpec(DcfVariable.WACC, 0.06, 1), AxisSpec(DcfVariable.TERMINAL_GROWTH, 0.005, 1)),
        (AxisSpec(DcfVariable.WACC, 0.005, 6), AxisSpec(DcfVariable.TERMINAL_GROWTH, 0.005, 1)),
        (AxisSpec(DcfVariable.WACC, 0.005, 0), AxisSpec(DcfVariable.TERMINAL_GROWTH, 0.005, 1)),
        (AxisSpec(DcfVariable.TAX_RATE, 0.001, 1), AxisSpec(DcfVariable.WACC, 0.005, 1)),
        (AxisSpec(DcfVariable.WACC, 0.005, 1), AxisSpec(DcfVariable.WACC, 0.005, 1)),
        (AxisSpec(DcfVariable.WACC, 0.005, True), AxisSpec(DcfVariable.TERMINAL_GROWTH, 0.005, 1)),  # type: ignore[arg-type]
        (AxisSpec("wacc", 0.005, 1), AxisSpec(DcfVariable.TERMINAL_GROWTH, 0.005, 1)),  # type: ignore[arg-type]
    ],
)
def test_axis_limits_are_enforced(row: AxisSpec, col: AxisSpec) -> None:
    with pytest.raises(EngineError):
        grid(dcf_inputs(), row=row, col=col)


def test_base_mismatch_is_detected() -> None:
    inp = dcf_inputs()
    r = run_dcf(inp)
    tampered = FrozenBase(r.wacc, r.enterprise_value, r.equity_value, r.value_per_share + 0.01)
    with pytest.raises(BaseMismatchError):
        frozen_run_grid(
            inp,
            tampered,
            AxisSpec(DcfVariable.WACC, 0.005, 1),
            AxisSpec(DcfVariable.TERMINAL_GROWTH, 0.005, 1),
            DcfOutput.VALUE_PER_SHARE,
        )


def test_grid_is_deterministic() -> None:
    assert canonical_json(grid(ka_dcf03_inputs())) == canonical_json(grid(ka_dcf03_inputs()))


# --------------------------------------------------------------------------- presentation


def test_presentation_margins_ka_dcf03_and_result_untouched() -> None:
    inp = ka_dcf03_inputs()
    r = run_dcf(inp)
    before = canonical_json(r)
    m = margins(r)
    # Y1: EBIT 302.4 / revenue 2,160 = 14.0%; UFCF 181.2 / 2,160 = 8.3889%
    assert m[0].ebit_margin.value == pytest.approx(302.4 / 2160)
    assert m[0].ufcf_margin.value == pytest.approx(181.2 / 2160)
    assert len(m) == 5 and all(x.ebit_margin.is_ok for x in m)
    assert canonical_json(r) == before  # presentation never alters the result


def test_presentation_nm_and_length_checks() -> None:
    m = margins_from_values([0.0, -5.0], [1.0, 1.0], [1.0, 1.0])
    assert all(x.ebit_margin.status is Status.NOT_MEANINGFUL for x in m)
    with pytest.raises(ValueError):
        margins_from_values([1.0], [1.0, 2.0], [1.0])
