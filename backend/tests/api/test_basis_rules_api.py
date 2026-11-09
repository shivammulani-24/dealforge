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

    instruments_source = client.get(
        f"/api/v1/companies/{ids['company']}/share-instruments", headers=auth
    ).json()[0]["source_id"]  # kind manual (Phase 3)
    manual = put(
        client, auth, sid, with_row(basis="reported", rationale=None, source_id=instruments_source)
    )
    assert manual.status_code == 422 and manual.json()["errors"][0]["code"] == "BASIS_SOURCE_KIND"

    other = login(client, "other@example.com")
    other_ids = full_setup(client, other)
    theirs = client.get(
        f"/api/v1/companies/{other_ids['company']}/financials", headers=other
    ).json()["periods"][-1]["line_items"][0]["source_id"]
    foreign = put(client, auth, sid, with_row(basis="reported", rationale=None, source_id=theirs))
    assert foreign.status_code == 404  # another user's source does not exist for this user
