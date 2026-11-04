"""Company management, CSV import over HTTP, provenance, manual corrections, instruments."""

from __future__ import annotations

from conftest import SAMPLE, create_company, import_csv
from fastapi.testclient import TestClient


def test_dry_run_preview_then_commit(client: TestClient, auth: dict[str, str]) -> None:
    c = create_company(client, auth)
    pre = import_csv(client, auth, c["id"], dry_run=True)
    assert pre.status_code == 200
    body = pre.json()
    assert body["committed"] is False and body["preview"]["ok"] is True
    fy25 = body["preview"]["periods"][-1]["values"]["revenue"]
    assert fy25 == {
        "value": 2000.0,
        "original_text": "2,000.0",
        "original_value": 2000.0,
        "row": 3,
        "column": "FY2025",
    }
    assert (
        client.get(f"/api/v1/companies/{c['id']}/financials", headers=auth).json()["periods"] == []
    )  # nothing stored by a dry run
    done = import_csv(client, auth, c["id"])
    assert done.json()["committed"] is True and done.json()["fiscal_years"] == [2023, 2024, 2025]


def test_stored_financials_carry_provenance_and_nulls(
    client: TestClient, auth: dict[str, str]
) -> None:
    c = create_company(client, auth)
    import_csv(client, auth, c["id"])
    data = client.get(f"/api/v1/companies/{c['id']}/financials", headers=auth).json()
    assert (data["currency"], data["scale"]) == ("INR", "crores")
    fy23 = {li["item_code"]: li for li in data["periods"][0]["line_items"]}
    assert fy23["reported_ebitda"]["value"] is None  # blank cell → null, never 0
    assert fy23["revenue"]["source_ref"] == f"{SAMPLE.name}: row 3, column FY2023"
    assert fy23["revenue"]["source_title"] == f"CSV import: {SAMPLE.name}"
    assert all(li["basis"] == "reported" and li["source_id"] for li in fy23.values())
    ana = client.get(f"/api/v1/companies/{c['id']}/historical-analysis", headers=auth).json()
    fy25 = ana["periods"][-1]
    assert fy25["metrics"]["nwc"]["value"] == 300.0
    assert fy25["metrics"]["revenue_growth"]["value"] == 2000 / 1800 - 1


def test_invalid_csv_is_reported_with_rows_and_cannot_be_committed(
    client: TestClient, auth: dict[str, str]
) -> None:
    c = create_company(client, auth)
    bad = b"item_code,FY2025\nperiod_end,2025-03-31\nrevenue,abc\ncapex,-3\nprofit,1\n"
    pre = import_csv(client, auth, c["id"], bad, dry_run=True).json()["preview"]
    assert [(e["code"], e["row"], e["column"]) for e in pre["errors"]] == [
        ("INVALID_NUMBER", 3, "FY2025"),
        ("SIGN_CONVENTION", 4, "FY2025"),
        ("UNKNOWN_ITEM", 5, "item_code"),
    ]
    commit = import_csv(client, auth, c["id"], bad)
    assert commit.status_code == 422 and commit.json()["error_type"] == "import"
    assert (
        client.get(f"/api/v1/companies/{c['id']}/financials", headers=auth).json()["periods"] == []
    )


def test_currency_mismatch_and_scale_conversion(client: TestClient, auth: dict[str, str]) -> None:
    c = create_company(client, auth)
    usd = import_csv(client, auth, c["id"], currency="USD", dry_run=True).json()["preview"]
    assert [e["code"] for e in usd["errors"]] == ["CURRENCY_MISMATCH"]
    lakhs = b'item_code,FY2025\nperiod_end,2025-03-31\nrevenue,"200,000"\n'
    r = import_csv(client, auth, c["id"], lakhs, scale="lakhs").json()
    assert r["committed"]
    li = client.get(f"/api/v1/companies/{c['id']}/financials", headers=auth).json()["periods"][0][
        "line_items"
    ][0]
    assert (li["value"], li["original_value"], li["original_scale"]) == (2000.0, 200000.0, "lakhs")


