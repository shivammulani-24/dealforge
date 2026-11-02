"""Enterprise value ↔ equity value bridge (spec section H.7, D-09).

::

    Equity value = EV
                 − total debt (excluding convertibles)
                 − lease liabilities           (only if EBITDA is before lease expense, D-09)
                 − convertible debt at face    (added back if it converts; see shares.py)
                 − preferred equity
                 − non-controlling interest
                 − other debt-like claims       (e.g. unfunded pensions)
                 + cash and cash equivalents
                 + non-operating assets         (e.g. equity-method investments)

Why: EV is the value of the operating business to *all* capital providers, because UFCF is
before any payment to lenders, preferred holders or minorities. Ordinary shareholders own what
is left after every prior claim is paid, so those claims are subtracted. Cash (and other
non-operating assets) is added because UFCF excludes interest income on it — the DCF has not
valued it yet, and it belongs to shareholders.

Consistency rule: subtract a claim *if and only if* the cash flows servicing it are inside
UFCF/EBITDA. NCI: consolidated EBITDA includes 100% of subsidiaries, so the minority share is
deducted. Leases: under IFRS 16 lease cost sits below EBITDA (depreciation + interest), so the
lease liability is debt-like; if lease expense is already deducted in EBITDA it must NOT be
subtracted again.

All inputs are required (no defaults): an absent claim must be entered explicitly as 0, so
"unknown" can never silently become "none".
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import Code, Issue, warning
from .validation import Checker


@dataclass(frozen=True, slots=True)
class BridgeInputs:
    cash: float
    total_debt: float  # excluding convertibles, which are listed in ShareCapitalInputs
    lease_liabilities: float
    include_leases_in_debt: bool  # True iff EBITDA is before lease expense (IFRS 16 style)
    preferred_equity: float
    non_controlling_interest: float
    other_debt_like_claims: float
    non_operating_assets: float


@dataclass(frozen=True, slots=True)
class BridgeLine:
    label: str
    amount: float  # signed contribution to equity value


@dataclass(frozen=True, slots=True)
class BridgeResult:
    enterprise_value: float
    lines: tuple[BridgeLine, ...]
    equity_value: float  # before adding back any converted convertibles
    issues: tuple[Issue, ...]


def validate_bridge(b: BridgeInputs, convertible_face: float) -> tuple[Issue, ...]:
    c = Checker()
    for name in (
        "cash",
        "total_debt",
        "lease_liabilities",
        "preferred_equity",
        "non_controlling_interest",
        "other_debt_like_claims",
        "non_operating_assets",
    ):
        c.non_negative(name, getattr(b, name))
    c.non_negative("convertible_face", convertible_face)
    if not isinstance(b.include_leases_in_debt, bool):
        c.error(
            Code.MISSING_INPUT if b.include_leases_in_debt is None else Code.INVALID_TYPE,
            "include_leases_in_debt must be True or False (D-09).",
            "include_leases_in_debt",
        )
    c.raise_if_errors()
    if b.lease_liabilities > 0 and not b.include_leases_in_debt:
        c.info(
            Code.LEASES_EXCLUDED,
            f"Lease liabilities of {b.lease_liabilities:,.2f} are not deducted because lease "
            "expense is already inside EBITDA (D-09).",
        )
    return c.warnings()


def claims_lines(b: BridgeInputs, convertible_face: float) -> tuple[BridgeLine, ...]:
    """Every claim (negative) and non-operating asset (positive), in display order."""
    lines = [BridgeLine("Less: total debt", -b.total_debt)]
    if b.include_leases_in_debt:
        lines.append(BridgeLine("Less: lease liabilities", -b.lease_liabilities))
    lines += [
        BridgeLine("Less: convertible debt (face)", -convertible_face),
        BridgeLine("Less: preferred equity", -b.preferred_equity),
        BridgeLine("Less: non-controlling interest", -b.non_controlling_interest),
        BridgeLine("Less: other debt-like claims", -b.other_debt_like_claims),
        BridgeLine("Plus: cash and equivalents", b.cash),
        BridgeLine("Plus: non-operating assets", b.non_operating_assets),
    ]
    return tuple(lines)


def equity_from_enterprise(
    enterprise_value: float, b: BridgeInputs, convertible_face: float
) -> BridgeResult:
    c = Checker()
    c.number("enterprise_value", enterprise_value)
    c.raise_if_errors()
    issues = list(validate_bridge(b, convertible_face))
    lines = claims_lines(b, convertible_face)
    equity = enterprise_value + sum(line.amount for line in lines)
    if equity <= 0:
        issues.append(
            warning(
                Code.EQUITY_VALUE_NON_POSITIVE,
                f"Claims exceed enterprise value: equity value is {equity:,.2f}.",
            )
        )
    return BridgeResult(enterprise_value, lines, equity, tuple(issues))


def enterprise_from_equity(
    equity_value: float, b: BridgeInputs, unconverted_convertible_face: float
) -> float:
    """Inverse bridge used for peers and deal EV: EV = equity + claims − cash − non-op assets.

    ``equity_value`` must already include any converted convertibles (as shares), and
    ``unconverted_convertible_face`` must include only those that did not convert, so each
    convertible is counted exactly once — as equity or as debt, never both.
    """
    c = Checker()
    c.number("equity_value", equity_value)
    c.raise_if_errors()
    validate_bridge(b, unconverted_convertible_face)
    return equity_value - sum(line.amount for line in claims_lines(b, unconverted_convertible_face))
