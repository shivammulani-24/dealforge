# Phase 3 design: data infrastructure and API

Built on the approved Phase 1 architecture (section D) and the API contract
([`api-contract.md`](api-contract.md)). Decisions that refine or extend the plan are marked **[P3-xx]**.

## Layers

```
FastAPI routers (app/api/v1)  ──  Pydantic schemas (app/schemas)  ── strict, structure only
        │                                   │ mappers: 1:1 field copy, no arithmetic
services (app/services)  ── orchestration: load data → build engine inputs → call engine → persist
        │                     │
SQLAlchemy models (app/db)    importers (app/importers)  ── pandas reads CSV as text only
        │
SQLite file  ── Alembic migrations (backend/alembic) → PostgreSQL later
                                         engine (app/engine) — unchanged, standard library only
```

## Decisions

| ID | Decision | Why | Trade-off |
|---|---|---|---|
| P3-01 | **Companies are top-level and owned by a user.** Financial periods and line items belong to a company. Valuation projects reference a company. | Statements are facts about a company and are reused by many projects and scenarios. | Slight change from the plan's "project 1–1 company". |
| P3-02 | **Line items are stored in the project's currency and scale, keeping the original value and scale** (D-04). CSV imports may convert scale (thousands → millions) within one currency. A currency mismatch is rejected: FX is out of scope (LIM-17). | Engine inputs must all be in one unit. | No multi-currency in Phase 3. |
| P3-03 | **Scenario assumptions are stored as rows** (key, year, value, basis, source, rationale). Statement-derived inputs (base revenue, base NWC, bridge claims, basic shares) are always read from the latest fiscal year's line items, never copied into assumptions. | Every input keeps its own provenance. Statements have a single source of truth. | Building the DCF inputs takes a join. |
| P3-04 | **Frozen runs** store canonical input JSON, result JSON, a provenance map, the engine version and the input hash. The ORM refuses updates and deletes, and SQLite triggers refuse them too. `POST /runs/{id}/verify` re-executes the stored inputs and compares the results byte for byte. | Immutability and reproducibility (requirement D). | The triggers are SQLite-specific; PostgreSQL needs equivalent triggers when migrating (LIM-18). |
| P3-05 | **Authentication: email + password, opaque bearer tokens.** Passwords are hashed with `hashlib.scrypt` (standard library, per-user salt). Login returns a random 256-bit token. Only its SHA-256 is stored, with an expiry (12 h) and logout revocation. | No extra crypto dependency. Tokens can be revoked server-side, unlike stateless JWTs. | A database lookup per request (fine at this scale). |
| P3-06 | **Authorisation: owner-only.** Every company, project, scenario and run belongs to one user. Another user's resource returns **404**, not 403, so existence isn't leaked. | Simple and sufficient for a single-analyst tool. | No sharing or roles yet (LIM-19). |
| P3-07 | **The CSV importer uses pandas with `dtype=str, keep_default_na=False`**, so pandas never invents NaN or numbers. Every cell is parsed by DealForge's own rules. | Approved stack, but none of pandas' silent conversions. | Slightly more parsing code. |
| P3-08 | **LIM-12 and LIM-13 are implemented in the engine** as pure functions (`engine/consistency.py`, plus a check in `historical.py`), and the service layer feeds them. | Keeps all financial rules in the engine, where they are testable without a database. | — |
| P3-09 | **No separate repository layer.** Services use SQLAlchemy sessions directly through small query helpers. | Less boilerplate for a single-database app. A repository layer can be extracted if a second store appears. | Services know about the ORM. |

## CSV format (v1)

```
item_code,FY2023,FY2024
period_end,2023-03-31,2024-03-31
revenue,"1,000.0",1200
cogs,600,720
cash,100,
...
```

- The first column holds canonical item codes (see `GET /api/v1/line-items`). Each other column is a fiscal year.
- `period_end` is required. Currency and scale are request fields: the currency must equal the
  company's; the scale is converted if it differs, and the original value is kept.
- Blank, `NA`, `N/A`, `-` and `n/a` mean **missing** and are stored as NULL, never 0. `(123)` means −123.
  Thousands separators are allowed. Any other text, `nan` or `inf` is an error with row and column.
- `?dry_run=true` returns a preview: parsed values, errors, warnings and historical metrics.
  A commit is refused while errors exist. Re-importing an existing year needs `replace=true` and is audited.
