# DealForge — Phase 1: Product Definition, Financial Requirements and Architecture

> **Status: APPROVED.** Decisions D-01…D-17 were approved by the project owner, with refinements to
> D-03, D-07 and D-10 recorded in [section L](#l-approval-record-and-refinements). Phase 2 (the
> calculation engine) implements this specification — see [`engine.md`](engine.md).

## Contents

- [A. Product requirements document](#a-product-requirements-document)
- [B. Prioritised MVP feature list](#b-prioritised-mvp-feature-list)
- [C. User journeys](#c-user-journeys)
- [D. System architecture](#d-system-architecture)
- [E. Repository and folder structure](#e-repository-and-folder-structure)
- [F. Database schema and entity relationships](#f-database-schema-and-entity-relationships)
- [G. API endpoint specification](#g-api-endpoint-specification)
- [H. Financial formula specification](#h-financial-formula-specification)
- [I. Test strategy and known-answer cases](#i-test-strategy-and-known-answer-cases)
- [J. Staged implementation roadmap](#j-staged-implementation-roadmap)
- [K. Decisions requiring approval](#k-decisions-requiring-approval)
- [L. Approval record and refinements](#l-approval-record-and-refinements)

---

## A. Product requirements document

### A.1 Problem

Student portfolio projects in finance are usually either (a) spreadsheets with no software
engineering, or (b) web apps with impressive UI and financially wrong maths (EV and equity value
confused, cash flows double-taxed, terminal growth above the discount rate). DealForge should show
both disciplines at once: **a correct, auditable valuation and M&A model, built as maintainable,
tested software.**

### A.2 Users

| Persona | Need | What DealForge must give them |
|---|---|---|
| **The analyst (primary: you)** | Build a valuation end-to-end and defend it | Editable assumptions, transparent maths, every number traceable to an input or formula |
| **The interviewer (secondary)** | Judge, in 10 minutes, whether you understand valuation | A clean demo path, visible formulas, sensible edge-case handling, tests they can read |
| **The reviewer / MD (tertiary)** | Read a conclusion quickly | A deal memo with a valuation range, key assumptions and risks |

### A.3 Goals

1. One complete workflow: **project → historicals → forecast → DCF → comps → sensitivity → M&A → memo**.
2. Financial correctness proven by known-answer tests, not by assertion.
3. Full provenance: every input carries source, period, unit and basis (reported / derived / assumed).
4. Reproducibility: the same inputs and engine version always give byte-identical outputs.
5. A professional, banking-style UI (dense tables, consistent number formats, input-vs-formula colour coding).

### A.4 Non-goals (MVP)

- Real-time market data, paid data feeds, user accounts / multi-tenancy, cloud infrastructure.
- Valuing banks and insurers (UFCF-based DCF and EV multiples are not meaningful for them — they need
  dividend discount / P/BV / P/TBV models). The app will **refuse or warn** for a "financial institution" sector flag.
- LBO models, sum-of-the-parts, full purchase-price allocation, full three-statement balance-sheet
  balancing in the forecast.
- An AI chatbot. AI-drafted commentary is a *future, optional* enhancement and never does arithmetic.

### A.5 Constraints

- Built by one student with AI assistance → small surface area, boring technology, strong tests.
- Zero-cost stack: everything runs locally (SQLite, Vite dev server, Uvicorn).
- Synthetic data only in the MVP, labelled as synthetic everywhere it appears.

### A.6 Success criteria (definition of "done" for the MVP)

- All known-answer tests in section I pass; engine line coverage ≥ 95 %.
- A user can go from a sample company to an exported memo in under 10 minutes without touching code.
- No calculated output is ever produced from a missing input that was silently treated as zero.
- Any number shown in the memo can be clicked/traced back to its run, its inputs and their provenance.

---

## B. Prioritised MVP feature list

Priority key: **P0** = MVP, required for the end-to-end demo · **P1** = strong next step, after the
MVP works · **P2** = future.

### B.1 P0 — Essential (MVP)

| # | Feature | Why it is essential | Trade-off accepted |
|---|---|---|---|
| 1 | Project CRUD + create-from-sample | Entry point of every workflow | Single user, no auth |
| 2 | Two clearly labelled **synthetic** sample companies (industrial, software) + one synthetic acquirer + 6–8 synthetic peers | Demo needs data; two profiles show why multiples differ | Not real data — by design |
| 3 | CSV import of annual historicals (3–5 years) with dry-run validation report | Shows data-quality discipline | Annual only; one fixed template |
| 4 | Provenance on every line item and assumption | Core credibility / auditability requirement | More columns, more UI |
| 5 | Historical analysis: growth, margins, FCF, NWC, net debt, effective tax, consistency checks | Analysts start from history | Fixed metric set |
| 6 | Five-year driver-based forecast (growth, EBITDA margin, D&A %, CapEx %, NWC %, tax) | Drives the DCF | No full 3-statement model |
| 7 | WACC builder (CAPM, after-tax Kd, market-value weights) | Required for DCF | Beta entered, not regressed |
| 8 | DCF with perpetual-growth terminal value + implied exit multiple cross-check | Core valuation | Gordon only as primary TV method |
| 9 | EV → equity bridge and diluted share count (treasury stock method) | Most common interview error zone | Convertibles excluded in MVP |
| 10 | Comparable companies: EV/Revenue, EV/EBITDA, P/E, exclusions with reasons, mean / median / quartiles, implied range | Second valuation lens | Manual peer data entry/CSV |
| 11 | Sensitivity grids: WACC × g, revenue growth shift × EBITDA margin shift | Expected in every banking model | 2-D grids only |
| 12 | Scenarios (Base / Upside / Downside + custom), save, clone, compare side by side | Requirement 12 | Overrides on one base forecast |
| 13 | Accretion/dilution (Year-1 pro forma) with sources & uses, cash/debt/stock mix, fees, synergies, breakeven synergies | Core M&A deliverable | One forecast year; no PPA |
| 14 | Valuation summary ("football field") chart combining DCF, comps and sensitivity ranges | Ties the work into one conclusion | — |
| 15 | Deterministic deal memo (template-generated from a saved run) with HTML/Markdown export and browser print-to-PDF | Requirement 11 without LLM risk | Template prose is formulaic |
| 16 | Persisted, versioned valuation runs (inputs snapshot + outputs + engine version + input hash) | Reproducibility and audit | Storage of JSON snapshots |

### B.2 P1 — Next enhancements

- Mid-year discounting convention and stub-period valuation date (**[D-07]**).
- Exit-multiple terminal value as an alternative method (not just a cross-check).
- Beta unlevering/relevering from peer betas (Hamada).
- Multi-year (Y1–Y3) accretion/dilution, synergy phase-in curves, simplified goodwill & intangible amortisation.
- Calendarisation of peer fiscal years; LTM construction from quarterly data.
- Excel export of the model (openpyxl) with live formulas, so an interviewer can audit it in Excel.
- Tornado chart (one-way sensitivity on each driver).
- Audit-log viewer UI.

### B.3 P2 — Future

- Public filings ingestion (SEC EDGAR XBRL "companyfacts" API; see H.10), FX normalisation with dated rates.
- LLM-drafted memo commentary, grounded in run outputs (see D.5).
- PostgreSQL, authentication, multi-user sharing, deployment to a free tier.
- LBO module, precedent transactions, sum-of-the-parts.

---

## C. User journeys

**J1 — Start a project from a sample.**
Dashboard → "New project" → choose *Ardent Precision Components (SYNTHETIC)* → project opens on
Company Overview with a persistent "Synthetic data" badge → historicals already loaded with
provenance `source = "DealForge synthetic sample v1"`, `basis = assumed`.

**J2 — Import historicals from CSV.**
Historicals tab → "Import CSV" → download template → upload → **dry run** returns a validation
report (unknown line items, non-numeric cells, missing required items, sign violations, period gaps,
balance-sheet imbalance, unit mismatch) → user fixes the file or confirms → import commits →
each value stored with provenance (file name, row, column, period, unit, basis = reported).
Missing cells stay **missing** and are shown as "—" with a tooltip; dependent metrics show "n/a (missing input)".

**J3 — Analyse historicals.**
Historicals tab shows the statement table and a metrics table (growth, margins, FCF, NWC, net debt,
tax rate) with trend sparklines and a "Checks" panel (e.g. "FY2024: Revenue − COGS − OpEx differs
from reported EBIT by 3.2 (1.1 %) — tolerance 0.5 %").

**J4 — Forecast and DCF.**
Forecast tab → edit per-year drivers (blue input cells) prefilled from historical averages, each
showing its historical reference → WACC panel → terminal growth → **live preview** recalculates on
the server (stateless endpoint) → DCF tab shows the UFCF build, discount factors, PV, TV, EV,
bridge, value per share, TV % of EV and implied exit multiple → warnings inline (e.g. "Terminal
value is 82 % of EV") → "Save run".

**J5 — Comparable companies.**
Comps tab → add/import peers → table of EV build and multiples per peer → exclude a peer with a
mandatory reason → statistics row (min / 25th / median / mean / 75th / max / n) → choose
multiple and range → implied EV, equity and value per share for the target.

**J6 — Sensitivity and scenarios.**
Sensitivity tab → choose grid (WACC × g) and step sizes → heat-mapped table; invalid cells (g ≥ WACC)
shown as "INVALID" not a number → base cell highlighted and equal to the saved DCF value.
Scenarios → clone Base to "Downside", override growth and margin → compare scenarios side by side.

**J7 — Acquisition simulation.**
M&A tab → choose acquirer (synthetic) → set offer premium, consideration mix, financing (cash on
hand / new debt / new shares), fees, synergies and integration costs → Sources & Uses must balance
→ pro forma EPS, accretion/(dilution) %, breakeven synergies, pro forma leverage → sensitivity of
accretion to premium × % stock.

**J8 — Memo and export.**
Memo tab → select a saved run (and optionally a transaction analysis) → memo generated from a
template: summary, company overview, key assumptions table (with provenance), valuation ranges,
football field, transaction analysis, risks (rule-based: e.g. high TV share, negative FCF years,
high leverage), conclusion → export HTML/Markdown or print to PDF. The memo footer records run ID,
engine version, input hash and "Contains synthetic data".

**J9 — Error journey.** User sets g = 9 % with WACC = 8 % → the DCF endpoint returns a validation
error (`TERMINAL_GROWTH_GE_WACC`) with a readable message; the previous valid outputs stay visible
but greyed out as "stale".

---

## D. System architecture

### D.1 Diagram

```
┌──────────────────────────── Browser ─────────────────────────────┐
│ React + TypeScript (Vite)                                        │
│  Pages: Dashboard · Overview · Historicals · Forecast · DCF ·    │
│         Comps · Sensitivity · Scenarios · M&A · Memo             │
│  TanStack Query (server state) · React Hook Form + Zod (forms)   │
│  Tailwind UI kit · Recharts · lib/format (numbers, units, NM)    │
│  Types generated from the backend OpenAPI schema                 │
│  ** NO financial arithmetic in the frontend **                   │
└───────────────────────────────┬──────────────────────────────────┘
                                │ JSON over HTTP (REST, /api/v1)
┌───────────────────────────────▼──────────────────────────────────┐
│ FastAPI application                                              │
│  api/ (routers)  ── request/response Pydantic schemas            │
│        │                                                         │
│  services/  orchestration: load inputs → call engine → persist   │
│        │                     │                    │              │
│  repositories/ (SQLAlchemy)  │          memo/ (Jinja2 templates) │
│        │                     ▼                                   │
│        │        engine/  PURE, DETERMINISTIC, NO I/O             │
│        │         historical · forecast · wacc · dcf · bridge ·   │
│        │         shares · comps · sensitivity · mna · checks     │
│        │         (inputs: frozen Pydantic models; outputs:       │
│        │          result + warnings + errors; ENGINE_VERSION)    │
│        │                                                         │
│  importers/ (pandas: CSV parse + validation, unit normalisation) │
└────────┬─────────────────────────────────────────────────────────┘
         │ SQLAlchemy 2.0 + Alembic migrations
┌────────▼─────────┐
│ SQLite (file)    │  →  PostgreSQL later: same models, same migrations
└──────────────────┘
```

### D.2 Layer responsibilities and why

| Layer | Responsibility | Why | Trade-off |
|---|---|---|---|
| **engine/** | All financial maths as pure functions on typed inputs | Testable without a DB or server; easy to explain line by line; reusable in a CLI or notebook | Services must assemble complete inputs explicitly |
| **services/** | Load data, build engine inputs, call engine, persist runs | Keeps routers thin and the engine I/O-free | One more layer to maintain |
| **repositories/** | DB access only | DB swap (SQLite→Postgres) touches one layer | Some boilerplate |
| **importers/** | CSV → validated, normalised line items | pandas is good at messy tabular parsing; keep it *out* of the engine | pandas dependency only at the edge |
| **memo/** | Render memo from a saved run | Memo numbers can only come from a persisted run → grounded by construction | Template prose is less fluent than an LLM |
| **frontend** | Presentation, input capture, formatting | Single source of truth for maths is the backend | Live preview needs a round trip (~tens of ms locally) |

### D.3 Technology choices

| Technology | Purpose | Why this and not something else | Trade-off |
|---|---|---|---|
| React + TypeScript | UI | Industry standard; TS catches unit/shape errors at compile time | Learning curve vs plain JS |
| Vite | Dev server / build | Fast, minimal config | — |
| Tailwind CSS + own small UI kit (Table, NumberCell, Input, Badge, Card, Tabs) | Consistent styling | Full control of a dense "banking" look; no heavy component library | You build components yourself (optionally use headless primitives such as Radix for dialogs/tabs) |
| Recharts | Charts | Declarative React charts, enough for football field, bars, lines, heatmap-like grids | Limited exotic charts |
| TanStack Query | Server-state caching | Handles loading/stale/error states cleanly | One more library |
| React Hook Form + Zod | Forms and client-side validation | Immediate feedback; server re-validates authoritatively | Validation rules exist in two places (mitigated: server is authority) |
| openapi-typescript | Generate TS types from FastAPI's OpenAPI | Prevents frontend/backend drift | Codegen step |
| Python 3.12+ / FastAPI | API | Automatic OpenAPI docs, Pydantic integration, async-ready | — |
| Pydantic v2 | Validation of every input and output | Typed, documented schemas; rejects bad inputs early | Verbose models |
| pandas | CSV import, historical tables | Robust parsing, pivoting long→wide | Must never `fillna(0)` (enforced by a CI grep check) |
| NumPy | Percentiles in comps, vectorised sensitivity if needed | Well-defined, documented percentile method | Core DCF stays plain Python for readability |
| SQLAlchemy 2.0 + Alembic | ORM + migrations | Portable to PostgreSQL with no model changes | ORM learning curve |
| SQLite | MVP database | Zero setup, file-based, free | No concurrent writers (irrelevant for single user) |
| Jinja2 | Memo templates | Deterministic text, auditable | — |
| pytest, hypothesis (property tests) | Backend testing | Known-answer + invariant testing | — |
| Vitest + React Testing Library, Playwright (1–2 E2E) | Frontend testing | Fast unit tests + one real end-to-end demo path | E2E tests are slower |
| Ruff, mypy (strict on engine), ESLint, Prettier, GitHub Actions | Quality gates | Catches errors before review; free for public repos | CI setup time |

Deliberately **not** used: Docker (optional later), Redis/Celery, cloud services, an ORM-free raw SQL
layer, a state-management library beyond TanStack Query, any paid API.

### D.4 Numeric representation **[D-01]**

Recommendation: **IEEE-754 float (Python `float`)** inside the engine, results rounded **only at
presentation**, tests using explicit tolerances (`abs=1e-9` on intermediate values,
`rel=1e-9` on outputs).
*Why:* valuation is estimation, not ledger accounting; Excel (the industry reference) uses doubles;
NumPy interop is natural. *Trade-off:* tiny representation error (e.g. `0.1 + 0.2`). Alternative:
`decimal.Decimal` — exact decimal arithmetic but slower, awkward with NumPy and `**` non-integer
powers. Floats are deterministic on the same platform, so reproducibility holds.

### D.5 AI policy (future)

The engine and memo never depend on an LLM. If LLM commentary is added later: the model receives
only the saved run's output JSON; it must reference numbers through placeholders
(`{{dcf.value_per_share}}`) that the backend substitutes; a validator rejects any generated text
containing a numeric literal not traceable to the run. Commentary is labelled "AI-drafted, review required".

---

## E. Repository and folder structure

**Decision [D-15], approved:** DealForge lives in its own GitHub repository (`dealforge`).

```
dealforge/
├── README.md                      # pitch, screenshots, how to run, "synthetic data" disclaimer
├── docs/
│   ├── phase-1-plan.md            # this document
│   ├── formulas.md                # section H, kept in sync with engine docstrings
│   ├── decisions/ADR-0001-*.md    # one Architecture Decision Record per approved [D-xx]
│   └── interview-guide.md         # how to explain each module
├── backend/
│   ├── pyproject.toml             # deps, ruff, mypy, pytest config
│   ├── alembic/                   # migrations
│   ├── app/
│   │   ├── main.py                # FastAPI app factory
│   │   ├── config.py
│   │   ├── api/v1/                # routers: projects, financials, scenarios, valuation, comps,
│   │   │                          #          sensitivity, transactions, memos, samples
│   │   ├── schemas/               # API request/response Pydantic models
│   │   ├── services/              # orchestration
│   │   ├── repositories/          # SQLAlchemy queries
│   │   ├── db/models.py           # ORM models
│   │   ├── importers/csv_financials.py, csv_peers.py, units.py
│   │   ├── engine/                # PURE: no imports from app.db / fastapi / pandas
│   │   │   ├── __init__.py        # ENGINE_VERSION = "0.1.0"
│   │   │   ├── types.py           # frozen input/output models, Warning/Error codes
│   │   │   ├── line_items.py      # canonical item dictionary (code, statement, sign rule, required?)
│   │   │   ├── historical.py
│   │   │   ├── forecast.py
│   │   │   ├── wacc.py
│   │   │   ├── dcf.py
│   │   │   ├── bridge.py
│   │   │   ├── shares.py          # treasury stock method
│   │   │   ├── comps.py
│   │   │   ├── sensitivity.py
│   │   │   ├── scenarios.py       # apply overrides to a base assumption set
│   │   │   ├── mna.py             # sources & uses, pro forma, accretion/dilution
│   │   │   └── checks.py          # consistency checks, validation rules
│   │   ├── memo/templates/*.j2, renderer.py, risk_rules.py
│   │   └── samples/               # synthetic company JSON/CSV + README describing how generated
│   └── tests/
│       ├── engine/                # unit + known-answer (KA-*) + property tests
│       ├── importers/
│       ├── api/                   # FastAPI TestClient tests
│       └── fixtures/known_answers/*.json   # inputs + expected outputs, hand-verified
├── frontend/
│   ├── package.json, vite.config.ts, tailwind.config.ts
│   └── src/
│       ├── api/                   # generated types + typed client
│       ├── components/ui/         # Table, NumberCell, InputCell, Badge, Tabs, EmptyState, ...
│       ├── components/charts/     # FootballField, SensitivityHeatmap, TrendLine
│       ├── features/{projects,historicals,forecast,dcf,comps,sensitivity,scenarios,mna,memo}/
│       ├── lib/format.ts          # number/percent/multiple/currency formatting
│       └── routes/
│   └── tests/ (vitest) · e2e/ (playwright)
└── .github/workflows/ci.yml       # ruff, mypy, pytest, eslint, vitest, build
```

*Why the engine has an import ban:* a CI check (`import-linter` or a simple test) fails if
`app/engine` imports FastAPI, SQLAlchemy or pandas. This guarantees the maths stays pure and
testable. *Trade-off:* data must be converted to plain engine models at the service boundary.

---

## F. Database schema and entity relationships

### F.1 Entity-relationship overview

```
Project 1───1 Company (target)
Project 1───* FinancialPeriod 1───* LineItem *───1 Source
Project 1───* Scenario 1───* Assumption *───0..1 Source
Scenario 1───* ValuationRun 1───* Memo
Project 1───* Peer 1───* PeerMetric *───1 Source
Project 1───* Transaction *───1 Acquirer(Company)   Transaction 1───* TransactionRun
Project 1───* AuditEvent
```

### F.2 Tables (MVP)

Conventions: `id` integer PK; `created_at`, `updated_at` UTC timestamps on every table; monetary
values stored **normalised to the project's currency and scale** (e.g. USD millions), with the
original value retained for provenance **[D-04]**.

**projects** — `id, name, description, currency (ISO 4217), scale (enum: units|thousands|millions|billions|crores|lakhs), is_synthetic bool, valuation_date, status, notes`

**companies** — `id, project_id FK, role (target|acquirer|peer), name, ticker nullable, sector, is_financial_institution bool, fiscal_year_end_month, is_synthetic bool, description`

**financial_periods** — `id, company_id FK, label ("FY2024"), period_type (annual|ltm), start_date, end_date, fiscal_year int, is_forecast bool`
Unique: `(company_id, period_type, end_date)`.

**sources** — `id, project_id FK, kind (synthetic|csv_import|filing|manual|derived), title, uri nullable, file_name nullable, file_sha256 nullable, retrieved_at nullable, notes`

**line_items** — long ("tall") format, one row per value
`id, period_id FK, item_code (FK to canonical dictionary, e.g. REVENUE, COGS, EBIT, DA, CAPEX, CASH, TOTAL_DEBT), value REAL NULL, basis (reported|derived|assumed), source_id FK, source_ref (e.g. "row 7, col FY2024" / XBRL tag), original_value REAL NULL, original_currency, original_scale, fx_rate REAL NULL, fx_rate_date NULL, note`
Unique: `(period_id, item_code)`. **`value` is nullable: NULL means missing, never zero.**
*Why tall format:* provenance per value, new items without migrations. *Trade-off:* pivoting required
for display (pandas at the service layer).

**scenarios** — `id, project_id FK, name, kind (base|upside|downside|custom), parent_scenario_id FK nullable, description, is_locked bool`

**assumptions** — `id, scenario_id FK, key (e.g. revenue_growth, ebitda_margin, wacc.risk_free_rate, terminal.growth), year_index int NULL (1..5 for per-year drivers, NULL for scalars), value REAL NOT NULL, unit (pct|x|currency|shares|years), basis (assumed|derived|reported), source_id FK NULL, rationale text`
Unique: `(scenario_id, key, year_index)`. Child scenarios store only overrides; the engine
receives the fully-resolved set (parent ⊕ overrides) and the resolved set is snapshotted in the run.

**valuation_runs** — `id, scenario_id FK, engine_version, input_hash (sha256 of canonical input JSON), inputs_json, outputs_json, warnings_json, status (ok|invalid), created_at, label`
Runs are **immutable**. Re-running with identical inputs produces the same `input_hash` and outputs.

**peers** — `id, project_id FK, company_id FK (role=peer), included bool, exclusion_reason text NULL, share_price, price_date, currency`
**peer_metrics** — `id, peer_id FK, metric_code (REVENUE, EBITDA, NET_INCOME, DILUTED_SHARES, TOTAL_DEBT, CASH, PREFERRED, NCI), period_label, period_type (ltm|ntm|fy), value REAL NULL, basis, source_id FK, source_ref`

**transactions** — `id, project_id FK, acquirer_company_id FK, target_company_id FK, name, inputs_json (premium, mix, financing, fees, synergies…), created_at`
**transaction_runs** — same immutable pattern as `valuation_runs`.

**memos** — `id, valuation_run_id FK, transaction_run_id FK NULL, template_version, rendered_markdown, rendered_html, created_at`

**audit_events** — `id, project_id FK, entity, entity_id, action (create|update|delete|import|run), field, old_value, new_value, created_at`

*Why JSON snapshots in runs:* exact reproducibility even if assumptions are later edited.
*Trade-off:* duplicated data and JSON is not relationally queryable (acceptable: runs are read whole).
SQLite JSON → PostgreSQL `JSONB` is a direct migration.

---

## G. API endpoint specification

Base path `/api/v1`. JSON throughout. Interactive docs auto-generated at `/docs`.

### G.1 Conventions

- **Validation error (422)**: `{ "error_code": "VALIDATION_ERROR", "message": "...", "field_errors": [ { "loc": ["terminal","growth"], "code": "TERMINAL_GROWTH_GE_WACC", "msg": "Terminal growth (9.0%) must be below WACC (8.0%)." } ] }`
- **Calculation envelope (200)**: `{ "result": {...}, "warnings": [ {"code": "TV_SHARE_HIGH", "msg": "...", "severity": "warning"} ], "engine_version": "0.1.0", "input_hash": "sha256:..." }`
- Rates in API payloads are **decimals** (`0.085` = 8.5 %). Monetary values are in the project's currency and scale; every monetary response field set carries `{currency, scale}` metadata.
- `404` unknown resource, `409` conflict (e.g. duplicate period), `400` malformed CSV.

### G.2 Endpoints

| Method & path | Purpose | Key request | Key response |
|---|---|---|---|
| `GET /health` | Liveness | — | `{status, engine_version}` |
| `GET /samples` | List synthetic samples | — | `[ {id, name, sector, description, is_synthetic: true} ]` |
| `GET /projects` · `POST /projects` | List / create | `{name, currency, scale, valuation_date}` | Project |
| `POST /projects/from-sample` | Create preloaded project | `{sample_id}` | Project |
| `GET/PATCH/DELETE /projects/{id}` | Read / update / delete | — | Project |
| `GET /projects/{id}/financials` | Wide table of historicals with provenance | `?company_id=` | `{periods[], items[{code, values[{period, value|null, basis, source}]}]}` |
| `POST /projects/{id}/financials/import?dry_run=true` | CSV import (multipart) | file | `{valid, errors[], warnings[], preview}`; with `dry_run=false` commits |
| `GET /projects/{id}/financials/template.csv` | Download import template | — | CSV |
| `PATCH /line-items/{id}` | Manual correction (audited) | `{value, basis, note}` | LineItem |
| `GET /projects/{id}/historical-analysis` | Metrics + consistency checks | — | `{metrics[{code, period, value|null, status: ok|missing|not_meaningful, reason}], checks[]}` |
| `GET/POST /projects/{id}/scenarios` | List / create | `{name, kind, parent_scenario_id?}` | Scenario |
| `POST /scenarios/{id}/clone` | Clone | `{name}` | Scenario |
| `GET/PUT /scenarios/{id}/assumptions` | Resolved assumption set / bulk upsert | `{forecast:{...per year}, wacc:{...}, terminal:{...}, bridge:{...}, shares:{...}}` | resolved set incl. inherited flags |
| `POST /calculate/dcf` | **Stateless preview** — nothing persisted | full engine input or `{scenario_id, overrides}` | envelope with forecast, UFCF, PVs, TV, EV, bridge, per-share |
| `POST /scenarios/{id}/valuation-runs` | Compute + persist immutable run | `{label?}` | ValuationRun |
| `GET /valuation-runs/{id}` | Fetch run | — | inputs, outputs, warnings, hash |
| `GET /projects/{id}/scenario-comparison?run_ids=1,2,3` | Side-by-side | — | table of key outputs and assumption deltas |
| `GET/POST /projects/{id}/peers`, `PATCH/DELETE /peers/{id}` | Manage peers incl. `included`, `exclusion_reason` | — | Peer |
| `POST /projects/{id}/peers/import` | CSV peers | file | validation report |
| `POST /projects/{id}/comps/analysis` | Multiples, stats, implied range | `{period_type, multiples[], range: "iqr"|"min_max"}` | envelope |
| `POST /scenarios/{id}/sensitivity` | 2-D grid | `{row: {var, values[]}, col: {var, values[]}, output: "value_per_share"|"enterprise_value"}` | `{cells[[{value|null, status, code}]], base_cell:{r,c}}` |
| `GET/POST /projects/{id}/transactions`, `GET/PUT /transactions/{id}` | M&A setup | premium, mix, financing, fees, synergies | Transaction |
| `POST /transactions/{id}/analyze` | Compute + persist transaction run | `{persist: bool}` | S&U, pro forma, EPS, accretion, breakeven synergies |
| `POST /transactions/{id}/sensitivity` | Accretion vs premium × % stock | grid spec | grid |
| `POST /memos` | Generate memo from saved runs | `{valuation_run_id, transaction_run_id?}` | Memo |
| `GET /memos/{id}/export?format=md|html` | Download | — | file |
| `GET /projects/{id}/audit-log` | Audit trail | `?entity=` | events |

Design choice: **stateless preview vs persisted run.** The preview lets the UI recalculate on every
edit without polluting history; persisted runs are what memos and comparisons reference.
*Trade-off:* two endpoints using the same service function (covered by a test asserting identical outputs).

---

## H. Financial formula specification

### H.1 Global conventions

| Topic | Convention |
|---|---|
| Currency & scale | One currency and scale per project (e.g. USD m). Shares in millions (same "millions" scale as money ⇒ per-share = currency units). Conversions happen only in importers. |
| Rates | Decimals (0.25). Displayed as % with 1 dp. Multiples displayed `8.5x`. |
| Periods | Annual. Historical `t = −(H−1)…0` (t = 0 is last actual FY, "LFY"); forecast `t = 1…5`. |
| Valuation date | End of LFY (MVP) **[D-07]**. Cash, debt and shares are as at the LFY balance sheet. |
| Discounting | End-of-year: `DF_t = 1 / (1 + WACC)^t` (MVP) **[D-07]**. |
| Sign convention **[D-02]** | **Magnitude convention for flows that have a fixed direction**: Revenue, COGS, OpEx, D&A, CapEx, interest expense, tax expense, debt, cash are stored **≥ 0**; formulas subtract them explicitly. Items that can legitimately be either sign are **signed**: EBIT, EBITDA, pre-tax income, net income, ΔNWC, NWC, FCF. The canonical item dictionary declares each item's rule; importer rejects violations (e.g. negative CapEx) unless the user explicitly converts. |
| Missing data | `None`, never 0. Any formula with a missing required input returns `status = missing` and names the inputs. Optional claims (preferred, NCI, options) must be explicitly entered as 0 if absent — the UI asks "None (0)" vs "Unknown". |
| Not meaningful | Ratios with zero/negative denominators where the ratio has no economic meaning return `status = not_meaningful` ("NM"), not ±∞. |
| Rounding | None in the engine. Display only. |

### H.2 Historical analysis

Required items per period: REVENUE, COGS, OPEX (operating expenses incl. D&A as reported), EBIT,
DA (from cash-flow statement), PRETAX_INCOME, TAX_EXPENSE, NET_INCOME, CFO, CAPEX,
ACCOUNTS_RECEIVABLE, INVENTORY, ACCOUNTS_PAYABLE, CASH, TOTAL_DEBT, DILUTED_SHARES.
Optional: OTHER_CURRENT_OPERATING_ASSETS/LIABILITIES, INTEREST_EXPENSE, PREFERRED, NCI, TOTAL_ASSETS,
TOTAL_LIABILITIES, TOTAL_EQUITY, EQUITY_INVESTMENTS.

| Metric | Formula | Edge cases |
|---|---|---|
| Revenue growth | `Rev_t / Rev_{t−1} − 1` | `Rev_{t−1} ≤ 0` → NM; first period → n/a |
| Gross profit | `Rev − COGS` (derived if not reported) | — |
| Gross / EBITDA / EBIT margin | `GP / Rev`, `EBITDA / Rev`, `EBIT / Rev` | `Rev ≤ 0` → NM |
| EBITDA | `EBIT + DA` (labelled *derived*; reported "adjusted EBITDA" is not used in MVP) **[D-03]** | — |
| Effective tax rate | `TAX_EXPENSE / PRETAX_INCOME` | `PRETAX ≤ 0` → NM; outside [0 %, 50 %] → warning `UNUSUAL_TAX_RATE` |
| Operating NWC | `AR + INV + OCA − AP − OCL` (excludes cash, debt, current portion of debt) | Missing optional items treated as *not reported* and flagged, not zero |
| ΔNWC | `NWC_t − NWC_{t−1}` (increase = cash outflow) | first period → n/a |
| Simple FCF | `CFO − CAPEX` | — |
| CapEx % revenue, D&A % revenue, CapEx / D&A | as named | — |
| Net debt | `TOTAL_DEBT − CASH` (may be negative = net cash) | — |
| Net debt / EBITDA | | `EBITDA ≤ 0` → NM |
| Interest coverage | `EBIT / INTEREST_EXPENSE` | interest = 0 → NM |

**Consistency checks** (tolerance `max(0.5 % × |reference|, 0.5 units)` → warning, not error **[D-12]**):
`Rev − COGS − OPEX ≈ EBIT`; `PRETAX − TAX ≈ NET_INCOME` (before NCI); `ASSETS ≈ LIABILITIES + EQUITY`;
contiguous fiscal years; no duplicate periods; required items present; sign rules; DA ≤ OPEX + COGS.

### H.3 Forecast (t = 1…5)

Drivers per year: `g_t` (revenue growth), `m_t` (EBITDA margin), `d_t` (D&A % revenue),
`c_t` (CapEx % revenue), `n_t` (NWC % revenue), `T` (tax rate for valuation **[D-05]**).

```
Rev_t     = Rev_{t−1} × (1 + g_t)            Rev_0 = LFY actual revenue
EBITDA_t  = Rev_t × m_t
DA_t      = Rev_t × d_t
EBIT_t    = EBITDA_t − DA_t
CapEx_t   = Rev_t × c_t
NWC_t     = Rev_t × n_t                      NWC_0 = LFY actual operating NWC
ΔNWC_t    = NWC_t − NWC_{t−1}
```

Validation: `g_t > −100 %`; `m_t ∈ (−100 %, 100 %)`; `d_t, c_t ≥ 0`; `T ∈ [0, 60 %]`; warnings for
`m_t` far outside historical range (> 10 pp), `c_t < d_t` in the final year (asset base shrinking in
perpetuity), and a jump in year-1 ΔNWC caused by `n_1` differing from the LFY NWC % (shown explicitly).

### H.4 Unlevered free cash flow

```
Taxes on EBIT_t = max(EBIT_t, 0) × T              [D-06: no tax credit on operating losses in MVP]
NOPAT_t        = EBIT_t − Taxes on EBIT_t
UFCF_t         = NOPAT_t + DA_t − CapEx_t − ΔNWC_t
```

Equivalent to `EBIT × (1 − T) + D&A − CapEx − ΔNWC` whenever `EBIT ≥ 0`. For `EBIT < 0` the MVP
assumes zero tax (no NOL asset modelled) and raises `NEGATIVE_EBIT_NO_TAX_CREDIT`. *Why:* the
symmetric formula implies the government pays the company when it loses money, which overstates
value unless the losses can be used against other profits. *Trade-off:* ignores future NOL
utilisation (conservative). Negative UFCF years are allowed (growth companies) and flagged.
Interest expense never appears in UFCF (it is a financing flow, reflected in WACC) — prevents double counting.

### H.5 WACC

```
Cost of equity      Ke  = Rf + β_L × ERP + size/specific premium (default 0, must be justified)
After-tax Kd            = Kd_pre × (1 − T)
Market values       E   = share price × diluted shares (TSM at current price)
                    D   = market value of debt (book value used as proxy → flagged DEBT_AT_BOOK)
                    P   = preferred at liquidation/market value (optional)
                    V   = E + D + P
WACC                    = (E/V) × Ke + (D/V) × Kd_pre × (1 − T) + (P/V) × Kp
```

- Weights: **current market capital structure** in MVP; option to enter a **target D/V** **[D-08]**.
- Optional (P1) Hamada relevering: `β_U = β_L / (1 + (1 − T) × D/E)`, `β_L = β_U × (1 + (1 − T) × D/E)`.
- `Rf` should match the cash-flow currency (e.g. 10-year government bond yield in that currency).
- Validation: `0 < WACC < 30 %`; `Ke > Kd_after-tax` (warning otherwise); `β` in [0, 3] warning range;
  weights sum to 1 (by construction); `T` here equals the valuation tax rate.

### H.6 Terminal value and enterprise value

```
TV_N        = UFCF_N × (1 + g) / (WACC − g)          N = 5
PV(TV)      = TV_N × DF_N
PV(UFCF)    = Σ_{t=1..N} UFCF_t × DF_t
EV          = PV(UFCF) + PV(TV)
TV share    = PV(TV) / EV
Implied exit multiple = TV_N / EBITDA_N               (cross-check)
Implied g from multiple (P1) = (TV×WACC − UFCF_N) / (TV + UFCF_N)
```

Validation rules:

| Rule | Severity | Code |
|---|---|---|
| `g ≥ WACC` | **error** – no TV produced | `TERMINAL_GROWTH_GE_WACC` |
| `WACC − g < 1 pp` | warning (TV explodes) | `TV_SPREAD_NARROW` |
| `g > 4 %` (long-run nominal GDP proxy, configurable) or `g > Rf` | warning | `TERMINAL_GROWTH_HIGH` |
| `g < 0` | warning (allowed for declining businesses) | `TERMINAL_GROWTH_NEGATIVE` |
| `UFCF_N ≤ 0` | **error** for Gordon TV | `TERMINAL_FCF_NON_POSITIVE` |
| `TV share > 75 %` | warning | `TV_SHARE_HIGH` |
| Implied exit multiple outside peer EV/EBITDA [min, max] | warning | `TV_MULTIPLE_INCONSISTENT` |
| `EBITDA_N ≤ 0` | implied multiple = NM | — |

### H.7 Enterprise value → equity value bridge

```
Equity value = EV
             − total debt (incl. finance leases; operating leases per [D-09])
             − preferred equity
             − non-controlling interest (NCI)
             − other debt-like claims (e.g. unfunded pensions; user-labelled, optional)
             + cash and cash equivalents (all cash in MVP; "trapped/minimum cash" adjustment optional)
             + non-operating assets (e.g. equity-method investments; optional, labelled)
```

Consistency principle (documented in the UI): *a claim is subtracted from EV if, and only if, the
cash flows that service it are included in UFCF/EBITDA.* NCI is subtracted because consolidated
EBITDA includes 100 % of subsidiaries; equity investments are added because their income is below
EBITDA. The **same bridge** is used for peers in comps (H.9) and for the target in M&A (H.11).

Edge case: equity value ≤ 0 → value per share reported as computed but flagged `EQUITY_VALUE_NON_POSITIVE`
(claims exceed EV; equity would trade on option value — out of scope).

### H.8 Diluted shares and value per share

Treasury stock method (TSM) for each option/warrant tranche `i` (count `n_i`, strike `K_i`) at price `P`:

```
new shares_i = n_i × (1 − K_i / P)   if K_i < P   else 0
Diluted shares = basic shares + Σ new shares_i + RSUs/PSUs (fully, unless anti-dilutive conditions)
Value per share = Equity value / diluted shares
Upside/(downside) vs market = Value per share / current price − 1
```

The DCF value per share depends on the price used in the TSM (circular). **[D-10]** MVP
recommendation: solve the fixed point `P* = Equity / dilutedShares(P*)` by iteration (converges in a
few steps because dilution is monotone and small; max 50 iterations, tolerance 1e-9; fallback error
`DILUTION_NO_CONVERGENCE`). Market-cap for WACC and comps uses the **current market price**.
Convertibles (if-converted method) are P1.

### H.9 Comparable-company analysis

Per peer (all in the peer's own currency — **multiples are currency-neutral** as long as numerator and
denominator share a currency and units; FX is needed only when displaying absolute values):

```
Equity value (market cap) = share price × diluted shares (TSM at that price)
EV        = market cap + total debt + preferred + NCI − cash − equity investments (same bridge as H.7)
EV/Revenue = EV / Revenue
EV/EBITDA  = EV / EBITDA
P/E        = market cap / net income attributable to common  (= price / diluted EPS)
```

Rules:
- Every multiple for every peer uses the **same period type** (LTM *or* NTM *or* FY) as the target metric
  it is applied to. Mixed periods → error. Fiscal year-ends > 3 months apart → warning (calendarisation is P1:
  `CY = (m/12)·FY_A + ((12−m)/12)·FY_B` with `m` months of FY_A in the calendar year).
- Negative or zero denominator → **NM** and automatically excluded from statistics (reason recorded).
- P/E > 100x or EV/EBITDA > 50x → flagged as potential outlier; exclusion is a **user decision with a mandatory reason** **[D-11]**.
- Statistics on included, non-NM values: n, min, 25th percentile, median, mean, 75th, max.
  Percentiles use **linear interpolation** (NumPy default, equivalent to Excel `PERCENTILE.INC`). n < 3 → warning.
- Implied target valuation: `EV = multiple × target metric` → equity via H.7 bridge → per share via H.8.
  For P/E: `Equity = P/E × target net income` directly (not via EV). Range = 25th–75th percentile (default), median point estimate.

Why different multiples suit different companies (shown in the UI help panel):

| Multiple | Suits | Why | Pitfalls |
|---|---|---|---|
| EV/EBITDA | Mature, profitable, capital-structure differences across peers | Capital-structure-neutral; pre-D&A reduces accounting policy differences | Ignores CapEx intensity; lease accounting (IFRS 16 vs US GAAP) distorts EBITDA |
| EV/Revenue | High-growth or loss-making (early SaaS) | Only metric that is positive | Ignores profitability; only comparable across similar margin profiles |
| P/E | Stable earners; financial institutions (with P/BV) where debt is operating | Directly what equity holders get | Affected by leverage, tax, one-offs; NM when losses |
| (not MVP) EV/EBIT, P/BV, EV/subscribers | Capex-heavy / banks / sector-specific | — | — |

### H.10 Data and source integrity

- Synthetic samples: deterministic generator script with documented assumptions; every value has
  `source.kind = synthetic`, `basis = assumed`; companies named with "(SYNTHETIC)" and fictional names.
  The UI, exports and memo footer display "Contains synthetic data — not real company figures".
- CSV import: fixed template (`item_code, FY2022, FY2023, …` plus header rows for currency, scale, fiscal year end).
  Values stored with `source_ref = "<file>:<row>:<column>"` and file SHA-256.
- Derived values (e.g. EBITDA = EBIT + DA) are never stored as *reported*; they are computed with `basis = derived`
  and list their inputs.
- **Future (P2) public filings:** SEC EDGAR XBRL `companyfacts` JSON (free, official) → map US-GAAP
  tags to canonical items via a versioned mapping table (e.g. `Revenues` / `RevenueFromContractWithCustomerExcludingAssessedTax` → REVENUE),
  keep accession number + tag + filing date as `source_ref`, use `fp`/`fy`/`frame` fields to identify periods,
  normalise `unit` (USD, shares) and scale; non-USD filers require dated FX rates from a stated source
  (e.g. a central bank reference rate) stored alongside the value. Indian companies would need a separate source
  (no equivalent free structured API), so manual CSV with provenance remains the fallback.

### H.11 M&A transaction analysis (Year-1 pro forma)

**Inputs:** acquirer price `P_A`, diluted shares `S_A`, standalone forecast net income `NI_A`;
target price `P_T`, diluted share inputs, standalone forecast net income `NI_T` (must exclude any synergies),
target debt and its interest; offer premium `π`; consideration mix (% cash, % stock); funding of cash
(acquirer cash on hand vs new debt); new debt rate `r_d`; pre-tax yield forgone on cash `r_c`;
tax rate `T`; advisory fees `F_adv`; financing fees `F_fin` and amortisation period `L`;
run-rate pre-tax cost synergies `Syn_C`; revenue synergies `Syn_R` with contribution margin `cm`;
synergy phase-in % for Year 1 `φ`; one-time integration costs `IC`; whether target debt is refinanced.

```
Offer price per share     = P_T × (1 + π)
Equity purchase price     = Offer price × diluted target shares (TSM at the offer price)
Enterprise value paid     = Equity purchase price + target net debt + preferred + NCI
Implied multiples         = EV paid / target EBITDA ; Offer price / target EPS

USES                                   SOURCES
 Equity purchase price                  Acquirer cash on hand
 Refinance target debt (if chosen)      New debt raised
 Advisory fees F_adv                    New acquirer shares issued (value)
 Financing fees F_fin
 Total uses                       ==    Total sources        (must balance to 1e-6 → else error SU_IMBALANCE)

New shares issued         = stock consideration value / (P_A × (1 − issue discount))     [issue discount default 0]

Pro forma net income (recurring, run-rate):
  NI_A + NI_T
  + (Syn_C + Syn_R × cm) × φ × (1 − T)                 synergies, counted once, after tax
  − New debt × r_d × (1 − T)                            new interest
  − Cash used × r_c × (1 − T)                           interest income forgone
  − (F_fin / L) × (1 − T)                               financing-fee amortisation
  + Target interest × (1 − T)   (only if target debt refinanced; its interest is in NI_T)
  − [P1] amortisation of acquired intangibles × (1 − T)

Pro forma shares          = S_A + new shares issued
Pro forma EPS             = PF net income / PF shares
Accretion/(dilution)      = PF EPS / standalone EPS_A − 1
Breakeven pre-tax synergies = (EPS_A × PF shares − PF NI excluding synergies) / (1 − T)
Pro forma leverage        = (Acquirer debt + target debt kept + new debt) / (EBITDA_A + EBITDA_T + run-rate synergies)
```

Treatment of one-time items (to avoid double counting):
- **Advisory fees** are a *use of funds* only; they are excluded from recurring PF EPS (they are
  expensed/capitalised at close, not every year). Shown separately as a one-time item.
- **Financing fees** are a use of funds *and* amortised over the debt term in PF EPS (this is their recurring P&L effect, not a double count).
- **Integration costs** are one-time; excluded from run-rate EPS and shown in a separate
  "Year-1 reported EPS incl. one-time costs" line **[D-13]**.
- **Synergies** appear only in PF net income — never in target standalone NI or in the standalone DCF.
- Revenue synergies are converted to profit using a contribution margin, never added at 100 %.
- The **premium is not an expense**; its EPS effect comes entirely through financing costs and new shares.

Validation: mix sums to 100 %; cash used ≤ acquirer cash available; `P_A > 0`; standalone EPS_A > 0
(accretion % is NM when acquirer EPS ≤ 0 — show absolute EPS change instead); warnings for
PF leverage > 4.0x, premium outside 10–60 %.

### H.12 Sensitivity and scenarios

- A sensitivity cell = a **complete engine run** with one or two inputs replaced (no shortcuts like
  rescaling EV), so the grid is guaranteed consistent with the DCF.
- Supported variables: WACC (overrides computed WACC), terminal g, revenue growth shift (adds Δ to every
  `g_t`), EBITDA margin shift (adds Δ to every `m_t`), CapEx % shift, tax rate; for M&A: premium, % stock, synergies.
- Invalid cells (e.g. `g ≥ WACC`) return `status = invalid` with the error code; never a number.
- The base values must appear in the grid (the service inserts them if the step doesn't hit them), and the
  base cell must equal the saved run exactly.
- Scenario = parent assumption set ⊕ overrides; resolution happens before the engine, the resolved set is snapshotted.

### H.13 Edge-case summary

| Situation | Handling |
|---|---|
| Negative EBIT (history) | Margins computed (negative); effective tax NM |
| Negative EBIT (forecast) | Zero tax (D-06) + warning |
| Negative UFCF in forecast years | Allowed, discounted normally, flagged |
| Negative UFCF in final year | Gordon TV error; suggest extending forecast or using exit multiple (P1) |
| Unusual tax rate (hist.) | Warning; forecast uses normalised rate (D-05) |
| `g ≥ WACC` | Error |
| Equity value ≤ 0 | Flag, show figure |
| Peer negative EBITDA / NI | NM, excluded from stats |
| Missing required input | `status = missing`, no number, named inputs |
| Zero/negative revenue | Ratios NM |
| Acquirer EPS ≤ 0 | Accretion % NM |
| Financial institution sector | DCF/EV comps disabled with explanation |

---

## I. Test strategy and known-answer cases

### I.1 Layers

| Layer | Tooling | What is tested | Target |
|---|---|---|---|
| Engine unit tests | pytest | Each formula in H, each validation rule and warning code | ≥ 95 % line, 100 % of rule codes exercised |
| Known-answer tests (KA) | pytest + JSON fixtures | Hand-computed cases below; fixtures checked into `tests/fixtures/known_answers` | All pass, tolerance `rel=1e-9` |
| Property / invariant tests | hypothesis | Monotonicity and identities (I.3) | — |
| Independent re-computation | pytest | A second, deliberately naive implementation (closed forms, `numpy` NPV) compared to the engine for random valid inputs | — |
| Importer tests | pytest | Bad CSVs: missing columns, text in numbers, duplicates, negative CapEx, unit header missing | Each error code covered |
| API tests | FastAPI TestClient | Status codes, envelopes, preview == persisted run, reproducible `input_hash` | All endpoints |
| Frontend unit | Vitest + RTL | `format.ts` (parentheses for negatives, NM, "—" for missing, `x` for multiples), input validation messages, stale-state display | — |
| E2E | Playwright | J1 → J4 → J5 → J7 → J8 happy path + J9 error path | 2 tests |
| Static checks | ruff, mypy --strict (engine), ESLint, tsc, a "no `fillna(0)` / no `or 0`" grep, engine import ban | CI on every push | Green |

### I.2 Known-answer cases (hand-verified)

**KA-FC-01 Forecast build.** `Rev_0 = 1,000`, `NWC_0 = 100`, `g = 10 %, 8 %`, `m = 20 %`, `d = 5 %`, `c = 6 %`, `n = 10 %`, `T = 25 %`.

| | Y1 | Y2 |
|---|---|---|
| Revenue | 1,100.00 | 1,188.00 |
| EBITDA | 220.00 | 237.60 |
| D&A | 55.00 | 59.40 |
| EBIT | 165.00 | 178.20 |
| NOPAT | 123.75 | 133.65 |
| CapEx | 66.00 | 71.28 |
| NWC / ΔNWC | 110.00 / 10.00 | 118.80 / 8.80 |
| **UFCF** | **102.75** | **112.97** |

**KA-UFCF-01** EBIT 200, T 25 %, D&A 50, CapEx 70, ΔNWC +10 → NOPAT 150 → **UFCF 120**.
**KA-UFCF-02** EBIT −40, T 25 %, D&A 30, CapEx 20, ΔNWC −5 → tax 0, NOPAT −40 → **UFCF −25** (+ warning `NEGATIVE_EBIT_NO_TAX_CREDIT`). (Symmetric-tax alternative would give −15; test documents the difference.)

**KA-WACC-01** Rf 4 %, β 1.20, ERP 5.5 % → **Ke 10.60 %**. Price 50 × 20 shares → E = 1,000; D = 250; V = 1,250.
Kd 6 %, T 25 % → after-tax 4.50 %. **WACC = 0.8 × 10.60 % + 0.2 × 4.50 % = 9.38 %.**

**KA-BETA-01** β_L 1.20, D/E 0.25, T 25 % → **β_U = 1.20 / 1.1875 = 1.010526…**; relevering returns 1.20.

**KA-DCF-01 Discounting and Gordon TV.** UFCF = 100.00, 110.00, 121.00, 133.10, 146.41; WACC 10 %; g 2 %.
Each `PV(UFCF_t) = 90.909091` (because UFCF grows at exactly WACC) → `ΣPV = 454.545455`.
`TV = 146.41 × 1.02 / 0.08 = 1,866.727500`; `DF_5 = 1/1.61051` → `PV(TV) = 1,159.090909`.
**EV = 1,613.636364** (closed form: `(100/1.1) × (5 + 12.75)`); TV share = **71.83 %**.

**KA-BRIDGE-01** EV 1,613.636364 − debt 300 + cash 100 − pref 0 − NCI 20 → **equity 1,393.636364**;
100.0 diluted shares → **13.936364 per share**.

**KA-TV-ERR-01** WACC 8 %, g 8 % → error `TERMINAL_GROWTH_GE_WACC`, no EV returned. g 8.5 % → same.

**KA-TSM-01** Price 50; basic 100.0 m; tranche A 4.0 m @ 30 → 4 × (1 − 30/50) = **1.6 m**; tranche B 2.0 m @ 60 → **0**; RSUs 1.0 m → **diluted 102.6 m**.

**KA-COMP-01 Peer EV and multiples.** Price 25 × 40 diluted = market cap 1,000; debt 300; cash 150; NCI 50 → **EV 1,200**.
Revenue 600 → **2.0x**; EBITDA 150 → **8.0x**; NI 80 → **P/E 12.5x**.

**KA-COMP-02 Statistics & exclusions.** EV/EBITDA for six peers: 8, 10, 12, 14, NM (EBITDA < 0), 30 (excluded by user, reason "one-off gain").
Included [8, 10, 12, 14]: **n 4, median 11.0x, mean 11.0x, 25th 9.5x, 75th 12.5x**. Target EBITDA 200 →
**implied EV 1,900 – 2,500, point 2,200**.

**KA-MA-01 All-stock, dilutive.** Acquirer: P 50, S 100, NI 500 → EPS 5.00 (P/E 10x). Target: P 20, 50 shares, NI 100, premium 30 % → offer 26, equity price **1,300** (target P/E at offer 13x). 100 % stock, no fees/synergies, no debt.
New shares **26.0**; PF NI **600**; PF shares **126** → PF EPS **4.761905** → **dilution −4.76 %**.
Breakeven pre-tax synergies = (5.00 × 126 − 600)/0.75 = **40.00**.

**KA-MA-02** = KA-MA-01 + run-rate pre-tax cost synergies 40, φ 100 % → PF NI 630 → EPS **5.000000** → **0.00 %** (validates breakeven).

**KA-MA-03 Debt/stock mix.** As KA-MA-01, 50 % stock / 50 % new debt at 6 %, synergies 40, T 25 %.
New shares 13; after-tax interest 650 × 6 % × 0.75 = 29.25; after-tax synergies 30.
PF NI = 500 + 100 + 30 − 29.25 = **600.75**; PF shares 113 → EPS **5.316372** → **accretion +6.33 %**.

**KA-MA-04 Fees and S&U.** KA-MA-03 + advisory fees 20 funded from acquirer cash (r_c = 0): Uses 1,320 = Sources (650 debt + 650 stock + 20 cash). Recurring PF EPS unchanged at **5.316372** (fees one-time). Changing debt to 640 → error `SU_IMBALANCE`.

### I.3 Invariants (property tests)

- EV strictly decreases as WACC increases (when all UFCF > 0); increases with g (when UFCF_N > 0).
- Scaling all monetary inputs by k scales EV and equity by k and leaves margins, multiples and WACC unchanged.
- Zero growth, constant margins, CapEx = D&A, ΔNWC = 0 and g = 0 ⇒ EV = NOPAT/WACC (perpetuity), within tolerance.
- Sensitivity base cell == saved run output exactly.
- Preview output == persisted run output for identical inputs; identical inputs ⇒ identical `input_hash`.
- S&U always balances for any accepted transaction; accretion is 0 at breakeven synergies.
- No engine output is numeric when a required input is `None`.

---

## J. Staged implementation roadmap

| Stage | Scope | Acceptance criteria |
|---|---|---|
| **0. Foundations** | New repo, backend/frontend skeletons, CI (ruff, mypy, pytest, eslint, vitest, build), ADRs for approved decisions | CI green on an empty test; `README` run instructions work on a clean machine |
| **1. Calculation engine (Phase 2)** | `engine/` modules H.2–H.12, types, warning/error codes, KA fixtures | All KA-* and invariant tests pass; ≥ 95 % coverage; mypy strict clean; engine import ban enforced; each function has a docstring citing its H-section formula |
| **2. Data layer & samples** | ORM models, Alembic migration 0001, synthetic sample generator, CSV importer with dry run, provenance | Sample loads with provenance on 100 % of values; each importer error code has a failing-CSV test; NULL never coerced to 0 |
| **3. API** | Routers + services for G.2; preview vs persisted runs; error envelope | API tests for every endpoint; preview == persisted; OpenAPI exported and TS types generated |
| **4. UI shell & historicals** | Design tokens, UI kit, dashboard, overview, historicals table + checks panel, empty states | Numbers right-aligned, tabular figures, negatives in parentheses, NM/—; synthetic badge visible; Vitest on formatters |
| **5. Forecast & DCF UI** | Driver grid (blue inputs), WACC panel, DCF output, warnings, save run | Matches KA-DCF numbers when sample inputs entered; J9 error path shows stale state |
| **6. Comps UI** | Peer table, exclusions with reasons, stats, implied range | KA-COMP-02 reproduced through the UI |
| **7. Sensitivity & scenarios** | Grids with heatmap, scenario clone/override/compare | Base cell equals run; invalid cells labelled; comparison shows assumption deltas |
| **8. M&A simulator** | S&U, financing, synergies, PF EPS, breakeven, accretion grid | KA-MA-01…04 reproduced via the UI; S&U imbalance blocked |
| **9. Football field, memo & export** | Summary chart, Jinja2 memo, MD/HTML export, print CSS | Every memo number traces to a run ID; footer shows engine version, hash, synthetic disclaimer |
| **10. Polish & interview pack** | Playwright E2E, README screenshots, interview guide, demo script, known-limitations doc | E2E green; a 10-minute demo script rehearsed end-to-end |

Each stage ends with a tagged commit and a short "what I can now explain" note in `docs/interview-guide.md`.

---

## K. Decisions requiring approval

Each has a recommendation; reply with approve / change per ID.

| ID | Decision | Recommendation | Alternative | Trade-off |
|---|---|---|---|---|
| D-01 | Numeric type in engine | `float` + tolerance tests | `Decimal` | Simplicity & Excel parity vs exact decimals |
| D-02 | Sign convention | Magnitudes for fixed-direction items; signed for EBIT/NI/ΔNWC/FCF; enforced by item dictionary | Fully signed (costs negative) | Readable formulas vs one uniform rule |
| D-03 | EBITDA definition | `EBIT + D&A` (derived, unadjusted) | Accept reported "adjusted EBITDA" | Consistency/auditability vs matching company presentations |
| D-04 | Storage of units | Normalise to project currency/scale at import; keep original value/unit/FX | Store raw, convert at read | Simple engine vs flexible multi-currency |
| D-05 | Forecast tax rate | User-entered normalised (statutory/marginal) rate, historical effective shown as reference | Historical average effective rate | Steady-state realism vs data-driven |
| D-06 | Tax on negative EBIT | Zero tax (no credit), warning; NOLs out of scope | Symmetric `EBIT×(1−T)` / NOL schedule | Conservative & simple vs more precise |
| D-07 | Valuation date & discounting | LFY year-end, end-of-year discounting (mid-year and stub as P1 toggles) | Today's date with stub + mid-year | Clean known answers vs banking-standard precision |
| D-08 | WACC weights | Current market values (debt at book as proxy, flagged), optional target D/V | Target structure only | Observable vs long-run representative |
| D-09 | Leases in the bridge | Include lease liabilities in debt **only if** EBITDA is pre-lease-expense (IFRS 16); synthetic samples have none | Always exclude | Correctness vs complexity |
| D-10 | Diluted shares for DCF value per share | Iterative TSM at implied price; current price for market cap | TSM at current price only | Internal consistency vs simplicity |
| D-11 | Peer outliers | Manual exclusion with mandatory reason + automatic NM exclusion; flags only for outliers | Automatic IQR-based exclusion | Analyst judgement & auditability vs automation |
| D-12 | Historical consistency failures | Warnings with tolerance; import still allowed | Hard errors | Usability with real data vs strictness |
| D-13 | M&A EPS basis | Run-rate recurring EPS primary; Year-1 incl. one-time costs as secondary line | Single "reported" EPS | Clean comparison vs GAAP-like figure |
| D-14 | Memo generation | Deterministic Jinja2 templates in MVP; LLM commentary deferred | LLM from day one | Grounded & testable vs fluent prose |
| D-15 | Repository | Separate `dealforge` repo (move this plan there) | Keep inside current repo | Clean portfolio artefact vs one extra setup step |
| D-16 | Forecast horizon | Fixed 5 years in MVP | Configurable 5–10 | Simpler UI/tests vs flexibility for high-growth targets |
| D-17 | Sector scope | Non-financial corporates only; FIs blocked with explanation | Support banks via P/BV | Focus vs breadth |

---

## L. Approval record and refinements

All of D-01, D-02, D-04 to D-06, D-08, D-09 and D-11 to D-17 were approved as recommended. Three
decisions were approved with refinements, which supersede the corresponding text above:

**D-03 — EBITDA (approved with addition).** Standardised EBITDA = EBIT + D&A stays the core
calculated metric. Company-reported EBITDA and adjusted EBITDA are preserved separately, each with
its source, and adjusted EBITDA carries its disclosed adjustments (label, amount, source). The
engine reconciles them (reported vs standardised; base + adjustments vs adjusted) and flags gaps.
Comparable-company analysis uses one basis for every peer and the target; a peer that lacks the
chosen basis gets a *missing* multiple and is never silently switched to another definition.
Implemented in `app/engine/ebitda.py`.

**D-07 — Valuation date (approved with addition).** The MVP keeps the last-fiscal-year-end
valuation date and end-of-year discounting, but four dates are held separately and never treated
as interchangeable: the historical statement date, the valuation date (must equal the statement
date in the MVP — a stub period is rejected), the forecast periods (FY labels and end dates,
discount exponent t = 1..5), and the market-data date for price, risk-free rate, beta and ERP
(must not precede the statements; any gap is reported, and a gap above 92 days is a warning).
Implemented in `app/engine/dates.py`.

**D-10 — Diluted shares (changed).** The model supports basic shares, options and warrants (treasury
stock method), RSUs/PSUs (added in full) and convertible debt (if-converted: converts when the
conversion price is below the share price; a converted instrument is equity, an unconverted one
stays a debt claim, never both). Calculations at an observed price — market capitalisation, WACC
weights, peers, the M&A offer price — are direct and never iterative. Only the DCF implied price is
genuinely circular, and only when options, warrants or convertibles exist; that case is solved
exactly (closed form per in-the-money set) rather than by open-ended iteration, and the solution
is re-verified by recomputing TSM at the solved price. Implemented in `app/engine/shares.py`.
