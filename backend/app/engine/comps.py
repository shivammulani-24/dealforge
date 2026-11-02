"""Comparable-company analysis (spec section H.9, decisions D-03 and D-11).

Per peer, in the peer's own currency::

    Market cap = share price × diluted shares (TSM / if-converted at that observed price)
    EV         = market cap + debt + (leases if in debt) + unconverted convertibles
                 + preferred + NCI + other debt-like claims − cash − non-operating assets
                 (the exact inverse of the DCF bridge, so EV is defined identically)
    EV/Revenue = EV / revenue        EV/EBITDA = EV / EBITDA(basis)        P/E = market cap / NI

Rules
-----
* Multiples are currency-neutral (numerator and denominator in the same currency), so peers
  reporting in different currencies can be compared; but each peer's share price must be
  quoted in its reporting currency, otherwise market cap mixes currencies.
* Every peer must use the analysis period type (LTM / NTM / FY) — mixing is an error.
  Fiscal period ends more than ~3 months from the target's are flagged.
* EBITDA is taken on one basis for every peer *and* the target (standardised by default).
  A peer without that basis gets a MISSING multiple; it is never swapped for another basis.
* Zero/negative denominators → NM, automatically left out of the statistics (with reason).
  Outliers are only flagged; excluding a peer is an analyst decision with a mandatory reason.
* Percentiles: linear interpolation between order statistics (Excel ``PERCENTILE.INC``,
  NumPy default).
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum

from .bridge import BridgeInputs, enterprise_from_equity, equity_from_enterprise
from .ebitda import EbitdaBasis, EbitdaFigures, select_ebitda
from .errors import Code, EngineError, Issue, error, info, warning
from .metrics import Metric, nm, safe_ratio
from .shares import ShareCapitalInputs, diluted_shares_at_price, implied_value_per_share
from .validation import Checker

PERIOD_ALIGNMENT_DAYS = 92
OUTLIER_THRESHOLDS = {"ev_revenue": 30.0, "ev_ebitda": 50.0, "pe": 100.0}
MIN_PEERS = 3


class PeriodType(StrEnum):
    LTM = "ltm"
    NTM = "ntm"
    FY = "fy"


class MultipleKind(StrEnum):
    EV_REVENUE = "ev_revenue"
    EV_EBITDA = "ev_ebitda"
    PE = "pe"


@dataclass(frozen=True, slots=True)
class PeerInputs:
    name: str
    share_price: float
    price_currency: str
    reporting_currency: str
    share_capital: ShareCapitalInputs
    bridge: BridgeInputs
    revenue: float | None
    ebitda: EbitdaFigures
    net_income: float | None  # attributable to common shareholders
    period_type: PeriodType
    period_end: date
    included: bool = True
    exclusion_reason: str | None = None


@dataclass(frozen=True, slots=True)
class PeerResult:
    name: str
    market_cap: float
    diluted_shares: float
    enterprise_value: float
    ebitda_used: Metric
    multiples: dict[MultipleKind, Metric]
    included: bool
    exclusion_reason: str | None
    issues: tuple[Issue, ...]


@dataclass(frozen=True, slots=True)
class MultipleStats:
    kind: MultipleKind
    values: tuple[float, ...]  # included, meaningful values, sorted ascending
    contributors: tuple[str, ...]
    left_out: tuple[tuple[str, str], ...]  # (peer, reason)
    n: int
    minimum: float | None
    p25: float | None
    median: float | None
    mean: float | None
    p75: float | None
    maximum: float | None


@dataclass(frozen=True, slots=True)
class CompsAnalysis:
    period_type: PeriodType
    ebitda_basis: EbitdaBasis
    peers: tuple[PeerResult, ...]
    stats: dict[MultipleKind, MultipleStats]
    issues: tuple[Issue, ...]


def percentile_inc(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile, identical to Excel PERCENTILE.INC / numpy default."""
    if not sorted_values:
        raise ValueError("percentile of empty sequence")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be in [0, 1]")
    h = (len(sorted_values) - 1) * q
    lo = math.floor(h)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (h - lo) * (sorted_values[hi] - sorted_values[lo])


