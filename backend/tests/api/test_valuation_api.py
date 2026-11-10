"""Scenarios, preview, frozen runs, retrieval and reproducibility through the HTTP API."""

from __future__ import annotations

from conftest import KA_DCF03_ASSUMPTIONS, KA_DCF03_SETTINGS, full_setup, idem
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from verification import independent as ind

REL = 1e-12


def close(a: float, b: object) -> bool:
    return abs(a - float(b)) <= REL * max(1.0, abs(float(b)))  # type: ignore[arg-type]


def test_preview_reproduces_the_independent_ka_dcf03_answer(
    client: TestClient, auth: dict[str, str]
) -> None:
    ids = full_setup(client, auth)
    r = client.post(f"/api/v1/scenarios/{ids['scenario']}/preview", headers=auth)
    assert r.status_code == 200, r.text
    res = r.json()["result"]
    exact = ind.dcf_check()
    assert close(res["wacc"], exact.wacc)
    assert close(res["valuation"]["enterprise_value"], exact.ev)
    assert close(res["bridge"]["equity_value"], exact.equity_pre)
    assert close(res["per_share"]["value_per_share"], exact.per_share)  # 31.2150…
    prov = r.json()["provenance"]
    assert prov["forecast.base_revenue"]["source_ref"].endswith("row 3, column FY2025")
    assert prov["forecast.base_nwc"]["basis"] == "derived"
    # C9: the rationale stored with the assumption is carried into provenance unchanged
    expected = next(
        a["rationale"]
        for a in KA_DCF03_ASSUMPTIONS
        if a["key"] == "revenue_growth" and a["year_index"] == 1
    )
    assert prov["forecast.years[1].revenue_growth"]["rationale"] == expected
    assert prov["dates"]["statement_date"] == "2025-03-31"
    assert prov["dates"]["market_data_date"] == "2025-04-30"
    codes = {w["code"] for w in r.json()["warnings"]}
    assert "DRIVER_OUTSIDE_HISTORY" not in codes  # drivers sit inside the history (LIM-12)


def test_frozen_run_is_retrievable_identical_and_verifiable(
    client: TestClient, auth: dict[str, str]
) -> None:
    ids = full_setup(client, auth)
    created = client.post(
        f"/api/v1/scenarios/{ids['scenario']}/runs",
        headers=idem(auth),
        json={"label": "Board pack v1"},
    )
    assert created.status_code == 201
    run = created.json()
    fetched = client.get(f"/api/v1/runs/{run['id']}", headers=auth).json()
    assert fetched["result"] == run["result"] and fetched["inputs"] == run["inputs"]
    assert fetched == run  # the whole payload, including created_at, renders identically
    assert fetched["input_hash"] == run["input_hash"] == run["result"]["input_hash"]
    v = client.post(f"/api/v1/runs/{run['id']}/verify", headers=auth).json()
    assert v["identical"] and v["inputs_round_trip_exact"] and v["input_hash_matches"]
    assert v["differing_paths"] == []
    assert v["value_per_share"]["stored"] == v["value_per_share"]["recomputed"]
    listed = client.get(f"/api/v1/scenarios/{ids['scenario']}/runs", headers=auth).json()
    assert [x["id"] for x in listed] == [run["id"]]


def test_editing_scenario_or_statements_never_changes_a_saved_run(
    client: TestClient, auth: dict[str, str]
) -> None:
    ids = full_setup(client, auth)
    run = client.post(
        f"/api/v1/scenarios/{ids['scenario']}/runs", headers=idem(auth), json={}
    ).json()
    edited = [dict(a) for a in KA_DCF03_ASSUMPTIONS]
    next(a for a in edited if a["key"] == "terminal_growth")["value"] = 0.03
    assert (
        client.put(
            f"/api/v1/scenarios/{ids['scenario']}",
            headers=auth,
            json={"settings": KA_DCF03_SETTINGS, "assumptions": edited},
        ).status_code
        == 200
    )
    fin = client.get(f"/api/v1/companies/{ids['company']}/financials", headers=auth).json()
    cash = next(li for li in fin["periods"][-1]["line_items"] if li["item_code"] == "cash")
    patched = client.patch(
        f"/api/v1/line-items/{cash['id']}",
        headers=auth,
        json={"value": 999.0, "basis": "assumed", "rationale": "test edit"},  # C6
    )
    assert patched.status_code == 200, patched.text  # the statement really changed
    again = client.get(f"/api/v1/runs/{run['id']}", headers=auth).json()
    assert again["result"] == run["result"]
    assert client.post(f"/api/v1/runs/{run['id']}/verify", headers=auth).json()["identical"]
    new = client.post(
        f"/api/v1/scenarios/{ids['scenario']}/runs", headers=idem(auth), json={}
    ).json()
    assert new["input_hash"] != run["input_hash"]
    assert (
        new["result"]["per_share"]["value_per_share"]
        != run["result"]["per_share"]["value_per_share"]
    )


