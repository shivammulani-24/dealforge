# DealForge Phase 4: professional financial analysis frontend (plan, revision 3)

> **Status: F0a–F0c (backend) IMPLEMENTED; awaiting review before F1.** No frontend code has
> been written. Transcript: [`demo/phase-4-f0-workflow-output.txt`](demo/phase-4-f0-workflow-output.txt). Based on `main` at `2fd8299` (Phase 3 merged via PR #1).
>
> **Revision 2** incorporates the owner's decisions on D4-01 to D4-11 (two amended: D4-02, D4-09)
> and seven additional requirements (R1–R7). See [section 10](#10-decision-record) for the decision
> record and [section 11](#11-conflicts-with-the-engine-and-phase-3-and-their-resolution) for
> conflicts found in the Phase 3 code and how they are resolved.
>
> **Revision 3** adds the owner's nine amendments A1–A9 (section 10.1): the engine version covers
> sensitivity as well as DCF semantics, golden sensitivity tests, a version-bump checklist,
> enforced basis rules, a mandatory `Idempotency-Key`, the SQLite transaction and locking strategy,
> and absolute plus percentage sensitivity changes.

## Contents

1. [Frontend architecture](#1-frontend-architecture)
2. [Proposed folder structure](#2-proposed-folder-structure)
3. [Screens and screen-by-screen API mapping](#3-screens-and-screen-by-screen-api-mapping)
4. [Backend changes required](#4-backend-changes-required)
5. [Liquidity: line items and ratio formulas](#5-liquidity-line-items-and-ratio-formulas)
6. [Financial integrity rules](#6-financial-integrity-rules)
7. [UI design direction](#7-ui-design-direction)
8. [Testing, error handling and acceptance criteria](#8-testing-error-handling-and-acceptance-criteria)
9. [Milestone-wise implementation plan](#9-milestone-wise-implementation-plan)
10. [Decision record](#10-decision-record)
11. [Conflicts with the engine and Phase 3, and their resolution](#11-conflicts-with-the-engine-and-phase-3-and-their-resolution)
12. [New limitations and remaining risks](#12-new-limitations-and-remaining-risks)

---

## 1. Frontend architecture

```
Browser ── React 18 + TypeScript (strict) + Vite
  │  React Router         routes = screens; URL carries company / project / scenario / run IDs
  │  TanStack Query       server state: caching, loading/error states, invalidation, cancellation
  │  React Hook Form+Zod  form structure only (required, type, length); financial rules stay server-side
  │  openapi-typescript   TS types generated from the committed OpenAPI document (D4-08)
  │  openapi-fetch        typed HTTP client; middleware adds bearer token, handles 401
  │  Tailwind CSS         design tokens (section 7); small in-house component kit
  │  Recharts             historical bars/lines, UFCF bars, EV composition, bridge waterfall
  │  lib/format.ts        DISPLAY ONLY: rounding, %, x, parentheses, units, "—"/"NM"
  │  lib/parse.ts         string-exact input parsing ("18.5" % → 0.185, no division)
  ▼
Development: Vite dev server proxies /api → FastAPI :8000 (same origin)
Production:  FastAPI serves frontend/dist from the same origin, with SPA fallback (D4-07, B11)
```

### Authentication and session handling (D4-01, approved)

- **Storage:**
  - The token is held in memory and mirrored to `sessionStorage` so a page reload keeps the session.
  - It's cleared on logout, on any 401 and when the tab closes.
  - It's never put in URLs, logs, error reports or `localStorage`.
- **Requests:** an `openapi-fetch` middleware adds `Authorization: Bearer …`.
- **Expiry:** a warning appears two minutes before `expires_at`. At expiry, or on any 401 (expired or revoked), the user goes to `/login?next=<path>`. An unsaved DCF draft is kept in `sessionStorage` and restored after re-login.
- **Logout:** `POST /auth/logout` revokes the token server-side, then the client clears it.
- **Hardening:** strict Content-Security-Policy on the production `index.html` (`default-src 'self'`, no inline script). ESLint bans `dangerouslySetInnerHTML`. A unit test checks that the token never appears in console output or error objects.
- **Deployment gate:** before any public deployment, auth must move to an **HttpOnly, Secure, SameSite=Strict cookie plus a CSRF token**. This is recorded as **LIM-20** (status *Planned*, marked as a deployment blocker) and in `docs/phase-3-design.md`.

### Loading, error and duplicate-submission handling (all screens)

| Situation | Behaviour |
|---|---|
| First load | Skeletons that keep the final layout |
| Background refetch | Content stays visible, with a small "updating" indicator |
| `error_type: validation` | Inline at the field from `loc`; the form isn't cleared |
| `error_type: calculation` | Issue panel (code, field, message, link to input). Previous results greyed out and labelled **Stale – inputs invalid**. |
| `not_found` | "Not found or not yours" page |
| `conflict` / `import` / `immutable` | Specific dialogs, e.g. replace FY2025?, engine version changed, sample already loaded |
| `authentication` | Session-expired flow |
| Network or 5xx | Retry button; POST is never retried automatically |
| Duplicate submissions | Every mutation button is disabled while pending. **Freeze run** sends a fresh `Idempotency-Key` per user action, enforced by the backend (D4-10, B5). |

---

## 2. Proposed folder structure

```
dealforge/
├── backend/
│   ├── alembic/versions/0002_run_idempotency_and_indexes.py   + hand-written (section 4.10)
│   ├── app/engine/
│   │   ├── historical.py      ~ liquidity fields, ratios, checks (additive; existing formulas untouched)
│   │   ├── presentation.py    + EBIT / UFCF margins from a DcfResult (pure, stdlib)
│   │   ├── errors.py          ~ new codes
│   │   └── version.py         ~ versioning policy text (value unchanged: 0.1.0)
│   ├── app/importers/line_items.py   ~ 3 new items, 1 label clarified, completeness groups
│   ├── app/api/v1/
│   │   ├── dashboard.py  runs.py  sources.py  samples.py                    +
│   │   └── spa.py        + production static serving + SPA fallback
│   ├── app/services/
│   │   ├── dcf_inputs.py      + ORM-free input assembly (refactor of build_dcf_inputs)
│   │   ├── dashboard.py  sensitivity.py  samples.py  idempotency.py          +
│   ├── app/schemas/responses.py      + typed response models (B6)
│   ├── samples/ardent_precision_synthetic.csv   ~ + liquidity rows (DCF inputs unchanged)
│   └── tests/
│       ├── engine/test_liquidity.py  test_presentation.py  test_engine_version_guard.py   +
│       ├── db/test_migration_0002.py  test_idempotency_concurrency.py                     +
│       └── api/test_dashboard_api.py  test_runs_list_api.py  test_sensitivity_api.py
│               test_draft_preview_api.py  test_samples_api.py  test_sources_api.py
│               test_completeness_api.py  test_spa_fallback.py  test_response_schemas.py
│               test_openapi_snapshot.py                                                   +
├── docs/openapi.json          + committed OpenAPI document; CI fails if stale
├── frontend/                  + (structure as in revision 1)
│   ├── src/{app,api,auth,components/{ui,charts},features/*,lib,styles}
│   ├── tests/ (Vitest + RTL + MSW; fixtures recorded from the real backend)
│   └── e2e/   (Playwright; real backend; viewports 1024×768 and 1440×900)
└── .github/workflows/ci.yml   ~ + OpenAPI drift check + Node 22 frontend job + E2E job
```

`+` new · `~` modified. **No existing engine formula is modified.**

---

## 3. Screens and screen-by-screen API mapping

Legend: ✅ existing endpoint · 🆕 new or extended (B-numbers in section 4). Every value on screen carries a basis marker: **R** reported · **D** derived · **A** assumed (R2).

### 3.1 Dashboard (`/`) and first-time experience (R5)

| Feature | Endpoint |
|---|---|
| Totals: companies, projects, scenarios, frozen runs | 🆕 B1 `GET /dashboard` → `counts` |
| Recent valuation runs (with units, value per share, engine-compatibility flag) | 🆕 B1 → `recent_runs` |
| **Recently active** companies, from audit events (D4-03) | 🆕 B1 → `recent_companies` |
| Activity feed (server-written summaries) | 🆕 B1 → `recent_activity` |
| **First-time user (all counts 0):** a guided panel, "Explore DealForge with a synthetic company", with a **Load sample company** button, plus "or create your own" | 🆕 B9 `GET /samples`, `POST /samples/ardent-precision/load` |
| **Onboarding checklist** (shown until complete): ① company ② statements imported ③ scenario ④ frozen run. Progress comes from the server; suggested next actions link to Analysis, DCF, Sensitivity and Audit. | 🆕 B1 → `onboarding` |
| New company / new valuation | ✅ `POST /companies`, ✅ `POST /projects` |

### 3.2 Company workspace (`/companies/:id`)

| Feature | Endpoint |
|---|---|
| Profile: name, sector, currency, scale, fiscal year end, **SYNTHETIC** banner | ✅ `GET /companies/{id}` |
| Periods and key figures (revenue, EBITDA (D), EBIT, net income) | ✅ `GET …/financials`, ✅ `GET …/historical-analysis` |
| **Completeness** per year: DCF group (definition unchanged) and **liquidity group** (new, R6) | 🆕 B8 extends `GET …/financials` |
| Validation warnings | ✅ `GET …/historical-analysis` → `issues` |
| Provenance popover for any value (basis, source, file, SHA-256, row, column, raw text) | ✅ line-item fields + 🆕 B7 `GET /sources/{id}` |
| Provenance for a **derived** metric: formula plus its component values, each with its own provenance | 🆕 B10 `metric_definitions` in `GET …/historical-analysis` |
| Import wizard: upload → dry-run preview (row/column errors) → commit, or replace with confirmation | ✅ `POST …/financials/import` |
| Manual correction (value or "mark missing", **basis required**, note required) | ✅ `PATCH /line-items/{id}` (body amended, section 11 C6) |
| Share instruments | ✅ `GET`/`PUT …/share-instruments` |

### 3.3 Financial analysis (`/companies/:id/analysis`)

| Feature | Endpoint |
|---|---|
| Income statement, balance sheet, cash flow (rows grouped by `statement`) with R/A badges | ✅ `GET /line-items` + ✅ `GET …/financials` |
| Growth, margins, leverage, working capital, cash-flow metrics (all D) | ✅ `GET …/historical-analysis` |
| **Liquidity: current, quick and cash ratios** (D), with "—" when missing and "NM" when TCL = 0 | 🆕 B10 (new metrics in `historical-analysis`) |
| Liquidity consistency warnings | 🆕 B10 → `issues` |
| Charts: revenue and EBITDA bars, margin lines, FCF vs net income, liquidity ratios | Same data, plotted directly |

### 3.4 DCF workspace (`/scenarios/:id/dcf`)

| Feature | Endpoint |
|---|---|
| Saved scenario: settings and assumptions (A) with rationale and source | ✅ `GET /scenarios/{id}` |
| Historical columns next to the forecast (R/D) | ✅ `GET …/historical-analysis` |
| Draft editing (drivers; tax; g; WACC build-up or override; market inputs) | Local draft only |
| **Live recalculation** of the draft, with no database or audit writes (D4-04) | 🆕 B4 `POST /scenarios/{id}/preview` with body |
| Projected revenue, EBITDA, D&A, EBIT, tax, NOPAT, CapEx, NWC, ΔNWC, UFCF, discount factor, PV (all D) | 🆕/✅ preview `result.*` |
| **EBIT margin and UFCF margin rows** (D, D4-06) | 🆕 B5 `presentation` |
| Units label | 🆕 B5 `context.company.{currency, scale}` |
| LIM-12 flags on the exact input cell | ✅ `warnings[].field` |
| Save, clone | ✅ `PUT /scenarios/{id}`, ✅ `POST …/clone` |
| **Freeze run** (blocked while the draft is dirty; idempotent) | 🆕 B5 `POST /scenarios/{id}/runs` + `Idempotency-Key` |

### 3.5 Valuation results (`/scenarios/:id/results`, `/runs/:id`)

| Feature | Endpoint |
|---|---|
| EV, equity value, value per share, upside vs market (D), with units | ✅ `result.*` + 🆕 B5 `context` |
| Sum of PV(FCF), TV, PV(TV), TV share of EV, implied exit multiple | ✅ `result.valuation`, `result.implied_exit_multiple` |
| WACC build, bridge waterfall, dilution detail, dates | ✅ `result.wacc_build`, `result.bridge.lines`, `result.per_share`, `result.schedule` |
| Input provenance table (every input with R/D/A, source, rationale) | ✅ `provenance` (market-input basis corrected, C5) |

### 3.6 Sensitivity (`/runs/:id/sensitivity`), frozen runs only (R1)

| Feature | Endpoint |
|---|---|
| WACC × g grid; output EV, equity or value per share; growth-shift × margin-shift preset | 🆕 B3 `POST /runs/{id}/sensitivity` |
| Base cell outlined, `base_matches_run: true` | 🆕 B3 |
| Invalid cells with code. Each cell shows the backend's **absolute change** (`change_abs`, in the output's units) and **percentage change** (`change_pct`, "NM" when the base is zero or negative). Heat shading uses `change_abs`, so it still works when the percentage is NM. | 🆕 B3 |
| Run frozen under another engine version: grid refused, with an explanation and a "re-freeze on current engine" action; stored results stay fully viewable | 🆕 B3 409 + B2 `engine_compatible` flag |

### 3.7 Model audit (`/scenarios/:id/audit`, `/runs/:id/audit`)

| Group | Endpoint |
|---|---|
| Missing inputs (blocking) | ✅ preview 422 `calculation` envelope, rendered as audit items |
| Historical consistency, including the new liquidity checks | ✅/🆕 `historical-analysis` → `issues` |
| Forecast outside history (LIM-12) | ✅ `warnings` |
| Valuation warnings | ✅ `warnings` |
| Provenance gaps (inputs with `status: missing`, partial NWC, values with basis A where R expected) | ✅ `provenance` |
| Invalid assumptions | ✅ `INVALID_ASSUMPTIONS` / `validation` |
| "Why?" explanations | Static catalogue keyed by issue code (frontend copy, no numbers) |

### 3.8 Saved runs (`/runs`, `/runs/:id`)

| Feature | Endpoint |
|---|---|
| Paginated, filterable list: run ID, company, scenario, valuation date, engine version, fingerprint, EV, equity, value per share, units, created at, `engine_compatible` | 🆕 B2 `GET /runs` |
| Run detail (read-only, lock icon) | ✅ `GET /runs/{id}` + 🆕 B5 `context`/`presentation` |
| Verify reproducibility (works on any engine version; reports differences) | ✅ `POST /runs/{id}/verify` + 🆕 `engine_version_changed` field |

---

## 4. Backend changes required

All endpoints are owner-scoped: another user's resource returns 404, and lists filter by the current user.

| # | Change | Kind |
|---|---|---|
| B1 | `GET /dashboard`, including the `onboarding` block | New endpoint |
| B2 | `GET /runs`, global and paginated | New endpoint |
| B3 | `POST /runs/{id}/sensitivity`, frozen inputs and matching engine only | New endpoint |
| B4 | Draft preview via `POST /scenarios/{id}/preview` with a body; refactors input assembly to be ORM-free | Extended endpoint |
| B5 | `context` and `presentation` blocks on preview and run responses; `Idempotency-Key` on freeze | Extended endpoints |
| B6 | Typed response models, a committed `docs/openapi.json` and a drift check | Schema only |
| B7 | `GET /sources/{id}` | New endpoint |
| B8 | Completeness groups (DCF unchanged, plus liquidity) in `GET …/financials` | Extended endpoint |
| **B9** | **Samples:** `GET /samples`, `POST /samples/{id}/load` (R4, R5) | New endpoints |
| **B10** | **Liquidity:** 3 line items, 3 ratios, 4 checks, metric definitions (D4-02, R6) | Engine (additive) + importer + response |
| **B11** | **SPA serving and fallback** (D4-07) | New routes |
| **B12** | **Basis corrections:** market-input basis, PATCH requires `basis`, `basis` on every metric and value (R2) | Fixes + contract change |

### 4.1 B1: `GET /api/v1/dashboard`

```jsonc
{
  "counts": { "companies": 1, "projects": 1, "scenarios": 1, "runs": 1 },
  "onboarding": {
    "complete": false,
    "steps": [
      { "key": "company",    "done": true,  "label": "Create or load a company" },
      { "key": "statements", "done": true,  "label": "Import financial statements" },
      { "key": "scenario",   "done": true,  "label": "Create a valuation scenario" },
      { "key": "run",        "done": false, "label": "Freeze a valuation run" } ],
    "sample_available": true, "sample_loaded": true },
  "recent_runs": [ { "id": 7, "label": "…", "created_at": "…",
      "company": { "id": 1, "name": "…", "currency": "INR", "scale": "crores", "is_synthetic": true },
      "scenario": { "id": 3, "name": "Base" },
      "value_per_share": 31.215006617818556, "engine_version": "0.1.0", "engine_compatible": true } ],
  "recent_companies": [ { "id": 1, "name": "…", "is_synthetic": true,
      "last_activity_at": "…", "fiscal_years": [2023, 2024, 2025] } ],
  "recent_activity": [ { "at": "…", "entity": "valuation_run", "entity_id": 7, "action": "create",
      "company_id": 1, "summary": "Froze run 7 for scenario 'Base' (sha256:37c66a53…)" } ]
}
```

- **Sizes:** 5 recent runs, 5 recent companies, 20 activity items.
- **Onboarding:** steps are derived from existing rows only; nothing is written.
- **Recently active companies:** the latest audit event resolved to its company, through company, period, line item, scenario/project or run.
- **Privacy:** summaries are written by the server. The raw audit `detail` (old values) is never returned.

### 4.2 B2: `GET /api/v1/runs?page&page_size&company_id&project_id&scenario_id`

- **Paging:** `page ≥ 1`, `page_size 1..100` (default 25). Ordered `created_at DESC, id DESC`.
- **Response:** `{page, page_size, total, items[]}`. Each item: `id, label, created_at, engine_version, engine_compatible, input_hash, valuation_date, company{id,name,currency,scale,is_synthetic}, project{id,name}, scenario{id,name}, enterprise_value, equity_value, value_per_share, warning_count`.
- **Values:** read **verbatim** from the stored `result_json` / `inputs_json`, never recomputed, so they're always available whatever the current engine version (R1).
- **Filters:** a filter ID belonging to another user returns an empty page.

### 4.3 B3: `POST /api/v1/runs/{run_id}/sensitivity`

The examples below are real responses from the F0c server (a fresh database loaded by
`scripts/demo_workflow.py`, i.e. the KA-DCF-03 run), shortened only where marked `…`.

```jsonc
// request (axes are built by the server around the run's own base values, D4-11).
// The wide g step is chosen to show invalid cells.
{ "row": { "variable": "wacc", "step": 0.005, "steps_each_side": 1 },
  "col": { "variable": "terminal_growth", "step": 0.05, "steps_each_side": 2 },
  "output": "value_per_share" }
// response (positive base: change_pct is computed)
{ "run_id": 1,
  "input_hash": "sha256:37c66a5382d863399822cc79268966c803179e0fae0d36679fc0c867efcf8114",
  "engine_version": "0.1.0", "basis": "derived",
  "context": { "company": { "id": 1, "name": "Ardent Precision Components (SYNTHETIC)",
                            "currency": "INR", "scale": "crores", "is_synthetic": true },
               "project": { "id": 1, "name": "Ardent valuation" },
               "scenario": { "id": 1, "name": "Base" } },
  "row_variable": "wacc", "col_variable": "terminal_growth", "output": "value_per_share",
  "row_values": [0.0909980079681275, 0.0959980079681275, 0.10099800796812751],
  "col_values": [-0.07500000000000001, -0.025, 0.025, 0.07500000000000001, 0.125],
  "base_row": 1, "base_col": 2,
  "base_value": 31.215006617818556, "base_matches_run": true,
  "cells": [
    [ …,
      // row 0, col 2: WACC 9.0998%, g 2.5%
      { "value": 33.866388741853164, "status": "ok", "codes": [],
        "change_abs": 2.6513821240346083,
        "change_pct": { "value": 0.08493934204457647, "status": "ok", "reason": null } },
      …,
      // row 0, col 4: g 12.5% ≥ WACC, so the cell is invalid
      { "value": null, "status": "invalid", "codes": ["TERMINAL_GROWTH_GE_WACC"],
        "change_abs": null,
        "change_pct": { "value": null, "status": "missing", "reason": "cell invalid" } } ],
    [ …,
      // the base cell (row 1, col 2)
      { "value": 31.215006617818556, "status": "ok", "codes": [], "change_abs": 0.0,
        "change_pct": { "value": 0.0, "status": "ok", "reason": null } },
      … ],
    … ] }
```

```jsonc
// Negative base: the same company with other_debt_like_claims set to 5,000 (basis "assumed",
// with a rationale), so equity is negative (EQUITY_VALUE_NON_POSITIVE). Request: WACC step
// 0.005 × 1, g step 0.005 × 1. change_abs is still given; change_pct is NM in every cell.
// base cell
{ "value": -17.190145117472877, "status": "ok", "codes": [], "change_abs": 0.0,
  "change_pct": { "value": null, "status": "not_meaningful",
                  "reason": "base value is zero or negative" } }
// row 0, col 2 (WACC 9.0998%, g 3.0%)
{ "value": -11.777498312518746, "status": "ok", "codes": [], "change_abs": 5.4126468049541305,
  "change_pct": { "value": null, "status": "not_meaningful",
                  "reason": "base value is zero or negative" } }
```

**Integrity sequence (R1):**
1. Load the run (owner check).
2. **If `run.engine_version != ENGINE_VERSION`: 409 `ENGINE_VERSION_MISMATCH`.** The message says the stored results are still available and suggests re-freezing (D4-05).
3. Rebuild inputs **only** from `run.inputs_json` with the strict `DcfInputsIn` schema.
4. **If `fingerprint(inputs) != run.input_hash`: 409 `RUN_INPUTS_CORRUPT`.**
5. Call **one pure engine function**, `engine.sensitivity.frozen_run_grid(inputs, base_outputs, spec)` (A1). It does all the sensitivity arithmetic, so the engine version governs it:
   - builds the axes with `centered_axis(base, step, n)`, taking the base from the frozen result (WACC = `result.wacc`, g = `inputs.terminal_growth`, shift = 0, tax = `inputs.tax_rate`);
   - runs `dcf_sensitivity`;
   - computes each cell's changes (A9):
     - `change_abs = v − base`, in the output's units (currency, or currency per share);
     - `change_pct = (v − base) / base` **only when `base > 0`**;
     - when `base ≤ 0`, `change_pct` is NM (`status: "not_meaningful"`, `value: null`) with reason *"base value is zero or negative"*, and `change_abs` is still given;
     - an invalid cell has `change_abs: null`, and its `change_pct` is `{value: null, status: "missing", reason: "cell invalid"}`.
   The service layer does no sensitivity arithmetic; it only loads the run, checks it and calls the engine.
6. **Assert the base cell `==` the run's stored output.** If it doesn't match, return 500 `BASE_MISMATCH`; this should be impossible after steps 2 and 4.

- **Limits:** variables `wacc`, `terminal_growth`, `revenue_growth_shift`, `ebitda_margin_shift`, `capex_pct_shift`, `tax_rate`, with row ≠ col. `steps_each_side` 1..5. `step` from 0.0005 to 0.05 (tax 0.005 to 0.10). A violation returns `validation`.
- **Persistence:** results aren't stored; they're deterministic in the frozen inputs.

### 4.4 B4: draft preview (D4-04), plus the refactor it requires

- **Request:** `POST /scenarios/{id}/preview`, body optional: `{settings: ScenarioSettingsIn, assumptions: AssumptionIn[]}`.
- **Response:** the same shape as now, plus `"draft": true|false`.
- **Refactor (C2):** input assembly moves to `services/dcf_inputs.py::assemble(company, periods, settings, assumptions, instruments)`, which takes **plain dataclasses**, not ORM objects.
  - Saved preview and freeze map the ORM scenario to plain data.
  - A draft maps the request body to plain data.
  - No ORM `Scenario` is created for a draft, so nothing can autoflush into the session.
- **Guarantee:** a draft preview performs **no INSERT, UPDATE or DELETE, and no audit event**. A SQLAlchemy `before_flush` / `after_cursor_execute` probe in tests asserts zero writes.

### 4.5 B5: context, presentation and idempotent freeze

- **`context`** on preview and run responses: `{company{id,name,currency,scale,is_synthetic}, project{id,name}, scenario{id,name}}`.
- **`presentation`** (D4-06), from a new pure engine function, `engine.presentation.margins(result)`:
  - per forecast year, `ebit_margin = EBIT_t / Revenue_t` and `ufcf_margin = UFCF_t / Revenue_t`;
  - `Revenue_t ≤ 0` gives NM;
  - `basis: "derived"`.
  - For stored runs it's computed on read from the stored `result_json`.
  - **It's never written into `result_json`**, so run fingerprints and stored results are byte-identical before and after this change (tested).
- **`Idempotency-Key`** on `POST /scenarios/{id}/runs` (D4-10). **Mandatory (A7):** a request without the header is rejected with **422 `validation`** (`loc: ["header", "idempotency-key"]`, code `missing`). No run is created and the engine isn't called. 422 keeps the single error envelope; 428 was considered and rejected for consistency. The frontend generates a UUIDv4 per user action and reuses it when retrying that action.
  - **Format:** 8–128 characters of `[A-Za-z0-9_-]`; anything else is a `validation` error.
  - **First request:** 201 with the new run. The key is stored on the run with `request_fingerprint = sha256(canonical({"scenario_id", "label"}))`.
  - **Same user, same key, same fingerprint:** 200 with **the same run** and the header `Idempotent-Replayed: true`. No new row and no new audit event. This holds even if the scenario was edited in between, because the key identifies the request.
  - **Same user, same key, different scenario or label:** 409 `IDEMPOTENCY_KEY_REUSED`.
  - **Different users** with the same key are independent.
  - **Concurrency:** handled by the transaction and locking strategy in **section 4.14** (A8).

### 4.6 B6: typed response models and the OpenAPI document (D4-08)

- **Models:** Pydantic response models for every endpoint the frontend calls. Engine result shapes are derived from the engine dataclasses via `TypeAdapter`, not hand-copied.
- **No behaviour change:** responses are still serialised through the canonical JSON path.
- **`docs/openapi.json` is committed.** CI regenerates it and **fails on any difference**; the frontend generates `schema.d.ts` from the committed file.
- **Test:** every 200 response produced anywhere in the API test suite is validated against its declared response model, so the schema and the real responses can't drift.
- **OpenAPI implications:**
  - new paths for B1–B3, B7 and B9;
  - a request body on preview;
  - the `Idempotency-Key` header parameter and `Idempotent-Replayed` response header;
  - new 409 responses documented;
  - new error codes listed in the `error_type` enum descriptions.

### 4.7 B7: `GET /api/v1/sources/{id}`

Returns `{id, kind, title, file_name, file_sha256, uri, notes, created_at}`. Owner-only.

### 4.8 B8: completeness, with the DCF definition unchanged (R6)

In `GET …/financials`, each period gains:

```jsonc
"completeness": {
  "present": 28, "missing": 1, "absent": 3,              // row with value / row with NULL / no row
  "groups": {
    "dcf":       { "required": [...12 codes...], "missing": [], "complete": true },
    "liquidity": { "required": ["total_current_assets","total_current_liabilities","cash",
                                "marketable_securities","accounts_receivable"],
                   "missing": [], "complete": true } } }
```

- **DCF group:** exactly the inputs the DCF already requires: `revenue, accounts_receivable, inventory, accounts_payable, cash, total_debt, lease_liabilities, preferred_equity, non_controlling_interest, other_debt_like_claims, non_operating_assets, basic_shares`. **Unchanged.**
- **Liquidity group:** new and separate, so liquidity gaps never affect DCF completeness.
- **Source of truth:** both groups are defined once, in `line_items.REQUIRED_FOR`.

### 4.9 B9: sample company (R4, R5)

- **`GET /samples`** → `[{id: "ardent-precision", name: "Ardent Precision Components (SYNTHETIC)", description, is_synthetic: true, includes: ["3 fiscal years", "share instruments", "Base scenario (KA-DCF-03)"]}]`
- **`POST /samples/ardent-precision/load`** runs as **one transaction**:
  - creates the company (`is_synthetic: true`);
  - imports `samples/ardent_precision_synthetic.csv` **through the same importer** (source kind `synthetic`, with file name and SHA-256);
  - sets the share instruments (source kind `synthetic`);
  - creates the project "Ardent valuation (sample)" and the "Base" scenario from `samples/ardent_base_scenario.json` (every assumption basis `assumed`, with rationale);
  - writes audit events;
  - returns `{company_id, project_id, scenario_id}`.
- **Already loaded:** 409 `SAMPLE_ALREADY_LOADED`, returning the existing IDs.
- **Any failure:** nothing is created.

### 4.10 Database migration `0002` (hand-written, not autogenerated: see C3)

```python
op.add_column("valuation_runs", sa.Column("idempotency_key", sa.String(128), nullable=True))
op.add_column("valuation_runs", sa.Column("request_fingerprint", sa.String(80), nullable=True))
op.add_column("valuation_runs", sa.Column("inputs_schema_version", sa.Integer(),
                                          nullable=False, server_default="1"))
op.create_index("uq_runs_owner_idempotency", "valuation_runs",
                ["created_by", "idempotency_key"], unique=True)       # NULLs never collide
op.create_index("ix_runs_owner_created", "valuation_runs", ["created_by", "created_at"])
op.create_index("ix_audit_user_created", "audit_events", ["user_id", "created_at"])
op.add_column("scenarios", sa.Column("market_rationale", sa.Text(), nullable=True))      # A5
# A4–A6 basis triggers (raw SQL, SQLite), BEFORE INSERT and BEFORE UPDATE:
#   line_items_basis_values        basis must be 'reported' or 'assumed'           (A6)
#   line_items_reported_source     basis 'reported' ⇒ source kind ∈ qualifying set (A4)
#   assumptions_basis_values       basis must be 'reported' or 'assumed'           (A6)
#   assumptions_reported_source    basis 'reported' ⇒ source_id set, qualifying    (A4)
#   assumptions_assumed_rationale  basis 'assumed'  ⇒ trim(rationale) <> ''        (A5)
#   scenarios_market_rationale     share_price set, no market_source_id ⇒ rationale (A5)
# WAL journal mode is set per connection (section 4.14), not by the migration.
```

- **Native `ALTER TABLE … ADD COLUMN`, no batch recreate**, so the two immutability triggers on `valuation_runs` survive. `ADD COLUMN` isn't an `UPDATE`, so the triggers don't fire.
- **Downgrade** drops the indexes and recreates the table without the columns (SQLite can't drop columns in place), then **re-creates both triggers explicitly**.
- **Existing runs** get `idempotency_key NULL` and `inputs_schema_version 1`; their data is otherwise untouched.
- **`inputs_schema_version`** tags which `DcfInputs` reader a run needs, for future schema evolution (LIM-22).
- **No migration is needed for the liquidity items:** line items are stored in tall format (one row per item code).

### 4.11 B11: production static serving and SPA fallback (D4-07)

- **Config:** `DEALFORGE_FRONTEND_DIST` points to `frontend/dist`. If it's unset or missing, the API runs as today.
- **Static files:** `/assets/*` is served by `StaticFiles` with immutable cache headers. A missing asset is a **404, never `index.html`** (otherwise HTML would be served as JavaScript).
- **Catch-all:** a final `GET`/`HEAD /{path:path}` route serves a real file from `dist` if one exists, otherwise `index.html` with `Cache-Control: no-cache` and the CSP header.
- **Never intercepted:** paths starting with **`api/`**, plus `docs`, `redoc` and `openapi.json`. An unknown `/api/...` path returns the JSON 404 envelope. Non-GET methods on SPA paths return 405.
- **Registration order:** the fallback is registered after every API router, and a test checks the order.

### 4.12 B12: basis on every value (R2)

| Value | Basis rule |
|---|---|
| Imported line items | As chosen at import (`reported` / `assumed`), unchanged |
| Manual corrections | **`PATCH /line-items/{id}` now requires `basis`**, either `reported` or `assumed`. `reported` requires a `source` object (the filing it was corrected to); `assumed` requires a `rationale`. Previously the old basis was kept, so an analyst-entered number could still say "reported" (C6). |
| Historical metrics, liquidity ratios, DCF outputs, presentation margins, sensitivity cells | `derived`. Each metric object and each result block carries `"basis": "derived"`. |
| Scenario assumptions | `assumed` with a rationale, or `reported` with a linked source (rules below) |
| Market inputs (share price, market-data date) | `reported` **only if `market_source_id` links to a qualifying source**; otherwise `assumed`, and then `market_rationale` is required. It's currently hard-coded as `reported` (C5). Affects provenance of **new** runs only; stored runs are never rewritten. |
| Base NWC | `derived`, with its components' provenance |

**Basis enforcement rules (A4–A6).** Clients may only submit `reported` or `assumed`. `derived` exists only in values the backend computes.

| Rule | Applies to | Enforced by |
|---|---|---|
| **A4. `reported` needs a linked source record.** The value's `source_id` must reference an existing source **owned by the user** whose `kind` is one of `csv_import`, `filing`, `market_data` or `synthetic`. A `manual` source can never back a `reported` value. | Line items (import, PATCH), assumptions, market inputs | (1) Pydantic: `reported` requires `source_id` (or a `source` object on PATCH, which creates a `filing` source). (2) Service: the source exists, is owned and is a qualifying kind; otherwise 422 `BASIS_SOURCE_REQUIRED` / `BASIS_SOURCE_KIND`. (3) **Database triggers** (migration 0002, section 4.10): `BEFORE INSERT/UPDATE` on `line_items` and `assumptions` raise if a `reported` row's source is missing or of another kind. |
| **A5. `assumed` needs a rationale.** A non-blank `rationale` (trimmed, 1–2,000 characters). | Assumptions (`rationale`); line items imported with `basis=assumed` (a `rationale` form field, stored on the source and on each item's `note`); PATCH with `assumed` (`rationale`); market inputs without a source (`market_rationale`) | (1) Pydantic `model_validator` → 422 `validation` (`RATIONALE_REQUIRED`). (2) Database triggers on `assumptions` (`rationale`) and `scenarios` (`market_rationale` when `share_price` is set without `market_source_id`). |
| **A6. `derived` can't be assigned manually.** | Every request body that carries a basis | (1) The schemas accept only `Literal["reported", "assumed"]`. `AssumptionIn` currently also accepts `"derived"`; that is removed (C12). (2) Database triggers reject `derived` on `line_items` and `assumptions`, because derived values are never stored as inputs. |

- **Existing rows:** the triggers fire only on INSERT and UPDATE, so existing rows are never rewritten. Migration 0002 runs a **read-only pre-check** that lists any existing rows that would violate A4–A6, so they can be reviewed. (There is no production data yet; development databases can be rebuilt.)
- **Creating sources:** B7 gains **`POST /sources`** (`{kind: "filing" | "market_data", title, uri?, reference?, notes?}`, owner-only), so analysts can link reported assumptions and market prices to a document. `csv_import` and `synthetic` sources are created by the system only.

### 4.13 Engine version: scope and bump checklist (A1, A3)

**Scope.** `ENGINE_VERSION` identifies the **valuation calculation contract**. It must change if, and only if, for some valid input, any of the following could change:

1. **DCF results:** any field of the canonical `run_dcf` result JSON. This includes issue codes, severities, messages and their order, because they are part of `result_json`.
2. **Input fingerprinting:** the canonical serialisation of `DcfInputs`, and therefore `input_hash`.
3. **Frozen-input reconstruction:** how `inputs_json` is turned back into `DcfInputs` (`DcfInputsIn` → engine mapping).
4. **Sensitivity semantics:**
   - the supported variables and how each is applied;
   - axis construction from `step` and `steps_each_side`;
   - cell validity and error codes;
   - output selection;
   - the `change_abs` / `change_pct` definitions and NM rules;
   - the base-match rule.

Outside the scope, so **no bump**: historical-analysis metrics (including the liquidity ratios), presentation margins, LIM-12 driver warnings (computed outside `result_json`), the API envelopes and the UI.

**Bump checklist.** Every step is required in the same pull request:
1. **Classify** the change against the four scope items. If in doubt, treat it as in scope.
2. **Bump** `ENGINE_VERSION`:
   - **minor** (`0.1.0` → `0.2.0`) for any in-scope change;
   - **major** only if frozen-input reconstruction (item 3) changes. That also needs an `inputs_schema_version` increment and a versioned reader that keeps old runs readable (LIM-22).
3. **Update the golden tables:** DCF goldens (SHA-256 of the canonical KA-DCF-02 and KA-DCF-03 results) and sensitivity goldens (KA-SENS-01, KA-SENS-02 and the KA-DCF-03 grid hash, section 8.1). Add a new entry keyed by the new version and **keep the old entries** as history.
4. **Explain every changed number:**
   - regenerate `docs/verification/independent-verification.md`;
   - record before and after values for every changed known answer in a new `docs/engine-changelog.md`, with the reason.
5. **Run the full backend suite** on Python 3.12 and 3.13, and confirm that `POST /runs/{id}/verify` on a run from the old version reports `engine_version_changed: true` while still returning the stored results.
6. **Update the limitations register** (LIM-21 impact) and write a release note: runs frozen under the old version keep their stored results and remain verifiable, but new sensitivity requests return 409 until the scenario is re-frozen.
7. **Record the owner's approval** in the pull request before merging.

**CI enforcement:** the golden test **fails** if any DCF or sensitivity golden value differs while `ENGINE_VERSION` is unchanged, or if `ENGINE_VERSION` has no golden entry. So an unannounced change in calculation semantics can't merge.

### 4.14 SQLite transaction and locking strategy for freezes (A8)

**Connection settings,** applied on every SQLite connection by an engine `connect` listener:
- `PRAGMA foreign_keys = ON` (already on);
- `PRAGMA busy_timeout = 5000`, so a writer waits up to 5 s for the lock instead of failing at once;
- `PRAGMA journal_mode = WAL` on file databases, so readers never block the writer and the writer never blocks readers;
- the pysqlite driver's implicit transaction handling is disabled (`isolation_level = None`), and SQLAlchemy's `begin` listener issues `BEGIN` explicitly. This is the documented SQLAlchemy recipe; pysqlite's default defers `BEGIN` and gives unreliable locking.
- A **`write_transaction(immediate=True)`** context manager makes the `begin` listener issue **`BEGIN IMMEDIATE`** instead. That takes SQLite's RESERVED write lock at the start of the transaction, before any read inside it.

**Freeze request sequence:**

| Step | Lock held | Action |
|---|---|---|
| 1 | None | Validate the header, key format and body (422 on failure). |
| 2 | Read (deferred transaction, WAL snapshot) | Owner check. **Fast replay path:** if `(user, key)` already exists, compare `request_fingerprint` and return 200 replay or 409 now. Otherwise load the scenario and statements, assemble the inputs and **run the engine. All computation happens outside the write lock** to keep it short. End the read transaction. |
| 3 | **`BEGIN IMMEDIATE`** (RESERVED, writers serialised) | Re-check `(user, key)` **inside** the write transaction, because another request may have committed since step 2. If it now exists: compare fingerprints, `COMMIT` without writing, and return 200 replay or 409. Otherwise `INSERT` the run and its single audit event, then `COMMIT`. |
| 4 | — | **Backstop:** the unique index `(created_by, idempotency_key)` stays in place. If an `IntegrityError` ever occurs (e.g. a writer outside this code path), roll back, re-read the winning row and return 200 replay or 409. |
| 5 | — | **Lock timeout:** if `BEGIN IMMEDIATE` can't get the lock within `busy_timeout` (`SQLITE_BUSY`), return **503 `DATABASE_BUSY`** with `Retry-After: 1`. Nothing has been written, so the client retries **with the same key**, which is safe. |

- **Consequence:** under any interleaving, exactly one row exists per `(user, key)`. Every concurrent request with the same key gets the same run (201 for the winner, 200 replays for the rest) or a clean 409/503, and never a duplicate.
- **Other multi-row writes** use the same `write_transaction(immediate=True)`: sample load (B9), CSV commit, and scenario save.
- **PostgreSQL later:** step 3 becomes `INSERT … ON CONFLICT (created_by, idempotency_key) DO NOTHING RETURNING id`, followed by a `SELECT` of the winner. This is noted against LIM-18.

---

## 5. Liquidity: line items and ratio formulas

### 5.1 Line items (all on the balance sheet, at the fiscal year-end; positive magnitudes, D-02)

| Code | Label | Status | Definition and rules |
|---|---|---|---|
| `total_current_assets` | Total current assets | **New** | As reported: assets expected to be realised within 12 months or one operating cycle. |
| `total_current_liabilities` | Total current liabilities | **New** | As reported, **including** the current portion of debt and current lease liabilities. |
| `marketable_securities` | Short-term marketable securities | **New** | Liquid investments held as current assets and **not** already in cash and cash equivalents. **Must not double-count `cash`.** If the company has none, enter **0** explicitly. A blank stays *missing* and the ratios that need it become *missing* (LIM-23). |
| `cash` | Cash and cash equivalents | Existing, unchanged | Reused. |
| `accounts_receivable` | **Trade (accounts) receivable** | Existing; **label clarified only** | Reused as trade receivables. The code is unchanged, so existing data and the NWC formula are unaffected. |
| `inventory` | Inventory | Existing, unchanged | Used in the consistency check only (the quick ratio is built from components; 5.2). |

The operating NWC used in the DCF (AR + inventory + other operating current assets − AP − other operating current liabilities) **is not changed** by these items.

### 5.2 Ratio formulas (new engine metrics in `historical.py`, missing-aware)

| Metric | Formula | Missing | Not meaningful |
|---|---|---|---|
| `current_ratio` | `total_current_assets / total_current_liabilities` | Either input missing → MISSING, naming the inputs | TCL = 0 → NM ("total current liabilities is zero") |
| `quick_ratio` | `(cash + marketable_securities + accounts_receivable) / total_current_liabilities` | Any of the four missing → MISSING, naming each | TCL = 0 → NM |
| `cash_ratio` | `(cash + marketable_securities) / total_current_liabilities` | Any of the three missing → MISSING | TCL = 0 → NM |

- **Quick ratio definition:** built from components (cash + marketable securities + receivables), the conservative acid test. It **never falls back** to the alternative `(TCA − inventory) / TCL`. Switching definitions silently would be the same mistake D-03 rules out for EBITDA. The definition is shown in `metric_definitions` (B10).
- **Zeros:** explicit zeros are data. Cash 0, securities 0 and receivables 0 with TCL 300 give a quick ratio of **0.0**, which is OK and *not* missing.
- **Negative inputs** are rejected at import (`SIGN_CONVENTION`).

### 5.3 Consistency checks (warnings, D-12)

| Code | Check | Missing-data rule |
|---|---|---|
| `LIQUIDITY_COMPONENTS_EXCEED_CA` | Sum of the **present** current-asset components (cash, marketable securities, AR, inventory, other operating current assets) > TCA | Uses only components that are present (all are ≥ 0, so a partial sum is still a valid lower bound) and **lists which were included**. Skipped and disclosed if TCA is missing. |
| `OPERATING_PAYABLES_EXCEED_CL` | AP + other operating current liabilities (present ones) > TCL | Same rule |
| `CURRENT_ASSETS_EXCEED_TOTAL` | TCA > total assets | Only if both are present |
| `CURRENT_LIABILITIES_EXCEED_TOTAL` | TCL > total liabilities | Only if both are present |

### 5.4 Known-answer cases (hand-computed from the updated synthetic sample)

Sample additions (INR crores; **marketable securities entered explicitly as 0**):

| | FY2023 | FY2024 | FY2025 |
|---|---|---|---|
| Total current assets | 480 | 540 | 600 |
| Total current liabilities | 260 | 280 | 300 |
| Marketable securities | 0 | 0 | 0 |
| *(existing)* cash / AR / inventory / other operating CA | 120 / 200 / 140 / 20 | 135 / 225 / 158 / 22 | 150 / 250 / 175 / 25 |

In every year, TCA equals cash + AR + inventory + other operating current assets exactly (e.g. FY2025: 150 + 250 + 175 + 25 = 600). AP + other operating current liabilities (FY2025: 150) ≤ TCL, and TCA ≤ total assets.

| Case | Expected |
|---|---|
| **KA-LIQ-01** FY2025 | current **2.000000**, quick (150+0+250)/300 = **1.333333**, cash 150/300 = **0.500000** |
| FY2024 | 540/280 = **1.928571**, 360/280 = **1.285714**, 135/280 = **0.482143** |
| FY2023 | 480/260 = **1.846154**, 320/260 = **1.230769**, 120/260 = **0.461538** |
| **KA-LIQ-02** marketable securities missing | current OK; quick and cash **MISSING** ("marketable_securities") |
| **KA-LIQ-03** TCL = 0 | all three **NM** |
| **KA-LIQ-04** explicit zeros (cash = ms = AR = 0) | quick **0.0** and cash **0.0** (OK, not missing) |
| **KA-LIQ-05** cash 400 with TCA 600 | `LIQUIDITY_COMPONENTS_EXCEED_CA` (400+0+250+175+25 = 850 > 600) |
| **KA-LIQ-06** TCA missing | current **MISSING**; component check skipped and disclosed; quick and cash still OK |
| **KA-DCF-03 unchanged** | The updated sample still produces **31.2150** per share; none of the new items is a DCF input (test) |

---

## 6. Financial integrity rules

| Rule | Enforcement |
|---|---|
| **No financial arithmetic in TypeScript** | `lib/format.ts` is the only number transformer (display only). An ESLint rule bans arithmetic on API financial fields outside `lib/`. A display-trace E2E test checks each displayed figure equals `format(apiValue)` on the Results, Runs, Sensitivity, Analysis and DCF screens. |
| **Exact input parsing** | `lib/parse.ts` shifts the decimal point on the string and never divides. Property-tested. |
| **Missing stays missing (R3)** | `null` renders as "—" with a reason tooltip; NM as "NM". Lint rule `no-nullish-zero` bans `?? 0` / `\|\| 0` on API values. Backend: no defaults on financial inputs, the engine's silent-zero test, and the new liquidity tests. |
| **Basis on every value (R2)** | Every financial value component requires a `basis` prop. The UI renders R, D or A, and assumed inputs in blue. The backend provides basis on every value (B12). A component test fails if a value renders without a basis. |
| **Immutable runs** | No mutating controls on `/runs/*`. A test asserts no mutating request is sent from those pages. |
| **Sensitivity only from frozen runs on a matching engine (R1)** | The route requires a run. The backend enforces version and fingerprint (B3). Stored results stay viewable on any engine version. |
| **Synthetic data labelled (R4)** | Banner whenever `is_synthetic`; also in the dashboard sample card and in screenshots. |
| **Engine independence (R7)** | The purity test is unchanged and enforced: the new `presentation.py` and liquidity code are standard library only. |

---

## 7. UI design direction

The design is unchanged from revision 1, with the following added for D4-09.

| Element | Specification |
|---|---|
| Palette | Navy 900 `#0B1B33` rail and header; white canvas; slate greys; one accent blue `#1F5FBF` for interactive elements and **assumed inputs**. Status colours only for status (amber, red, green). Negatives in parentheses, never red/green. No gradients or decorative shadows. |
| Typography | Inter with tabular figures; IBM Plex Mono for hashes and codes. 13 px tables, 14 px body. |
| Basis badges | **R** slate outline · **D** slate filled · **A** blue outline. A legend sits in each table footer. |
| Numbers | Right-aligned; thousands separators; `(1,234.5)`; `9.6%`; `7.9x`; full precision on hover; "—" missing; "NM". |
| **≥ 1280 px** | Full layout: expanded left rail, side panels beside tables. |
| **1024–1279 px** (D4-09) | Left rail collapses to icons with tooltips. Side panels move below the main content. KPI strip wraps to two rows. **Wide tables scroll horizontally inside their container** with a sticky first column and header, and the page itself never scrolls sideways. The DCF grid keeps the label column pinned. |
| < 1024 px | Non-blocking notice ("DealForge is designed for desktop screens"). No mobile-first layout (LIM-24). |
| First-time dashboard (R5) | One clear primary action, *Load the synthetic sample company*, with a short description of what it contains and a "SYNTHETIC – not real data" tag. A secondary *Create your own company* action. Then the 4-step checklist with server-derived progress. |

---

## 8. Testing, error handling and acceptance criteria

### 8.1 New backend tests (in addition to the existing 374, which must stay green)

| Area | Tests |
|---|---|
| Liquidity (engine) | KA-LIQ-01…06. Hypothesis property test: ratios are MISSING whenever any required input is `None`, and never numeric. Explicit-zero cases. Sign rules for the new items. Purity test still green. |
| Engine version guard (A1–A3) | **DCF goldens:** SHA-256 of the canonical KA-DCF-02 and KA-DCF-03 `result_json`, keyed by `ENGINE_VERSION`. **Sensitivity goldens:** KA-SENS-01, KA-SENS-02 and the SHA-256 of the canonical KA-DCF-03 7×7 WACC × g grid, keyed by `ENGINE_VERSION`. The test fails on any golden difference without a version bump, and on a version with no golden entry (section 4.13). |
| **KA-SENS-01** (known answer, A2) | KA-DCF-02 inputs: UFCF 100 / 110 / 121 / 133.1 / 146.41, bridge −300 + 100 − 20, 100 shares, base WACC 10%, g 2%. Request: WACC step 0.005 × 1, g step 0.005 × 1, output value per share. Engine values must match an **independent exact (`Fraction`) recomputation** to 1e-12 relative; the values below are to 6 dp. **Rows WACC 9.5 / 10.0 / 10.5%; columns g 1.5 / 2.0 / 2.5%:** 9.5%: 14.207944 / 15.056602 / 16.026498 · 10.0%: 13.201070 / **13.936364** (base) / 14.769697 · 10.5%: 12.306780 / 12.948625 / 13.670701. Selected `change_abs`: +1.120239 (9.5%, 2.0%), −0.735294 (10.0%, 1.5%), −0.265663 (10.5%, 2.5%). Matching `change_pct`: +8.0382%, −5.2761%, −1.9063%. |
| **KA-SENS-02** (NM rule, A9) | The same request on KA-DCF-02 with debt 2,000 instead of 300, so the base equity is negative: base value per share = (1,613.636364 − 2,000 + 100 − 20) / 100 = **−3.063636**. Every cell's `change_pct` is **NM** ("base value is zero or negative"). Every `change_abs` **equals KA-SENS-01's** (the bridge shift is constant), e.g. +1.120239 at (9.5%, 2.0%), and each value is KA-SENS-01's minus 17.0 (e.g. 15.056602 − 17 = −1.943398). A unit test also covers `base == 0` exactly. |
| Presentation | Margins equal hand calculations for KA-DCF-03; revenue ≤ 0 gives NM; stored `result_json` byte-identical and fingerprints unchanged after B5. |
| Migration 0002 | Upgrade adds the columns and indexes. **Both immutability triggers still exist and still refuse UPDATE/DELETE after upgrade, and after downgrade → upgrade.** Existing runs keep their data. The schema matches the ORM (`compare_metadata` empty). |
| Idempotency (A7, A8) | **Missing header → 422 and no row; the engine isn't called (spy).** Replay → 200, same run, replay header. Reused key with a different body → 409. Malformed key → validation. Keys are per user. **8 threads, same key** (file SQLite, WAL) → exactly 1 row, 1 audit event, and all responses carry the same run ID and hash (one 201, seven 200). **8 threads, different keys** → 8 rows. **Re-check inside `BEGIN IMMEDIATE`:** a test injects a competing commit between steps 2 and 3 and gets a replay, not a duplicate. **Lock timeout:** with `busy_timeout` set to 50 ms while another connection holds `BEGIN IMMEDIATE` → 503 `DATABASE_BUSY` and no row; retrying the same key afterwards gives exactly 1 run. WAL mode is active on file databases. Immutability triggers still enforced. |
| Basis enforcement (A4–A6) | `reported` without a source, with another user's source, or with a `manual` source → 422, and the **database trigger** also rejects a direct `INSERT`. `assumed` without a rationale or with whitespace only → 422 and trigger rejection. `derived` in any request → 422 and trigger rejection. Market price without a source and without `market_rationale` → 422. `POST /sources` owner-only, allowed kinds only. Pre-check lists violating legacy rows without modifying them. |
| Draft preview | Zero database writes (probe). A draft equal to the saved scenario gives a byte-identical result to the saved preview. Draft validation errors. Other user's scenario → 404. |
| Sensitivity | `change_abs` and `change_pct` per section 4.3. All sensitivity arithmetic lives in the engine (the purity test covers `frozen_run_grid`). Base cell == stored run value. Scenario edited after freezing → grid unchanged. Monotonic in WACC and g. Invalid cells. **Engine mismatch → 409 while `GET /runs/{id}` still serves the stored result.** Corrupted inputs → 409. Limits. Isolation. |
| Dashboard / onboarding | Exact counts. Onboarding steps flip as data is added. Recent companies resolved through every audit entity type. No raw `detail` leaks. Empty account. Isolation. |
| Runs list | Pagination, filters, ordering, isolation, values identical to `GET /runs/{id}`, `engine_compatible` flag. |
| Samples | Load gives a complete company with provenance on every value. **Preview equals the independent KA-DCF-03 result exactly.** Liquidity ratios equal KA-LIQ-01. Second load → 409 with the existing IDs. Atomic on injected failure. Isolation. |
| Sources / completeness / basis | Source fields equal the import's. DCF group unchanged for the sample (complete). Liquidity group lists missing marketable securities when blank. PATCH without `basis` → validation. Market basis follows `market_source_id`. |
| SPA fallback | `/api/v1/nope` → JSON 404, not HTML. Unauthenticated API → 401 JSON. `/companies/1/analysis` → `index.html`. Missing `/assets/x.js` → 404. `/openapi.json` and `/docs` unaffected. POST to an SPA path → 405. Fallback disabled when `dist` is absent. |
| Response schemas | Every 200 response in the suite validates against its declared model. `docs/openapi.json` up to date (CI drift check). |

### 8.2 Frontend tests

These are the same as revision 1, plus:
- **1024×768 and 1440×900 Playwright projects:** no page-level horizontal overflow (`scrollWidth ≤ innerWidth`); wide tables scroll inside their container with a sticky first column.
- **Onboarding E2E:** new user → load sample → checklist updates step by step → freeze a run → sensitivity opens.
- **Basis badge component test:** a value can't render without a basis.
- **Engine-mismatch UI:** with a fixture of a run on another engine version, the results still render and the sensitivity screen shows the 409 explanation.
- **Idempotency UI:** a double-click on Freeze sends one key, produces one run, and shows one success state.

### 8.3 Phase 4 definition of done

- All 8 screens and the first-time flow work against the real API.
- No hardcoded financial outputs (display-trace and review checklist).
- Backend suite green (374 existing plus new), frontend unit, component and E2E green on CI, OpenAPI drift check green.
- Screenshots of every screen at 1440 px and key screens at 1024 px in `docs/screenshots/`.
- README has instructions for running the whole application locally.
- Limitations register updated (section 12).

---

## 9. Milestone-wise implementation plan

Each milestone ends with tests run, outputs verified, a list of files changed, the limitations register updated and a commit. **⏸ = I stop for your review.**

| # | Milestone | Deliverables | Acceptance criteria |
|---|---|---|---|
| **F0a** | Engine and data additions | Liquidity items, ratios and checks (B10); `presentation.py`; **`engine.sensitivity.frozen_run_grid` with `change_abs`/`change_pct`** (A1, A9); versioning-policy text, **bump checklist** and `docs/engine-changelog.md` stub (A3); **DCF and sensitivity golden tests including KA-SENS-01/02** (A2); sample CSV liquidity rows; sample JSON gains a rationale on every assumption and a `market_rationale` (A5, C9); label clarification; updated Phase 3 test expectations (C4) | KA-LIQ-01…06 and KA-SENS-01/02 pass against exact recomputation. KA-DCF-03 still 31.2150. Golden hashes unchanged at `0.1.0`. Purity green. No existing formula diff. All 374 tests green, with the documented expectation updates only. |
| **F0b** | Migration, transactions and idempotency | Migration `0002` (hand-written: columns, indexes, **basis triggers**, pre-check); **SQLite connection settings and `write_transaction(immediate=True)`** (section 4.14); **mandatory** idempotent freeze (A7, A8); concurrency tests | Immutability and basis triggers work after upgrade and after downgrade/upgrade. Every idempotency and locking test in section 8.1 green. Schema matches ORM. Phase 3 suite green under the new transaction handling (C11). |
| **F0c** | API additions | ORM-free input assembly (C2); B1–B4, B5 `context`/`presentation`, B7–B9, B11, B12; response models and committed `docs/openapi.json` (B6); CI drift check | All section 8.1 tests green. Every 200 response schema-valid. Draft preview has zero writes. |
| **⏸ F0 review** | Backend report | Endpoint list, test results, sample demo transcript, limitations | **Your approval before frontend work.** |
| **F1** ⏸ | Frontend foundation and style guide | Scaffold, tokens, component kit including basis badges, `format`/`parse`, typed client, auth flows, app shell (both breakpoints), frontend CI job, style-guide page with screenshots at 1440 and 1024 | CI green. Auth and expiry tested. **Style guide approved before F2.** |
| F2 | Dashboard and first-time flow | Dashboard, onboarding panel, sample loader, companies list and create | New-user flow loads the sample in one click. Counts and checklist from the API. |
| F3 | Company workspace and import | Overview, completeness groups, issues, provenance (values and derived metrics), import wizard, PATCH with basis, instruments | Broken CSV blocked with row/column errors. Provenance shows file, SHA-256, row and column. "Mark missing" shows "—". |
| F4 | Financial analysis | Statements, ratio tables including **liquidity**, charts | All ratios from the API. KA-LIQ-01 values visible for the sample. Missing and NM rendered correctly. |
| F5 ⏸ | DCF workspace | Draft model, live draft preview, LIM-12 flags, margins, save, clone, idempotent freeze | Exact request bodies. Zero-write preview (backend-verified). One run per click. **Demo-flow review.** |
| F6 | Valuation results | KPIs, EV composition, bridge waterfall, dilution, dates, input provenance | Display-trace green. Units and basis on every figure. |
| F7 | Saved runs | Global list, filters, pagination, detail, verify, engine-compatibility badges | Values identical to the stored results. No mutating controls. |
| F8 | Sensitivity | Grids, base outline, invalid cells, heat shading, engine-mismatch state | Base == run. Post-freeze scenario edit has no effect. 409 handled with results still viewable. |
| F9 | Model audit | All issue groups, "why" catalogue, go-to links | Each category reproduced from a fixture. |
| F10 ⏸ | Hardening and delivery | Full E2E at both viewports, axe, screenshots, README run guide, limitations, final report | Everything green on CI. Final report. |

---

## 10. Decision record

| ID | Decision | Outcome |
|---|---|---|
| D4-01 | Token storage | **Approved:** memory + `sessionStorage` for the development stage. HttpOnly/Secure/SameSite cookie + CSRF **required before public deployment** (LIM-20). |
| D4-02 | Liquidity ratios | **Amended:** implement current, quick and cash ratios with 3 new line items, missing-aware formulas, zero-denominator NM and tests (section 5). |
| D4-03 | Recently accessed | **Approved:** recently *active*, from audit events (LIM-26). |
| D4-04 | Live recalculation | **Approved:** draft preview with no database or audit writes (B4). |
| D4-05 | Engine mismatch | **Approved:** 409 for new sensitivity; stored results stay viewable and verifiable (R1). |
| D4-06 | EBIT and UFCF margins | **Approved:** backend `presentation` block, outside `result_json` and the fingerprint. |
| D4-07 | Serving | **Approved:** FastAPI same-origin, with SPA fallback that never intercepts `/api` (B11). |
| D4-08 | Typed client | **Approved:** generated OpenAPI types plus a committed `openapi.json` with a drift check. |
| D4-09 | Device support | **Amended:** target ≥ 1280 px; usable at 1024 px through a compact rail and in-table horizontal scrolling; no mobile-first. |
| D4-10 | Freeze idempotency | **Approved:** backend-enforced, concurrency-safe, persisted (migration 0002). |
| D4-11 | Sensitivity axes | **Approved:** generated by the backend around the frozen base. |
| R1–R7 | Additional requirements | Incorporated: R1 → B3, B2 and §3.6; R2 → B12 and §6; R3 → §5 and §6; R4 → B9; R5 → B1, B9 and §7; R6 → B8; R7 → §6 and C1–C4. |

### 10.1 Owner amendments in revision 3

| ID | Amendment | Where it's specified |
|---|---|---|
| A1 | Engine version covers DCF **and** sensitivity semantics | §4.13 scope; §4.3 step 5 (all sensitivity arithmetic in the engine); C1 |
| A2 | Known-answer sensitivity golden test | §8.1 KA-SENS-01, KA-SENS-02 and the KA-DCF-03 grid hash; F0a |
| A3 | Explicit engine version-bump checklist | §4.13 checklist and CI enforcement |
| A4 | `reported` basis needs a linked source record | §4.12 enforcement rules; `POST /sources`; DB triggers (§4.10) |
| A5 | `assumed` basis needs a rationale | §4.12; `market_rationale` column (§4.10); C9 |
| A6 | `derived` basis can't be assigned manually | §4.12; schema literals; DB triggers; C12 |
| A7 | `Idempotency-Key` mandatory for freezes | §4.5 (422 when missing); C10 |
| A8 | SQLite transaction and locking strategy | §4.14 (WAL, busy timeout, `BEGIN IMMEDIATE`, re-check, backstop, 503); C11 |
| A9 | Absolute changes; percentage NM when base ≤ 0 | §4.3 response and step 5; §3.6; KA-SENS-02 |

---

## 11. Conflicts with the engine and Phase 3, and their resolution

| # | Conflict found in the current code | Resolution |
|---|---|---|
| **C1** | `version.py` says *"Bump on any change that can alter a numeric output"*. Adding liquidity metrics to the historical analysis would then force a bump, and under D4-05 **every existing run would immediately lose sensitivity**. | **Versioning policy clarified (A1):** `ENGINE_VERSION` identifies the **valuation calculation contract**, which covers DCF results, input fingerprinting, frozen-input reconstruction **and sensitivity semantics** (§4.13). Additive analysis metrics and presentation fields don't change it. **The value stays `0.1.0`**, because adding `frozen_run_grid` creates new sensitivity semantics with no prior version to differ from. Enforced by the DCF and sensitivity golden tests. |
| **C2** | `build_dcf_inputs` takes an ORM `Scenario`. Building a draft as a transient ORM object attached to a project would be **cascaded into the session and could autoflush an INSERT**, breaking D4-04. | Refactor into an ORM-free `assemble(...)` over plain dataclasses. Behaviour is unchanged: the existing preview, run and contract tests must pass unmodified, and a zero-write probe is added. |
| **C3** | `alembic/env.py` uses `render_as_batch=True`, so an **autogenerated** 0002 would recreate `valuation_runs` and **silently drop both immutability triggers**. | 0002 is hand-written with native `ADD COLUMN` and `CREATE INDEX`. The downgrade recreates the triggers. Tests assert the triggers exist and work after upgrade and after a round trip. |
| **C4** | Adding liquidity rows to the sample CSV changes two Phase 3 expectations: stored line items 84 → 93 (`test_import_persistence`) and dictionary size 29 → 32 (`test_financials_api`). The demo transcript and file SHA change too. | Expected and documented test updates, not formula changes. A new test proves the KA-DCF-03 tie (31.2150) is unchanged. The demo transcript is regenerated. |
| **C5** | Provenance hard-codes the market share price as `basis: "reported"`, even when no source was given. | Basis is `reported` only with a `market_source_id`, otherwise `assumed`. Affects new runs only; stored runs are never rewritten. |
| **C6** | `PATCH /line-items/{id}` keeps the item's previous basis, so an analyst-entered number can still be labelled *reported*, violating R2. | PATCH now **requires** `basis`. This is a **breaking change** to a Phase 3 contract. The three Phase 3 tests that patch line items (four PATCH calls, in `test_financials_api.py` and `test_valuation_api.py`) are updated, and `api-contract.md` records the change. |
| C7 | Operating NWC and the new current-asset totals could be confused. | NWC is unchanged and documented as *operating*. Liquidity totals are separate items, and the label and definition text make the difference explicit. |
| C8 | Concurrent freezes on SQLite could raise "database is locked" instead of the intended `IntegrityError` path. | Explicit `busy_timeout` and serialised writes, proven by the 8-thread test. |

| **C9** | A5 requires a rationale on every `assumed` value. The sample `ardent_base_scenario.json` has a rationale only on the revenue-growth rows and no `market_rationale`, and Phase 3 tests and the demo send these assumptions. | The sample JSON gains a rationale on every assumption and a `market_rationale` (data only; the numbers are unchanged, so the KA-DCF-03 tie holds). Tests that build assumptions inline add rationales. **Breaking change** for API clients that omit rationales, recorded in `api-contract.md`. |
| **C10** | A7 makes `Idempotency-Key` mandatory. Every Phase 3 freeze call omits it: 8 call sites in total, 5 in `test_valuation_api.py`, 2 in `test_auth_and_access.py` and 1 in `scripts/demo_workflow.py`. | All callers send a key. A test proves the old call without a key now fails with 422 and creates nothing. **Breaking change**, recorded in `api-contract.md`. |
| **C11** | A8 changes how every SQLite connection manages transactions (`isolation_level=None`, explicit `BEGIN`, WAL). That affects all Phase 3 code paths, not just freezes. | Applied in `db/session.py` only. **The entire Phase 3 suite must pass unchanged** as the acceptance check. WAL creates `-wal` and `-shm` files next to the database; `.gitignore` is updated. In-memory databases aren't used. |
| **C12** | `AssumptionIn.basis` currently accepts `"derived"`, which violates A6. | The literal is narrowed to `"reported" | "assumed"`. Existing tests don't send `derived`; a new test proves it's rejected. |

**No conflict with engine independence:** every engine addition is standard library only, the purity test is unchanged, and no existing formula function is edited.

---

## 12. New limitations and remaining risks

### Limitations to add to `docs/limitations-register.md`

| ID | Limitation | Status |
|---|---|---|
| LIM-20 | Auth token in memory + `sessionStorage` (exposed to XSS). **HttpOnly, Secure, SameSite cookie + CSRF required before public deployment.** | Planned (deployment blocker) |
| LIM-21 | Sensitivity is refused for runs frozen under an older engine version; stored results stay viewable and verifiable. | Accepted |
| LIM-22 | Rebuilding old runs depends on the `DcfInputs` schema; future schema changes need a versioned reader (`inputs_schema_version` stored from 0002). | Planned |
| LIM-23 | Quick and cash ratios need marketable securities entered explicitly (0 if none); a blank makes them *missing*. | Accepted |
| LIM-24 | Layouts below 1024 px are not supported (non-blocking notice). | Accepted |
| LIM-25 | Idempotency keys are retained indefinitely (runs are immutable). | Accepted |
| LIM-26 | "Recent companies" reflects writes (audit events), not views. | Accepted |
| LIM-27 | Under heavy write contention SQLite can return 503 `DATABASE_BUSY` after 5 s. Clients retry with the same idempotency key, which is safe. | Accepted (SQLite stage) |
| LIM-28 | Basis triggers apply to new and updated rows only. Legacy development rows are reported by the pre-check, not rewritten. | Accepted |

### Remaining risks

| Risk | Mitigation |
|---|---|
| Hidden arithmetic creeping into React | Single `format.ts`, lint rules, display-trace E2E, review checklist |
| Float drift in input parsing | String-based parsing, property-tested |
| Live preview races | Query cancellation, AbortController, sequence check, stale overlay |
| OpenAPI or response drift | Committed `openapi.json`, CI drift check, response validation test |
| Breaking PATCH change (C6) | Only internal clients exist today; recorded in `api-contract.md` |
| SQLite-specific behaviour (triggers, locking) | Tests on SQLite now; PostgreSQL triggers and locking noted for the migration (LIM-18) |
| Scope creep (comps and M&A screens) | Out of Phase 4; proposed for Phase 5 |
| Design subjectivity | ⏸ style-guide approval at F1; demo review at F5 |
