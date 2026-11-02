"""Serialisation properties the Phase 3 API contract depends on (see docs/api-contract.md)."""

from __future__ import annotations

import json
import math

import pytest
from builders import dcf_inputs
from hypothesis import given
from hypothesis import strategies as st

from app.engine.hashing import canonical_json, to_plain
from app.engine.historical import HistoricalPeriod
from app.engine.valuation import run_dcf

finite = st.floats(allow_nan=False, allow_infinity=False)


@given(x=finite)
def test_every_finite_float_round_trips_exactly(x: float) -> None:
    back = json.loads(canonical_json({"v": x}))["v"]
    assert back == x
    assert math.copysign(1.0, back) == math.copysign(1.0, x)  # even −0.0 survives


def test_none_serialises_as_null_never_zero() -> None:
    plain = to_plain(HistoricalPeriod(fiscal_year=2025, revenue=100.0))
    assert plain["cogs"] is None
    assert '"cogs":null' in canonical_json(HistoricalPeriod(fiscal_year=2025, revenue=100.0))


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_cannot_be_serialised(bad: float) -> None:
    with pytest.raises(ValueError):
        canonical_json({"v": bad})


def test_result_survives_json_round_trip_exactly() -> None:
    r = run_dcf(dcf_inputs())
    data = json.loads(canonical_json(r))
    assert data["valuation"]["enterprise_value"] == r.enterprise_value
    assert data["per_share"]["value_per_share"] == r.value_per_share
    assert [f["present_value"] for f in data["valuation"]["flows"]] == [
        f.present_value for f in r.valuation.flows
    ]
    assert data["input_hash"] == r.input_hash
