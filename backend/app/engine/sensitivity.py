"""Two-way sensitivity tables (spec section H.12).

Every cell is a **complete re-run** of :func:`run_dcf` with one or two inputs replaced — no
shortcuts such as rescaling EV — so every cell is internally consistent with the DCF.
Invalid combinations (e.g. terminal growth ≥ WACC) become ``invalid`` cells carrying the
error codes; they never show a number.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from .errors import Code, EngineError, error
from .metrics import Metric, Status, nm, ok
from .validation import Checker
from .valuation import DcfInputs, DcfResult, run_dcf

BASE_MATCH_TOLERANCE = 1e-12


class DcfVariable(StrEnum):
    WACC = "wacc"  # replaces the CAPM result with a direct WACC
    TERMINAL_GROWTH = "terminal_growth"
    REVENUE_GROWTH_SHIFT = "revenue_growth_shift"  # added to every year's growth
    EBITDA_MARGIN_SHIFT = "ebitda_margin_shift"  # added to every year's margin
    CAPEX_PCT_SHIFT = "capex_pct_shift"  # added to every year's CapEx % revenue
    TAX_RATE = "tax_rate"


class DcfOutput(StrEnum):
    VALUE_PER_SHARE = "value_per_share"
    ENTERPRISE_VALUE = "enterprise_value"
    EQUITY_VALUE = "equity_value"


@dataclass(frozen=True, slots=True)
class Cell:
    value: float | None
    status: str  # "ok" | "invalid"
    codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Grid:
    row_variable: str
    col_variable: str
    output: str
    row_values: tuple[float, ...]
    col_values: tuple[float, ...]
    cells: tuple[tuple[Cell, ...], ...]
    base_row: int
    base_col: int
    base_value: float


def centered_axis(base: float, step: float, steps_each_side: int) -> tuple[float, ...]:
    """``base + k × step`` for k = −n..n; the middle value is exactly ``base``."""
    if step <= 0 or steps_each_side < 0:
        raise EngineError([error(Code.INVALID_AXIS, "step must be > 0 and steps ≥ 0.")])
    return tuple(base + k * step for k in range(-steps_each_side, steps_each_side + 1))


def _index_of(values: Sequence[float], base: float, name: str) -> int:
    for i, v in enumerate(values):
        if abs(v - base) <= BASE_MATCH_TOLERANCE:
            return i
    raise EngineError(
        [
            error(
                Code.BASE_NOT_IN_AXIS,
                f"The base value of {name} ({base!r}) must appear on its axis so the base case "
                "can be read off the grid.",
            )
        ]
    )


def two_way_grid(
    evaluate: Callable[[float, float], float],
    row_values: Sequence[float],
    col_values: Sequence[float],
    *,
    row_base: float,
    col_base: float,
    row_name: str,
    col_name: str,
    output: str,
) -> Grid:
    if not row_values or not col_values:
        raise EngineError([error(Code.INVALID_AXIS, "Both axes need at least one value.")])
    if len(set(row_values)) != len(row_values) or len(set(col_values)) != len(col_values):
        raise EngineError([error(Code.INVALID_AXIS, "Axis values must be distinct.")])
    if row_name == col_name:
        raise EngineError([error(Code.INVALID_AXIS, "Row and column variables must differ.")])
    br = _index_of(row_values, row_base, row_name)
    bc = _index_of(col_values, col_base, col_name)
    # Use the exact base values at the base indices so the base cell reproduces the base run.
    rows = tuple(row_base if i == br else v for i, v in enumerate(row_values))
    cols = tuple(col_base if j == bc else v for j, v in enumerate(col_values))

    cells: list[tuple[Cell, ...]] = []
    for r in rows:
        line: list[Cell] = []
        for col in cols:
            try:
                line.append(Cell(evaluate(r, col), "ok", ()))
            except EngineError as exc:
                line.append(Cell(None, "invalid", exc.codes))
        cells.append(tuple(line))
    base_cell = cells[br][bc]
    if base_cell.value is None:
        raise EngineError(
            [error(Code.BASE_NOT_IN_AXIS, f"The base case itself is invalid: {base_cell.codes}.")]
        )
    return Grid(row_name, col_name, output, rows, cols, tuple(cells), br, bc, base_cell.value)


def apply_variable(inp: DcfInputs, var: DcfVariable, value: float) -> DcfInputs:
    if var is DcfVariable.WACC:
        return replace(inp, wacc_assumptions=None, wacc_override=value)
    if var is DcfVariable.TERMINAL_GROWTH:
        return replace(inp, terminal_growth=value)
    if var is DcfVariable.TAX_RATE:
        return replace(inp, tax_rate=value)
    field = {
        DcfVariable.REVENUE_GROWTH_SHIFT: "revenue_growth",
        DcfVariable.EBITDA_MARGIN_SHIFT: "ebitda_margin",
        DcfVariable.CAPEX_PCT_SHIFT: "capex_pct_revenue",
    }[var]
    if value == 0.0:
        return inp  # the base case is the untouched input
    years = tuple(replace(y, **{field: getattr(y, field) + value}) for y in inp.forecast.years)
    return replace(inp, forecast=replace(inp.forecast, years=years))


def base_value(inp: DcfInputs, base: DcfResult, var: DcfVariable) -> float:
    if var is DcfVariable.WACC:
        return base.wacc
    if var is DcfVariable.TERMINAL_GROWTH:
        return inp.terminal_growth
    if var is DcfVariable.TAX_RATE:
        return inp.tax_rate
    return 0.0


def read_output(res: DcfResult, output: DcfOutput) -> float:
    if output is DcfOutput.VALUE_PER_SHARE:
        return res.value_per_share
    if output is DcfOutput.ENTERPRISE_VALUE:
        return res.enterprise_value
    return res.equity_value


def dcf_sensitivity(
    inp: DcfInputs,
    row: DcfVariable,
    row_values: Sequence[float],
    col: DcfVariable,
    col_values: Sequence[float],
    output: DcfOutput = DcfOutput.VALUE_PER_SHARE,
) -> Grid:
    base = run_dcf(inp)

    def evaluate(rv: float, cv: float) -> float:
        changed = inp
        if rv != base_value(inp, base, row):
            changed = apply_variable(changed, row, rv)
        if cv != base_value(inp, base, col):
            changed = apply_variable(changed, col, cv)
        return read_output(run_dcf(changed), output)

    return two_way_grid(
        evaluate,
        row_values,
        col_values,
        row_base=base_value(inp, base, row),
        col_base=base_value(inp, base, col),
        row_name=row.value,
        col_name=col.value,
        output=output.value,
    )


# ------------------------------------------------------------------------------------------
# Frozen-run grids (Phase 4 plan §4.3, amendments A1 and A9). All sensitivity arithmetic for a
# saved run lives here, so ENGINE_VERSION governs it: axis construction, cell evaluation,
# absolute and percentage changes and the base-match rule.
# ------------------------------------------------------------------------------------------

#: (min step, max step) per variable; steps_each_side is limited to 1..MAX_STEPS_EACH_SIDE.
STEP_LIMITS: dict[DcfVariable, tuple[float, float]] = {
    DcfVariable.WACC: (0.0005, 0.05),
    DcfVariable.TERMINAL_GROWTH: (0.0005, 0.05),
    DcfVariable.REVENUE_GROWTH_SHIFT: (0.0005, 0.05),
    DcfVariable.EBITDA_MARGIN_SHIFT: (0.0005, 0.05),
    DcfVariable.CAPEX_PCT_SHIFT: (0.0005, 0.05),
    DcfVariable.TAX_RATE: (0.005, 0.10),
}
MAX_STEPS_EACH_SIDE = 5


@dataclass(frozen=True, slots=True)
class AxisSpec:
    variable: DcfVariable
    step: float
    steps_each_side: int


@dataclass(frozen=True, slots=True)
class FrozenBase:
    """Outputs read from the run's stored result, used to anchor axes and verify the base."""

    wacc: float
    enterprise_value: float
    equity_value: float
    value_per_share: float

    def output(self, which: DcfOutput) -> float:
        return float(getattr(self, which.value))


