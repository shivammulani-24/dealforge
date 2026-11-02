"""Discounting, Gordon-growth terminal value and enterprise value (spec section H.6, D-07).

::

    DF_t     = 1 / (1 + WACC)^t                      end-of-year convention, t = 1..N
    TV_N     = UFCF_N × (1 + g) / (WACC − g)         value at the end of year N of all
                                                     cash flows from year N+1 onwards
    PV(TV)   = TV_N × DF_N
    EV       = Σ UFCF_t × DF_t + PV(TV)

Why g must be below WACC: the Gordon formula is the closed-form sum of the geometric series
Σ_{k≥1} UFCF_N (1+g)^k / (1+WACC)^k. That series converges only if (1+g)/(1+WACC) < 1, i.e.
g < WACC. At g = WACC the sum is infinite; above it the formula returns a *negative* number
that has no economic meaning. Economically, a business cannot grow faster than the economy
(and its own cost of capital) forever.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .errors import Code, Issue, warning
from .metrics import Metric, nm, ok
from .validation import Checker

#: Long-run nominal growth ceiling above which terminal growth is flagged.
TERMINAL_GROWTH_CEILING = 0.04
#: Minimum comfortable spread between WACC and g.
MIN_SPREAD = 0.01
#: TV share of EV above which a warning is raised.
TV_SHARE_WARNING = 0.75


@dataclass(frozen=True, slots=True)
class TerminalValue:
    final_ufcf: float
    growth: float
    wacc: float
    value: float  # at end of year N (undiscounted)
    issues: tuple[Issue, ...]


@dataclass(frozen=True, slots=True)
class DiscountedFlow:
    t: int
    cash_flow: float
    discount_factor: float
    present_value: float


@dataclass(frozen=True, slots=True)
class EnterpriseValue:
    flows: tuple[DiscountedFlow, ...]
    sum_pv_flows: float
    terminal_value: float
    pv_terminal_value: float
    enterprise_value: float
    tv_share_of_ev: Metric
    issues: tuple[Issue, ...]


def discount_factor(rate: float, t: float) -> float:
    """1 / (1 + rate)^t. ``t`` is in years from the valuation date."""
    c = Checker()
    c.in_range("rate", rate, -1.0, 10.0, low_inclusive=False)
    c.non_negative("t", t)
    c.raise_if_errors()
    return float(1.0 / (1.0 + rate) ** t)


def terminal_value_gordon(
    final_ufcf: float,
    wacc: float,
    growth: float,
    *,
    risk_free_rate: float | None = None,
) -> TerminalValue:
    c = Checker()
    c.number("final_ufcf", final_ufcf)
    c.number("wacc", wacc)
    c.in_range("terminal_growth", growth, -1.0, 1.0, low_inclusive=False, high_inclusive=False)
    c.raise_if_errors()

    if growth >= wacc:
        c.error(
            Code.TERMINAL_GROWTH_GE_WACC,
            f"Terminal growth ({growth:.2%}) must be below WACC ({wacc:.2%}); otherwise the "
            "perpetuity has no finite value.",
            "terminal_growth",
        )
    if final_ufcf <= 0:
        c.error(
            Code.TERMINAL_FCF_NON_POSITIVE,
            f"Final-year UFCF is {final_ufcf:,.2f}. A growing perpetuity of a non-positive cash "
            "flow implies a non-positive business value; extend the forecast until the business "
            "reaches steady state, or use an exit multiple.",
            "final_ufcf",
        )
    c.raise_if_errors()

    issues: list[Issue] = []
    if wacc - growth < MIN_SPREAD:
        issues.append(
            warning(
                Code.TV_SPREAD_NARROW,
                f"WACC − g is only {wacc - growth:.2%}; the terminal value is extremely sensitive "
                "to small changes in either input.",
            )
        )
    if growth > TERMINAL_GROWTH_CEILING:
        issues.append(
            warning(
                Code.TERMINAL_GROWTH_HIGH,
                f"Terminal growth {growth:.2%} exceeds a long-run nominal GDP proxy of "
                f"{TERMINAL_GROWTH_CEILING:.0%}.",
            )
        )
    if risk_free_rate is not None and growth > risk_free_rate:
        issues.append(
            warning(
                Code.TERMINAL_GROWTH_ABOVE_RF,
                f"Terminal growth {growth:.2%} exceeds the risk-free rate {risk_free_rate:.2%}.",
            )
        )
    if growth < 0:
        issues.append(
            warning(
                Code.TERMINAL_GROWTH_NEGATIVE,
                f"Terminal growth is negative ({growth:.2%}): the business is assumed to decline "
                "forever.",
            )
        )
    tv = final_ufcf * (1.0 + growth) / (wacc - growth)
    return TerminalValue(final_ufcf, growth, wacc, tv, tuple(issues))


def discount_cash_flows(
    cash_flows: Sequence[float], wacc: float, terminal_value: float
) -> EnterpriseValue:
    """Present value of explicit flows (years 1..N) plus the terminal value at year N."""
    c = Checker()
    for i, cf in enumerate(cash_flows, start=1):
        c.number(f"cash_flows[{i}]", cf)
    c.number("terminal_value", terminal_value)
    if not cash_flows:
        c.error(Code.HORIZON_NOT_SUPPORTED, "At least one forecast cash flow is required.")
    c.raise_if_errors()

    flows = tuple(
        DiscountedFlow(t, cf, discount_factor(wacc, t), cf * discount_factor(wacc, t))
        for t, cf in enumerate(cash_flows, start=1)
    )
    n = len(cash_flows)
    sum_pv = sum(f.present_value for f in flows)
    pv_tv = terminal_value * discount_factor(wacc, n)
    ev = sum_pv + pv_tv

    issues: list[Issue] = []
    if ev <= 0:
        share = nm("enterprise value is not positive")
        issues.append(
            warning(
                Code.ENTERPRISE_VALUE_NON_POSITIVE,
                f"Enterprise value is {ev:,.2f}; review the forecast.",
            )
        )
    else:
        share = ok(pv_tv / ev)
        if pv_tv / ev > TV_SHARE_WARNING:
            issues.append(
                warning(
                    Code.TV_SHARE_HIGH,
                    f"Terminal value is {pv_tv / ev:.1%} of enterprise value (> "
                    f"{TV_SHARE_WARNING:.0%}); the valuation rests mostly on the perpetuity.",
                )
            )
    return EnterpriseValue(flows, sum_pv, terminal_value, pv_tv, ev, share, tuple(issues))


def implied_exit_multiple(terminal_value: float, final_ebitda: float) -> Metric:
    """TV / EBITDA_N — cross-check against trading multiples."""
    if final_ebitda <= 0:
        return nm("final-year EBITDA is not positive")
    return ok(terminal_value / final_ebitda)


def implied_perpetual_growth(terminal_value: float, final_ufcf: float, wacc: float) -> Metric:
    """Solve TV = UFCF_N (1+g)/(WACC−g) for g:  g = (TV×WACC − UFCF_N) / (TV + UFCF_N)."""
    if terminal_value + final_ufcf == 0:
        return nm("TV + UFCF is zero")
    return ok((terminal_value * wacc - final_ufcf) / (terminal_value + final_ufcf))
