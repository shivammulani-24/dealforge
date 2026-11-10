"""Basis rules at the API (A4–A6). Database triggers for the same rules arrive in F0b."""

from __future__ import annotations

from typing import Any

from conftest import KA_DCF03_ASSUMPTIONS, KA_DCF03_SETTINGS, full_setup, login
from fastapi.testclient import TestClient


def put(client: TestClient, h: dict[str, str], sid: int, rows: list[dict[str, Any]]) -> Any:
    return client.put(
        f"/api/v1/scenarios/{sid}",
        headers=h,
        json={"settings": KA_DCF03_SETTINGS, "assumptions": rows},
    )


def with_row(**kw: Any) -> list[dict[str, Any]]:
    rows = [dict(a) for a in KA_DCF03_ASSUMPTIONS]
    rows[0] = {**rows[0], **kw}
    return rows


def manual_source(client: TestClient, h: dict[str, str], company: int) -> int:
    """A genuinely 'manual' source: the one an assumed PATCH correction creates."""
    fin = client.get(f"/api/v1/companies/{company}/financials", headers=h).json()
    li = next(x for x in fin["periods"][-1]["line_items"] if x["item_code"] == "total_assets")
    r = client.patch(
        f"/api/v1/line-items/{li['id']}",
        headers=h,
        json={"value": li["value"], "basis": "assumed", "rationale": "restated"},
    )
    assert r.status_code == 200
    src = client.get(f"/api/v1/sources/{r.json()['source_id']}", headers=h).json()
    assert src["kind"] == "manual"
    return int(src["id"])


def test_assumed_requires_a_non_blank_rationale(client: TestClient, auth: dict[str, str]) -> None:
    sid = full_setup(client, auth)["scenario"]
    for bad in (None, "", "   ", "x" * 2001):
        r = put(client, auth, sid, with_row(rationale=bad))
        assert r.status_code == 422 and r.json()["error_type"] == "validation", bad
        assert r.json()["errors"][0]["code"] == "rationale_required"
    assert put(client, auth, sid, with_row(rationale="x" * 2000)).status_code == 200


def test_derived_basis_cannot_be_submitted(client: TestClient, auth: dict[str, str]) -> None:
    sid = full_setup(client, auth)["scenario"]
    r = put(client, auth, sid, with_row(basis="derived"))
    assert r.status_code == 422 and r.json()["error_type"] == "validation"
    assert r.json()["errors"][0]["loc"][-1] == "basis"


def test_reported_requires_a_qualifying_owned_source(
    client: TestClient, auth: dict[str, str]
) -> None:
    ids = full_setup(client, auth)
    sid = ids["scenario"]
    no_source = put(client, auth, sid, with_row(basis="reported", rationale=None))
    assert no_source.status_code == 422
    assert no_source.json()["errors"][0]["code"] == "basis_source_required"

    fin = client.get(f"/api/v1/companies/{ids['company']}/financials", headers=auth).json()
    csv_source = fin["periods"][-1]["line_items"][0]["source_id"]  # kind csv_import: qualifies
    ok = put(client, auth, sid, with_row(basis="reported", rationale=None, source_id=csv_source))
    assert ok.status_code == 200, ok.text

    manual_src = manual_source(client, auth, ids["company"])
    manual = put(
        client, auth, sid, with_row(basis="reported", rationale=None, source_id=manual_src)
    )
    assert manual.status_code == 422 and manual.json()["errors"][0]["code"] == "BASIS_SOURCE_KIND"

    other = login(client, "other@example.com")
    other_ids = full_setup(client, other)
    theirs = client.get(
        f"/api/v1/companies/{other_ids['company']}/financials", headers=other
    ).json()["periods"][-1]["line_items"][0]["source_id"]
    foreign = put(client, auth, sid, with_row(basis="reported", rationale=None, source_id=theirs))
    assert foreign.status_code == 404  # another user's source does not exist for this user


def _cash(client: TestClient, h: dict[str, str], company: int) -> dict[str, Any]:
    fin = client.get(f"/api/v1/companies/{company}/financials", headers=h).json()
    return next(li for li in fin["periods"][-1]["line_items"] if li["item_code"] == "cash")