def compute_peer(peer: PeerInputs, ebitda_basis: EbitdaBasis) -> PeerResult:
    c = Checker()
    c.positive(f"{peer.name}.share_price", peer.share_price)
    if peer.revenue is not None:
        c.non_negative(f"{peer.name}.revenue", peer.revenue)
    if peer.net_income is not None:
        c.number(f"{peer.name}.net_income", peer.net_income)
    if peer.price_currency != peer.reporting_currency:
        c.error(
            Code.CURRENCY_MISMATCH,
            f"{peer.name}: share price in {peer.price_currency} but financials in "
            f"{peer.reporting_currency}; convert one of them at a dated FX rate first.",
        )
    if not peer.included and not (peer.exclusion_reason and peer.exclusion_reason.strip()):
        c.error(
            Code.EXCLUSION_REASON_REQUIRED,
            f"{peer.name} is excluded without a reason (D-11).",
        )
    c.raise_if_errors()

    dil = diluted_shares_at_price(peer.share_capital, peer.share_price)
    market_cap = peer.share_price * dil.diluted_shares
    ev = enterprise_from_equity(market_cap, peer.bridge, dil.unconverted_face)
    ebitda = select_ebitda(peer.ebitda, ebitda_basis)

    multiples: dict[MultipleKind, Metric] = {}
    if ev <= 0:
        for k in (MultipleKind.EV_REVENUE, MultipleKind.EV_EBITDA):
            multiples[k] = nm("enterprise value is not positive")
    else:
        multiples[MultipleKind.EV_REVENUE] = safe_ratio(
            ev, peer.revenue, num_name="enterprise_value", den_name="revenue"
        )
        multiples[MultipleKind.EV_EBITDA] = (
            ebitda
            if not ebitda.is_ok
            else safe_ratio(ev, ebitda.value, num_name="enterprise_value", den_name="ebitda")
        )
    multiples[MultipleKind.PE] = safe_ratio(
        market_cap, peer.net_income, num_name="market_cap", den_name="net_income"
    )

    issues: list[Issue] = []
    for k, m in multiples.items():
        if m.is_ok and m.value is not None and m.value > OUTLIER_THRESHOLDS[k.value]:
            issues.append(
                info(
                    Code.POTENTIAL_OUTLIER,
                    f"{peer.name}: {k.value} of {m.value:.1f}x is above "
                    f"{OUTLIER_THRESHOLDS[k.value]:.0f}x — review; exclusion requires a reason.",
                )
            )
    return PeerResult(
        name=peer.name,
        market_cap=market_cap,
        diluted_shares=dil.diluted_shares,
        enterprise_value=ev,
        ebitda_used=ebitda,
        multiples=multiples,
        included=peer.included,
        exclusion_reason=peer.exclusion_reason,
        issues=tuple(issues),
    )


def multiple_stats(kind: MultipleKind, peers: Sequence[PeerResult]) -> MultipleStats:
    vals: list[tuple[float, str]] = []
    left_out: list[tuple[str, str]] = []
    for p in peers:
        m = p.multiples[kind]
        if not p.included:
            left_out.append((p.name, f"excluded by analyst: {p.exclusion_reason}"))
        elif not m.is_ok or m.value is None:
            left_out.append((p.name, f"{m.status.value}: {m.reason}"))
        else:
            vals.append((m.value, p.name))
    vals.sort()
    xs = tuple(v for v, _ in vals)
    if not xs:
        return MultipleStats(kind, (), (), tuple(left_out), 0, None, None, None, None, None, None)
    return MultipleStats(
        kind=kind,
        values=xs,
        contributors=tuple(n for _, n in vals),
        left_out=tuple(left_out),
        n=len(xs),
        minimum=xs[0],
        p25=percentile_inc(xs, 0.25),
        median=statistics.median(xs),
        mean=statistics.fmean(xs),
        p75=percentile_inc(xs, 0.75),
        maximum=xs[-1],
    )


