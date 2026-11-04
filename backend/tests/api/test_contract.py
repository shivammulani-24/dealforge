"""API contract tests (docs/api-contract.md section 5). The API must never change a value."""

from __future__ import annotations

import dataclasses
import json
import typing
from datetime import date
from typing import Any

import pytest
from builders import dcf_inputs
from fastapi.testclient import TestClient
from test_independent_verification import ka_dcf03_inputs

from app.engine import valuation as engine_valuation
from app.engine.hashing import fingerprint, to_plain
from app.engine.valuation import DcfInputs, run_dcf
from app.schemas import dcf as schemas

URL = "/api/v1/calculate/dcf"


def body_for(inp: DcfInputs) -> dict[str, Any]:
    return to_plain(inp)  # type: ignore[no-any-return]


@pytest.mark.parametrize("make", [dcf_inputs, ka_dcf03_inputs], ids=["KA-DCF-02", "KA-DCF-03"])
def test_1_no_value_drift(client: TestClient, auth: dict[str, str], make: Any) -> None:
    inp = make()
    r = client.post(URL, json=body_for(inp), headers=auth)
    assert r.status_code == 200, r.text
    assert r.json() == to_plain(run_dcf(inp))  # exact equality of every float, not approximate


def test_8_fingerprint_matches_engine(client: TestClient, auth: dict[str, str]) -> None:
    inp = ka_dcf03_inputs()
    assert client.post(URL, json=body_for(inp), headers=auth).json()["input_hash"] == (
        fingerprint(inp)
    )


@pytest.mark.parametrize(
    "path, field",
    [
        (("tax_rate",), "tax_rate"),
        (("bridge", "cash"), "cash"),
        (("bridge", "non_controlling_interest"), "non_controlling_interest"),
        (("share_capital", "basic_shares"), "basic_shares"),
        (("forecast", "base_nwc"), "base_nwc"),
    ],
)
def test_2_null_reaches_engine_as_missing(
    client: TestClient, auth: dict[str, str], path: tuple[str, ...], field: str
) -> None:
    b = body_for(dcf_inputs())
    target = b
    for k in path[:-1]:
        target = target[k]
    target[path[-1]] = None
    r = client.post(URL, json=b, headers=auth)
    assert r.status_code == 422 and r.json()["error_type"] == "calculation", r.text
    assert ("MISSING_INPUT", field) in {(e["code"], e["field"]) for e in r.json()["errors"]}


def test_2_omitted_key_is_a_validation_error(client: TestClient, auth: dict[str, str]) -> None:
    b = body_for(dcf_inputs())
    del b["bridge"]["cash"]
    r = client.post(URL, json=b, headers=auth)
    assert r.status_code == 422 and r.json()["error_type"] == "validation"
    assert r.json()["errors"][0]["code"] == "missing"
    assert r.json()["errors"][0]["loc"][-2:] == ["bridge", "cash"]


def _models() -> list[type[schemas.StrictModel]]:
    return [
        m
        for m in vars(schemas).values()
        if isinstance(m, type)
        and issubclass(m, schemas.StrictModel)
        and m is not schemas.StrictModel
    ]


def test_2_no_schema_field_has_a_numeric_default() -> None:
    for model in _models():
        for name, f in model.model_fields.items():
            assert f.is_required(), f"{model.__name__}.{name} has a default"


@pytest.mark.parametrize(
    "value, code",
    [
        ("0.25", "float_type"),
        (True, "float_type"),
        ([0.25], "float_type"),
        (2**53 + 1, "int_not_exact"),
    ],
)
def test_3_coercion_is_rejected(
    client: TestClient, auth: dict[str, str], value: Any, code: str
) -> None:
    b = body_for(dcf_inputs())
    b["tax_rate"] = value
    r = client.post(URL, json=b, headers=auth)
    assert r.status_code == 422 and r.json()["error_type"] == "validation"
    assert r.json()["errors"][0]["code"] == code


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e400"])
def test_3_non_finite_literals_are_rejected(
    client: TestClient, auth: dict[str, str], literal: str
) -> None:
    raw = json.dumps(body_for(dcf_inputs())).replace('"tax_rate": 0.25', f'"tax_rate": {literal}')
    r = client.post(URL, content=raw, headers={**auth, "Content-Type": "application/json"})
    assert r.status_code == 422 and r.json()["error_type"] == "validation"


def test_3_integers_are_accepted_exactly(client: TestClient, auth: dict[str, str]) -> None:
    """Resolves the strict-mode question: JSON integers ≤ 2^53 become the identical float."""
    b = body_for(dcf_inputs())
    b["forecast"]["base_revenue"] = 1000  # int instead of 1000.0
    b["share_capital"]["basic_shares"] = 100
    r = client.post(URL, json=b, headers=auth)
    assert r.status_code == 200
    assert r.json() == to_plain(run_dcf(dcf_inputs()))
    big = 2**53
    b["forecast"]["base_revenue"] = big
    assert client.post(URL, json=b, headers=auth).status_code == 200


