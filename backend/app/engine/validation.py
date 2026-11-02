"""Input validation helpers.

The :class:`Checker` collects *all* problems in an input set before raising, so a user sees every
error at once instead of fixing them one by one.

Rules enforced here (Phase 1 spec, section H.1):

* ``None`` means **missing**. A required ``None`` raises :class:`MissingInputError`; it is never
  coerced to ``0``.
* ``NaN`` and ``±inf`` are rejected (they usually come from a division by zero upstream).
* ``bool`` is rejected where a number is expected (``True`` would otherwise behave as ``1``).
"""

from __future__ import annotations

import math

from .errors import (
    Code,
    EngineError,
    Issue,
    MissingInputError,
    Severity,
    error,
    info,
    warning,
)


def fmt_pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def fmt_num(x: float) -> str:
    return f"{x:,.4f}"


class Checker:
    """Accumulates issues; call :meth:`raise_if_errors` once all checks have run."""

    def __init__(self) -> None:
        self.issues: list[Issue] = []
        self._missing: list[Issue] = []

    # -- recording --------------------------------------------------------------------------
    def error(self, code: str, message: str, field: str | None = None) -> None:
        self.issues.append(error(code, message, field))

    def warn(self, code: str, message: str, field: str | None = None) -> None:
        self.issues.append(warning(code, message, field))

    def info(self, code: str, message: str, field: str | None = None) -> None:
        self.issues.append(info(code, message, field))

    def extend(self, issues: tuple[Issue, ...] | list[Issue]) -> None:
        self.issues.extend(issues)

    # -- value checks -----------------------------------------------------------------------
    def number(self, field: str, value: object) -> float | None:
        """Return ``value`` as a float if present and finite; record a problem otherwise.

        Returns ``None`` when the value is unusable, so callers can skip dependent checks.
        """
        if value is None:
            self._missing.append(
                error(Code.MISSING_INPUT, f"Required input '{field}' is missing.", field)
            )
            return None
        if isinstance(value, bool) or not isinstance(value, int | float):
            self.error(Code.INVALID_TYPE, f"'{field}' must be a number, got {value!r}.", field)
            return None
        v = float(value)
        if not math.isfinite(v):
            self.error(Code.NON_FINITE_INPUT, f"'{field}' must be finite, got {v}.", field)
            return None
        return v

    def non_negative(self, field: str, value: object) -> float | None:
        v = self.number(field, value)
        if v is not None and v < 0:
            self.error(
                Code.SIGN_CONVENTION,
                f"'{field}' is stored as a positive magnitude (D-02); got {fmt_num(v)}.",
                field,
            )
            return None
        return v

    def positive(self, field: str, value: object) -> float | None:
        v = self.number(field, value)
        if v is not None and v <= 0:
            self.error(Code.OUT_OF_RANGE, f"'{field}' must be > 0; got {fmt_num(v)}.", field)
            return None
        return v

    def in_range(
        self,
        field: str,
        value: object,
        low: float,
        high: float,
        *,
        low_inclusive: bool = True,
        high_inclusive: bool = True,
    ) -> float | None:
        v = self.number(field, value)
        if v is None:
            return None
        ok_low = v >= low if low_inclusive else v > low
        ok_high = v <= high if high_inclusive else v < high
        if not (ok_low and ok_high):
            lb = "[" if low_inclusive else "("
            hb = "]" if high_inclusive else ")"
            self.error(
                Code.OUT_OF_RANGE,
                f"'{field}' must be in {lb}{low}, {high}{hb}; got {fmt_num(v)}.",
                field,
            )
            return None
        return v

    # -- finishing --------------------------------------------------------------------------
    @property
    def has_errors(self) -> bool:
        return bool(self._missing) or any(i.severity is Severity.ERROR for i in self.issues)

    def raise_if_errors(self) -> None:
        errors = [i for i in self.issues if i.severity is Severity.ERROR]
        if self._missing and not errors:
            raise MissingInputError(self._missing)
        if self._missing or errors:
            raise EngineError([*self._missing, *errors])

    def warnings(self) -> tuple[Issue, ...]:
        return tuple(i for i in self.issues if i.severity is not Severity.ERROR)


def require(field: str, value: object) -> float:
    """Validate a single required finite number (raises immediately)."""
    c = Checker()
    v = c.number(field, value)
    c.raise_if_errors()
    assert v is not None
    return v


def approx_equal(a: float, b: float, *, rel: float = 0.005, abs_: float = 0.5) -> bool:
    """Reconciliation tolerance used by consistency checks: max(0.5% × |b|, 0.5 units) (D-12)."""
    return abs(a - b) <= max(rel * abs(b), abs_)
