# DealForge Phase 4: professional financial analysis frontend (plan)

> **Status: PLANNING ONLY. Awaiting approval.** No frontend or backend code has been written for
> Phase 4. Based on `main` at `2fd8299` (Phase 3 merged via PR #1), the 29 live API endpoints,
> `docs/api-contract.md` and `docs/phase-3-design.md`. Decisions needing approval are marked **[D4-xx]**
> and collected in section 9.

## Contents

1. [Frontend architecture](#1-frontend-architecture)
2. [Proposed folder structure](#2-proposed-folder-structure)
3. [Screens and screen-by-screen API mapping](#3-screens-and-screen-by-screen-api-mapping)
4. [Backend changes required](#4-backend-changes-required)
5. [Financial integrity rules for the frontend](#5-financial-integrity-rules-for-the-frontend)
6. [UI design direction](#6-ui-design-direction)
7. [Testing, error handling and acceptance criteria](#7-testing-error-handling-and-acceptance-criteria)
8. [Milestone-wise implementation plan](#8-milestone-wise-implementation-plan)
9. [Risks and unresolved decisions](#9-risks-and-unresolved-decisions)

---

## 1. Frontend architecture

```
Browser ── React 18 + TypeScript (strict) + Vite
  │  React Router         routes = screens; URL carries company / project / scenario / run IDs
  │  TanStack Query       server state: caching, loading/error states, invalidation, cancellation
  │  React Hook Form+Zod  form structure only (required, type, length); financial rules stay server-side
  │  openapi-typescript   TS types generated from FastAPI's OpenAPI → no hand-copied shapes
  │  openapi-fetch        typed HTTP client; one middleware adds the bearer token and handles 401
  │  Tailwind CSS         design tokens (section 6); small in-house component kit
  │  Recharts             historical bars/lines, UFCF bars, EV composition, bridge waterfall
  │  lib/format.ts        DISPLAY ONLY: rounding, %, x, parentheses, units, "—"/"NM"
  ▼
Vite dev proxy /api → FastAPI :8000      (same origin: no CORS, token never sent cross-site)
Production build: FastAPI serves frontend/dist as static files [D4-07]
```

| Choice | Why | Trade-off |
|---|---|---|
| **TanStack Query** for all server data | Built-in loading, error, stale and refetch handling. Queries are cancelled when inputs change, which live DCF previews need. | One more library to learn. |
| **Generated API types** (`openapi-typescript`) | Backend schema changes break the frontend build instead of failing silently at runtime. | Needs typed response models on the backend (B6). Today many endpoints return untyped `dict[str, Any]`. |
| **URL-driven navigation** (`/companies/7/analysis`, `/runs/42`) | Every screen is linkable and reload-safe; an interviewer can be sent a deep link. | More route definitions. |
| **No global state library** | Server state lives in TanStack Query. Only auth and the unsaved DCF draft are client state (React context / `useReducer`). | — |
| **Draft vs saved vs frozen** made explicit in the DCF workspace | Mirrors the backend: scenarios are editable, runs are immutable. | The UI has three states to explain (section 3.4). |

### Authentication and session handling

- **Login:** `POST /auth/token` returns `{access_token, expires_at}`. The token lives in an in-memory store, mirrored to `sessionStorage` so a page reload doesn't log the user out. It's cleared on tab close, logout or any 401 **[D4-01]**.
- **Every request:** an `openapi-fetch` middleware adds `Authorization: Bearer …`. Tokens are never put in URLs, logs, error messages or local files.
- **Expiry:** the expiry time is known, so the app warns two minutes before it and redirects to `/login?next=<current path>` when it passes. Any 401 from the server (expired or revoked) does the same, and the user returns to the same screen after logging in. An unsaved DCF draft is kept in `sessionStorage` and restored after re-login.
- **Logout:** `POST /auth/logout` revokes the token server-side, then the client clears it.
- **Hardening:** strict Content-Security-Policy in the production build (no inline scripts, `connect-src 'self'`). No `dangerouslySetInnerHTML` (ESLint rule). Never log a token (lint rule plus a test).

### Loading, error and duplicate-submission handling (all screens)

| Situation | Behaviour |
|---|---|
| First load | Skeleton tables and charts that keep the final layout, so nothing jumps around |
| Background refetch | Content stays visible, with a small "updating" indicator |
| `error_type: validation` | Inline next to the field, mapped from `loc`; the form is not cleared |
| `error_type: calculation` | Panel listing each engine issue (`code`, `field`, message), with links to the input; **previous results greyed out and labelled "Stale – inputs invalid"** |
| `not_found` | "Not found or not yours" page (the backend deliberately doesn't distinguish) |
| `conflict` / `import` / `immutable` | Specific dialogs, e.g. "FY2025 already exists – replace?" |
| `authentication` | Session-expired flow (above) |
| Network or 5xx | Retry button, with no automatic retry on POST |
| Duplicate submissions | Mutation buttons are disabled while pending; "Freeze run" also needs a confirm step and has an idempotency key **[D4-10]** |

---

## 2. Proposed folder structure

```
dealforge/
├── backend/                         # unchanged layout; Phase 4 additions marked +
│   ├── app/api/v1/
│   │   ├── dashboard.py             + B1
│   │   ├── runs.py                  + B2, B3 (moved from valuations.py; same paths)
│   │   └── sources.py               + B7
│   ├── app/schemas/responses.py     + B6 typed response models
│   ├── app/services/dashboard.py    + B1
│   ├── app/services/sensitivity.py  + B3
│   └── tests/api/
│       ├── test_dashboard_api.py    +
│       ├── test_runs_list_api.py    +
│       ├── test_sensitivity_api.py  +
│       ├── test_draft_preview_api.py+
│       └── test_response_schemas.py + every 200 response validates against its OpenAPI model
├── frontend/                        + all new
│   ├── package.json  vite.config.ts  tsconfig.json  tailwind.config.ts  index.html
│   ├── scripts/gen-api-types.mjs    # OpenAPI → src/api/schema.d.ts
│   ├── src/
│   │   ├── main.tsx
│   │   ├── app/        App.tsx  routes.tsx  providers.tsx  AppShell.tsx  NotFound.tsx
│   │   ├── api/        schema.d.ts (generated)  client.ts  errors.ts  queries/*.ts (one file per resource)
│   │   ├── auth/       AuthProvider.tsx  RequireAuth.tsx  tokenStore.ts  LoginPage.tsx  RegisterPage.tsx
│   │   ├── components/
│   │   │   ├── ui/     Button Input PercentInput NumberInput Select Tabs Dialog Toast Badge
│   │   │   │           DataTable NumberCell MetricCell BasisBadge ProvenancePopover
│   │   │   │           IssueList ErrorPanel EmptyState Skeleton StaleOverlay SyntheticBanner
│   │   │   └── charts/ HistoricalBars  MarginLines  UfcfBars  EvComposition  BridgeWaterfall
│   │   ├── features/
│   │   │   ├── dashboard/   companies/   financials/   analysis/
│   │   │   ├── dcf/         results/     sensitivity/  audit/   runs/
│   │   ├── lib/        format.ts  parse.ts (string-exact % parsing)  units.ts
│   │   └── styles/     tokens.css
│   ├── tests/          unit + component tests (Vitest + React Testing Library + MSW)
│   │   └── fixtures/   API responses RECORDED from the real backend (never hand-typed numbers)
│   └── e2e/            Playwright tests against the real backend + screenshot capture
└── .github/workflows/ci.yml         + frontend job: lint, typecheck, vitest, build, e2e
```

---

## 3. Screens and screen-by-screen API mapping

Legend: ✅ existing endpoint · 🆕 backend addition from section 4 (B-numbers).

**Navigation:**
- **Left rail:** Dashboard · Companies · Valuations · Saved Runs.
- **Company context:** tabs for Overview · Financial Statements · Analysis · Import.
- **Scenario context:** tabs for DCF Workspace · Results · Audit, plus a Sensitivity tab on a frozen run.
- **Header:** a breadcrumb (`Company › Project › Scenario`), a units chip (`INR crores`), a SYNTHETIC banner when `is_synthetic`, and the user menu.

### 3.1 Dashboard (`/`)

| Feature | Endpoint |
|---|---|
| Totals: companies, projects, scenarios, frozen runs | 🆕 B1 `GET /dashboard` → `counts` |
| Recent valuation runs (company, scenario, value per share with units, time) | 🆕 B1 → `recent_runs` |
| Recently active companies | 🆕 B1 → `recent_companies` **[D4-03]** |
| Recent activity feed (imports, scenario edits, runs) | 🆕 B1 → `recent_activity` (backend-written summaries) |
| New company / new valuation actions | ✅ `POST /companies`, ✅ `POST /projects` |
| Empty state for a first-time user | Same endpoint (`counts` all zero), linking to the guided "import sample company" path |

### 3.2 Company workspace (`/companies/:id`)

| Feature | Endpoint |
|---|---|
| Name, sector, currency, scale, fiscal year end, synthetic flag | ✅ `GET /companies/{id}` |
| Reporting periods and period-end dates | ✅ `GET /companies/{id}/financials` |
| Key historicals: revenue, EBITDA, EBIT, net income per year | ✅ `GET …/financials` (reported items) + ✅ `GET …/historical-analysis` (standardised EBITDA, a derived value) |
| Statement completeness per year (present / missing / required by the DCF) | 🆕 B8, adds `completeness` to `GET …/financials` |
| Data validation warnings | ✅ `GET …/historical-analysis` → `issues` |
| Provenance of any value (click → popover: source, file, SHA-256, row, column, raw text, basis) | ✅ line-item fields in `GET …/financials` + 🆕 B7 `GET /sources/{id}` |
| Import flow: upload → dry-run preview with row/column error table → commit, or replace with a confirm step | ✅ `POST …/financials/import` (`dry_run=true`, then `false`, `replace`) |
| Manual correction, including "mark as missing" (a required note) | ✅ `PATCH /line-items/{id}` |
| Share instruments (options, RSUs, convertibles) | ✅ `GET`/`PUT …/share-instruments` |

### 3.3 Financial analysis (`/companies/:id/analysis`)

| Feature | Endpoint |
|---|---|
| Income statement, balance sheet, cash flow (rows grouped by `statement`, years as columns) | ✅ `GET /line-items` (dictionary) + ✅ `GET …/financials` |
| Each cell: value, a basis badge (**R** reported · **D** derived · **A** assumed), "—" if missing, provenance on click | Same |
| Growth, gross/EBITDA/EBIT/net margins | ✅ `GET …/historical-analysis` |
| Leverage: net debt, net debt / EBITDA, interest coverage | ✅ same |
| Working capital: NWC, NWC % of revenue, ΔNWC | ✅ same |
| Cash flow: simple FCF, FCF conversion, CapEx % revenue, CapEx / D&A | ✅ same |
| Earnings-vs-cash divergence, reconciliations, D&A check | ✅ same → `issues` |
| **Liquidity ratios** (current ratio, quick ratio, cash ratio) | ❌ **Not computable today:** there are no total current assets or liabilities line items. **[D4-02]** |
| Charts: revenue and EBITDA bars, margin lines, FCF vs net income | ✅ same data, plotted directly |

### 3.4 DCF workspace (`/scenarios/:id/dcf`)

Three states shown explicitly in a status strip:
- **Saved scenario:** what's in the database.
- **Draft:** local unsaved edits, outlined in blue.
- **Frozen runs:** read-only snapshots, listed on the right.

| Feature | Endpoint |
|---|---|
| Load the scenario: settings plus assumption rows with rationale and source | ✅ `GET /scenarios/{id}` |
| Historical columns next to the forecast (FY2023–FY2025, actuals, read-only) | ✅ `GET …/historical-analysis` |
| Editable drivers, Y1–Y5: revenue growth, **EBITDA margin**, D&A %, CapEx %, NWC % *(the engine is driven by EBITDA margin and D&A %; EBIT is derived – Phase 1 H.3)* | Edits stay in a local draft |
| Tax rate, terminal growth, WACC inputs (Rf, β, ERP, Kd, size premium, optional Kp, target D/V) or a direct WACC override | Same |
| Market inputs: share price, market-data date, debt basis, leases-as-debt | Same |
| **Live recalculation** on each valid edit (debounced 400 ms, in-flight request cancelled) | 🆕 B4 `POST /scenarios/{id}/preview` with an optional draft body (nothing saved) |
| Projected revenue, EBITDA, D&A, EBIT, tax, NOPAT, CapEx, NWC, ΔNWC, UFCF, discount factor, PV | ✅/🆕 preview response → `result.forecast`, `result.ufcf`, `result.valuation.flows` |
| EBIT margin and UFCF margin rows (display) | 🆕 B5 `presentation` block **[D4-06]** |
| LIM-12 "outside historical range" flags on the exact cell | ✅ preview `warnings[].field` (e.g. `years[3].ebitda_margin`) |
| Save the draft into the scenario | ✅ `PUT /scenarios/{id}` |
| Clone as Upside or Downside | ✅ `POST /scenarios/{id}/clone` |
| **Freeze run** (disabled while a draft has unsaved changes, or while pending) | ✅ `POST /scenarios/{id}/runs` (+ idempotency key **[D4-10]**) |

### 3.5 Valuation results (`/scenarios/:id/results`, also `/runs/:id`)

| Feature | Endpoint |
|---|---|
| EV, equity value, value per diluted share, upside vs market price, with units | ✅ preview / `GET /runs/{id}` → `result.*`; units from 🆕 B5 `company` block |
| PV of forecast cash flows, terminal value, PV of TV, **TV share of EV** | ✅ `result.valuation.{sum_pv_flows, terminal_value, pv_terminal_value, tv_share_of_ev}` |
| Implied exit multiple (cross-check) | ✅ `result.implied_exit_multiple` |
| WACC build (Ke, Kd after tax, weights) | ✅ `result.wacc_build` |
| EV-to-equity bridge (waterfall chart plus table) | ✅ `result.bridge.lines` |
| Diluted shares: method, each instrument, whether the circular case was solved | ✅ `result.per_share.dilution.lines`, `.circular`, `.method` |
| "What does this mean?" side notes (plain text, not generated) | Static copy from `docs/interview-guide.md` |
| Dates: statement, valuation, market data (D-07) | ✅ `result.schedule` |

### 3.6 Sensitivity analysis (`/runs/:id/sensitivity`)

Only available **for a frozen run**, so the grid always uses that run's frozen inputs and its engine version.

| Feature | Endpoint |
|---|---|
| WACC × terminal growth grid of value per share, also selectable as EV or equity value | 🆕 B3 `POST /runs/{id}/sensitivity` |
| Second preset: revenue-growth shift × EBITDA-margin shift | 🆕 B3 (engine already supports it) |
| Base cell outlined; it **equals the run's stored value exactly** | 🆕 B3 asserts and returns `base_matches_run: true` |
| Invalid cells (g ≥ WACC) shown as "n/a – g ≥ WACC" with the error code on hover | 🆕 B3 `cells[][].status/codes` |
| Heat shading by change vs base | 🆕 B3 `change_vs_base`, computed by the backend |
| Provenance strip: run ID, input fingerprint, engine version | 🆕 B3 echoes them |

### 3.7 Model audit (`/scenarios/:id/audit`, `/runs/:id/audit`)

Grouped and filterable by severity. Each item shows code, field, message, and a "go to" link.

| Group | Endpoint |
|---|---|
| Missing financial inputs (blocking) | ✅ the preview's 422 `calculation` envelope (`MISSING_INPUT` + field), rendered as audit items rather than a failure |
| Historical consistency (EBIT and net income reconciliation, balance sheet, D&A check, earnings-vs-cash) | ✅ `GET …/historical-analysis` → `issues` |
| Forecast outside historical range (LIM-12) | ✅ preview / run `warnings` (`DRIVER_OUTSIDE_HISTORY`, `DRIVER_NO_HISTORY`) |
| Valuation warnings (TV share, narrow spread, high g, stale market data, debt at book…) | ✅ preview / run `warnings` |
| Provenance gaps (inputs with `status: missing`, derived NWC built from partial items) | ✅ preview / run `provenance` |
| Invalid or unsupported assumptions | ✅ `INVALID_ASSUMPTIONS` and `validation` envelopes |
| "Why?" detail: full message, and for engine codes a short explanation from a static code catalogue | Static map from `errors.Code` → doc text |

### 3.8 Saved valuation runs (`/runs`, `/runs/:id`)

| Feature | Endpoint |
|---|---|
| Paginated table: run ID, company, project / scenario, label, valuation date, engine version, input fingerprint (short, copyable), EV, equity, value per share, units, created at | 🆕 B2 `GET /runs?page=&page_size=&company_id=&project_id=&scenario_id=` |
| Filters by company / project / scenario | 🆕 B2 |
| Run detail: results (3.5), inputs, provenance, warnings | ✅ `GET /runs/{id}` (+ 🆕 B5 context) |
| "Verify reproducibility" button showing identical / hash match / engine version | ✅ `POST /runs/{id}/verify` |
| No edit or delete anywhere | The API offers none, and the UI shows a lock icon labelled "Frozen run" |

---

## 4. Backend changes required

All additions are read-only or compute-only. **No engine formula changes.** The engine stays standard-library-only, and every addition gets owner-scoping tests.

### B1: `GET /api/v1/dashboard`

```jsonc
{
  "counts": { "companies": 3, "projects": 2, "scenarios": 4, "runs": 7 },
  "recent_runs": [            // newest 5 of the user's runs
    { "id": 7, "label": "Board pack v1", "created_at": "2026-11-05T10:02:11Z",
      "company": { "id": 1, "name": "Ardent… (SYNTHETIC)", "currency": "INR", "scale": "crores" },
      "scenario": { "id": 3, "name": "Base" },
      "value_per_share": 31.215006617818556, "engine_version": "0.1.0" } ],
  "recent_companies": [       // by latest audit event touching the company or its projects
    { "id": 1, "name": "…", "last_activity_at": "…", "periods": [2023, 2024, 2025] } ],
  "recent_activity": [        // newest 20 audit events
    { "at": "…", "entity": "valuation_run", "entity_id": 7, "action": "create",
      "summary": "Froze run 7 for scenario 'Base' (sha256:37c66a53…)" } ]
}
```

- **Access:** every query is filtered by `owner_id` or `user_id` = the current user.
- **Privacy:** `recent_activity` returns server-written summaries only, not the raw `detail` JSON (which can hold old values).
- **Tests:**
  - counts are exact after a scripted setup;
  - another user's data never appears, and their counts read 0;
  - ordering and limits;
  - an empty account returns all zeros with empty lists;
  - summaries contain no raw old values.

### B2: `GET /api/v1/runs` (global, paginated)

Query: `page ≥ 1` (default 1), `page_size 1..100` (default 25), optional `company_id`, `project_id` or `scenario_id`. Ordered `created_at DESC, id DESC`.

```jsonc
{ "page": 1, "page_size": 25, "total": 7,
  "items": [ { "id": 7, "label": "…", "created_at": "…", "engine_version": "0.1.0",
               "input_hash": "sha256:…", "valuation_date": "2025-03-31",
               "company": {"id":1,"name":"…","currency":"INR","scale":"crores"},
               "project": {"id":2,"name":"…"}, "scenario": {"id":3,"name":"Base"},
               "enterprise_value": 3558.79…, "equity_value": 3248.79…,
               "value_per_share": 31.2150…, "warning_count": 3 } ] }
```

- **Values:** read verbatim from the stored `result_json` and `inputs_json`; nothing is recomputed.
- **Access:** `created_by` = the current user. A filter ID belonging to another user returns an empty page, not an error, so it doesn't reveal that the ID exists.
- **Tests:**
  - pagination boundaries;
  - `page_size` > 100 → `validation`;
  - filters;
  - ordering;
  - isolation between users;
  - listed values equal `GET /runs/{id}` exactly.

### B3: `POST /api/v1/runs/{run_id}/sensitivity` (frozen inputs only)

```jsonc
// request: the server builds centred axes around the run's own base values
{ "row": { "variable": "wacc",            "step": 0.005, "steps_each_side": 3 },
  "col": { "variable": "terminal_growth", "step": 0.005, "steps_each_side": 3 },
  "output": "value_per_share" }      // or enterprise_value | equity_value
// response
{ "run_id": 7, "input_hash": "sha256:…", "engine_version": "0.1.0",
  "row_variable": "wacc", "col_variable": "terminal_growth", "output": "value_per_share",
  "row_values": [...], "col_values": [...], "base_row": 3, "base_col": 3,
  "base_value": 31.2150…, "base_matches_run": true,
  "cells": [[ { "value": 34.1…, "status": "ok", "codes": [], "change_vs_base": 0.0931… },
              { "value": null, "status": "invalid", "codes": ["TERMINAL_GROWTH_GE_WACC"],
                "change_vs_base": null } ]] }
```

**Integrity rules:**
1. Inputs come **only** from the run's frozen `inputs_json`, via the same strict `DcfInputsIn` reconstruction `verify` uses, and nothing from the scenario's current state.
2. Before computing, the server checks `fingerprint(rebuilt inputs) == run.input_hash`; a mismatch means `409 RUN_INPUTS_CORRUPT`.
3. If `ENGINE_VERSION != run.engine_version`, the request is refused with `409 ENGINE_VERSION_MISMATCH`, never silently computed on a different engine **[D4-05]**.
4. The base cell must equal the stored run output exactly (`==`), or the server returns a 500 with `BASE_MISMATCH`.
5. Allowed variables: `wacc`, `terminal_growth`, `revenue_growth_shift`, `ebitda_margin_shift`, `capex_pct_shift`, `tax_rate`.
6. Limits: `steps_each_side ≤ 5` (11×11 at most); `step` > 0 and within a sensible range per variable.
7. Results aren't stored. They're deterministic, recomputable functions of a frozen run.

**Tests:**
- base cell equals `GET /runs/{id}` exactly;
- editing the scenario after freezing doesn't change the grid (proof it uses frozen inputs);
- monotonic in WACC and g;
- g ≥ WACC cells invalid with the code;
- engine-version mismatch → 409 (simulated by monkeypatching `ENGINE_VERSION`);
- a corrupted fingerprint → 409;
- another user's run → 404;
- limits → `validation`;
- `change_vs_base` equals the backend's own value minus base, divided by base.

### B4: draft preview, `POST /scenarios/{id}/preview` with an optional body (live editing)

- **Body:** optional `{settings, assumptions}` (same schemas as `PUT`).
- **Without a body:** behaviour is unchanged.
- **With a body:** the backend builds inputs from the company's statements plus the draft, runs the engine, **saves nothing**, and labels the response `"draft": true`. Provenance marks assumption values as `basis: "assumed", draft: true`.
- **Why:** without this, every keystroke would `PUT` the scenario, filling the audit log and blurring saved vs draft.
- **Tests:**
  - a draft preview never changes the database (row counts and audit log unchanged);
  - a draft equal to the saved scenario gives a byte-identical result to a plain preview;
  - draft validation errors arrive as `validation` / `INVALID_ASSUMPTIONS`.

### B5: context and presentation fields on preview and run responses

- **`company` block:** `{id, name, currency, scale, is_synthetic}` plus `scenario` and `project` names, so every figure can be labelled with units. The frontend never guesses units.
- **`presentation` block [D4-06]:** per forecast year, `ebitda_margin`, `ebit_margin` and `ufcf_margin`, computed in Python from the result. These are **not** stored in or added to the frozen `result_json`, so the engine output and run hashes don't change.
- **Tests:**
  - presentation values equal hand calculations for KA-DCF-03;
  - stored `result_json` is byte-identical before and after this change.

### B6: typed response models (OpenAPI)

- Pydantic response models for every endpoint the frontend calls. Engine result shapes come from the engine dataclasses via `TypeAdapter`, so they're not hand-copied.
- There's no behaviour change: responses keep being serialised by the canonical JSON path.
- **Test:** every 200 response in the API test suite validates against its declared response schema, so the OpenAPI and the real responses can't drift apart.
- This is what makes the generated TS types trustworthy.

### B7: `GET /api/v1/sources/{id}`

- **Returns:** `{id, kind, title, file_name, file_sha256, uri, notes, created_at}`.
- **Access:** owner-only.
- **Tests:** isolation, and fields matching what the import recorded.

### B8: completeness in `GET /companies/{id}/financials`

- **Per period:** `{present: n, missing: n, absent: n, dcf_required_missing: [codes]}`.
- **Definitions:**
  - *present* = a row with a value;
  - *missing* = a row with NULL;
  - *absent* = no row at all;
  - *DCF-required* = revenue, the NWC components, the bridge items and basic shares, defined once in Python.
- **Tests:** counts on the sample company; a manual "mark as missing" moves an item from present to missing.

**Backend regression:**
- all 374 existing tests stay green, with new tests added alongside;
- CI keeps the Python 3.12/3.13 matrix;
- the engine purity, no-silent-zero and limitations-register tests stay in place.

---

## 5. Financial integrity rules for the frontend

| Rule | Enforcement |
|---|---|
| **No financial arithmetic in TypeScript.** Every figure, ratio, total, change and margin comes from an API field. | (1) A code-review checklist. (2) `lib/format.ts` is the only module that transforms numbers: it rounds, scales ×100 for a % *display*, and adds units and parentheses. (3) An ESLint rule bans arithmetic operators on values typed as API financial fields outside `lib/` (a custom rule on generated-type identifiers; if that proves brittle, review plus E2E tracing instead). (4) **Display-trace E2E test:** for the results, runs and sensitivity screens, every displayed number equals `format(apiValue)` for the field it's bound to. |
| **Exact input parsing.** Typing `18.5` in a % field sends `0.185`, the same float as the JSON literal `0.185`. | `lib/parse.ts` shifts the decimal point on the *string* (`"18.5"` → `"0.185"`) and then calls `Number()`. It never divides by 100, which would give values like `1.1/100 = 0.011000000000000001`. Property-tested over 10,000 inputs. |
| **Missing stays missing** | `null` renders as **"—"** with a tooltip "Missing: <reason>"; NM renders as **"NM"**. Number-typed props refuse `null`, so `?? 0` and `|| 0` on API values fail lint (`no-nullish-zero` custom rule plus grep test). |
| **Clear basis** | Every statement value shows R / D / A. Draft values show in blue (banking "input" colour). Backend-calculated outputs show in near-black. |
| **Immutable runs** | Run screens have no edit or delete controls. A test asserts there's no mutating request from any `/runs/*` page. |
| **Sensitivity only from frozen runs** | The sensitivity route requires a run ID. There's no sensitivity on a draft or unsaved scenario. |
| **Synthetic data labelled** | `SyntheticBanner` appears whenever `company.is_synthetic`, and in every screenshot. |
| **Units on every figure** | Table headers carry `INR crores`. KPI tiles carry the unit. Percentages and multiples are suffixed (`%`, `x`). |

---

## 6. UI design direction

Institutional and data-dense: a modelling tool, not a marketing dashboard.

| Element | Specification |
|---|---|
| Palette | **Navy 900 `#0B1B33`** (left rail and header), **white** content canvas, **slate** greys for text, borders and table stripes (`#F8FAFC` / `#E2E8F0` / `#475569` / `#0F172A`), one **accent blue `#1F5FBF`** for interactive elements and user inputs. Status colours only for status: amber `#B7791F` warning, red `#B42318` error, green `#027A48` OK. **No red/green for negative/positive values**: negatives use parentheses. No gradients, no drop shadows beyond 1 px borders, no animations except a 150 ms fade on stale/loading. |
| Typography | **Inter** with tabular figures (`font-variant-numeric: tabular-nums`) for the UI and numbers; **IBM Plex Mono** for hashes and codes. 13 px tables, 14 px body, 600-weight section headers, 11 px uppercase column labels. |
| Numbers | Right-aligned, aligned decimals. Thousands separators. Negatives `(1,234.5)`. Percentages to 1 dp (`9.6%`), WACC to 2 dp, multiples `7.9x`, per-share to 2 dp, with full precision on hover. Missing `—`, NM `NM`. |
| Tables | Compact rows (28 px). Sticky header and first column. Years as columns, oldest left. Historical and forecast columns separated by a vertical rule and a shaded "Forecast" header. Subtotal rows bold with a top border. |
| Input cells | Blue text on a white cell with a thin blue underline. Unsaved draft cells get a faint blue background. Invalid cells get a red outline plus an inline message. |
| Charts | Few series, slate and blue. Axes labelled with units. No 3D or pie charts. Small multiples instead of dual axes. EV composition as one stacked horizontal bar (PV of FCF vs PV of TV). The EV→equity bridge as a waterfall. The sensitivity grid as a heat-shaded **table**, not a chart. |
| Layout | Desktop and laptop (minimum width 1280 px, comfortable at 1440+). Collapsible left rail. Content in a 12-column grid. KPI tiles are slim (label, value, unit), not oversized cards. |
| Accessibility | WCAG AA contrast. Full keyboard navigation through tables and inputs. Visible focus rings. Status never conveyed by colour alone (an icon plus text as well). |

**DCF workspace wireframe**

```
┌ DealForge ┬───────────────────────────────────────────────────────────────────────────────┐
│ ▣ Dash    │ Ardent Precision (SYNTHETIC) › Ardent valuation › Base     INR crores  [Draft●] │
│ ▣ Compan. │ ┌ Status: Draft has 2 unsaved changes   [Discard] [Save scenario] [Freeze run]┐ │
│ ▣ Valuat. │ │ Drivers            FY23A  FY24A  FY25A │ FY26E  FY27E  FY28E  FY29E  FY30E   │ │
│ ▣ Runs    │ │ Revenue growth       —    12.5%  11.1% │  8.0%   7.0%   6.0%   5.0%   4.0%   │ │
│           │ │ EBITDA margin      19.0%  19.5%  20.0% │ 18.0%  18.5% ⚠35.0% 19.5%  20.0%   │ │
│           │ │ …                                      │                                    │ │
│           │ │ Output (backend)                       │                                    │ │
│           │ │ Revenue            1,600  1,800  2,000 │ 2,160  2,311  …                    │ │
│           │ │ UFCF                                   │ 181.2  205.6  …                    │ │
│           │ └────────────────────────────────────────┴────────────────────────────────────┘ │
│           │ WACC 9.60% │ g 2.50% │ EV 3,558.8 │ Equity 3,248.8 │ Value/share 31.22  [Results]│
└───────────┴───────────────────────────────────────────────────────────────────────────────┘
```

Before any screen is built, milestone F1 delivers a **style-guide page**:
- tokens, the type scale and number formats;
- tables, inputs and badges;
- one chart and the heat-shaded grid.

It comes with screenshots for your approval.

---

## 7. Testing, error handling and acceptance criteria

| Layer | Tooling | Covers |
|---|---|---|
| Frontend unit | Vitest | `format.ts`: parentheses, NM, "—", units, % and x, rounding. `parse.ts`: string-exact %, property-tested. Error-envelope parsing. Token store and expiry. Debounce, cancel and stale logic. |
| Component | Vitest + React Testing Library + **MSW** | Every screen in loading, empty, success, `validation`, `calculation`, `not_found` and 401 states. Missing values render "—", never 0. Basis badges and provenance popover. DCF edit → **the request body contains the exact numbers typed**. Freeze button disabled while pending or while the draft is dirty. No mutating calls from run pages. |
| Fixtures | `scripts/record-fixtures` hits the **real** backend (sample company + KA-DCF-03) and saves the responses. A test fails if fixtures no longer validate against the generated OpenAPI types. | Mocks never contain invented numbers. |
| E2E | **Playwright** against a real uvicorn server and a fresh SQLite database | Full journey: register → create company → upload CSV (broken file first) → commit → analysis → create scenario → edit a driver → value per share changes → save → freeze → run detail → verify identical → sensitivity base cell == run value → audit shows the LIM-12 warning. Session expiry and re-login restore the draft. |
| Display trace | Playwright | Results, runs and sensitivity screens: each bound number equals the formatted API value. |
| Accessibility | `@axe-core/playwright` | No serious or critical violations on any screen. |
| Backend | pytest (existing 374 + new) | B1–B8 contract, access-control and integrity tests (section 4). |
| CI | GitHub Actions | The existing Python matrix, plus a Node 22 job: `eslint`, `tsc --noEmit`, `vitest`, `vite build`, then Playwright with the backend started in the job. |

**Phase 4 definition of done:**
- all 8 screens are reachable and wired to the API, with no hardcoded financial outputs (verified by the display-trace and code-review checklist);
- the E2E journey passes in CI;
- the frontend type-checks with the generated types;
- backend and frontend suites are green on CI;
- screenshots of every screen are committed to `docs/screenshots/`;
- the README has "run the whole app locally" instructions;
- new limitations are added to the register.

---

## 8. Milestone-wise implementation plan

Each milestone ends with tests run, outputs verified, a list of files changed, limitations updated and a commit. Stops for review are marked ⏸.

| # | Milestone | Deliverables | Acceptance criteria |
|---|---|---|---|
| **F0** | Backend additions | B1–B8, response models, tests, regenerated OpenAPI | All new endpoint tests pass. Every 200 response validates against its schema. 374 existing tests unchanged and green. Stored run JSON byte-identical (B5). |
| **F1** ⏸ | Frontend foundation and style guide | Vite/TS/Tailwind scaffold, design tokens, component kit, `format`/`parse` with tests, typed client, auth (login, register, logout, expiry, 401 handling), app shell, frontend CI job, **style-guide page and screenshots** | Lint, typecheck, unit tests and build green in CI. Login and expiry flows tested. **Style guide approved by you before F2.** |
| F2 | Dashboard and companies | Dashboard (B1), companies list, create-company form | Counts and recent lists match the API. Empty state for a new user. Validation errors inline. |
| F3 | Company workspace and import | Overview, completeness (B8), issues, provenance popover (B7), import wizard (dry run → errors table → commit or replace), manual correction, share instruments | A broken CSV shows row/column errors and can't be committed. Provenance popover shows file, SHA-256, row and column. "Mark missing" shows "—" everywhere. |
| F4 | Financial analysis | Three statements with R/D/A badges, ratio tables, charts | Every ratio comes from `historical-analysis`. Liquidity section handled per D4-02. |
| F5 ⏸ | DCF workspace | Scenario list/create/clone, driver grid, WACC and market panels, draft model, live preview (B4), LIM-12 cell flags, save, freeze | An edit produces an exact request body. The result updates within the debounce. Invalid input greys results as stale. Freeze is impossible with a dirty draft. **Review the demo flow before F6.** |
| F6 | Valuation results | KPI strip, EV composition, bridge waterfall, dilution panel, dates panel, explanations | Display-trace test passes. Units on every figure. |
| F7 | Saved runs | Global list (B2) with filters and pagination, run detail, verify button | Values identical to `GET /runs/{id}`. No mutating controls. Verify shows identical. |
| F8 | Sensitivity | Grid (B3) for WACC × g and growth × margin, base outline, invalid cells, heat shading | Base cell == run value. A scenario edit after the freeze doesn't change the grid. |
| F9 | Model audit | Grouped, filterable issue list from all sources, "why" catalogue, go-to links | Each issue category is reproducible from a fixture. Blocking missing inputs listed rather than shown as a failure. |
| F10 ⏸ | Hardening and delivery | Full E2E journey, axe checks, screenshots, README run guide, limitations update, final report | Everything green in CI. Final report with screenshots, screen list, API status, test results, limitations and run instructions. |

---

## 9. Risks and unresolved decisions

### Decisions needing your approval

| ID | Decision | Recommendation | Alternative and trade-off |
|---|---|---|---|
| D4-01 | Where the auth token lives | In memory, mirrored to `sessionStorage`. Strict CSP, no `innerHTML`, cleared on 401/logout/tab close. | **httpOnly SameSite=Strict cookie** plus a CSRF token: safer against XSS, but needs backend changes and a CSRF design. Recommended later for any public deployment (would become LIM-20). |
| D4-02 | Liquidity ratios | Add `total_current_assets`, `total_current_liabilities` and (optional) `marketable_securities` to the item dictionary, plus engine metrics for current, quick and cash ratios (new `MISSING`-aware functions, tested; no change to existing formulas) | Defer and show a "Not available: requires current assets and liabilities" panel. Less work, but the Financial Analysis screen is incomplete. |
| D4-03 | "Recently accessed companies" | Implement as **recently *active*** (latest audit event). Reads aren't tracked. | Track reads with a `last_viewed_at` write on every GET: more literal, but turns read endpoints into writes. |
| D4-04 | Live recalculation | B4 draft preview (nothing saved) | Save-then-preview: no new endpoint, but writes and audit-logs every keystroke. |
| D4-05 | Sensitivity on a run from an older engine version | **Refuse (409)** and explain; the user can re-freeze the scenario on the current engine | Compute and flag the version difference: more convenient, but breaks "same engine as the run". |
| D4-06 | Display ratios not in the engine output (EBIT margin, UFCF margin) | B5 `presentation` block computed in Python, outside the frozen result | Omit these rows: simpler, but less informative. |
| D4-07 | Production serving | FastAPI serves the built frontend (single origin, no CORS) | A separate static host plus CORS: more deployment options, more configuration and security surface. |
| D4-08 | Typed client | `openapi-typescript` + `openapi-fetch`, with B6 response models | Hand-written types: no backend work, but drift risk. |
| D4-09 | Device support | Desktop and laptop, ≥ 1280 px. Below that, a "use a larger screen" notice. | Full responsive or mobile: much more work for a modelling tool. |
| D4-10 | Duplicate "Freeze run" | UI guard (disabled while pending, confirm dialog) **plus** an `Idempotency-Key` header stored on the run (small migration `0002`) | UI guard only: no migration, but a network retry could create two runs. |
| D4-11 | Sensitivity axes | Server builds centred axes from `step` and `steps_each_side` | Client sends explicit value lists: more flexible, but the frontend would compute axis values. |

### Risks

| Risk | Mitigation |
|---|---|
| Floating-point drift when parsing % inputs | String-based decimal shifting, property-tested (section 5) |
| Live preview races (an old response arriving after a newer one) | TanStack Query cancellation, AbortController, and a request sequence check; stale overlay until the latest result returns |
| Hidden arithmetic creeping into React | `format.ts` as the single transformation point, lint rules, display-trace E2E, review checklist |
| OpenAPI types too loose (`dict[str, Any]` today) | B6 response models, with a test that every 200 response validates |
| Engine version bump makes old runs' sensitivity unavailable (D4-05) | Clear 409 message; register entry; re-freeze path |
| Recharts limits (waterfall, heat map) | Waterfall via the stacked-bar technique; heat map as a styled table |
| Design quality is subjective | ⏸ style-guide approval at F1 and demo review at F5, before further screens |
| Scope creep (comps, M&A screens) | The engine supports them but no API exposes them. **Out of Phase 4**, proposed for Phase 5. |
| npm supply chain | Lockfile committed, exact versions, `npm ci` in CI, minimal dependency list |
| CI time growth from Playwright | E2E runs one Chromium project, with test retries off and artefacts kept on failure |
