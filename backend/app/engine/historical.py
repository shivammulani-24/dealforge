"""Historical financial analysis (spec section H.2).

Input: a list of annual periods with possibly-missing line items. Output: per-period metrics
(each a :class:`Metric` that may be OK / MISSING / NM) plus consistency-check issues.

Sign convention (D-02): revenue, COGS, OpEx, D&A, CapEx, tax expense, interest expense, cash,
debt and working-capital balances are positive magnitudes; EBIT, pre-tax income, net income
and CFO are signed.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, fields

from .ebitda import (
    EbitdaAdjustment,
    EbitdaFigures,
    EbitdaReconciliation,
    reconcile_ebitda,
    standardized_ebitda,
)
from .errors import Code, Issue, info, warning
from .metrics import Metric, missing, nm, ok, safe_ratio
from .validation import Checker, approx_equal

MAGNITUDE_ITEMS = (
    "revenue",
    "cogs",
    "opex",
    "da",
    "tax_expense",
    "capex",
    "accounts_receivable",
    "inventory",
    "other_current_operating_assets",
    "accounts_payable",
    "other_current_operating_liabilities",
    "cash",
    "total_debt",
    "interest_expense",
    "total_assets",
    "total_liabilities",
)
SIGNED_ITEMS = ("ebit", "pretax_income", "net_income", "cfo", "total_equity")

#: Effective tax rates outside this band are flagged (not rejected).
TAX_RATE_BAND = (0.0, 0.50)


@dataclass(frozen=True, slots=True)
class HistoricalPeriod:
    """One fiscal year. ``None`` = not provided (missing), never zero."""

    fiscal_year: int
    revenue: float | None = None
    cogs: float | None = None
    opex: float | None = None  # operating expenses as reported, including D&A where embedded
    ebit: float | None = None
    da: float | None = None  # from the cash-flow statement
    pretax_income: float | None = None
    tax_expense: float | None = None
    net_income: float | None = None
    cfo: float | None = None
    capex: float | None = None
    accounts_receivable: float | None = None
    inventory: float | None = None
    other_current_operating_assets: float | None = None
    accounts_payable: float | None = None
    other_current_operating_liabilities: float | None = None
    cash: float | None = None
    total_debt: float | None = None
    interest_expense: float | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None
    total_equity: float | None = None
    reported_ebitda: float | None = None
    adjusted_ebitda: float | None = None
    ebitda_adjustments: tuple[EbitdaAdjustment, ...] = ()


@dataclass(frozen=True, slots=True)
class PeriodAnalysis:
    fiscal_year: int
    metrics: dict[str, Metric]
    ebitda: EbitdaReconciliation


@dataclass(frozen=True, slots=True)
class HistoricalAnalysis:
    periods: tuple[PeriodAnalysis, ...]
    issues: tuple[Issue, ...]

    def metric(self, fiscal_year: int, name: str) -> Metric:
        for p in self.periods:
            if p.fiscal_year == fiscal_year:
                return p.metrics[name]
        raise KeyError(fiscal_year)


def operating_nwc(p: HistoricalPeriod) -> tuple[Metric, bool]:
    """Operating NWC = AR + inventory + other op. current assets − AP − other op. current liabs.

    Cash and debt are excluded: they are financing items handled in the EV→equity bridge.
    AR, inventory and AP are required; the two "other" lines are optional. Returns
    ``(metric, partial)`` where ``partial`` is True if an optional line was not provided — that
    is disclosed as an issue rather than silently assumed to be zero.
    """
    req = {
        "accounts_receivable": p.accounts_receivable,
        "inventory": p.inventory,
        "accounts_payable": p.accounts_payable,
    }
    absent = [k for k, v in req.items() if v is None]
    if absent:
        return missing(*absent), False
    assert p.accounts_receivable is not None and p.inventory is not None
    assert p.accounts_payable is not None
    value = p.accounts_receivable + p.inventory - p.accounts_payable
    partial = False
    if p.other_current_operating_assets is not None:
        value += p.other_current_operating_assets
    else:
        partial = True
    if p.other_current_operating_liabilities is not None:
        value -= p.other_current_operating_liabilities
    else:
        partial = True
    return ok(value), partial


def _diff(a: Metric, b: Metric, name_a: str, name_b: str) -> Metric:
    if not a.is_ok or not b.is_ok:
        return missing(*(n for n, m in ((name_a, a), (name_b, b)) if not m.is_ok))
    assert a.value is not None and b.value is not None
    return ok(a.value - b.value)


def _validate_period(c: Checker, p: HistoricalPeriod) -> None:
    for name in MAGNITUDE_ITEMS:
        v = getattr(p, name)
        if v is not None:
            c.non_negative(f"FY{p.fiscal_year}.{name}", v)
    for name in SIGNED_ITEMS:
        v = getattr(p, name)
        if v is not None:
            c.number(f"FY{p.fiscal_year}.{name}", v)


def analyze_historicals(
    periods: list[HistoricalPeriod] | tuple[HistoricalPeriod, ...],
) -> HistoricalAnalysis:
    c = Checker()
    if not periods:
        c.error(Code.NO_PERIODS, "At least one historical period is required.")
        c.raise_if_errors()
    ordered = sorted(periods, key=lambda p: p.fiscal_year)
    years = [p.fiscal_year for p in ordered]
    if len(set(years)) != len(years):
        c.error(Code.DUPLICATE_PERIOD, f"Duplicate fiscal years in {years}.")
    for p in ordered:
        _validate_period(c, p)
    c.raise_if_errors()

    issues: list[Issue] = []
    for prev, cur in itertools.pairwise(ordered):
        if cur.fiscal_year != prev.fiscal_year + 1:
            issues.append(
                warning(
                    Code.PERIODS_NOT_CONTIGUOUS,
                    f"Gap between FY{prev.fiscal_year} and FY{cur.fiscal_year}; growth and ΔNWC "
                    "across the gap are not computed.",
                )
            )

    analyses: list[PeriodAnalysis] = []
    prev_p: HistoricalPeriod | None = None
    prev_m: dict[str, Metric] | None = None
    for p in ordered:
        fy = f"FY{p.fiscal_year}"
        m: dict[str, Metric] = {}
        contiguous = prev_p is not None and p.fiscal_year == prev_p.fiscal_year + 1

        # Growth
        if not contiguous or prev_p is None:
            m["revenue_growth"] = nm("no immediately preceding fiscal year")
        else:
            g = safe_ratio(p.revenue, prev_p.revenue, num_name="revenue", den_name="prior revenue")
            m["revenue_growth"] = ok(g.value - 1.0) if g.is_ok and g.value is not None else g

        # Profitability
        gp = (
            ok(p.revenue - p.cogs)
            if p.revenue is not None and p.cogs is not None
            else missing(*(n for n, v in (("revenue", p.revenue), ("cogs", p.cogs)) if v is None))
        )
        m["gross_profit"] = gp
        m["gross_margin"] = (
            gp
            if not gp.is_ok
            else safe_ratio(gp.value, p.revenue, num_name="gross_profit", den_name="revenue")
        )
        ebitda_fig = EbitdaFigures(
            ebit=p.ebit,
            da=p.da,
            reported=p.reported_ebitda,
            adjusted=p.adjusted_ebitda,
            adjustments=p.ebitda_adjustments,
        )
        rec = reconcile_ebitda(ebitda_fig)
        ebitda = standardized_ebitda(p.ebit, p.da)
        m["ebitda"] = ebitda
        m["ebitda_margin"] = (
            ebitda
            if not ebitda.is_ok
            else safe_ratio(ebitda.value, p.revenue, num_name="ebitda", den_name="revenue")
        )
        m["ebit_margin"] = safe_ratio(p.ebit, p.revenue, num_name="ebit", den_name="revenue")
        m["net_margin"] = safe_ratio(
            p.net_income, p.revenue, num_name="net_income", den_name="revenue"
        )
        etr = safe_ratio(
            p.tax_expense, p.pretax_income, num_name="tax_expense", den_name="pretax_income"
        )
        m["effective_tax_rate"] = etr
        if (
            etr.is_ok
            and etr.value is not None
            and not (TAX_RATE_BAND[0] <= etr.value <= TAX_RATE_BAND[1])
        ):
            issues.append(
                warning(
                    Code.UNUSUAL_TAX_RATE,
                    f"{fy}: effective tax rate {etr.value:.1%} is outside "
                    f"{TAX_RATE_BAND[0]:.0%}–{TAX_RATE_BAND[1]:.0%}; use a normalised forecast "
                    "rate (D-05).",
                )
            )

        # Cash flow
        fcf = (
            ok(p.cfo - p.capex)
            if p.cfo is not None and p.capex is not None
            else missing(*(n for n, v in (("cfo", p.cfo), ("capex", p.capex)) if v is None))
        )
        m["simple_fcf"] = fcf
        m["fcf_conversion"] = (
            fcf
            if not fcf.is_ok
            else safe_ratio(fcf.value, p.net_income, num_name="simple_fcf", den_name="net_income")
        )
        m["capex_pct_revenue"] = safe_ratio(
            p.capex, p.revenue, num_name="capex", den_name="revenue"
        )
        m["da_pct_revenue"] = safe_ratio(p.da, p.revenue, num_name="da", den_name="revenue")
        m["capex_to_da"] = safe_ratio(p.capex, p.da, num_name="capex", den_name="da")

        # Working capital
        nwc, partial = operating_nwc(p)
        m["nwc"] = nwc
        if partial and nwc.is_ok:
            issues.append(
                info(
                    Code.NWC_PARTIAL,
                    f"{fy}: other operating current assets/liabilities not provided; NWC uses "
                    "AR + inventory − AP only.",
                )
            )
        m["nwc_pct_revenue"] = (
            nwc
            if not nwc.is_ok
            else safe_ratio(nwc.value, p.revenue, num_name="nwc", den_name="revenue")
        )
        if contiguous and prev_m is not None:
            m["change_in_nwc"] = _diff(nwc, prev_m["nwc"], "nwc", "prior nwc")
        else:
            m["change_in_nwc"] = nm("no immediately preceding fiscal year")

        # Leverage
        net_debt = (
            ok(p.total_debt - p.cash)
            if p.total_debt is not None and p.cash is not None
            else missing(
                *(n for n, v in (("total_debt", p.total_debt), ("cash", p.cash)) if v is None)
            )
        )
        m["net_debt"] = net_debt
        m["net_debt_to_ebitda"] = (
            net_debt
            if not net_debt.is_ok
            else ebitda
            if not ebitda.is_ok
            else safe_ratio(net_debt.value, ebitda.value, num_name="net_debt", den_name="ebitda")
        )
        m["interest_coverage"] = safe_ratio(
            p.ebit, p.interest_expense, num_name="ebit", den_name="interest_expense"
        )

        # Consistency checks (warnings only, D-12)
        # LIM-13: D&A is part of operating costs, so it cannot exceed COGS + OpEx (both are
        # reported inclusive of embedded D&A). Missing inputs → the check is skipped and that
        # is disclosed; it is never run against a zero.
        da_inputs = {"da": p.da, "cogs": p.cogs, "opex": p.opex}
        absent_da = [k for k, val in da_inputs.items() if val is None]
        if absent_da:
            issues.append(
                info(
                    Code.DA_CHECK_SKIPPED,
                    f"{fy}: D&A vs COGS + OpEx check not performed; missing "
                    f"{', '.join(absent_da)}.",
                )
            )
        else:
            assert p.da is not None and p.cogs is not None and p.opex is not None
            if p.da > p.cogs + p.opex:
                issues.append(
                    warning(
                        Code.DA_EXCEEDS_OPERATING_COSTS,
                        f"{fy}: D&A {p.da:,.2f} exceeds COGS + OpEx {p.cogs + p.opex:,.2f}; "
                        "D&A is a component of those costs, so a line item is probably "
                        "misclassified or mis-scaled.",
                    )
                )
        if None not in (p.revenue, p.cogs, p.opex, p.ebit):
            assert p.revenue is not None and p.cogs is not None
            assert p.opex is not None and p.ebit is not None
            implied = p.revenue - p.cogs - p.opex
            if not approx_equal(implied, p.ebit):
                issues.append(
                    warning(
                        Code.EBIT_RECONCILIATION,
                        f"{fy}: revenue − COGS − OpEx = {implied:,.2f} but reported EBIT is "
                        f"{p.ebit:,.2f} (difference {implied - p.ebit:,.2f}).",
                    )
                )
        if None not in (p.pretax_income, p.tax_expense, p.net_income):
            assert p.pretax_income is not None and p.tax_expense is not None
            assert p.net_income is not None
            implied = p.pretax_income - p.tax_expense
            if not approx_equal(implied, p.net_income):
                issues.append(
                    warning(
                        Code.NET_INCOME_RECONCILIATION,
                        f"{fy}: pre-tax income − tax = {implied:,.2f} but net income is "
                        f"{p.net_income:,.2f} (other items such as discontinued operations?).",
                    )
                )
        if None not in (p.total_assets, p.total_liabilities, p.total_equity):
            assert p.total_assets is not None and p.total_liabilities is not None
            assert p.total_equity is not None
            if not approx_equal(p.total_liabilities + p.total_equity, p.total_assets):
                issues.append(
                    warning(
                        Code.BALANCE_SHEET_IMBALANCE,
                        f"{fy}: assets {p.total_assets:,.2f} ≠ liabilities + equity "
                        f"{p.total_liabilities + p.total_equity:,.2f}.",
                    )
                )
        # Earnings up while cash flow down (interview question 6)
        if (
            contiguous
            and prev_m is not None
            and prev_p is not None
            and (
                p.net_income is not None
                and prev_p.net_income is not None
                and fcf.is_ok
                and prev_m["simple_fcf"].is_ok
            )
        ):
            assert fcf.value is not None and prev_m["simple_fcf"].value is not None
            if p.net_income > prev_p.net_income and fcf.value < prev_m["simple_fcf"].value:
                cause = ""
                dn = m["change_in_nwc"]
                if dn.is_ok and dn.value is not None and dn.value > 0:
                    cause = f" Working capital absorbed {dn.value:,.2f} of cash this year."
                issues.append(
                    warning(
                        Code.EARNINGS_CASH_DIVERGENCE,
                        f"{fy}: net income rose ({prev_p.net_income:,.2f} → "
                        f"{p.net_income:,.2f}) while free cash flow fell "
                        f"({prev_m['simple_fcf'].value:,.2f} → {fcf.value:,.2f})." + cause,
                    )
                )

        issues.extend(rec.issues)
        analyses.append(PeriodAnalysis(p.fiscal_year, m, rec))
        prev_p, prev_m = p, m

    return HistoricalAnalysis(tuple(analyses), tuple(issues))


def historical_field_names() -> tuple[str, ...]:
    return tuple(f.name for f in fields(HistoricalPeriod))