def test_reimport_conflict_then_replace(client: TestClient, auth: dict[str, str]) -> None:
    c = create_company(client, auth)
    import_csv(client, auth, c["id"])
    again = import_csv(client, auth, c["id"])
    assert again.status_code == 409 and again.json()["error_type"] == "conflict"
    assert import_csv(client, auth, c["id"], replace=True).json()["committed"]


def test_manual_correction_is_sourced_and_audited(client: TestClient, auth: dict[str, str]) -> None:
    c = create_company(client, auth)
    import_csv(client, auth, c["id"])
    fin = client.get(f"/api/v1/companies/{c['id']}/financials", headers=auth).json()
    cash = next(li for li in fin["periods"][-1]["line_items"] if li["item_code"] == "cash")
    r = client.patch(
        f"/api/v1/line-items/{cash['id']}",
        headers=auth,
        json={"value": None, "note": "Cash figure disputed; marked missing"},
    )
    assert r.status_code == 200 and r.json()["value"] is None
    neg = client.patch(
        f"/api/v1/line-items/{cash['id']}", headers=auth, json={"value": -1.0, "note": "typo"}
    )
    assert neg.status_code == 409
    after = client.get(f"/api/v1/companies/{c['id']}/financials", headers=auth).json()
    cash2 = next(li for li in after["periods"][-1]["line_items"] if li["item_code"] == "cash")
    assert cash2["value"] is None and cash2["source_ref"] == "manual entry"
    assert cash2["source_title"] == "Manual correction: cash"


def test_instruments_are_validated_per_kind(client: TestClient, auth: dict[str, str]) -> None:
    c = create_company(client, auth)
    url = f"/api/v1/companies/{c['id']}/share-instruments"
    base = {"source_title": "Note 28", "source_ref": None}
    bad = client.put(
        url,
        headers=auth,
        json={**base, "instruments": [{"kind": "option", "label": "x", "count": 1.0}]},
    )
    assert bad.status_code == 422 and bad.json()["error_type"] == "validation"
    wrong_field = client.put(
        url,
        headers=auth,
        json={**base, "instruments": [{"kind": "rsu", "label": "x", "count": 1.0, "strike": 2.0}]},
    )
    assert wrong_field.status_code == 422
    ok = client.put(
        url,
        headers=auth,
        json={
            **base,
            "instruments": [
                {
                    "kind": "convertible",
                    "label": "2029 notes",
                    "face_value": 100.0,
                    "conversion_price": 25.0,
                    "coupon_rate": 0.04,
                }
            ],
        },
    )
    assert ok.status_code == 200
    assert client.get(url, headers=auth).json()[0]["conversion_price"] == 25.0


def test_company_validation_and_duplicates(client: TestClient, auth: dict[str, str]) -> None:
    create_company(client, auth)
    dup = client.post(
        "/api/v1/companies",
        headers=auth,
        json={
            "name": "Ardent Precision Components (SYNTHETIC)",
            "sector": None,
            "currency": "INR",
            "scale": "crores",
            "fiscal_year_end_month": 3,
            "is_financial_institution": False,
            "is_synthetic": True,
        },
    )
    assert dup.status_code == 409
    bad = client.post(
        "/api/v1/companies",
        headers=auth,
        json={
            "name": "X",
            "sector": None,
            "currency": "inr",
            "scale": "dozens",
            "fiscal_year_end_month": 13,
            "is_financial_institution": False,
            "is_synthetic": True,
        },
    )
    assert bad.status_code == 422
    assert {e["loc"][-1] for e in bad.json()["errors"]} == {
        "currency",
        "scale",
        "fiscal_year_end_month",
    }
    assert len(client.get("/api/v1/line-items", headers=auth).json()) == 28 + 1  # + adjusted
