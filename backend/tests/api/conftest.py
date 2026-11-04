"""API fixtures: a fresh migrated database per test and helpers that drive the real HTTP API."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "ardent_precision_synthetic.csv"
PASSWORD = "correct horse battery"

# KA-DCF-03 assumptions (docs/verification/independent-verification.md)
KA_DCF03_ASSUMPTIONS: list[dict[str, Any]] = [
    *[
        {"key": "revenue_growth", "year_index": t, "value": v, "rationale": "KA-DCF-03"}
        for t, v in enumerate([0.08, 0.07, 0.06, 0.05, 0.04], start=1)
    ],
    *[
        {"key": "ebitda_margin", "year_index": t, "value": v}
        for t, v in enumerate([0.18, 0.185, 0.19, 0.195, 0.20], start=1)
    ],
    *[{"key": "da_pct_revenue", "year_index": t, "value": 0.04} for t in range(1, 6)],
    *[
        {"key": "capex_pct_revenue", "year_index": t, "value": v}
        for t, v in enumerate([0.05, 0.05, 0.045, 0.045, 0.045], start=1)
    ],
    *[{"key": "nwc_pct_revenue", "year_index": t, "value": 0.15} for t in range(1, 6)],
    {"key": "tax_rate", "year_index": None, "value": 0.25},
    {"key": "terminal_growth", "year_index": None, "value": 0.025},
    {"key": "risk_free_rate", "year_index": None, "value": 0.045},
    {"key": "levered_beta", "year_index": None, "value": 1.1},
    {"key": "equity_risk_premium", "year_index": None, "value": 0.055},
    {"key": "pre_tax_cost_of_debt", "year_index": None, "value": 0.07},
    {"key": "size_premium", "year_index": None, "value": 0.0},
]
KA_DCF03_SETTINGS = {
    "market_data_date": "2025-04-30",
    "share_price": 20.0,
    "debt_value_basis": "book",
    "include_leases_in_debt": True,
}


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'api.sqlite3'}"))
    with TestClient(app) as c:
        yield c
    app.state.db_engine.dispose()


def login(client: TestClient, email: str = "analyst@example.com") -> dict[str, str]:
    r = client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    assert r.status_code in (201, 409), r.text
    r = client.post("/api/v1/auth/token", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client: TestClient) -> dict[str, str]:
    return login(client)


def create_company(client: TestClient, h: dict[str, str], **kw: Any) -> dict[str, Any]:
    body = {
        "name": "Ardent Precision Components (SYNTHETIC)",
        "sector": "Industrials",
        "currency": "INR",
        "scale": "crores",
        "fiscal_year_end_month": 3,
        "is_financial_institution": False,
        "is_synthetic": True,
        **kw,
    }
    r = client.post("/api/v1/companies", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def import_csv(
    client: TestClient,
    h: dict[str, str],
    company_id: int,
    data: bytes | None = None,
    *,
    dry_run: bool = False,
    replace: bool = False,
    scale: str = "crores",
    currency: str = "INR",
) -> Any:
    return client.post(
        f"/api/v1/companies/{company_id}/financials/import",
        headers=h,
        files={"file": ("ardent_precision_synthetic.csv", data or SAMPLE.read_bytes(), "text/csv")},
        data={
            "currency": currency,
            "scale": scale,
            "basis": "reported",
            "dry_run": str(dry_run).lower(),
            "replace": str(replace).lower(),
        },
    )


def set_instruments(client: TestClient, h: dict[str, str], company_id: int) -> None:
    r = client.put(
        f"/api/v1/companies/{company_id}/share-instruments",
        headers=h,
        json={
            "source_title": "FY2025 annual report, note 28 (SYNTHETIC)",
            "source_ref": "note 28",
            "instruments": [
                {"kind": "option", "label": "ESOP 2021", "count": 5.0, "strike": 12.0},
                {"kind": "rsu", "label": "RSU plan", "count": 1.0},
            ],
        },
    )
    assert r.status_code == 200, r.text


def full_setup(client: TestClient, h: dict[str, str]) -> dict[str, int]:
    """Company → CSV import → instruments → project → KA-DCF-03 scenario."""
    c = create_company(client, h)
    assert import_csv(client, h, c["id"]).status_code == 200
    set_instruments(client, h, c["id"])
    p = client.post(
        "/api/v1/projects",
        headers=h,
        json={"company_id": c["id"], "name": "Ardent valuation", "description": None},
    ).json()
    s = client.post(
        f"/api/v1/projects/{p['id']}/scenarios",
        headers=h,
        json={
            "name": "Base",
            "kind": "base",
            "settings": KA_DCF03_SETTINGS,
            "assumptions": KA_DCF03_ASSUMPTIONS,
        },
    )
    assert s.status_code == 201, s.text
    return {"company": c["id"], "project": p["id"], "scenario": s.json()["id"]}
