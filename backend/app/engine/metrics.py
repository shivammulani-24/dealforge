"""A value that may legitimately be absent.

Analytical metrics (margins, growth, multiples) can be:

* ``OK``             — computed;
* ``MISSING``        — an input was missing (the metric is unknown, **not zero**);
* ``NOT_MEANINGFUL`` — "NM": the inputs exist but the ratio has no economic meaning
  (e.g. P/E on a loss, growth from a negative base).

The UI renders these as a number, "n/a (missing input)" and "NM" respectively.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Status(StrEnum):
    OK = "ok"
    MISSING = "missing"
    NOT_MEANINGFUL = "not_meaningful"


@dataclass(frozen=True, slots=True)
class Metric:
    value: float | None
    status: Status
    reason: str | None = None

    def __post_init__(self) -> None:
        if (self.status is Status.OK) != (self.value is not None):
            raise ValueError("Metric.value must be set if and only if status is OK")

    @property
    def is_ok(self) -> bool:
        return self.status is Status.OK


def ok(value: float, reason: str | None = None) -> Metric:
    return Metric(value, Status.OK, reason)


def missing(*inputs: str) -> Metric:
    return Metric(None, Status.MISSING, "missing input: " + ", ".join(inputs))


def nm(reason: str) -> Metric:
    return Metric(None, Status.NOT_MEANINGFUL, reason)


def safe_ratio(
    numerator: float | None,
    denominator: float | None,
    *,
    num_name: str,
    den_name: str,
    require_positive_denominator: bool = True,
) -> Metric:
    """numerator / denominator with explicit missing / NM handling.

    With ``require_positive_denominator`` (the default for margins, multiples and growth), a
    zero or negative denominator gives NM; otherwise only an exactly-zero denominator does.
    """
    absent = [n for n, v in ((num_name, numerator), (den_name, denominator)) if v is None]
    if absent:
        return missing(*absent)
    assert numerator is not None and denominator is not None
    if require_positive_denominator and denominator <= 0:
        return nm(f"{den_name} is {'zero' if denominator == 0 else 'negative'}")
    if denominator == 0:
        return nm(f"{den_name} is zero")
    return ok(numerator / denominator)