def test_patch_reported_needs_a_source_document(client: TestClient, auth: dict[str, str]) -> None:
    ids = full_setup(client, auth)
    url = f"/api/v1/line-items/{_cash(client, auth, ids['company'])['id']}"
    bad = client.patch(url, headers=auth, json={"value": 151.0, "basis": "reported"})
    assert bad.status_code == 422 and bad.json()["errors"][0]["code"] == "basis_source_required"
    ok = client.patch(
        url,
        headers=auth,
        json={
            "value": 151.0,
            "basis": "reported",
            "source": {"title": "FY2025 annual report (SYNTHETIC)", "reference": "p. 42"},
        },
    )
    assert ok.status_code == 200 and ok.json()["basis"] == "reported"
    li = _cash(client, auth, ids["company"])
    assert (li["value"], li["basis"], li["source_ref"]) == (151.0, "reported", "p. 42")
    src = client.get(f"/api/v1/companies/{ids['company']}/financials", headers=auth).json()
    assert li["source_title"] == "FY2025 annual report (SYNTHETIC)" and src


def test_patch_rejects_derived_and_unexplained_assumptions(
    client: TestClient, auth: dict[str, str]
) -> None:
    ids = full_setup(client, auth)
    url = f"/api/v1/line-items/{_cash(client, auth, ids['company'])['id']}"
    for body in (
        {"value": 1.0, "basis": "derived"},
        {"value": 1.0, "basis": "assumed"},
        {"value": 1.0, "basis": "assumed", "rationale": "  "},
        {"value": 1.0, "note": "the Phase 3 body"},
    ):
        r = client.patch(url, headers=auth, json=body)
        assert r.status_code == 422 and r.json()["error_type"] == "validation", body


def test_import_as_assumed_needs_a_rationale(client: TestClient, auth: dict[str, str]) -> None:
    from conftest import SAMPLE, create_company

    c = create_company(client, auth, name="Assumed Co (SYNTHETIC)")
    form = {"currency": "INR", "scale": "crores", "basis": "assumed", "dry_run": "false"}
    files = {"file": ("s.csv", SAMPLE.read_bytes(), "text/csv")}
    r = client.post(
        f"/api/v1/companies/{c['id']}/financials/import", headers=auth, files=files, data=form
    )
    assert r.status_code == 422 and r.json()["error_type"] == "import"
    form["rationale"] = "Management projections for illustration (SYNTHETIC)"
    ok = client.post(
        f"/api/v1/companies/{c['id']}/financials/import", headers=auth, files=files, data=form
    )
    assert ok.status_code == 200, ok.text
    li = _cash(client, auth, c["id"])
    assert li["basis"] == "assumed" and li["note"] == form["rationale"]


def test_market_price_needs_a_source_or_a_rationale(
    client: TestClient, auth: dict[str, str]
) -> None:
    ids = full_setup(client, auth)
    sid = ids["scenario"]
    settings = {k: v for k, v in KA_DCF03_SETTINGS.items() if k != "market_rationale"}
    r = client.put(
        f"/api/v1/scenarios/{sid}",
        headers=auth,
        json={"settings": settings, "assumptions": KA_DCF03_ASSUMPTIONS},
    )
    assert r.status_code == 422 and r.json()["errors"][0]["code"] == "rationale_required"

    manual_src = manual_source(client, auth, ids["company"])
    manual = client.put(
        f"/api/v1/scenarios/{sid}",
        headers=auth,
        json={
            "settings": {**settings, "market_source_id": manual_src},
            "assumptions": KA_DCF03_ASSUMPTIONS,
        },
    )
    assert manual.status_code == 422 and manual.json()["errors"][0]["code"] == "BASIS_SOURCE_KIND"

    preview = client.post(f"/api/v1/scenarios/{sid}/preview", headers=auth).json()
    price = preview["provenance"]["current_share_price"]
    assert price["basis"] == "assumed"  # C5: no market source, so not "reported"
    assert price["rationale"] == KA_DCF03_SETTINGS["market_rationale"]
