"""B6: every documented route returns exactly its documented shape, and the committed OpenAPI
document (docs/openapi.json, from which the frontend's TypeScript types are generated) is current."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import schema_check
from conftest import SAMPLE, idem
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[2]
OPENAPI = BACKEND.parent / "docs" / "openapi.json"


def test_every_documented_route_is_exercised_and_validated(
    client: TestClient, auth: dict[str, str]
) -> None:
    schema_check.VALIDATED.clear()
    a, v = "/api/v1", auth
    c = client
    c.get(f"{a}/health")
    c.get(f"{a}/line-items", headers=v)
    c.get(f"{a}/samples", headers=v)
    ids = c.post(f"{a}/samples/ardent-precision/load", headers=v).json()
    cid, pid, sid = ids["company_id"], ids["project_id"], ids["scenario_id"]
    c.post(
        f"{a}/companies/{cid}/financials/import",
        headers=v,
        files={"file": ("s.csv", SAMPLE.read_bytes(), "text/csv")},
        data={"currency": "INR", "scale": "crores", "basis": "reported", "dry_run": "true"},
    )
    fin = c.get(f"{a}/companies/{cid}/financials", headers=v).json()
    c.get(f"{a}/companies/{cid}/historical-analysis", headers=v)
    li = fin["periods"][-1]["line_items"][0]
    c.patch(
        f"{a}/line-items/{li['id']}",
        headers=v,
        json={"value": li["value"], "basis": "assumed", "rationale": "schema test"},
    )
    c.get(f"{a}/companies/{cid}/share-instruments", headers=v)
    c.put(
        f"{a}/companies/{cid}/share-instruments",
        headers=v,
        json={
            "source_title": "Note 28 (SYNTHETIC)",
            "source_ref": None,
            "instruments": [{"kind": "rsu", "label": "RSU", "count": 1.0}],
        },
    )
    c.get(f"{a}/sources/{li['source_id']}", headers=v)
    c.post(f"{a}/sources", headers=v, json={"kind": "filing", "title": "AR 2025 (SYNTHETIC)"})
    sc = c.get(f"{a}/scenarios/{sid}", headers=v).json()
    c.get(f"{a}/projects/{pid}/scenarios", headers=v)
    c.put(
        f"{a}/scenarios/{sid}",
        headers=v,
        json={"settings": sc["settings"], "assumptions": sc["assumptions"]},
    )
    c.post(
        f"{a}/projects/{pid}/scenarios",
        headers=v,
        json={
            "name": "Alt",
            "kind": "custom",
            "settings": sc["settings"],
            "assumptions": sc["assumptions"],
        },
    )
    c.post(f"{a}/scenarios/{sid}/clone", headers=v, json={"name": "Copy", "kind": "upside"})
    c.post(f"{a}/scenarios/{sid}/preview", headers=v)
    run = c.post(f"{a}/scenarios/{sid}/runs", headers=idem(v), json={"label": "s"}).json()
    c.get(f"{a}/scenarios/{sid}/runs", headers=v)
    c.get(f"{a}/runs/{run['id']}", headers=v)
    c.post(f"{a}/runs/{run['id']}/verify", headers=v)
    c.get(f"{a}/runs", headers=v)
    c.post(
        f"{a}/runs/{run['id']}/sensitivity",
        headers=v,
        json={
            "row": {"variable": "wacc", "step": 0.005, "steps_each_side": 1},
            "col": {"variable": "terminal_growth", "step": 0.005, "steps_each_side": 1},
            "output": "value_per_share",
        },
    )
    c.post(f"{a}/calculate/dcf", headers=v, json=run["inputs"])
    c.get(f"{a}/dashboard", headers=v)

    documented = schema_check.documented_routes(client.app)
    # 7 company + 11 scenario/run + 7 insights routes + health; update deliberately
    assert len(documented) == 26
    assert documented - schema_check.VALIDATED == set()


def test_committed_openapi_document_is_current() -> None:
    out = subprocess.run(
        [sys.executable, "scripts/export_openapi.py", "--check"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stdout + out.stderr


def test_openapi_documents_the_new_contracts() -> None:
    spec = json.loads(OPENAPI.read_text(encoding="utf-8"))
    paths = spec["paths"]
    for p in (
        "/api/v1/dashboard",
        "/api/v1/runs",
        "/api/v1/runs/{run_id}/sensitivity",
        "/api/v1/sources",
        "/api/v1/sources/{source_id}",
        "/api/v1/samples",
        "/api/v1/samples/{sample_id}/load",
    ):
        assert p in paths, p
    freeze = paths["/api/v1/scenarios/{scenario_id}/runs"]["post"]
    header = next(x for x in freeze["parameters"] if x["name"] == "Idempotency-Key")
    assert header["in"] == "header" and header["required"] is True
    assert {"200", "201", "409", "503"} <= set(freeze["responses"])
    assert "requestBody" in paths["/api/v1/scenarios/{scenario_id}/preview"]["post"]