def analyze_comps(
    peers: Sequence[PeerInputs],
    *,
    period_type: PeriodType,
    ebitda_basis: EbitdaBasis,
    target_period_end: date,
) -> CompsAnalysis:
    c = Checker()
    if not peers:
        c.error(Code.NO_VALID_PEERS, "At least one peer is required.")
    mismatched = [p.name for p in peers if p.period_type is not period_type]
    if mismatched:
        c.error(
            Code.PERIOD_TYPE_MISMATCH,
            f"Peers {mismatched} do not use the analysis period type {period_type.value.upper()}.",
        )
    c.raise_if_errors()

    issues: list[Issue] = []
    results = []
    for p in peers:
        r = compute_peer(p, ebitda_basis)
        results.append(r)
        issues.extend(r.issues)
        gap = abs((p.period_end - target_period_end).days)
        if gap > PERIOD_ALIGNMENT_DAYS:
            issues.append(
                warning(
                    Code.FISCAL_PERIOD_MISALIGNED,
                    f"{p.name}: period ends {p.period_end.isoformat()}, {gap} days from the "
                    f"target's {target_period_end.isoformat()}; consider calendarising.",
                )
            )
    currencies = sorted({p.reporting_currency for p in peers})
    if len(currencies) > 1:
        issues.append(
            info(
                Code.CURRENCY_MISMATCH,
                f"Peers report in {currencies}; multiples are currency-neutral, absolute values "
                "are not comparable without FX conversion.",
            )
        )
    stats = {k: multiple_stats(k, results) for k in MultipleKind}
    for k, s in stats.items():
        if 0 < s.n < MIN_PEERS:
            issues.append(
                warning(Code.LOW_PEER_COUNT, f"{k.value}: only {s.n} meaningful peer value(s).")
            )
        elif s.n == 0:
            issues.append(warning(Code.NO_VALID_PEERS, f"{k.value}: no meaningful peer values."))
    return CompsAnalysis(period_type, ebitda_basis, tuple(results), stats, tuple(issues))


# ------------------------------------------------------------------------------------------
# Applying multiples to the target
# ------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ImpliedPoint:
    label: str  # "low" / "mid" / "high"
    multiple: float
    enterprise_value: float | None  # None for P/E (applies to equity directly)
    equity_value: float  # equity attributable to common shareholders
    value_per_share: float


@dataclass(frozen=True, slots=True)
class ImpliedValuation:
    kind: MultipleKind
    target_metric: float
    points: tuple[ImpliedPoint, ...]
    issues: tuple[Issue, ...]


def implied_valuation(
    stats: MultipleStats,
    target_metric: Metric,
    *,
    bridge: BridgeInputs,
    share_capital: ShareCapitalInputs,
    low: str = "p25",
    mid: str = "median",
    high: str = "p75",
) -> ImpliedValuation:
    """Apply peer multiples to the target. Target metric must use the same period and basis."""
    if stats.n == 0:
        raise EngineError([error(Code.NO_VALID_PEERS, f"No meaningful {stats.kind.value} values.")])
    if not target_metric.is_ok or target_metric.value is None or target_metric.value <= 0:
        raise EngineError(
            [
                error(
                    Code.TARGET_METRIC_NOT_MEANINGFUL,
                    f"Target metric for {stats.kind.value} is "
                    f"{target_metric.value if target_metric.is_ok else target_metric.reason}; a "
                    "multiple of a non-positive or missing metric is not meaningful.",
                )
            ]
        )
    metric = target_metric.value
    issues: list[Issue] = []
    cap = share_capital
    if stats.kind is MultipleKind.PE and share_capital.convertibles:
        cap = replace(share_capital, convertibles=())
        issues.append(
            warning(
                Code.PE_CONVERTIBLES_IGNORED,
                "P/E route: convertibles are ignored in the per-share step (if-converted EPS is "
                "not modelled); use an EV multiple for companies with material convertibles.",
            )
        )
    points = []
    for label, stat_name in (("low", low), ("mid", mid), ("high", high)):
        mult = getattr(stats, stat_name)
        assert isinstance(mult, float)
        if stats.kind is MultipleKind.PE:
            equity = mult * metric
            per = implied_value_per_share(cap, equity)
            points.append(
                ImpliedPoint(label, mult, None, per.equity_value_to_common, per.value_per_share)
            )
        else:
            ev = mult * metric
            br = equity_from_enterprise(ev, bridge, share_capital.convertible_face)
            per = implied_value_per_share(share_capital, br.equity_value)
            points.append(
                ImpliedPoint(label, mult, ev, per.equity_value_to_common, per.value_per_share)
            )
    return ImpliedValuation(stats.kind, metric, tuple(points), tuple(issues))