def test_runs_cannot_be_altered_even_with_raw_sql(client: TestClient, auth: dict[str, str]) -> None:
    ids = full_setup(client, auth)
    run = client.post(
        f"/api/v1/scenarios/{ids['scenario']}/runs", headers=idem(auth), json={}
    ).json()
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        for sql in (
            "UPDATE valuation_runs SET result_json='{}' WHERE id=:i",
            "DELETE FROM valuation_runs WHERE id=:i",
        ):
            try:
                s.execute(text(sql), {"i": run["id"]})
                raise AssertionError("mutation was allowed")
            except DBAPIError as exc:
                assert "immutable" in str(exc)
                s.rollback()


def test_missing_inputs_are_calculation_errors_naming_the_field(
    client: TestClient, auth: dict[str, str]
) -> None:
    ids = full_setup(client, auth)
    url = f"/api/v1/scenarios/{ids['scenario']}"
    without_tax = [a for a in KA_DCF03_ASSUMPTIONS if a["key"] != "tax_rate"]
    client.put(url, headers=auth, json={"settings": KA_DCF03_SETTINGS, "assumptions": without_tax})
    r = client.post(f"{url}/preview", headers=auth)
    assert r.status_code == 422 and r.json()["error_type"] == "calculation"
    assert {(e["code"], e["field"]) for e in r.json()["errors"]} >= {("MISSING_INPUT", "tax_rate")}
    no_date = {**KA_DCF03_SETTINGS, "market_data_date": None}
    client.put(url, headers=auth, json={"settings": no_date, "assumptions": KA_DCF03_ASSUMPTIONS})
    r2 = client.post(f"{url}/runs", headers=idem(auth), json={})
    assert r2.status_code == 422
    assert r2.json()["errors"][0]["field"] == "market_data_date"


def test_missing_statement_value_is_never_zero(client: TestClient, auth: dict[str, str]) -> None:
    ids = full_setup(client, auth)
    fin = client.get(f"/api/v1/companies/{ids['company']}/financials", headers=auth).json()
    nci = next(
        li
        for li in fin["periods"][-1]["line_items"]
        if li["item_code"] == "non_controlling_interest"
    )
    patched = client.patch(
        f"/api/v1/line-items/{nci['id']}",
        headers=auth,
        json={"value": None, "basis": "assumed", "rationale": "unknown"},  # C6
    )
    assert patched.status_code == 200, patched.text
    r = client.post(f"/api/v1/scenarios/{ids['scenario']}/preview", headers=auth)
    assert r.status_code == 422
    assert ("MISSING_INPUT", "non_controlling_interest") in {
        (e["code"], e["field"]) for e in r.json()["errors"]
    }


def test_lim12_warning_surfaces_in_preview(client: TestClient, auth: dict[str, str]) -> None:
    ids = full_setup(client, auth)
    edited = [dict(a) for a in KA_DCF03_ASSUMPTIONS]
    next(a for a in edited if a["key"] == "ebitda_margin" and a["year_index"] == 3)["value"] = 0.35
    client.put(
        f"/api/v1/scenarios/{ids['scenario']}",
        headers=auth,
        json={"settings": KA_DCF03_SETTINGS, "assumptions": edited},
    )
    w = client.post(f"/api/v1/scenarios/{ids['scenario']}/preview", headers=auth).json()["warnings"]
    hits = [x for x in w if x["code"] == "DRIVER_OUTSIDE_HISTORY"]
    assert len(hits) == 1 and hits[0]["field"] == "years[3].ebitda_margin"


def test_scenario_validation_clone_and_listing(client: TestClient, auth: dict[str, str]) -> None:
    ids = full_setup(client, auth)
    bad = client.put(
        f"/api/v1/scenarios/{ids['scenario']}",
        headers=auth,
        json={
            "settings": KA_DCF03_SETTINGS,
            "assumptions": [
                # rationales added per C9; the invalid year and key are what is being tested
                {"key": "revenue_growth", "year_index": 7, "value": 0.1, "rationale": "test"},
                {"key": "made_up", "year_index": None, "value": 1.0, "rationale": "test"},
            ],
        },
    )
    assert bad.status_code == 422 and bad.json()["errors"][0]["code"] == "INVALID_ASSUMPTIONS"
    assert len(bad.json()["errors"][0]["detail"]) == 2
    clone = client.post(
        f"/api/v1/scenarios/{ids['scenario']}/clone",
        headers=auth,
        json={"name": "Downside", "kind": "downside"},
    )
    assert clone.status_code == 201
    a = client.get(f"/api/v1/scenarios/{ids['scenario']}", headers=auth).json()
    b = clone.json()
    assert a["assumptions"] == b["assumptions"] and a["settings"] == b["settings"]
    names = [
        s["name"]
        for s in client.get(f"/api/v1/projects/{ids['project']}/scenarios", headers=auth).json()
    ]
    assert names == ["Base", "Downside"]
    pa = client.post(f"/api/v1/scenarios/{ids['scenario']}/preview", headers=auth).json()
    pb = client.post(f"/api/v1/scenarios/{b['id']}/preview", headers=auth).json()
    assert pa["result"] == pb["result"]  # same inputs → byte-identical result
    dup = client.post(
        f"/api/v1/scenarios/{ids['scenario']}/clone",
        headers=auth,
        json={"name": "Downside", "kind": "downside"},
    )
    assert dup.status_code == 409
