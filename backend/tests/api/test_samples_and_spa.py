"""B9 sample company (R4, R5) and B11 production static serving with SPA fallback (D4-07)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import idem, login
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import valuations as vsvc
from verification import independent as ind

LOAD = "/api/v1/samples/ardent-precision/load"


def table_counts(client: TestClient) -> dict[str, int]:
    tables = [
        "companies",
        "line_items",
        "sources",
        "share_instruments",
        "valuation_projects",
        "scenarios",
        "assumptions",
        "audit_events",
    ]
    with client.app.state.db_engine.connect() as c:  # type: ignore[attr-defined]
        return {t: c.exec_driver_sql(f"SELECT COUNT(*) FROM {t}").scalar_one() for t in tables}


def test_sample_listing_is_labelled_synthetic(client: TestClient, auth: dict[str, str]) -> None:
    s = client.get("/api/v1/samples", headers=auth).json()
    assert [x["id"] for x in s] == ["ardent-precision"]
    assert s[0]["is_synthetic"] is True and "SYNTHETIC" in s[0]["name"]
    assert "not real company data" in s[0]["description"]


def test_loaded_sample_is_complete_and_reproduces_ka_dcf03(
    client: TestClient, auth: dict[str, str]
) -> None:
    r = client.post(LOAD, headers=auth)
    assert r.status_code == 201, r.text
    ids = r.json()
    fin = client.get(f"/api/v1/companies/{ids['company_id']}/financials", headers=auth).json()
    assert [p["fiscal_year"] for p in fin["periods"]] == [2023, 2024, 2025]
    for p in fin["periods"]:
        assert p["completeness"]["groups"]["dcf"]["complete"]
        assert p["completeness"]["groups"]["liquidity"]["complete"]
        for li in p["line_items"]:
            assert li["source_id"] and li["source_ref"] and li["basis"] == "reported"
    src = client.get(
        f"/api/v1/sources/{fin['periods'][0]['line_items'][0]['source_id']}", headers=auth
    ).json()
    assert src["kind"] == "synthetic" and len(src["file_sha256"]) == 64
    sc = client.get(f"/api/v1/scenarios/{ids['scenario_id']}", headers=auth).json()
    assert len(sc["assumptions"]) == 32 and all(a["rationale"] for a in sc["assumptions"])
    pv = client.post(f"/api/v1/scenarios/{ids['scenario_id']}/preview", headers=auth).json()
    vps = pv["result"]["per_share"]["value_per_share"]
    assert vps == pytest.approx(float(ind.dcf_check().per_share), rel=1e-12)  # 31.2150
    ana = client.get(
        f"/api/v1/companies/{ids['company_id']}/historical-analysis", headers=auth
    ).json()
    assert ana["periods"][-1]["metrics"]["quick_ratio"]["value"] == pytest.approx(400 / 300)
    d = client.get("/api/v1/dashboard", headers=auth).json()
    assert d["onboarding"]["sample_loaded"] is True
    assert d["recent_activity"][0]["summary"] == "Loaded the synthetic sample company"
    run = client.post(
        f"/api/v1/scenarios/{ids['scenario_id']}/runs", headers=idem(auth), json={"label": "sample"}
    )
    assert run.status_code == 201
    assert client.get("/api/v1/dashboard", headers=auth).json()["onboarding"]["complete"]


def test_loading_twice_returns_the_existing_ids(client: TestClient, auth: dict[str, str]) -> None:
    first = client.post(LOAD, headers=auth).json()
    again = client.post(LOAD, headers=auth)
    assert again.status_code == 409 and again.json()["error_type"] == "conflict"
    err = again.json()["errors"][0]
    assert err["code"] == "SAMPLE_ALREADY_LOADED"
    assert err["detail"] == first
    other = login(client, "other@example.com")  # per user: another user can load their own
    assert client.post(LOAD, headers=other).status_code == 201


def test_sample_load_is_atomic(
    client: TestClient, auth: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    before = table_counts(client)

    def boom(*a: Any, **k: Any) -> None:
        raise RuntimeError("injected failure after statements and instruments were written")

    monkeypatch.setattr(vsvc, "apply_scenario_payload", boom)
    with pytest.raises(RuntimeError):
        client.post(LOAD, headers=auth)
    assert table_counts(client) == before  # nothing half-created


def test_unknown_sample_is_not_found(client: TestClient, auth: dict[str, str]) -> None:
    assert client.post("/api/v1/samples/nope/load", headers=auth).status_code == 404


# ------------------------------------------------------------------ B11 SPA serving


@pytest.fixture
def spa(tmp_path: Path) -> Iterator[tuple[FastAPI, TestClient]]:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>DealForge</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    app = create_app(
        Settings(database_url=f"sqlite:///{tmp_path / 'spa.sqlite3'}", frontend_dist=str(dist))
    )
    with TestClient(app) as c:
        yield app, c
    app.state.db_engine.dispose()


def test_client_side_routes_get_index_html(spa: tuple[FastAPI, TestClient]) -> None:
    _, c = spa
    for path in ("/", "/companies/1/analysis", "/runs/42/sensitivity"):
        r = c.get(path)
        assert r.status_code == 200 and "DealForge" in r.text, path
        assert r.headers["cache-control"] == "no-cache"
        assert "default-src 'self'" in r.headers["content-security-policy"]
    assert c.head("/companies/1").status_code == 200


def test_real_files_and_assets(spa: tuple[FastAPI, TestClient]) -> None:
    _, c = spa
    assert c.get("/assets/app.js").text == "console.log(1)"
    assert c.get("/favicon.svg").text == "<svg/>"
    missing = c.get("/assets/missing.js")
    assert missing.status_code == 404 and "DealForge" not in missing.text  # never index.html


def test_api_and_docs_are_never_intercepted(spa: tuple[FastAPI, TestClient]) -> None:
    _, c = spa
    for method in ("get", "post", "delete"):
        r = getattr(c, method)("/api/v1/does-not-exist")
        assert r.status_code == 404, method
        assert r.headers["content-type"].startswith("application/json")
        assert r.json()["error_type"] == "not_found"
    unauth = c.get("/api/v1/companies")
    assert unauth.status_code == 401 and unauth.json()["error_type"] == "authentication"
    assert c.get("/api/v1/health").json()["status"] == "ok"
    assert c.get("/openapi.json").json()["info"]["title"] == "DealForge API"
    assert "swagger" in c.get("/docs").text.lower()


def test_non_get_on_spa_paths_is_405(spa: tuple[FastAPI, TestClient]) -> None:
    _, c = spa
    r = c.post("/companies/1")
    assert r.status_code == 405 and r.json()["error_type"] == "method_not_allowed"


def test_fallback_is_registered_after_every_api_route(spa: tuple[FastAPI, TestClient]) -> None:
    app, _ = spa
    paths = [getattr(r, "path", "") for r in app.routes]
    fallback = paths.index("/{full_path:path}")
    api_paths = [i for i, p in enumerate(paths) if p.startswith("/api/")]
    assert api_paths and max(api_paths) < fallback


def test_without_a_build_the_api_runs_unchanged(client: TestClient) -> None:
    assert client.get("/companies/1").status_code == 404
    assert client.get("/api/v1/health").status_code == 200
