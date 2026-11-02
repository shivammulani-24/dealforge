"""Scenarios: a base input set plus explicit, auditable overrides (spec section H.12).

An override is ``(path, value)`` where ``path`` names one scalar input, e.g.::

    "terminal_growth"                 "tax_rate"                 "wacc_override"
    "forecast.years[3].ebitda_margin" "forecast.base_revenue"    "wacc_assumptions.levered_beta"

Unknown paths are rejected (a typo must never silently leave the base value in place).
The resolved inputs are what get run, fingerprinted and stored.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass, replace
from typing import Any

from .errors import Code, EngineError, error
from .valuation import DcfInputs, DcfResult, run_dcf

_STEP = re.compile(r"^(?P<name>[a-z_][a-z0-9_]*)(?:\[(?P<idx>\d+)\])?$")


def _is_number_slot(current: Any) -> bool:
    """A scalar numeric input (``None`` allowed for optional numbers such as wacc_override)."""
    return current is None or (isinstance(current, int | float) and not isinstance(current, bool))


def _bad(path: str, why: str) -> EngineError:
    return EngineError([error(Code.INVALID_TYPE, f"Override '{path}': {why}.", path)])


def _set(obj: Any, steps: list[str], value: float, path: str) -> Any:
    m = _STEP.match(steps[0])
    if not m or not is_dataclass(obj) or m["name"] not in {f.name for f in fields(obj)}:
        raise _bad(path, "unknown path")
    assert not isinstance(obj, type)
    name, idx = m["name"], m["idx"]
    current = getattr(obj, name)
    last = len(steps) == 1

    if idx is not None:
        i = int(idx) - 1  # 1-based to match "Year 1..5"
        if not isinstance(current, tuple) or not 0 <= i < len(current):
            raise _bad(path, "index out of range")
        if last:
            raise _bad(path, "an index must be followed by a field name")
        item = _set(current[i], steps[1:], value, path)
        return replace(obj, **{name: (*current[:i], item, *current[i + 1 :])})

    if last:
        if not _is_number_slot(current):
            raise _bad(path, "does not name a number")
        return replace(obj, **{name: value})
    if current is None:
        raise EngineError(
            [error(Code.MISSING_INPUT, f"Cannot override '{path}': parent is not set.", path)]
        )
    return replace(obj, **{name: _set(current, steps[1:], value, path)})


def apply_overrides(base: DcfInputs, overrides: Mapping[str, float]) -> DcfInputs:
    out = base
    for path in sorted(overrides):  # sorted → deterministic regardless of dict order
        out = _set(out, path.split("."), overrides[path], path)
    return out


@dataclass(frozen=True, slots=True)
class ScenarioRun:
    name: str
    overrides: tuple[tuple[str, float], ...]
    result: DcfResult


def run_scenarios(
    base: DcfInputs, scenarios: Sequence[tuple[str, Mapping[str, float]]]
) -> tuple[ScenarioRun, ...]:
    return tuple(
        ScenarioRun(name, tuple(sorted(ov.items())), run_dcf(apply_overrides(base, ov)))
        for name, ov in scenarios
    )