@pytest.mark.parametrize(
    "path, value",
    [
        (("dates", "statement_date"), "31/03/2025"),
        (("dates", "statement_date"), 1743379200),
        (("dates", "statement_date"), "2025-03-31T00:00:00"),
        (("share_capital", "basic_shares"), "100"),
    ],
)
def test_3_dates_and_types_are_exact(
    client: TestClient, auth: dict[str, str], path: tuple[str, str], value: Any
) -> None:
    b = body_for(dcf_inputs())
    b[path[0]][path[1]] = value
    r = client.post(URL, json=b, headers=auth)
    assert r.status_code == 422 and r.json()["error_type"] == "validation"


def test_3_enum_values_are_case_sensitive(client: TestClient, auth: dict[str, str]) -> None:
    b = body_for(ka_dcf03_inputs())
    b["wacc_assumptions"]["debt_value_basis"] = "BOOK"
    assert client.post(URL, json=b, headers=auth).json()["error_type"] == "validation"
    b["wacc_assumptions"]["debt_value_basis"] = "book"
    assert client.post(URL, json=b, headers=auth).status_code == 200


def test_4_unknown_fields_are_rejected(client: TestClient, auth: dict[str, str]) -> None:
    b = body_for(dcf_inputs())
    b["termnal_growth"] = 0.02
    r = client.post(URL, json=b, headers=auth)
    assert r.status_code == 422 and r.json()["errors"][0]["code"] == "extra_forbidden"


def test_5_units_preserved_through_storage(client: TestClient, auth: dict[str, str]) -> None:
    from conftest import create_company, import_csv

    c = create_company(client, auth, name="Units Co (SYNTHETIC)")
    import_csv(client, auth, c["id"], b"item_code,FY2025\nperiod_end,2025-03-31\nrevenue,2000\n")
    fin = client.get(f"/api/v1/companies/{c['id']}/financials", headers=auth).json()
    assert (fin["currency"], fin["scale"]) == ("INR", "crores")
    assert fin["periods"][0]["line_items"][0]["value"] == 2000.0


def test_6_malformed_body_never_reaches_the_engine(
    client: TestClient, auth: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []
    from app.api.v1 import valuations as routes

    def spy(inp: object) -> object:
        calls.append(inp)
        return engine_valuation.run_dcf(inp)  # type: ignore[arg-type]

    monkeypatch.setattr(routes, "run_dcf", spy)
    bad = body_for(dcf_inputs())
    bad["tax_rate"] = "0.25"
    assert client.post(URL, json=bad, headers=auth).json()["error_type"] == "validation"
    assert calls == []
    calc = body_for(dcf_inputs())
    calc["terminal_growth"] = 0.10  # = WACC
    r = client.post(URL, json=calc, headers=auth)
    assert r.json()["error_type"] == "calculation" and len(calls) == 1
    assert r.json()["errors"][0]["code"] == "TERMINAL_GROWTH_GE_WACC"


def _dataclass_for(model: type) -> type:
    return {
        schemas.DcfInputsIn: engine_valuation.DcfInputs,
        schemas.ValuationDatesIn: schemas.ValuationDates,
        schemas.ForecastInputsIn: schemas.ForecastInputs,
        schemas.ForecastYearDriversIn: schemas.ForecastYearDrivers,
        schemas.BridgeInputsIn: schemas.BridgeInputs,
        schemas.ShareCapitalInputsIn: schemas.ShareCapitalInputs,
        schemas.OptionTrancheIn: schemas.OptionTranche,
        schemas.RsuGrantIn: schemas.RsuGrant,
        schemas.ConvertibleInstrumentIn: schemas.ConvertibleInstrument,
        schemas.WaccAssumptionsIn: schemas.WaccAssumptions,
    }[model]


def test_7_schema_fields_equal_dataclass_fields() -> None:
    models = _models()
    assert len(models) == 10
    for m in models:
        dc = _dataclass_for(m)
        assert set(m.model_fields) == {f.name for f in dataclasses.fields(dc)}, m.__name__


def test_auth_is_required_for_calculation(client: TestClient) -> None:
    assert client.post(URL, json=body_for(dcf_inputs())).status_code == 401


def test_typing_helpers_are_sane() -> None:
    assert typing.get_origin(schemas.DcfInputsIn.model_fields["peer_ev_ebitda_range"].annotation)
    assert date(2025, 3, 31).isoformat() == "2025-03-31"