@dataclass(frozen=True, slots=True)
class SensitivityCell:
    value: float | None
    status: str  # "ok" | "invalid"
    codes: tuple[str, ...]
    change_abs: float | None  # value − base, in the output's units
    change_pct: Metric  # (value − base) / base; NM when base ≤ 0


@dataclass(frozen=True, slots=True)
class FrozenGrid:
    row_variable: str
    col_variable: str
    output: str
    row_values: tuple[float, ...]
    col_values: tuple[float, ...]
    base_row: int
    base_col: int
    base_value: float
    base_matches_run: bool
    cells: tuple[tuple[SensitivityCell, ...], ...]


class BaseMismatchError(EngineError):
    """The recomputed base cell differs from the stored run output (should be impossible)."""


def change_vs_base(value: float | None, base: float) -> tuple[float | None, Metric]:
    """Absolute and percentage change of one cell (A9).

    The percentage is only meaningful for a positive base; for base ≤ 0 it is NM, while the
    absolute change is still reported.
    """
    if value is None:
        return None, Metric(None, Status.MISSING, "cell invalid")
    diff = value - base
    if base <= 0:
        return diff, nm("base value is zero or negative")
    return diff, ok(diff / base)


def _validate_axis(c: Checker, name: str, axis: AxisSpec) -> None:
    if not isinstance(axis.variable, DcfVariable):
        c.error(Code.INVALID_AXIS, f"{name}.variable is not a supported variable.", name)
        return
    lo, hi = STEP_LIMITS[axis.variable]
    c.in_range(f"{name}.step", axis.step, lo, hi)
    if isinstance(axis.steps_each_side, bool) or not isinstance(axis.steps_each_side, int):
        c.error(Code.INVALID_AXIS, f"{name}.steps_each_side must be an integer.", name)
    elif not 1 <= axis.steps_each_side <= MAX_STEPS_EACH_SIDE:
        c.error(
            Code.INVALID_AXIS, f"{name}.steps_each_side must be 1..{MAX_STEPS_EACH_SIDE}.", name
        )


