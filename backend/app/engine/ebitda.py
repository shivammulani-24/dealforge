"""EBITDA definitions (decision D-03, refined).

Three figures are kept side by side and never mixed:

* **Standardised EBITDA** = EBIT + D&A, calculated by DealForge from reported EBIT and the
  cash-flow-statement D&A. Same definition for every company → the default for comps.
* **Reported EBITDA** — the company's own "EBITDA" line, if it publishes one, with its source.
* **Adjusted EBITDA** — the company's non-GAAP figure, with the disclosed adjustments
  (e.g. share-based compensation, restructuring) and their sources.

Example (₹ crore): EBIT 800 + D&A 200 → standardised 1,000; reported 1,000;
adjusted 1,150 = 1,000 + SBC 100 + restructuring 50.

:func:`select_ebitda` returns exactly the requested basis. If that basis is not available it
returns ``MISSING`` — it never falls back to a different definition.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .errors import Code, Issue, info, warning
from .metrics import Metric, missing, ok
from .validation import Checker, approx_equal


class EbitdaBasis(StrEnum):
    STANDARDIZED = "standardized"
    REPORTED = "reported"
    ADJUSTED = "adjusted"


@dataclass(frozen=True, slots=True)
class EbitdaAdjustment:
    label: str
    amount: float  # signed: + adds back an expense, − removes a gain
    source: str | None = None


@dataclass(frozen=True, slots=True)
class EbitdaFigures:
    ebit: float | None
    da: float | None
    reported: float | None = None
    reported_source: str | None = None
    adjusted: float | None = None
    adjusted_source: str | None = None
    adjustments: tuple[EbitdaAdjustment, ...] = ()


@dataclass(frozen=True, slots=True)
class EbitdaReconciliation:
    standardized: Metric
    reported: Metric
    adjusted: Metric
    adjustments_total: float | None
    adjustments_base: EbitdaBasis | None  # which figure the adjustments are applied to
    issues: tuple[Issue, ...]


def standardized_ebitda(ebit: float | None, da: float | None) -> Metric:
    """EBITDA = EBIT + D&A. D&A is a positive magnitude (D-02)."""
    absent = [n for n, v in (("ebit", ebit), ("da", da)) if v is None]
    if absent:
        return missing(*absent)
    assert ebit is not None and da is not None
    c = Checker()
    c.non_negative("da", da)
    c.number("ebit", ebit)
    c.raise_if_errors()
    return ok(ebit + da)


def reconcile_ebitda(fig: EbitdaFigures) -> EbitdaReconciliation:
    c = Checker()
    if fig.reported is not None:
        c.number("reported", fig.reported)
    if fig.adjusted is not None:
        c.number("adjusted", fig.adjusted)
    for i, a in enumerate(fig.adjustments):
        c.number(f"adjustments[{i}].amount", a.amount)
    c.raise_if_errors()

    std = standardized_ebitda(fig.ebit, fig.da)
    rep = ok(fig.reported) if fig.reported is not None else missing("reported EBITDA")
    adj = ok(fig.adjusted) if fig.adjusted is not None else missing("adjusted EBITDA")
    issues: list[Issue] = []

    if std.is_ok and rep.is_ok:
        assert std.value is not None and rep.value is not None
        if not approx_equal(rep.value, std.value):
            issues.append(
                info(
                    Code.REPORTED_VS_STANDARDIZED_EBITDA,
                    f"Reported EBITDA {rep.value:,.2f} differs from standardised EBIT + D&A "
                    f"{std.value:,.2f} by {rep.value - std.value:,.2f}; the company's definition "
                    "differs from DealForge's.",
                )
            )

    total: float | None = None
    base_basis: EbitdaBasis | None = None
    if fig.adjustments:
        total = sum(a.amount for a in fig.adjustments)
        base = rep if rep.is_ok else std
        base_basis = EbitdaBasis.REPORTED if rep.is_ok else EbitdaBasis.STANDARDIZED
        if not adj.is_ok:
            issues.append(
                warning(
                    Code.ADJUSTMENTS_WITHOUT_ADJUSTED,
                    "Adjustments were disclosed but no adjusted EBITDA figure was provided.",
                )
            )
        elif base.is_ok:
            assert base.value is not None and adj.value is not None
            implied = base.value + total
            if not approx_equal(adj.value, implied):
                issues.append(
                    warning(
                        Code.ADJUSTED_EBITDA_UNRECONCILED,
                        f"{base_basis.value.capitalize()} EBITDA {base.value:,.2f} + disclosed "
                        f"adjustments {total:,.2f} = {implied:,.2f}, but adjusted EBITDA is "
                        f"{adj.value:,.2f} (unexplained {adj.value - implied:,.2f}).",
                    )
                )
    elif adj.is_ok:
        issues.append(
            warning(
                Code.ADJUSTMENTS_NOT_DISCLOSED,
                "Adjusted EBITDA provided without the adjustments that bridge it to reported or "
                "standardised EBITDA; it cannot be audited.",
            )
        )

    return EbitdaReconciliation(std, rep, adj, total, base_basis, tuple(issues))


def select_ebitda(fig: EbitdaFigures, basis: EbitdaBasis) -> Metric:
    """Exactly the requested definition — never a substitute."""
    if basis is EbitdaBasis.STANDARDIZED:
        return standardized_ebitda(fig.ebit, fig.da)
    if basis is EbitdaBasis.REPORTED:
        return ok(fig.reported) if fig.reported is not None else missing("reported EBITDA")
    return ok(fig.adjusted) if fig.adjusted is not None else missing("adjusted EBITDA")
