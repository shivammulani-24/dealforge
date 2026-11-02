"""Weighted average cost of capital (spec section H.5, decision D-08).

::

    Ke   = Rf + β_L × ERP + size premium                    (CAPM)
    Kd_at = Kd_pre-tax × (1 − T)                             (interest is tax-deductible)
    WACC = E/V × Ke + D/V × Kd_at + P/V × Kp                 V = E + D + P

Why WACC discounts FCFF: FCFF is the cash available to debt *and* equity holders together,
so it must be discounted at the blended return those providers require, weighted by how much
of the firm each finances. The debt tax shield is captured once — in the after-tax Kd — which
is why UFCF itself is computed before interest.

Weights use market values (D-08): E = share price × diluted shares on the market-data date;
D is market value of debt where available, otherwise book value (flagged ``DEBT_AT_BOOK``).
An optional target debt-to-capital ratio replaces the observed weights.

Hamada (for unlevering / relevering peer betas)::

    β_U = β_L / (1 + (1 − T) × D/E)          β_L = β_U × (1 + (1 − T) × D/E)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .errors import Code, Issue, info
from .validation import Checker

WACC_MAX = 1.0  # ≥ 100% is rejected outright
WACC_EXTREME = 0.25  # above this a warning is raised


class DebtValueBasis(StrEnum):
    MARKET = "market"
    BOOK = "book"


@dataclass(frozen=True, slots=True)
class WaccAssumptions:
    risk_free_rate: float
    levered_beta: float
    equity_risk_premium: float
    pre_tax_cost_of_debt: float
    size_premium: float
    debt_value_basis: DebtValueBasis
    cost_of_preferred: float | None = None  # required only if preferred value > 0
    target_debt_to_capital: float | None = None  # None → use observed market weights


@dataclass(frozen=True, slots=True)
class CapitalStructure:
    equity_value: float  # market capitalisation, diluted, at the market-data date
    debt_value: float
    preferred_value: float


@dataclass(frozen=True, slots=True)
class WaccResult:
    cost_of_equity: float
    after_tax_cost_of_debt: float
    cost_of_preferred: float | None
    weight_equity: float
    weight_debt: float
    weight_preferred: float
    wacc: float
    issues: tuple[Issue, ...]


def cost_of_equity(
    risk_free_rate: float, levered_beta: float, equity_risk_premium: float, size_premium: float
) -> float:
    return risk_free_rate + levered_beta * equity_risk_premium + size_premium


def unlever_beta(levered_beta: float, debt_to_equity: float, tax_rate: float) -> float:
    c = Checker()
    c.number("levered_beta", levered_beta)
    c.non_negative("debt_to_equity", debt_to_equity)
    c.in_range("tax_rate", tax_rate, 0.0, 0.60)
    c.raise_if_errors()
    return levered_beta / (1.0 + (1.0 - tax_rate) * debt_to_equity)


def relever_beta(unlevered_beta: float, debt_to_equity: float, tax_rate: float) -> float:
    c = Checker()
    c.number("unlevered_beta", unlevered_beta)
    c.non_negative("debt_to_equity", debt_to_equity)
    c.in_range("tax_rate", tax_rate, 0.0, 0.60)
    c.raise_if_errors()
    return unlevered_beta * (1.0 + (1.0 - tax_rate) * debt_to_equity)


def validate_discount_rate(c: Checker, wacc: object, field: str = "wacc") -> float | None:
    v = c.number(field, wacc)
    if v is None:
        return None
    if v <= 0 or v >= WACC_MAX:
        c.error(
            Code.INVALID_WACC,
            f"WACC must be greater than 0% and below {WACC_MAX:.0%}; got {v:.2%}.",
            field,
        )
        return None
    if v > WACC_EXTREME:
        c.warn(Code.EXTREME_WACC, f"WACC of {v:.2%} is above {WACC_EXTREME:.0%}.", field)
    return v


def compute_wacc(a: WaccAssumptions, cap: CapitalStructure, tax_rate: float) -> WaccResult:
    c = Checker()
    c.in_range("risk_free_rate", a.risk_free_rate, -0.05, 0.30)
    c.number("levered_beta", a.levered_beta)
    c.in_range("equity_risk_premium", a.equity_risk_premium, 0.0, 0.30)
    c.in_range("pre_tax_cost_of_debt", a.pre_tax_cost_of_debt, 0.0, 0.50)
    c.in_range("size_premium", a.size_premium, 0.0, 0.20)
    c.in_range("tax_rate", tax_rate, 0.0, 0.60)
    c.positive("equity_value", cap.equity_value)
    c.non_negative("debt_value", cap.debt_value)
    c.non_negative("preferred_value", cap.preferred_value)
    if not isinstance(a.debt_value_basis, DebtValueBasis):
        c.error(
            Code.INVALID_TYPE, "debt_value_basis must be 'market' or 'book'.", "debt_value_basis"
        )
    if cap.preferred_value and cap.preferred_value > 0:
        c.in_range("cost_of_preferred", a.cost_of_preferred, 0.0, 0.50)
    if a.target_debt_to_capital is not None:
        c.in_range(
            "target_debt_to_capital", a.target_debt_to_capital, 0.0, 1.0, high_inclusive=False
        )
    c.raise_if_errors()

    ke = cost_of_equity(a.risk_free_rate, a.levered_beta, a.equity_risk_premium, a.size_premium)
    kd_at = a.pre_tax_cost_of_debt * (1.0 - tax_rate)
    kp = a.cost_of_preferred if cap.preferred_value > 0 else None

    v_total = cap.equity_value + cap.debt_value + cap.preferred_value
    wp = cap.preferred_value / v_total
    if a.target_debt_to_capital is not None:
        wd = a.target_debt_to_capital
        if wd + wp >= 1.0:
            c.error(
                Code.OUT_OF_RANGE,
                f"Target debt weight {wd:.1%} plus preferred weight {wp:.1%} leaves no equity.",
                "target_debt_to_capital",
            )
            c.raise_if_errors()
        we = 1.0 - wd - wp
        c.info(
            Code.TARGET_STRUCTURE_USED,
            f"Target capital structure used: D/V {wd:.1%} instead of observed "
            f"{cap.debt_value / v_total:.1%}.",
        )
    else:
        wd = cap.debt_value / v_total
        we = cap.equity_value / v_total

    wacc = we * ke + wd * kd_at + (wp * kp if kp is not None else 0.0)
    validate_discount_rate(c, wacc)
    c.raise_if_errors()

    if a.debt_value_basis is DebtValueBasis.BOOK and cap.debt_value > 0:
        c.info(
            Code.DEBT_AT_BOOK, "Debt weight uses book value as an approximation of market value."
        )
    if not 0.3 <= a.levered_beta <= 3.0:
        c.warn(Code.UNUSUAL_BETA, f"Levered beta {a.levered_beta:.2f} is outside 0.3–3.0.")
    if not 0.03 <= a.equity_risk_premium <= 0.10:
        c.warn(Code.UNUSUAL_ERP, f"ERP {a.equity_risk_premium:.2%} is outside 3%–10%.")
    if not 0.0 <= a.risk_free_rate <= 0.15:
        c.warn(Code.UNUSUAL_RISK_FREE, f"Risk-free rate {a.risk_free_rate:.2%} is outside 0%–15%.")
    if a.size_premium > 0:
        c.info(
            Code.SIZE_PREMIUM_APPLIED,
            f"A size/specific premium of {a.size_premium:.2%} is included in Ke; justify it.",
        )
    if wd > 0 and ke < kd_at:
        c.warn(
            Code.COST_OF_EQUITY_BELOW_DEBT,
            f"Cost of equity {ke:.2%} is below after-tax cost of debt {kd_at:.2%}; equity is "
            "riskier than debt, so this is almost certainly an input error.",
        )
    return WaccResult(ke, kd_at, kp, we, wd, wp, wacc, c.warnings())


def wacc_override_issue(wacc: float) -> Issue:
    return info(Code.WACC_OVERRIDDEN, f"WACC set directly to {wacc:.2%} (CAPM build-up bypassed).")