def _axis_base(inp: DcfInputs, base: FrozenBase, var: DcfVariable) -> float:
    if var is DcfVariable.WACC:
        return base.wacc
    if var is DcfVariable.TERMINAL_GROWTH:
        return inp.terminal_growth
    if var is DcfVariable.TAX_RATE:
        return inp.tax_rate
    return 0.0


def frozen_run_grid(
    inp: DcfInputs, base: FrozenBase, row: AxisSpec, col: AxisSpec, output: DcfOutput
) -> FrozenGrid:
    """Two-way sensitivity of a frozen run. ``inp`` must be the run's frozen inputs and
    ``base`` its stored outputs; the base cell must reproduce the stored output exactly."""
    c = Checker()
    _validate_axis(c, "row", row)
    _validate_axis(c, "col", col)
    if not isinstance(output, DcfOutput):
        c.error(Code.INVALID_AXIS, "output is not supported.", "output")
    c.raise_if_errors()
    if row.variable is col.variable:
        raise EngineError([error(Code.INVALID_AXIS, "Row and column variables must differ.")])

    row_values = centered_axis(_axis_base(inp, base, row.variable), row.step, row.steps_each_side)
    col_values = centered_axis(_axis_base(inp, base, col.variable), col.step, col.steps_each_side)
    grid = dcf_sensitivity(inp, row.variable, row_values, col.variable, col_values, output)

    stored = base.output(output)
    matches = grid.base_value == stored
    if not matches:
        raise BaseMismatchError(
            [
                error(
                    "BASE_MISMATCH",
                    f"Recomputed base {grid.base_value!r} differs from stored {stored!r}.",
                )
            ]
        )
    cells = tuple(
        tuple(
            SensitivityCell(
                cell.value, cell.status, cell.codes, *change_vs_base(cell.value, stored)
            )
            for cell in line
        )
        for line in grid.cells
    )
    return FrozenGrid(
        row_variable=grid.row_variable,
        col_variable=grid.col_variable,
        output=grid.output,
        row_values=grid.row_values,
        col_values=grid.col_values,
        base_row=grid.base_row,
        base_col=grid.base_col,
        base_value=stored,
        base_matches_run=matches,
        cells=cells,
    )
