"""End-to-end demonstration against a running DealForge API server.

Create company → import financial statements → validate data → run DCF → save valuation run →
retrieve saved run → verify identical results.

Usage (from backend/):
    DEALFORGE_DATABASE_URL=sqlite:///./demo.sqlite3 uvicorn app.main:create_app --factory --port 8000
    python scripts/demo_workflow.py http://127.0.0.1:8000

All data is synthetic (samples/ardent_precision_synthetic.csv).
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx

BACKEND = Path(__file__).resolve().parents[1]
SAMPLE = BACKEND / "samples" / "ardent_precision_synthetic.csv"
SCENARIO = json.loads((BACKEND / "samples" / "ardent_base_scenario.json").read_text("utf-8"))
KA_DCF03_SETTINGS, KA_DCF03_ASSUMPTIONS = SCENARIO["settings"], SCENARIO["assumptions"]


def step(n: int, title: str) -> None:
    print(f"\n=== Step {n}: {title} " + "=" * max(0, 60 - len(title)))


def check(r: httpx.Response, expected: int) -> Any:
    if r.status_code != expected:
        print(f"!! HTTP {r.status_code}: {r.text}")
        raise SystemExit(1)
    return r.json() if r.content else None


def main(base: str) -> None:
    api = httpx.Client(base_url=f"{base}/api/v1", timeout=30)
    print("Health:", check(api.get("/health"), 200))

    step(0, "Register and log in")
    creds = {"email": "demo.analyst@example.com", "password": "demo-password-123"}
    r = api.post("/auth/register", json=creds)
    print("register:", r.status_code, "(409 = already registered)")
    tok = check(api.post("/auth/token", json=creds), 200)
    api.headers["Authorization"] = f"Bearer {tok['access_token']}"
    print("token expires:", tok["expires_at"])

    step(1, "Create company")
    company = check(
        api.post(
            "/companies",
            json={
                "name": "Ardent Precision Components (SYNTHETIC)",
                "sector": "Industrials",
                "currency": "INR",
                "scale": "crores",
                "fiscal_year_end_month": 3,
                "is_financial_institution": False,
                "is_synthetic": True,
            },
        ),
        201,
    )
    print(json.dumps(company, indent=2))
    cid = company["id"]

    step(2, "Validate the statements (dry run, nothing saved)")
    files = {"file": (SAMPLE.name, SAMPLE.read_bytes(), "text/csv")}
    form = {"currency": "INR", "scale": "crores", "basis": "reported", "dry_run": "true"}
    pre = check(api.post(f"/companies/{cid}/financials/import", files=files, data=form), 200)
    p = pre["preview"]
    print(f"file {p['file_name']}  sha256 {p['file_sha256'][:16]}…  ok={p['ok']}")
    print(
        f"errors: {len(p['errors'])}   other issues: "
        f"{[(i['code'], i['severity']) for i in p['issues']]}"
    )
    print("fiscal years:", [x["fiscal_year"] for x in p["periods"]])
    bad = b"item_code,FY2025\nperiod_end,2025-03-31\nrevenue,abc\ncapex,-3\n"
    badp = check(
        api.post(
            f"/companies/{cid}/financials/import",
            files={"file": ("broken.csv", bad, "text/csv")},
            data=form,
        ),
        200,
    )
    print("A deliberately broken file is rejected with row/column errors:")
    for e in badp["preview"]["errors"]:
        print(f"   row {e['row']} {e['column']}: {e['code']} — {e['message']}")

    step(3, "Import the statements (commit)")
    form["dry_run"] = "false"
    done = check(api.post(f"/companies/{cid}/financials/import", files=files, data=form), 200)
    print("committed fiscal years:", done["fiscal_years"])
    fin = check(api.get(f"/companies/{cid}/financials"), 200)
    rev = next(li for li in fin["periods"][-1]["line_items"] if li["item_code"] == "revenue")
    print(
        f"FY2025 revenue = {rev['value']} {fin['currency']} {fin['scale']}  provenance: "
        f"{rev['source_title']} / {rev['source_ref']} (raw text '{rev['original_text']}')"
    )
    ana = check(api.get(f"/companies/{cid}/historical-analysis"), 200)
    for per in ana["periods"]:
        m = per["metrics"]
        print(
            f"   FY{per['fiscal_year']}: growth {m['revenue_growth']['value']}, EBITDA margin "
            f"{m['ebitda_margin']['value']:.4f}, NWC {m['nwc']['value']}"
        )
    check(
        api.put(
            f"/companies/{cid}/share-instruments",
            json={
                "source_title": "FY2025 annual report, note 28 (SYNTHETIC)",
                "source_ref": "note 28",
                "instruments": [
                    {"kind": "option", "label": "ESOP 2021", "count": 5.0, "strike": 12.0},
                    {"kind": "rsu", "label": "RSU plan", "count": 1.0},
                ],
            },
        ),
        200,
    )
    print("share instruments recorded: 5.0m options @ 12.00, 1.0m RSUs")

    step(4, "Run DCF (preview, nothing saved)")
    project = check(
        api.post(
            "/projects",
            json={"company_id": cid, "name": "Ardent valuation", "description": "Phase 3 demo"},
        ),
        201,
    )
    scen = check(
        api.post(
            f"/projects/{project['id']}/scenarios",
            json={
                "name": "Base",
                "kind": "base",
                "settings": KA_DCF03_SETTINGS,
                "assumptions": KA_DCF03_ASSUMPTIONS,
            },
        ),
        201,
    )
    pv = check(api.post(f"/scenarios/{scen['id']}/preview"), 200)
    res = pv["result"]
    print(
        f"WACC {res['wacc']:.6%}   EV {res['valuation']['enterprise_value']:,.4f}   "
        f"equity {res['bridge']['equity_value']:,.4f}   "
        f"value/share {res['per_share']['value_per_share']:.4f}"
    )
    print("warnings:", [w["code"] for w in pv["warnings"]])

    step(5, "Save the valuation run (frozen)")
    key = f"demo-{uuid.uuid4()}"  # mandatory Idempotency-Key (A7); reuse it to retry safely
    run = check(
        api.post(
            f"/scenarios/{scen['id']}/runs",
            json={"label": "Phase 3 demo run"},
            headers={"Idempotency-Key": key},
        ),
        201,
    )
    print(f"run {run['id']}  engine {run['engine_version']}  {run['input_hash']}")

    step(6, "Retrieve the saved run")
    got = check(api.get(f"/runs/{run['id']}"), 200)
    print("retrieved value/share:", got["result"]["per_share"]["value_per_share"])
    print("result identical to the response at save time:", got["result"] == run["result"])
    print("result identical to the preview:", got["result"] == pv["result"])

    step(7, "Verify identical results (re-execute the frozen inputs)")
    v = check(api.post(f"/runs/{run['id']}/verify"), 200)
    print(json.dumps(v, indent=2))
    ok = v["identical"] and v["input_hash_matches"] and v["inputs_round_trip_exact"]

    step(8, "Replay the freeze with the same Idempotency-Key")
    replay = api.post(
        f"/scenarios/{scen['id']}/runs",
        json={"label": "Phase 3 demo run"},
        headers={"Idempotency-Key": key},
    )
    print(
        f"HTTP {replay.status_code}, Idempotent-Replayed: "
        f"{replay.headers.get('idempotent-replayed')}, same run: "
        f"{replay.json()['id'] == run['id']}"
    )
    ok = ok and replay.status_code == 200 and replay.json()["id"] == run["id"]

    step(9, "Sensitivity of the frozen run (WACC × terminal growth)")
    grid = check(
        api.post(
            f"/runs/{run['id']}/sensitivity",
            json={
                "row": {"variable": "wacc", "step": 0.005, "steps_each_side": 1},
                "col": {"variable": "terminal_growth", "step": 0.005, "steps_each_side": 1},
                "output": "value_per_share",
            },
        ),
        200,
    )
    print("value per share (INR); rows WACC, columns g; base cell outlined by [ ]")
    print("            " + "".join(f"g {g:6.2%}         " for g in grid["col_values"]))
    for i, (w, line) in enumerate(zip(grid["row_values"], grid["cells"], strict=True)):
        cells = []
        for j, c in enumerate(line):
            txt = f"{c['value']:.4f} ({c['change_pct']['value']:+.1%})"
            cells.append(
                f"[{txt}]" if (i, j) == (grid["base_row"], grid["base_col"]) else f" {txt} "
            )
        print(f"WACC {w:7.4%} " + "  ".join(cells))
    print("base matches the frozen run:", grid["base_matches_run"])
    ok = ok and grid["base_matches_run"]

    step(10, "Saved runs across all companies, and the dashboard")
    page = check(api.get("/runs?page=1&page_size=10"), 200)
    for it in page["items"]:
        print(
            f"run {it['id']}  {it['company']['name']} / {it['scenario']['name']}  "
            f"valuation date {it['valuation_date']}  engine {it['engine_version']}  "
            f"{it['value_per_share']:.4f} per share  {it['input_hash'][:19]}…"
        )
    d = check(api.get("/dashboard"), 200)
    print("counts:", d["counts"], " onboarding complete:", d["onboarding"]["complete"])
    print("latest activity:", d["recent_activity"][0]["summary"])

    print("\nRESULT:", "IDENTICAL — workflow verified" if ok else "MISMATCH")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000")
