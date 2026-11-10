# Limitations and enhancement backlog

Every known limitation of the financial engine is tracked here with a stable ID. Rules:

- An entry is **never deleted**. When it is resolved, set its status to `Resolved` and give the
  commit or PR and the test that proves the fix.
- `tests/engine/test_limitations_register.py` fails if a `LIM-xx` ID cited in `engine.md` is
  missing from this register, or if an entry lacks a status, target or impact.
- Status values: `Open` · `Planned` · `Accepted` (a deliberate MVP simplification, kept visible)
  · `Resolved`.

| ID | Limitation | Impact on outputs | Current mitigation | Status | Target |
|---|---|---|---|---|---|
| LIM-01 | No NOL / tax-loss carry-forward asset (D-06). Negative EBIT pays zero tax, and future profits get no shield. | Undervalues loss-making companies with usable losses | `NEGATIVE_EBIT_NO_TAX_CREDIT` warning on each affected year | Accepted | P1 (NOL schedule) |
| LIM-02 | Year-end discounting only; valuation date must equal the statement date (D-07). | Understates value by about half a year of discounting vs mid-year. No valuation at intra-year dates | `STUB_PERIOD_NOT_SUPPORTED` error; convention text in every result | Planned | P1 (mid-year toggle, stub period) |
| LIM-03 | Gordon growth is the only terminal-value method. The exit multiple is a cross-check only. | No exit-multiple valuation | Implied exit multiple and peer-range check (`TV_MULTIPLE_INCONSISTENT`) | Planned | P1 |
| LIM-04 | Market value of debt must be supplied by the user. Book value is accepted as a proxy. | WACC weights are off when debt trades away from par | `DEBT_AT_BOOK` info note | Accepted | P2 (bond-price input) |
| LIM-05 | The comps P/E route ignores convertibles in the per-share step (if-converted EPS with coupon add-back is not modelled). | Overstates value per share for P/E-valued targets with in-the-money convertibles | `PE_CONVERTIBLES_IGNORED` warning; EV multiples handle convertibles correctly | Open | P1 |
| LIM-06 | Peer fiscal periods are not calendarised; LTM is not built from quarters. | Peers with offset year-ends are compared on different periods | `FISCAL_PERIOD_MISALIGNED` warning (> 92 days) | Planned | P1 |
| LIM-07 | Accretion/dilution covers one pro forma year. No purchase-price allocation, so no goodwill or intangible amortisation. | Overstates accretion where acquired intangibles would be amortised | Run-rate and Year-1 lines shown separately; documented in the memo template (Phase 3+) | Planned | P1 (multi-year, simplified PPA) |
| LIM-08 | Advisory fees are treated as non-deductible in the Year-1 EPS line. | Year-1 EPS is slightly conservative where fees are deductible | Documented in `mna.py` docstring | Accepted | — |
| LIM-09 | RSUs/PSUs are added in full: no vesting or performance conditions, no anti-dilution test. | Slightly overstates the diluted share count | Instrument-level dilution lines in every result | Accepted | P2 |
| LIM-10 | All options are treated as exercisable. No vested/unvested split and no option-pricing alternative to TSM. | TSM understates the economic cost of out-of-the-money options | Per-tranche in/out-of-the-money disclosure | Accepted | P2 |
| LIM-11 | Floating-point arithmetic (D-01). | Agreement with exact arithmetic to ~1e-12 relative (verified in `docs/verification/`) | Rounding at display only | Accepted | — |
| LIM-12 | No warning when a forecast driver differs sharply from its historical range (spec H.3: > 10 pp). | — | **Resolved in Phase 3:** `engine/consistency.py` `driver_history_warnings` (`DRIVER_OUTSIDE_HISTORY`, `DRIVER_NO_HISTORY`); tests `tests/engine/test_consistency.py` | Resolved | Phase 3 |
| LIM-13 | The historical check "D&A ≤ COGS + OpEx" (spec H.2) was not implemented. | — | **Resolved in Phase 3:** `historical.py` raises `DA_EXCEEDS_OPERATING_COSTS`; missing inputs give `DA_CHECK_SKIPPED` (disclosed, never compared with zero); tests `test_consistency.py::test_da_*` | Resolved | Phase 3 |
| LIM-14 | No trapped-cash / minimum operating cash adjustment; all cash is added in the bridge. | Overstates equity when part of the cash is needed for operations or is trapped abroad | The user can lower `cash`, or add the amount as an other debt-like claim, with a note | Open | P1 |
| LIM-15 | Hamada unlever/relever is implemented but not yet wired into a peer-beta workflow. | Beta must be entered directly | `unlever_beta` / `relever_beta` functions tested (KA-BETA-01) | Planned | P1 |
| LIM-16 | Banks and insurers are out of scope (D-17). | No valuation for financial institutions | `FINANCIAL_INSTITUTION_NOT_SUPPORTED` error with an explanation | Accepted | P2 (P/BV, dividend discount) |
| LIM-17 | No FX conversion: a CSV whose currency differs from the company's is rejected (P3-02). | Statements reported in another currency can't be imported | `CURRENCY_MISMATCH` import error | Planned | P2 (dated FX rates with source) |
| LIM-18 | Frozen-run immutability triggers exist for SQLite only (P3-04). The ORM guard works on any database. | A PostgreSQL deployment would rely on the ORM guard alone until equivalent triggers are added | `ImmutableRunError` in the ORM; migration note | Planned | PostgreSQL migration |
| LIM-19 | Owner-only authorisation: no sharing, teams or roles (P3-06). | One analyst per dataset | Other users' resources return 404 | Accepted | P2 |
| LIM-20 | Auth token kept in memory and `sessionStorage` (exposed to XSS) in the development-stage frontend (D4-01). **An HttpOnly, Secure, SameSite cookie with CSRF protection is required before any public deployment.** | A script injected into the page could read the token | Strict CSP on the served `index.html` (B11); no `innerHTML`; token cleared on 401/logout | Planned | **Deployment blocker:** before any public deployment |
| LIM-21 | Sensitivity is refused (409 `ENGINE_VERSION_MISMATCH`) for runs frozen under an older engine version (D4-05). | Old runs can't get new grids | Stored results stay viewable (`GET /runs/{id}`, runs list, dashboard) and verifiable; re-freeze the scenario on the current engine | Accepted | — |
| LIM-22 | Rebuilding a frozen run depends on the `DcfInputs` schema. A future schema change needs a versioned reader. | Old runs could become unreadable for verify/sensitivity after an input-schema change | `inputs_schema_version` stored on every run since migration 0002; the bump checklist requires a reader (§4.13) | Planned | First input-schema change |
| LIM-23 | Quick and cash ratios need `marketable_securities` entered explicitly (0 if none); a blank makes them *missing*. | Fewer ratios for companies whose filings omit the line | Completeness "liquidity" group lists the gap; label says "enter 0 if none" | Accepted | — |
| LIM-24 | Layouts below 1024 px are not supported (D4-09). | Phones and small tablets | Non-blocking notice in the frontend (Phase 4 F1+) | Accepted | — |
| LIM-25 | Idempotency keys are kept indefinitely on their runs (runs are immutable). | A client can't reuse a key for a new request, ever | Clients generate a fresh UUID per action | Accepted | — |
| LIM-26 | "Recent companies" on the dashboard reflects writes (audit events), not views (D4-03). | A company only viewed doesn't appear as recent | Clear label "recently active" | Accepted | — |
| LIM-27 | Under heavy write contention SQLite returns 503 `DATABASE_BUSY` after the busy timeout (5 s). | A freeze can fail transiently | Safe retry with the same `Idempotency-Key` (tested); `Retry-After: 1` | Accepted | SQLite stage; revisit at the PostgreSQL migration |
| LIM-28 | The basis triggers (migration 0002) apply to new and updated rows only. Legacy development rows that break A4–A6 are reported by the migration's pre-check, not rewritten. | Legacy rows may carry an unsupported basis until edited | Pre-check lists them; any update is then forced through the rules | Accepted | — |
