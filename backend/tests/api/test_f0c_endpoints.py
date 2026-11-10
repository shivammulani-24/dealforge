"""F0c endpoints: draft preview (B4), context/presentation (B5), runs list (B2), sensitivity (B3),
dashboard (B1), sources (B7), completeness and metric definitions (B8, B10)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from conftest import KA_DCF03_ASSUMPTIONS, KA_DCF03_SETTINGS, full_setup, idem, login
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from app.services import sensitivity as sens_svc
from verification import independent as ind

GRID = {
    "row": {"variable": "wacc", "step": 0.005, "steps_each_side": 1},
    "col": {"variable": "terminal_growth", "step": 0.005, "steps_each_side": 1},
    "output": "value_per_share",
}


def freeze(client: TestClient, h: dict[str, str], sid: int, label: str | None = None) -> Any:
    r = client.post(f"/api/v1/scenarios/{sid}/runs", headers=idem(h), json={"label": label})
    assert r.status_code == 201, r.text
    return r.json()


class WriteProbe:
    """Records every INSERT/UPDATE/DELETE the engine executes while active."""

    def __init__(self, engine: Any) -> None:
        self.engine, self.writes = engine, []  # type: ignore[var-annotated]

    def _on(self, conn: Any, cursor: Any, statement: str, *a: Any) -> None:
        if statement.lstrip().split(" ", 1)[0].upper() in ("INSERT", "UPDATE", "DELETE"):
            self.writes.append(statement)

    def __enter__(self) -> WriteProbe:
        event.listen(self.engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc: object) -> None:
        event.remove(self.engine, "before_cursor_execute", self._on)


def table_counts(client: TestClient) -> dict[str, int]:
    tables = [
        "companies",
        "line_items",
        "scenarios",
        "assumptions",
        "valuation_runs",
        "audit_events",
        "sources",
    ]
    with client.app.state.db_engine.connect() as c:  # type: ignore[attr-defined]
        return {t: c.exec_driver_sql(f"SELECT COUNT(*) FROM {t}").scalar_one() for t in tables}


# ------------------------------------------------------------------ B4 draft preview, B5 blocks


def test_draft_preview_writes_nothing(client: TestClient, auth: dict[str, str]) -> None:
    ids = full_setup(client, auth)
    draft = [dict(a) for a in KA_DCF03_ASSUMPTIONS]
    next(a for a in draft if a["key"] == "terminal_growth")["value"] = 0.03
    before = table_counts(client)
    with WriteProbe(client.app.state.db_engine) as probe:  # type: ignore[attr-defined]
        r = client.post(
            f"/api/v1/scenarios/{ids['scenario']}/preview",
            headers=auth,
            json={"settings": KA_DCF03_SETTINGS, "assumptions": draft},
        )
    assert r.status_code == 200, r.text
    assert probe.writes == [] and table_counts(client) == before
    body = r.json()
    assert body["draft"] is True
    assert body["provenance"]["terminal_growth"]["draft"] is True
    assert body["provenance"]["terminal_growth"]["assumption_id"] is None
    saved = client.post(f"/api/v1/scenarios/{ids['scenario']}/preview", headers=auth).json()
    assert saved["draft"] is False
    assert (
        body["result"]["per_share"]["value_per_share"]
        > saved["result"]["per_share"]["value_per_share"]
    )  # higher g, higher value; the saved scenario is untouched


def test_draft_equal_to_saved_gives_an_identical_result(
    client: TestClient, auth: dict[str, str]
) -> None:
    ids = full_setup(client, auth)
    url = f"/api/v1/scenarios/{ids['scenario']}/preview"
    saved = client.post(url, headers=auth).json()
    draft = client.post(
        url, headers=auth, json={"settings": KA_DCF03_SETTINGS, "assumptions": KA_DCF03_ASSUMPTIONS}
    ).json()
    assert draft["result"] == saved["result"] and draft["input_hash"] == saved["input_hash"]


def test_draft_is_validated_like_a_save(client: TestClient, auth: dict[str, str]) -> None:
    ids = full_setup(client, auth)
    url = f"/api/v1/scenarios/{ids['scenario']}/preview"
    bad_key = [
        *KA_DCF03_ASSUMPTIONS,
        {"key": "made_up", "year_index": None, "value": 1.0, "rationale": "x"},
    ]
    r = client.post(url, headers=auth, json={"settings": KA_DCF03_SETTINGS, "assumptions": bad_key})
    assert r.status_code == 422 and r.json()["errors"][0]["code"] == "INVALID_ASSUMPTIONS"
    no_reason = [dict(a) for a in KA_DCF03_ASSUMPTIONS]
    no_reason[0]["rationale"] = None
    r2 = client.post(
        url, headers=auth, json={"settings": KA_DCF03_SETTINGS, "assumptions": no_reason}
    )
    assert r2.status_code == 422 and r2.json()["error_type"] == "validation"
    other = login(client, "other@example.com")
    r3 = client.post(
        url,
        headers=other,
        json={"settings": KA_DCF03_SETTINGS, "assumptions": KA_DCF03_ASSUMPTIONS},
    )
    assert r3.status_code == 404


def test_context_and_presentation_blocks(client: TestClient, auth: dict[str, str]) -> None:
    ids = full_setup(client, auth)
    pv = client.post(f"/api/v1/scenarios/{ids['scenario']}/preview", headers=auth).json()
    assert pv["context"]["company"] == {
        "id": ids["company"],
        "name": "Ardent Precision Components (SYNTHETIC)",
        "currency": "INR",
        "scale": "crores",
        "is_synthetic": True,
    }
    assert pv["result_basis"] == "derived" and pv["presentation"]["basis"] == "derived"
    y1 = pv["presentation"]["years"][0]
    assert y1["ebit_margin"]["value"] == pytest.approx(302.4 / 2160)  # KA-DCF-03 Y1
    assert y1["ufcf_margin"]["value"] == pytest.approx(181.2 / 2160)
    assert "presentation" not in pv["result"]  # never inside the frozen result
    run = freeze(client, auth, ids["scenario"])
    assert run["presentation"] == pv["presentation"] and run["context"] == pv["context"]
    assert run["engine_compatible"] is True


# ------------------------------------------------------------------ B2 runs list


def test_global_runs_list_paginates_filters_and_matches_stored_values(
    client: TestClient, auth: dict[str, str]
) -> None:
    ids = full_setup(client, auth)
    runs = [freeze(client, auth, ids["scenario"], f"run {i}") for i in range(3)]
    page1 = client.get("/api/v1/runs?page=1&page_size=2", headers=auth).json()
    page2 = client.get("/api/v1/runs?page=2&page_size=2", headers=auth).json()
    assert page1["total"] == 3 and len(page1["items"]) == 2 and len(page2["items"]) == 1
    assert [i["id"] for i in page1["items"] + page2["items"]] == [r["id"] for r in runs[::-1]]
    item = page1["items"][0]
    stored = client.get(f"/api/v1/runs/{item['id']}", headers=auth).json()
    assert item["value_per_share"] == stored["result"]["per_share"]["value_per_share"]
    assert item["enterprise_value"] == stored["result"]["valuation"]["enterprise_value"]
    assert item["valuation_date"] == "2025-03-31" and item["company"]["currency"] == "INR"
    assert item["engine_compatible"] is True
    for q in (
        f"company_id={ids['company']}",
        f"project_id={ids['project']}",
        f"scenario_id={ids['scenario']}",
    ):
        assert client.get(f"/api/v1/runs?{q}", headers=auth).json()["total"] == 3
    assert client.get("/api/v1/runs?company_id=999", headers=auth).json()["total"] == 0
    for bad in ("page=0", "page_size=0", "page_size=101"):
        r = client.get(f"/api/v1/runs?{bad}", headers=auth)
        assert r.status_code == 422 and r.json()["error_type"] == "validation"
    other = login(client, "other@example.com")
    assert client.get("/api/v1/runs", headers=other).json()["total"] == 0
    assert (
        client.get(f"/api/v1/runs?company_id={ids['company']}", headers=other).json()["items"] == []
    )


# ------------------------------------------------------------------ B3 sensitivity


def test_sensitivity_from_a_frozen_run(client: TestClient, auth: dict[str, str]) -> None:
    ids = full_setup(client, auth)
    run = freeze(client, auth, ids["scenario"])
    r = client.post(f"/api/v1/runs/{run['id']}/sensitivity", headers=auth, json=GRID)
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["base_matches_run"] is True and g["basis"] == "derived"
    base = g["cells"][1][1]
    assert base["value"] == run["result"]["per_share"]["value_per_share"]  # exact
    assert base["value"] == pytest.approx(float(ind.dcf_check().per_share), rel=1e-12)
    assert base["change_abs"] == 0.0 and base["change_pct"]["value"] == 0.0
    assert g["row_values"][1] == run["result"]["wacc"]  # axis built around the frozen base
    vals = [[c["value"] for c in row] for row in g["cells"]]
    assert vals[0][1] > vals[1][1] > vals[2][1]  # higher WACC, lower value
    assert vals[1][0] < vals[1][1] < vals[1][2]  # higher g, higher value
    assert g["context"]["company"]["scale"] == "crores"


def test_sensitivity_ignores_later_scenario_edits(client: TestClient, auth: dict[str, str]) -> None:
    ids = full_setup(client, auth)
    run = freeze(client, auth, ids["scenario"])
    before = client.post(f"/api/v1/runs/{run['id']}/sensitivity", headers=auth, json=GRID).json()
    edited = [dict(a) for a in KA_DCF03_ASSUMPTIONS]
    next(a for a in edited if a["key"] == "terminal_growth")["value"] = 0.035
    client.put(
        f"/api/v1/scenarios/{ids['scenario']}",
        headers=auth,
        json={"settings": KA_DCF03_SETTINGS, "assumptions": edited},
    )
    after = client.post(f"/api/v1/runs/{run['id']}/sensitivity", headers=auth, json=GRID).json()
    assert after == before  # frozen inputs only (R1)


def test_engine_version_mismatch_refuses_but_keeps_results(
    client: TestClient, auth: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = full_setup(client, auth)
    run = freeze(client, auth, ids["scenario"])
    monkeypatch.setattr(sens_svc, "ENGINE_VERSION", "9.9.9")
    r = client.post(f"/api/v1/runs/{run['id']}/sensitivity", headers=auth, json=GRID)
    assert r.status_code == 409 and r.json()["errors"][0]["code"] == "ENGINE_VERSION_MISMATCH"
    assert r.json()["error_type"] == "conflict"
    stored = client.get(f"/api/v1/runs/{run['id']}", headers=auth)
    assert stored.status_code == 200 and stored.json()["result"] == run["result"]
    from app.services import valuations as vsvc

    monkeypatch.setattr(vsvc, "ENGINE_VERSION", "9.9.9")
    v = client.post(f"/api/v1/runs/{run['id']}/verify", headers=auth).json()
    assert v["engine_version_changed"] is True and v["identical"] is True
    assert (
        client.get(f"/api/v1/runs/{run['id']}", headers=auth).json()["engine_compatible"] is False
    )


def test_corrupted_frozen_inputs_are_refused(client: TestClient, auth: dict[str, str]) -> None:
    ids = full_setup(client, auth)
    run = freeze(client, auth, ids["scenario"])
    with client.app.state.db_engine.connect() as c:  # type: ignore[attr-defined]
        c.exec_driver_sql("DROP TRIGGER valuation_runs_no_update")  # simulate tampering
        stored = json.loads(
            c.exec_driver_sql(
                "SELECT inputs_json FROM valuation_runs WHERE id = ?", (run["id"],)
            ).scalar_one()
        )
        stored["terminal_growth"] = 0.0251
        c.execute(
            text("UPDATE valuation_runs SET inputs_json = :j WHERE id = :i"),
            {"j": json.dumps(stored, sort_keys=True, separators=(",", ":")), "i": run["id"]},
        )
        c.commit()
    r = client.post(f"/api/v1/runs/{run['id']}/sensitivity", headers=auth, json=GRID)
    assert r.status_code == 409 and r.json()["errors"][0]["code"] == "RUN_INPUTS_CORRUPT"


@pytest.mark.parametrize(
    "patch",
    [
        {"row": {"variable": "wacc", "step": 0.1, "steps_each_side": 1}},
        {"row": {"variable": "wacc", "step": 0.005, "steps_each_side": 6}},
        {"row": {"variable": "tax_rate", "step": 0.001, "steps_each_side": 1}},
        {"col": {"variable": "wacc", "step": 0.005, "steps_each_side": 1}},
        {"output": "ebitda"},
        {"row": {"variable": "beta", "step": 0.1, "steps_each_side": 1}},
    ],
)
def test_sensitivity_limits_are_validation_errors(
    client: TestClient, auth: dict[str, str], patch: dict[str, Any]
) -> None:
    ids = full_setup(client, auth)
    run = freeze(client, auth, ids["scenario"])
    r = client.post(f"/api/v1/runs/{run['id']}/sensitivity", headers=auth, json={**GRID, **patch})
    assert r.status_code == 422 and r.json()["error_type"] == "validation"


def test_sensitivity_is_owner_only(client: TestClient, auth: dict[str, str]) -> None:
    ids = full_setup(client, auth)
    run = freeze(client, auth, ids["scenario"])
    other = login(client, "other@example.com")
    r = client.post(f"/api/v1/runs/{run['id']}/sensitivity", headers=other, json=GRID)
    assert r.status_code == 404


# ------------------------------------------------------------------ B1 dashboard


def test_dashboard_for_a_new_user_and_after_activity(
    client: TestClient, auth: dict[str, str]
) -> None:
    empty = client.get("/api/v1/dashboard", headers=auth).json()
    assert empty["counts"] == {"companies": 0, "projects": 0, "scenarios": 0, "runs": 0}
    assert not any(s["done"] for s in empty["onboarding"]["steps"])
    assert empty["onboarding"]["sample_loaded"] is False
    assert empty["recent_runs"] == empty["recent_companies"] == empty["recent_activity"] == []

    ids = full_setup(client, auth)
    mid = client.get("/api/v1/dashboard", headers=auth).json()
    assert [s["done"] for s in mid["onboarding"]["steps"]] == [True, True, True, False]
    run = freeze(client, auth, ids["scenario"])
    d = client.get("/api/v1/dashboard", headers=auth).json()
    assert d["counts"] == {"companies": 1, "projects": 1, "scenarios": 1, "runs": 1}
    assert d["onboarding"]["complete"] is True
    assert d["recent_runs"][0]["id"] == run["id"]
    assert d["recent_runs"][0]["value_per_share"] == run["result"]["per_share"]["value_per_share"]
    assert d["recent_companies"][0]["id"] == ids["company"]
    assert d["recent_companies"][0]["fiscal_years"] == [2023, 2024, 2025]
    summaries = [a["summary"] for a in d["recent_activity"]]
    assert summaries[0].startswith(f"Froze run {run['id']} for scenario 'Base'")
    assert "Imported financial statements (FY2023–FY2025)" in summaries
    assert all("detail" not in a for a in d["recent_activity"])  # raw detail never exposed
    other = login(client, "other@example.com")
    assert client.get("/api/v1/dashboard", headers=other).json()["counts"]["runs"] == 0


# ------------------------------------------------------------------ B7 sources, B8, B10


def test_sources_get_and_create(client: TestClient, auth: dict[str, str]) -> None:
    ids = full_setup(client, auth)
    fin = client.get(f"/api/v1/companies/{ids['company']}/financials", headers=auth).json()
    sid = fin["periods"][0]["line_items"][0]["source_id"]
    src = client.get(f"/api/v1/sources/{sid}", headers=auth).json()
    assert src["kind"] == "csv_import" and len(src["file_sha256"]) == 64
    made = client.post(
        "/api/v1/sources",
        headers=auth,
        json={
            "kind": "market_data",
            "title": "Exchange close 30 Apr 2025 (SYNTHETIC)",
            "reference": "closing price",
        },
    )
    assert made.status_code == 201 and made.json()["kind"] == "market_data"
    for kind in ("manual", "csv_import", "synthetic"):
        bad = client.post("/api/v1/sources", headers=auth, json={"kind": kind, "title": "x"})
        assert bad.status_code == 422, kind
    settings = {
        **KA_DCF03_SETTINGS,
        "market_source_id": made.json()["id"],
        "market_rationale": None,
    }
    put = client.put(
        f"/api/v1/scenarios/{ids['scenario']}",
        headers=auth,
        json={"settings": settings, "assumptions": KA_DCF03_ASSUMPTIONS},
    )
    assert put.status_code == 200, put.text
    pv = client.post(f"/api/v1/scenarios/{ids['scenario']}/preview", headers=auth).json()
    assert pv["provenance"]["current_share_price"]["basis"] == "reported"  # C5 with a source
    other = login(client, "other@example.com")
    assert client.get(f"/api/v1/sources/{sid}", headers=other).status_code == 404


def test_completeness_groups(client: TestClient, auth: dict[str, str]) -> None:
    ids = full_setup(client, auth)
    fin = client.get(f"/api/v1/companies/{ids['company']}/financials", headers=auth).json()
    fy23, fy25 = fin["periods"][0]["completeness"], fin["periods"][-1]["completeness"]
    assert (fy25["present"], fy25["missing"], fy25["absent"]) == (31, 0, 1)  # adjusted absent
    assert (fy23["present"], fy23["missing"]) == (30, 1)  # reported_ebitda blank in FY2023
    assert fy25["groups"]["dcf"]["complete"] and fy25["groups"]["liquidity"]["complete"]
    assert len(fy25["groups"]["dcf"]["required"]) == 12
    ms = next(
        li for li in fin["periods"][-1]["line_items"] if li["item_code"] == "marketable_securities"
    )
    client.patch(
        f"/api/v1/line-items/{ms['id']}",
        headers=auth,
        json={"value": None, "basis": "assumed", "rationale": "not disclosed"},
    )
    after = client.get(f"/api/v1/companies/{ids['company']}/financials", headers=auth).json()[
        "periods"
    ][-1]["completeness"]
    assert after["groups"]["liquidity"]["missing"] == ["marketable_securities"]
    assert after["groups"]["dcf"]["complete"] is True  # liquidity gaps never affect the DCF


def test_metric_definitions_cover_every_metric(client: TestClient, auth: dict[str, str]) -> None:
    ids = full_setup(client, auth)
    a = client.get(f"/api/v1/companies/{ids['company']}/historical-analysis", headers=auth).json()
    defs = a["metric_definitions"]
    for p in a["periods"]:
        assert set(p["metrics"]) <= set(defs)
        assert all(m["basis"] == "derived" for m in p["metrics"].values())
    fy25 = a["periods"][-1]["metrics"]
    assert fy25["current_ratio"]["value"] == 2.0 and fy25["cash_ratio"]["value"] == 0.5
    assert defs["quick_ratio"]["items"] == [
        "cash",
        "marketable_securities",
        "accounts_receivable",
        "total_current_liabilities",
    ]
