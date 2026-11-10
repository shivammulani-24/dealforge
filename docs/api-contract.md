# API contract: Pydantic schemas ↔ engine dataclasses (Phase 3 preparation)

Status: **implemented in Phase 3** (`app/schemas/`, `app/api/`); contract tests in
`backend/tests/api/test_contract.py`. See section 6 for what testing established.

## 1. Two layers, two jobs

| Layer | Responsible for | Must NOT do |
|---|---|---|
| **Pydantic schema** (`app/schemas/`) | *Structure*: field names, JSON types, presence of keys, finite numbers, enums, ISO dates, unknown-field rejection | Financial rules (sign conventions, ranges, g < WACC, S&U balance). Duplicating them would create two sources of truth that can drift. |
| **Engine** (`app/engine/`) | *Finance*: every rule in the formula spec, with stable issue codes | Parse JSON, read the database, guess defaults |
| **Mapper** (`app/schemas/mappers.py`) | A 1:1 field copy, schema → engine dataclass, and engine result → response schema | Arithmetic, rounding, unit conversion, filling in defaults |

The engine stays the only judge of financial validity. The schema only guarantees that the engine
receives exactly what the client sent, in the right types.

## 2. Schema rules (every request model)

```python
class StrictModel(BaseModel):
    model_config = ConfigDict(
        strict=True,          # no coercion: "12.5" (string) or true (bool) is rejected, not converted
        extra="forbid",       # unknown keys are rejected, so a typo such as "termnal_growth" cannot be ignored
        allow_inf_nan=False,  # NaN / ±Infinity rejected at the boundary
        frozen=True,
    )
```

| Concern | Rule |
|---|---|
| **Missing stays missing** | Every engine field typed `float \| None` maps to a schema field that is *required but nullable*: `revenue: float \| None` **with no default**. An omitted key → 422 (`missing`). An explicit `null` → passed to the engine as `None` → the engine reports `MISSING_INPUT` or returns a `MISSING` metric. No schema field has a numeric default. Bridge claims (debt, NCI, leases, …) are required non-null numbers: the client must send `0` for "none". |
| **Integers vs floats** | **Resolved (section 6).** Strict mode accepts a JSON integer for a `float` field (`2000` → `2000.0`). Integers above 2^53 are rejected (`int_not_exact`), because a float would silently round them. Strings, booleans, lists, NaN, ±Infinity and overflow (`1e400`) are rejected. |
| **Units** | Every request carries `{"currency": "INR", "scale": "crores"}` at the top level. All monetary fields in that request are in that unit. The API never rescales. Converting units is an importer job (Phase 3 CSV) and is recorded in provenance. Responses repeat `currency` and `scale`. Rates are decimals (`0.25`), and the schema docs state "decimal, not percent". |
| **Sign conventions (D-02)** | Magnitude fields are documented as "≥ 0 magnitude" in the OpenAPI description, but the check itself is the engine's `SIGN_CONVENTION` error, so the client gets the same code whichever entry point it uses. |
| **Enums** | Accepted only as their exact string values (`"standardized"`, `"ltm"`, `"book"`), case-sensitive. |
| **Dates** | ISO `YYYY-MM-DD` only. `statement_date`, `valuation_date` and `market_data_date` are three separate required fields (D-07). |
| **Tuples** | Forecast years are a list of exactly 5 objects. Length is checked by the engine (`HORIZON_NOT_SUPPORTED`), not the schema, so the message and code stay financial. |

## 3. Mapping table (DCF request; the other endpoints follow the same pattern)

| JSON path | Schema type | Engine field |
|---|---|---|
| `dates.statement_date` / `valuation_date` / `market_data_date` | `date` | `ValuationDates.*` |
| `forecast.base_revenue`, `forecast.base_nwc` | `float` | `ForecastInputs.base_revenue`, `.base_nwc` |
| `forecast.years[i].{revenue_growth, ebitda_margin, da_pct_revenue, capex_pct_revenue, nwc_pct_revenue}` | `float` | `ForecastYearDrivers.*` |
| `tax_rate`, `terminal_growth` | `float` | `DcfInputs.tax_rate`, `.terminal_growth` |
| `wacc_assumptions` | object \| `null` | `WaccAssumptions` (exactly one of this and `wacc_override`; the engine enforces it) |
| `wacc_override` | `float \| null` | `DcfInputs.wacc_override` |
| `bridge.{cash, total_debt, lease_liabilities, preferred_equity, non_controlling_interest, other_debt_like_claims, non_operating_assets}` | `float` (required, non-null) | `BridgeInputs.*` |
| `bridge.include_leases_in_debt` | `bool` (required) | `BridgeInputs.include_leases_in_debt` |
| `share_capital.basic_shares`, `.options[]`, `.rsus[]`, `.convertibles[]` | objects | `ShareCapitalInputs`, `OptionTranche`, `RsuGrant`, `ConvertibleInstrument` |
| `current_share_price` | `float \| null` | `DcfInputs.current_share_price` |
| `is_financial_institution` | `bool` (required) | `DcfInputs.is_financial_institution` |

