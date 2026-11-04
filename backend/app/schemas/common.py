"""Strict base model and exact-number type for every API request (docs/api-contract.md)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from enum import Enum
from typing import Annotated, Any, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict
from pydantic_core import PydanticCustomError

MAX_EXACT_INT = 2**53


def _exact_number(v: Any) -> Any:
    """Reject integers that a float cannot hold exactly (they would be silently rounded).

    Strict mode already rejects strings, booleans, NaN and ±Infinity; JSON integers up to 2^53
    convert to float without loss (verified by contract tests).
    """
    if isinstance(v, int) and not isinstance(v, bool) and abs(v) > MAX_EXACT_INT:
        raise PydanticCustomError(
            "int_not_exact",
            "Integer {value} is larger than 2^53 and cannot be represented exactly; send it in "
            "a larger scale (e.g. millions).",
            {"value": v},
        )
    return v


Num = Annotated[float, BeforeValidator(_exact_number)]


def _iso_date(v: Any) -> Any:
    """Dates arrive as JSON strings. Accept exactly YYYY-MM-DD; reject timestamps and the rest.

    FastAPI validates bodies in Python mode, where strict mode refuses *all* strings for dates
    and lax mode would also accept integers as Unix timestamps. This keeps one exact format.
    """
    if isinstance(v, date):
        return v
    if isinstance(v, str) and len(v) == 10:
        try:
            return date.fromisoformat(v)
        except ValueError:
            pass
    raise PydanticCustomError("iso_date", "Expected a date as 'YYYY-MM-DD'")


IsoDate = Annotated[date, BeforeValidator(_iso_date)]

E = TypeVar("E", bound=Enum)


def _exact_enum[E: Enum](enum_cls: type[E]) -> Callable[[Any], Any]:
    def convert(v: Any) -> Any:
        if isinstance(v, enum_cls):
            return v
        for member in enum_cls:
            if isinstance(v, str) and v == member.value:  # case-sensitive, no coercion
                return member
        raise PydanticCustomError(
            "enum", "Expected one of {expected}", {"expected": [m.value for m in enum_cls]}
        )

    return convert


def ExactEnum[E: Enum](enum_cls: type[E]) -> Any:
    return Annotated[enum_cls, BeforeValidator(_exact_enum(enum_cls))]


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False, frozen=True)


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
