"""Diluted share count (spec section H.8, decision D-10, refined).

Instruments
-----------
* **Basic shares** outstanding.
* **Options and warrants** — treasury stock method (TSM): if strike K < price P, holders
  exercise, the company receives n × K and is assumed to buy back n × K / P shares, so the net
  new shares are ``n × (1 − K / P)``. Out-of-the-money (K ≥ P) tranches add nothing.
* **RSUs / PSUs** — no exercise price, so every unit is added in full.
* **Convertible debt** — if-converted method: it converts when the conversion price is below
  the share price (the shares are then worth more than the face value). Converted: add
  ``face / conversion price`` shares and treat the face value as equity, not debt.
  Not converted: no shares, face value stays a debt claim in the bridge. Each convertible is
  counted once — as equity or as debt, never both.

When is the calculation circular?
---------------------------------
* At an **observed** price (market price for market cap / WACC / comps, offer price in M&A)
  the share count is a direct function of that price → :func:`diluted_shares_at_price`, no
  iteration.
* For the **DCF implied price**, the price is the *output*: P = equity / diluted shares(P).
  That is a genuine circularity, but only when price-dependent instruments (options,
  warrants, convertibles) exist. With only basic shares and RSUs the answer is direct.

How the circularity is solved (no iteration needed)
---------------------------------------------------
For a given set A of instruments that are in the money, TSM gives::

    P × (B + R + Σ_{A,opt} n_i + Σ_{A,conv} F_j / C_j) − Σ_{A,opt} n_i K_i = E + Σ_{A,conv} F_j

so ``P = (E + Σ n_i K_i + Σ F_j) / (B + R + Σ n_i + Σ F_j / C_j)`` — the familiar result that
TSM is equivalent to "all in-the-money holders exercise and the company keeps the cash".
Instruments enter A in order of their strike / conversion price, so the engine tries each
candidate set in that order and keeps the one that is self-consistent (every included
threshold < P ≤ every excluded threshold). Value per diluted share is strictly decreasing in
the assumed price, so exactly one candidate is consistent; the result is then re-checked by
recomputing TSM at the solved price.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .errors import Code, EngineError, Issue, error, info, warning
from .validation import Checker

SELF_CHECK_TOLERANCE = 1e-9


class InstrumentKind(StrEnum):
    OPTION = "option"
    WARRANT = "warrant"
    RSU = "rsu"
    CONVERTIBLE = "convertible"


@dataclass(frozen=True, slots=True)
class OptionTranche:
    label: str
    count: float  # millions of options / warrants
    strike: float
    kind: InstrumentKind = InstrumentKind.OPTION  # OPTION or WARRANT


@dataclass(frozen=True, slots=True)
class RsuGrant:
    label: str
    count: float


@dataclass(frozen=True, slots=True)
class ConvertibleInstrument:
    label: str
    face_value: float
    conversion_price: float
    coupon_rate: float | None = None  # needed only where interest is added back (M&A)

    @property
    def shares_if_converted(self) -> float:
        return self.face_value / self.conversion_price


@dataclass(frozen=True, slots=True)
class ShareCapitalInputs:
    basic_shares: float
    options: tuple[OptionTranche, ...]
    rsus: tuple[RsuGrant, ...]
    convertibles: tuple[ConvertibleInstrument, ...]

    @property
    def convertible_face(self) -> float:
        return sum(cv.face_value for cv in self.convertibles)

    @property
    def has_price_dependent_instruments(self) -> bool:
        return bool(self.options or self.convertibles)


@dataclass(frozen=True, slots=True)
class InstrumentDilution:
    label: str
    kind: InstrumentKind
    gross_shares: float
    included: bool  # in the money / converted / always for RSUs
    proceeds: float
    shares_repurchased: float
    net_new_shares: float
    note: str


@dataclass(frozen=True, slots=True)
class DilutionResult:
    price: float
    basic_shares: float
    lines: tuple[InstrumentDilution, ...]
    diluted_shares: float
    converted_face: float
    unconverted_face: float
    method: str


@dataclass(frozen=True, slots=True)
class ImpliedPerShare:
    equity_value_before_conversion: float
    equity_value_to_common: float  # + face value of converted convertibles
    value_per_share: float
    dilution: DilutionResult
    circular: bool
    method: str
    issues: tuple[Issue, ...]


def validate_share_capital(cap: ShareCapitalInputs) -> None:
    c = Checker()
    c.positive("basic_shares", cap.basic_shares)
    for i, o in enumerate(cap.options):
        c.non_negative(f"options[{i}].count", o.count)
        c.non_negative(f"options[{i}].strike", o.strike)
        if o.kind not in (InstrumentKind.OPTION, InstrumentKind.WARRANT):
            c.error(Code.INVALID_TYPE, f"options[{i}].kind must be option or warrant.")
    for i, r in enumerate(cap.rsus):
        c.non_negative(f"rsus[{i}].count", r.count)
    for i, cv in enumerate(cap.convertibles):
        c.non_negative(f"convertibles[{i}].face_value", cv.face_value)
        c.positive(f"convertibles[{i}].conversion_price", cv.conversion_price)
        if cv.coupon_rate is not None:
            c.in_range(f"convertibles[{i}].coupon_rate", cv.coupon_rate, 0.0, 0.5)
    c.raise_if_errors()


def diluted_shares_at_price(cap: ShareCapitalInputs, price: float) -> DilutionResult:
    """Diluted shares at an observed price — direct, never iterative."""
    validate_share_capital(cap)
    c = Checker()
    c.positive("price", price)
    c.raise_if_errors()

    lines: list[InstrumentDilution] = []
    for o in cap.options:
        if o.strike < price:
            proceeds = o.count * o.strike
            repurchased = proceeds / price
            lines.append(
                InstrumentDilution(
                    o.label,
                    o.kind,
                    o.count,
                    True,
                    proceeds,
                    repurchased,
                    o.count - repurchased,
                    f"in the money (strike {o.strike:,.4f} < price {price:,.4f}); TSM",
                )
            )
        else:
            lines.append(
                InstrumentDilution(
                    o.label,
                    o.kind,
                    o.count,
                    False,
                    0.0,
                    0.0,
                    0.0,
                    f"out of the money (strike {o.strike:,.4f} ≥ price {price:,.4f})",
                )
            )
    for r in cap.rsus:
        lines.append(
            InstrumentDilution(
                r.label, InstrumentKind.RSU, r.count, True, 0.0, 0.0, r.count, "added in full"
            )
        )
    converted_face = 0.0
    for cv in cap.convertibles:
        n = cv.shares_if_converted
        if cv.conversion_price < price:
            converted_face += cv.face_value
            lines.append(
                InstrumentDilution(
                    cv.label,
                    InstrumentKind.CONVERTIBLE,
                    n,
                    True,
                    0.0,
                    0.0,
                    n,
                    f"converts (conversion price {cv.conversion_price:,.4f} < price "
                    f"{price:,.4f}); face {cv.face_value:,.2f} treated as equity",
                )
            )
        else:
            lines.append(
                InstrumentDilution(
                    cv.label,
                    InstrumentKind.CONVERTIBLE,
                    n,
                    False,
                    0.0,
                    0.0,
                    0.0,
                    f"does not convert; face {cv.face_value:,.2f} remains debt",
                )
            )
    diluted = cap.basic_shares + sum(line.net_new_shares for line in lines)
    return DilutionResult(
        price=price,
        basic_shares=cap.basic_shares,
        lines=tuple(lines),
        diluted_shares=diluted,
        converted_face=converted_face,
        unconverted_face=cap.convertible_face - converted_face,
        method="treasury stock method (options/warrants) and if-converted (convertibles) at an "
        "observed price",
    )


def implied_value_per_share(cap: ShareCapitalInputs, equity_value: float) -> ImpliedPerShare:
    """Value per diluted share when the price is the output of the valuation.

    ``equity_value`` is the bridge result *before* any convertible is treated as converted
    (i.e. with every convertible subtracted at face).
    """
    validate_share_capital(cap)
    c = Checker()
    c.number("equity_value", equity_value)
    c.raise_if_errors()

    rsu_total = sum(r.count for r in cap.rsus)
    issues: list[Issue] = []

    def _direct(note: str) -> ImpliedPerShare:
        shares = cap.basic_shares + rsu_total
        per_share = equity_value / shares
        lines = (
            tuple(
                InstrumentDilution(
                    r.label, InstrumentKind.RSU, r.count, True, 0.0, 0.0, r.count, "added in full"
                )
                for r in cap.rsus
            )
            + tuple(
                InstrumentDilution(
                    o.label, o.kind, o.count, False, 0.0, 0.0, 0.0, "not exercised at this value"
                )
                for o in cap.options
            )
            + tuple(
                InstrumentDilution(
                    cv.label,
                    InstrumentKind.CONVERTIBLE,
                    cv.shares_if_converted,
                    False,
                    0.0,
                    0.0,
                    0.0,
                    "does not convert at this value; remains debt",
                )
                for cv in cap.convertibles
            )
        )
        dil = DilutionResult(
            price=per_share,
            basic_shares=cap.basic_shares,
            lines=lines,
            diluted_shares=shares,
            converted_face=0.0,
            unconverted_face=cap.convertible_face,
            method=note,
        )
        return ImpliedPerShare(
            equity_value, equity_value, per_share, dil, False, note, tuple(issues)
        )

    if not cap.has_price_dependent_instruments:
        return _direct(
            "direct: basic shares + RSUs (no price-dependent instruments, no circularity)"
        )
    if equity_value <= 0:
        issues.append(
            warning(
                Code.EQUITY_VALUE_NON_POSITIVE,
                "Equity value is not positive, so no option or convertible is in the money; "
                "value per share shown on basic shares + RSUs.",
            )
        )
        return _direct("direct: equity value not positive, instruments out of the money")

    # Candidate thresholds in ascending order (stable sort on (threshold, kind, label)).
    items: list[tuple[float, str, OptionTranche | ConvertibleInstrument]] = [
        (o.strike, o.label, o) for o in cap.options
    ] + [(cv.conversion_price, cv.label, cv) for cv in cap.convertibles]
    items.sort(key=lambda x: (x[0], x[1]))
    thresholds = [t for t, _, _ in items]

    solved: float | None = None
    for k in range(len(items) + 1):
        num = equity_value
        den = cap.basic_shares + rsu_total
        for _, _, inst in items[:k]:
            if isinstance(inst, OptionTranche):
                num += inst.count * inst.strike
                den += inst.count
            else:
                num += inst.face_value
                den += inst.shares_if_converted
        p = num / den
        lower_ok = k == 0 or thresholds[k - 1] < p
        upper_ok = k == len(items) or thresholds[k] >= p
        if lower_ok and upper_ok:
            solved = p
            break
    if solved is None:  # pragma: no cover - mathematically unreachable (see module docstring)
        raise EngineError([error("DILUTION_NO_SOLUTION", "No self-consistent diluted price.")])

    dil = diluted_shares_at_price(cap, solved)
    equity_to_common = equity_value + dil.converted_face
    check = equity_to_common / dil.diluted_shares
    if abs(check - solved) > SELF_CHECK_TOLERANCE * max(1.0, abs(solved)):  # pragma: no cover
        raise EngineError(
            [error("DILUTION_SELF_CHECK_FAILED", f"TSM re-check {check} ≠ solved {solved}.")]
        )
    issues.append(
        info(
            Code.DILUTION_SOLVED,
            "Diluted shares depend on the implied price (options/convertibles); solved exactly "
            f"for a self-consistent price of {solved:,.4f}.",
        )
    )
    for line in dil.lines:
        if line.kind is InstrumentKind.CONVERTIBLE and line.included:
            issues.append(info(Code.CONVERTIBLE_CONVERTED, f"{line.label}: {line.note}."))
    return ImpliedPerShare(
        equity_value,
        equity_to_common,
        solved,
        dil,
        True,
        "self-consistent TSM / if-converted solution (closed form per in-the-money set)",
        tuple(issues),
    )