Field names are identical on both sides, so the mapper is a mechanical copy. A unit test asserts
that the set of schema fields equals the set of dataclass fields for every pair, so adding a field
on one side only fails CI.

## 4. Error responses: validation vs calculation

```json
{ "error_type": "validation",          "status": 422,
  "errors": [ { "loc": ["body","forecast","years",2,"ebitda_margin"], "code": "float_type",
               "message": "Input should be a valid number" } ] }

{ "error_type": "calculation",         "status": 422,
  "errors": [ { "field": "terminal_growth", "code": "TERMINAL_GROWTH_GE_WACC", "severity": "error",
               "message": "Terminal growth (10.00%) must be below WACC (9.38%)…" } ],
  "engine_version": "0.1.0" }
```

| | `validation` | `calculation` |
|---|---|---|
| Raised by | Pydantic (schema) | `EngineError` / `MissingInputError` |
| Meaning | The request is malformed: the engine never ran | The request is well-formed but financially invalid, or a required value is `null` |
| Codes | Pydantic's (`missing`, `float_type`, `extra_forbidden`, `finite_number`, …) | `errors.Code.*` (stable, documented) |
| HTTP | 422 | 422 (`MISSING_INPUT` included). Successful runs return 200 with `warnings[]`. |

The client can always tell which layer refused the request from `error_type`.

## 5. Contract tests (to be written in Phase 3, Stage 3; each is an acceptance criterion)

1. **No value drift (round trip).** For every known-answer case, POST the inputs as JSON →
   the API response equals the result of calling the engine directly with the same dataclasses,
   compared **exactly** (`==` on floats), not approximately. Includes KA-DCF-03 from
   `docs/verification/independent-verification.md`.
2. **Missing stays missing.** For each nullable field: send `null` → the engine's `MISSING_INPUT`
   (or a `MISSING` metric in the response), never a number. Omit the key → `validation` /
   `missing`. Static check: no schema field has a numeric default.
3. **Coercion rejected.** `"0.25"` (string), `true` and `[0.25]` sent for a number → `validation`
   error. `NaN` / `Infinity` literals → `validation` error.
4. **Unknown fields rejected.** A misspelled key → `extra_forbidden`, not silently ignored.
5. **Units preserved.** The response `currency`/`scale` equal the request's. Monetary outputs
   equal the engine outputs in the same scale.
6. **Error-type separation.** A malformed body → `error_type == "validation"` and the engine
   is not called (asserted with a spy). g ≥ WACC → `error_type == "calculation"` with
   `TERMINAL_GROWTH_GE_WACC`.
7. **Field parity.** Schema field sets equal dataclass field sets (section 3).
8. **Fingerprint stability.** The `input_hash` returned by the API equals
   `fingerprint(engine_inputs)` for the same request.

Groundwork already in place (Phase 2): `tests/engine/test_contract_groundwork.py` proves that
the engine's canonical JSON keeps every finite float exactly (shortest round-trip `repr`), keeps
`None` as `null` (never `0`), and rejects NaN. These are the properties the API serialisation will
rely on.

## 6. Findings from implementing and testing the contract

1. **Integers (the open question from Phase 2): resolved.** Pydantic v2 strict mode accepts a JSON
   integer for a `float` field, and the value arrives as the identical float
   (`test_3_integers_are_accepted_exactly` checks that the API result equals the engine result
   computed with `1000.0`). An experiment showed one silent change: `9007199254740993` (2^53 + 1)
   became `9007199254740992.0`. The `Num` type now rejects integers above 2^53 with
   `int_not_exact` (`test_3_coercion_is_rejected`).
2. **FastAPI validates bodies in Python mode, not JSON mode.** In strict Python mode, Pydantic rejects
   every string for a `date` or `Enum` field, so ISO dates sent by clients failed. Switching those
   fields to lax mode would also accept integers as Unix timestamps for dates. Instead, two narrow
   types are used: `IsoDate` accepts exactly `YYYY-MM-DD` and `ExactEnum` accepts exactly an
   enum's value, case-sensitive. Timestamps, `31/03/2025`, datetimes and `"BOOK"` are rejected
   (`test_3_dates_and_types_are_exact`, `test_3_enum_values_are_case_sensitive`).
3. **Null vs omitted.** An explicit `null` reaches the engine as `None` and comes back as a
   `calculation` error `MISSING_INPUT` naming the field (tested for tax rate, cash, NCI, basic
   shares and base NWC separately). An omitted key is a `validation` error `missing`. A planted
   mapper bug that turned a null cash into `0.0` was caught by these tests.
4. **No value drift.** For KA-DCF-02 and KA-DCF-03, `POST /calculate/dcf` returns JSON equal,
   with exact float equality, to `run_dcf` called directly. Saved runs re-execute byte for byte
   (`POST /runs/{id}/verify`).

