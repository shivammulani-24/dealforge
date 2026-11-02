"""Acquisition simulation and accretion/dilution (spec section H.11, decision D-13).

Purchase price
--------------
::

    Offer price per share   = target price × (1 + premium)
    Equity purchase price   = offer price × target diluted shares at the OFFER price
                              (options via TSM; convertibles convert if conversion price < offer)
    Enterprise value paid   = equity purchase price + debt claims − cash − non-op assets

Sources & uses (must balance)
-----------------------------
::

    USES:    equity purchase price + target debt refinanced + advisory fees + financing fees
    SOURCES: acquirer cash used + new debt + new acquirer shares (stock consideration)

Pro forma net income
--------------------
Run-rate (recurring) — the primary basis (D-13)::

    NI_acquirer + NI_target (standalone, no synergies)
    + run-rate synergies × (1 − T)          cost synergies + revenue synergies × contribution margin
    − new debt × rate × (1 − T)
    − cash used × forgone yield × (1 − T)
    − financing fees / amortisation years × (1 − T)
    + interest on target debt that is refinanced × (1 − T)   (it is inside NI_target)
    + coupon on convertibles that convert or are refinanced × (1 − T)

Year 1 incl. one-time items — secondary line: synergies × year-1 phase-in, minus integration
costs × (1 − T), minus advisory fees (treated as non-deductible, a conservative simplification).

Why no double counting: synergies appear only here (never in target standalone NI or in the
standalone DCF); advisory fees are a one-time use of funds, not a recurring cost; financing
fees are a use of funds *and* amortised — that amortisation is their recurring P&L effect;
the premium is not an expense — it affects EPS only through financing cost and new shares.

Why a value-creating deal can still be EPS-dilutive: in an all-stock deal, EPS rises only if
the acquirer buys earnings more cheaply than its own shares are priced — i.e. the target's
P/E at the offer is below the acquirer's P/E. Paying 13x for earnings with 10x stock dilutes
EPS even if synergies, growth or strategic fit create value over time; EPS is a one-year
accounting measure, value is the present value of all future cash flows.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from .bridge import BridgeInputs, enterprise_from_equity
from .errors import Code, EngineError, Issue, error, info, warning
from .metrics import Metric, nm, ok, safe_ratio
from .sensitivity import Grid, two_way_grid
from .shares import DilutionResult, ShareCapitalInputs, diluted_shares_at_price
from .validation import Checker

SU_TOLERANCE = 1e-6
PREMIUM_BAND = (0.10, 0.60)
LEVERAGE_WARNING = 4.0


@dataclass(frozen=True, slots=True)
class AcquirerInputs:
    share_price: float
    diluted_shares: float
    net_income: float  # standalone forecast for the pro forma year
    ebitda: float
    total_debt: float
    cash_available: float


@dataclass(frozen=True, slots=True)
class TargetInputs:
    share_price: float
    share_capital: ShareCapitalInputs
    net_income: float  # standalone forecast for the pro forma year, excluding synergies
    ebitda: float
    bridge: BridgeInputs
    interest_expense: float | None  # pre-tax, on non-convertible debt; needed if refinanced
    refinance_debt: bool


@dataclass(frozen=True, slots=True)
class DealInputs:
    offer_premium: float
    stock_pct: float  # share of the equity purchase price paid in acquirer stock
    cash_used: float  # from the acquirer's balance sheet
    new_debt: float
    new_debt_rate: float
    interest_rate_on_cash: float  # pre-tax yield forgone on cash used
    tax_rate: float
    stock_issue_discount: float
    advisory_fees: float
    financing_fees: float
    financing_fee_amortization_years: float | None  # required if financing_fees > 0
    run_rate_cost_synergies: float  # pre-tax
    revenue_synergies: float
    revenue_synergy_margin: float  # contribution margin applied to revenue synergies
    synergy_phase_in_year1: float  # 0..1
    integration_costs_year1: float  # one-time, pre-tax


@dataclass(frozen=True, slots=True)
class SourcesAndUses:
    uses: tuple[tuple[str, float], ...]
    sources: tuple[tuple[str, float], ...]
    total_uses: float
    total_sources: float


@dataclass(frozen=True, slots=True)
class ProFormaLine:
    label: str
    amount: float


@dataclass(frozen=True, slots=True)
class DealResult:
    offer_price: float
    target_dilution: DilutionResult
    equity_purchase_price: float
    enterprise_value_paid: float
    ev_to_ebitda_paid: Metric
    pe_paid: Metric
    stock_consideration: float
    cash_consideration: float
    new_shares_issued: float
    sources_and_uses: SourcesAndUses
    run_rate_synergies_pre_tax: float
    recurring_bridge: tuple[ProFormaLine, ...]
    recurring_net_income: float
    year1_net_income: float
    acquirer_eps: float
    pro_forma_shares: float
    recurring_eps: float
    year1_eps: float
    recurring_accretion: Metric
    year1_accretion: Metric
    recurring_eps_change: float
    breakeven_synergies_pre_tax: float
    acquirer_ownership: float
    pro_forma_leverage: Metric
    issues: tuple[Issue, ...]


def _validate(a: AcquirerInputs, t: TargetInputs, d: DealInputs) -> Checker:
    c = Checker()
    c.positive("acquirer.share_price", a.share_price)
    c.positive("acquirer.diluted_shares", a.diluted_shares)
    c.number("acquirer.net_income", a.net_income)
    c.number("acquirer.ebitda", a.ebitda)
    c.non_negative("acquirer.total_debt", a.total_debt)
    c.non_negative("acquirer.cash_available", a.cash_available)
    c.positive("target.share_price", t.share_price)
    c.number("target.net_income", t.net_income)
    c.number("target.ebitda", t.ebitda)
    if t.refinance_debt:
        c.non_negative("target.interest_expense", t.interest_expense)
    c.in_range("offer_premium", d.offer_premium, -1.0, 5.0, low_inclusive=False)
    c.in_range("stock_pct", d.stock_pct, 0.0, 1.0)
    c.non_negative("cash_used", d.cash_used)
    c.non_negative("new_debt", d.new_debt)
    c.in_range("new_debt_rate", d.new_debt_rate, 0.0, 0.5)
    c.in_range("interest_rate_on_cash", d.interest_rate_on_cash, 0.0, 0.5)
    c.in_range("tax_rate", d.tax_rate, 0.0, 0.60)
    c.in_range("stock_issue_discount", d.stock_issue_discount, 0.0, 1.0, high_inclusive=False)
    c.non_negative("advisory_fees", d.advisory_fees)
    c.non_negative("financing_fees", d.financing_fees)
    if d.financing_fees and d.financing_fees > 0:
        c.positive("financing_fee_amortization_years", d.financing_fee_amortization_years)
    c.non_negative("run_rate_cost_synergies", d.run_rate_cost_synergies)
    c.non_negative("revenue_synergies", d.revenue_synergies)
    c.in_range("revenue_synergy_margin", d.revenue_synergy_margin, 0.0, 1.0)
    c.in_range("synergy_phase_in_year1", d.synergy_phase_in_year1, 0.0, 1.0)
    c.non_negative("integration_costs_year1", d.integration_costs_year1)
    return c


def analyze_deal(a: AcquirerInputs, t: TargetInputs, d: DealInputs) -> DealResult:
    c = _validate(a, t, d)
    c.raise_if_errors()
    tax = d.tax_rate
    after_tax = 1.0 - tax

    offer = t.share_price * (1.0 + d.offer_premium)
    dil = diluted_shares_at_price(t.share_capital, offer)
    equity_price = offer * dil.diluted_shares
    ev_paid = enterprise_from_equity(equity_price, t.bridge, dil.unconverted_face)

    stock_value = d.stock_pct * equity_price
    cash_consideration = equity_price - stock_value
    refinanced = (t.bridge.total_debt + dil.unconverted_face) if t.refinance_debt else 0.0

    uses = (
        ("Equity purchase price", equity_price),
        ("Refinance target debt", refinanced),
        ("Advisory fees", d.advisory_fees),
        ("Financing fees", d.financing_fees),
    )
    sources = (
        ("Acquirer cash", d.cash_used),
        ("New debt", d.new_debt),
        ("New acquirer shares", stock_value),
    )
    total_uses = sum(v for _, v in uses)
    total_sources = sum(v for _, v in sources)
    if abs(total_uses - total_sources) > SU_TOLERANCE * max(1.0, total_uses):
        c.error(
            Code.SU_IMBALANCE,
            f"Sources {total_sources:,.4f} ≠ uses {total_uses:,.4f} (gap "
            f"{total_uses - total_sources:,.4f}). Adjust cash used or new debt.",
        )
    if d.cash_used > a.cash_available:
        c.error(
            Code.INSUFFICIENT_CASH,
            f"Cash used {d.cash_used:,.2f} exceeds acquirer cash available {a.cash_available:,.2f}.",
        )
    # Convertible coupons are needed only where their interest disappears.
    conv_addback = 0.0
    for line, cv in zip(
        (ln for ln in dil.lines if ln.kind.value == "convertible"),
        t.share_capital.convertibles,
        strict=True,
    ):
        if line.included or t.refinance_debt:
            if cv.coupon_rate is None:
                c.number(f"target.convertibles[{cv.label}].coupon_rate", None)
            else:
                conv_addback += cv.face_value * cv.coupon_rate * after_tax
    c.raise_if_errors()

    issues: list[Issue] = list(c.warnings())
    if not PREMIUM_BAND[0] <= d.offer_premium <= PREMIUM_BAND[1]:
        issues.append(
            warning(
                Code.UNUSUAL_PREMIUM,
                f"Offer premium {d.offer_premium:.1%} is outside the typical "
                f"{PREMIUM_BAND[0]:.0%}–{PREMIUM_BAND[1]:.0%} range.",
            )
        )
    for ln in dil.lines:
        if ln.kind.value == "convertible" and ln.included:
            issues.append(info(Code.CONVERTIBLE_CONVERTED, f"Target {ln.label}: {ln.note}."))

    new_shares = stock_value / (a.share_price * (1.0 - d.stock_issue_discount))
    synergies = d.run_rate_cost_synergies + d.revenue_synergies * d.revenue_synergy_margin
    new_interest = d.new_debt * d.new_debt_rate * after_tax
    forgone = d.cash_used * d.interest_rate_on_cash * after_tax
    fee_amort = (
        d.financing_fees / d.financing_fee_amortization_years * after_tax
        if d.financing_fees > 0 and d.financing_fee_amortization_years
        else 0.0
    )
    refi_addback = 0.0
    if t.refinance_debt:  # interest_expense was validated as present above
        assert t.interest_expense is not None
        refi_addback = t.interest_expense * after_tax

    bridge_lines = (
        ProFormaLine("Acquirer standalone net income", a.net_income),
        ProFormaLine("Target standalone net income", t.net_income),
        ProFormaLine("Run-rate synergies, after tax", synergies * after_tax),
        ProFormaLine("Interest on new debt, after tax", -new_interest),
        ProFormaLine("Interest income forgone on cash, after tax", -forgone),
        ProFormaLine("Financing fee amortisation, after tax", -fee_amort),
        ProFormaLine("Refinanced target debt interest removed, after tax", refi_addback),
        ProFormaLine("Convertible coupons removed, after tax", conv_addback),
    )
    recurring_ni = sum(x.amount for x in bridge_lines)
    ni_ex_synergies = recurring_ni - synergies * after_tax
    year1_ni = (
        ni_ex_synergies
        + synergies * d.synergy_phase_in_year1 * after_tax
        - d.integration_costs_year1 * after_tax
        - d.advisory_fees
    )

    pf_shares = a.diluted_shares + new_shares
    eps_a = a.net_income / a.diluted_shares
    eps_rec = recurring_ni / pf_shares
    eps_y1 = year1_ni / pf_shares
    if eps_a <= 0:
        acc_rec: Metric = nm("acquirer standalone EPS is not positive")
        acc_y1: Metric = acc_rec
        issues.append(
            warning(
                Code.ACQUIRER_EPS_NON_POSITIVE,
                "Acquirer EPS is not positive; accretion % is not meaningful — see the absolute "
                "EPS change instead.",
            )
        )
    else:
        acc_rec = ok(eps_rec / eps_a - 1.0)
        acc_y1 = ok(eps_y1 / eps_a - 1.0)
    breakeven = (eps_a * pf_shares - ni_ex_synergies) / after_tax

    b = t.bridge
    target_debt_kept = (
        0.0
        if t.refinance_debt
        else b.total_debt
        + (b.lease_liabilities if b.include_leases_in_debt else 0.0)
        + dil.unconverted_face
    )
    pf_debt = a.total_debt + target_debt_kept + d.new_debt
    pf_ebitda = a.ebitda + t.ebitda + synergies
    leverage = safe_ratio(
        pf_debt, pf_ebitda, num_name="pro forma debt", den_name="pro forma EBITDA"
    )
    if leverage.is_ok and leverage.value is not None and leverage.value > LEVERAGE_WARNING:
        issues.append(
            warning(
                Code.HIGH_PRO_FORMA_LEVERAGE,
                f"Pro forma debt / EBITDA is {leverage.value:.1f}x (> {LEVERAGE_WARNING:.1f}x).",
            )
        )

    return DealResult(
        offer_price=offer,
        target_dilution=dil,
        equity_purchase_price=equity_price,
        enterprise_value_paid=ev_paid,
        ev_to_ebitda_paid=safe_ratio(
            ev_paid, t.ebitda, num_name="EV paid", den_name="target EBITDA"
        ),
        pe_paid=safe_ratio(
            equity_price, t.net_income, num_name="equity price", den_name="target NI"
        ),
        stock_consideration=stock_value,
        cash_consideration=cash_consideration,
        new_shares_issued=new_shares,
        sources_and_uses=SourcesAndUses(uses, sources, total_uses, total_sources),
        run_rate_synergies_pre_tax=synergies,
        recurring_bridge=bridge_lines,
        recurring_net_income=recurring_ni,
        year1_net_income=year1_ni,
        acquirer_eps=eps_a,
        pro_forma_shares=pf_shares,
        recurring_eps=eps_rec,
        year1_eps=eps_y1,
        recurring_accretion=acc_rec,
        year1_accretion=acc_y1,
        recurring_eps_change=eps_rec - eps_a,
        breakeven_synergies_pre_tax=breakeven,
        acquirer_ownership=a.diluted_shares / pf_shares,
        pro_forma_leverage=leverage,
        issues=tuple(issues),
    )


def new_debt_to_balance(a: AcquirerInputs, t: TargetInputs, d: DealInputs) -> float:
    """New debt that balances sources and uses for the given cash used (the "debt plug")."""
    c = Checker()
    c.positive("target.share_price", t.share_price)
    c.in_range("offer_premium", d.offer_premium, -1.0, 5.0, low_inclusive=False)
    c.in_range("stock_pct", d.stock_pct, 0.0, 1.0)
    c.raise_if_errors()
    offer = t.share_price * (1.0 + d.offer_premium)
    dil = diluted_shares_at_price(t.share_capital, offer)
    equity_price = offer * dil.diluted_shares
    refinanced = (t.bridge.total_debt + dil.unconverted_face) if t.refinance_debt else 0.0
    uses = equity_price + refinanced + d.advisory_fees + d.financing_fees
    plug = uses - d.cash_used - d.stock_pct * equity_price
    if plug < -SU_TOLERANCE:
        raise EngineError(
            [
                error(
                    Code.NEGATIVE_DEBT_PLUG,
                    f"Cash used exceeds the cash needed by {-plug:,.2f}; reduce cash used.",
                )
            ]
        )
    return max(plug, 0.0)


def accretion_sensitivity(
    a: AcquirerInputs,
    t: TargetInputs,
    d: DealInputs,
    premiums: Sequence[float],
    stock_pcts: Sequence[float],
) -> Grid:
    """Run-rate accretion/(dilution) for premium × % stock; new debt re-plugged in each cell."""

    def evaluate(prem: float, pct: float) -> float:
        cell = replace(d, offer_premium=prem, stock_pct=pct)
        cell = replace(cell, new_debt=new_debt_to_balance(a, t, cell))
        acc = analyze_deal(a, t, cell).recurring_accretion
        if not acc.is_ok or acc.value is None:
            raise EngineError([error(Code.ACQUIRER_EPS_NON_POSITIVE, "accretion not meaningful")])
        return acc.value

    return two_way_grid(
        evaluate,
        premiums,
        stock_pcts,
        row_base=d.offer_premium,
        col_base=d.stock_pct,
        row_name="offer_premium",
        col_name="stock_pct",
        output="recurring_accretion",
    )
