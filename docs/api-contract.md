# API contract: Pydantic schemas ↔ engine dataclasses (Phase 3 preparation)

Status: **design, approved before Phase 3 implementation**. No API code exists yet. This document
fixes the rules the Phase 3 API must follow so it can never quietly change a financial value.

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
| **Integers vs floats** | A JSON integer such as `2000` must be accepted for a `float` field: the conversion is lossless up to 2^53. Strings and booleans must be rejected. Pydantic's strict-mode behaviour for int → float is to be confirmed by contract test 3 when the schemas are written. If strict mode rejects integers, the fields use an explicit `StrictInt \| StrictFloat` type converted with `float()`. |
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