## 7. Intentional breaking changes (Phase 4)

Each was approved before implementation (see `phase-4-plan.md` §10–§11). Clients written against
the Phase 3 API must make these changes.

| ID | Endpoint | Phase 3 behaviour | Phase 4 behaviour | Why |
|---|---|---|---|---|
| C6 | `PATCH /line-items/{id}` | Body `{value, note}`; the item's old basis was kept | Body `{value, basis, rationale?, source?}`. `basis` is `reported` or `assumed`. `reported` needs `source: {title, reference?, uri?}` (stored as a `filing` source). `assumed` needs a `rationale`. The old body is a `validation` error. | An analyst-entered number could still be labelled "reported" (R2, A4–A6). |
| C9 | `POST /projects/{id}/scenarios`, `PUT /scenarios/{id}`, `POST …/clone` | Assumptions could omit `rationale`; settings had no `market_rationale` | Every `assumed` assumption needs a `rationale` (1–2,000 non-blank characters). A `share_price` without `market_source_id` needs `settings.market_rationale`. Missing → `validation` (`rationale_required`). | A5: an assumption must say why. |
| C9 | `POST /companies/{id}/financials/import` | `basis=assumed` needed nothing else | `basis=assumed` needs a `rationale` form field, stored on the source and on each line item's `note`. Missing → `import` error. | A5. |
| C10 | `POST /scenarios/{id}/runs` | No idempotency | **`Idempotency-Key` header required** (8–128 of `[A-Za-z0-9_-]`). Missing or malformed → 422 `validation`; nothing is created and the engine isn't called. Same key and request → 200 with the same run and `Idempotent-Replayed: true`. Same key, different request → 409 `IDEMPOTENCY_KEY_REUSED`. Lock timeout → 503 `DATABASE_BUSY` with `Retry-After: 1`; retry with the same key. | A7, A8: no duplicate frozen runs, including under concurrency. |
| C12 | Assumption `basis` | Accepted `assumed`, `reported` or `derived` | Accepts only `assumed` or `reported`. `reported` needs a `source_id` the user owns, of kind `csv_import`, `filing`, `market_data` or `synthetic`; otherwise 422 (`basis_source_required` / `BASIS_SOURCE_KIND`) or 404 for another user's source. | A4, A6. |

**Also enforced in the database (migration 0002):** triggers reject any `line_items`,
`assumptions` or `scenarios` row that breaks A4–A6, including direct SQL. Existing rows are not
rewritten; the migration's read-only pre-check lists any that violate the rules (LIM-28).

**Non-breaking fix:** `created_at` on a run is now always rendered in UTC with an explicit offset
(`…+00:00`). Previously a run read back from SQLite rendered without the offset, so the response
to `POST …/runs` and a later `GET /runs/{id}` differed for the same run.

## 8. Phase 4 F0 additions (non-breaking)

| Endpoint | Purpose |
|---|---|
| `GET /dashboard` | Counts, onboarding progress, recent runs, recently active companies, activity summaries (no raw audit detail) |
| `GET /runs?page&page_size&company_id&project_id&scenario_id` | All of the user's frozen runs, read verbatim from stored results, with `engine_compatible` |
| `POST /runs/{id}/sensitivity` | Grid from the run's frozen inputs only; 409 `ENGINE_VERSION_MISMATCH` or `RUN_INPUTS_CORRUPT`; `change_abs` always, `change_pct` NM when the base ≤ 0 |
| `POST /scenarios/{id}/preview` with a body | Draft preview: validated like a save; no database writes, no audit event (`"draft": true`) |
| `GET /sources/{id}`, `POST /sources` | Source details; analysts create `filing` or `market_data` sources to back reported values |
| `GET /samples`, `POST /samples/{id}/load` | The synthetic sample company, loaded atomically; 409 `SAMPLE_ALREADY_LOADED` with existing IDs |
| Preview and run responses | New `context` (company, currency, scale), `presentation` (EBIT/UFCF margins, outside `result_json`), `result_basis`, `engine_compatible` |
| `GET …/financials` | `completeness` per period (DCF group unchanged, separate liquidity group) |
| `GET …/historical-analysis` | `basis: "derived"` on every metric; `metric_definitions` (formula, items, NM rule); liquidity ratios |
| Production | With `DEALFORGE_FRONTEND_DIST` set, the built frontend is served from the same origin; `/api`, `/docs`, `/redoc`, `/openapi.json` are never intercepted |

**Response schemas (B6):** every frontend-facing route documents its success body in OpenAPI.
`docs/openapi.json` is committed and checked in CI (`scripts/export_openapi.py --check`). In the
test suite, every successful response is validated against its declared model in strict JSON mode
(no coercion, no unknown fields), and a test exercises all 26 documented routes.
`error_type` now falls back to the HTTP status (409 → `conflict`, 503 → `unavailable`, 500 →
`internal`), so a conflict is never labelled `validation`.
