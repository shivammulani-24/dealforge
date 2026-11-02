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
| LIM-12 | No warning when a forecast driver differs sharply from its historical range (spec H.3: > 10 pp). The engine's forecast takes no historical input. | An unrealistic margin or CapEx assumption is not flagged automatically | Historical metrics are available side by side. Found while preparing Phase 3 | Open | Phase 3 (service layer compares the forecast with `analyze_historicals`) |
| LIM-13 | The historical check "D&A ≤ COGS + OpEx" (spec H.2) is not implemented. | A data-entry error placing D&A above total costs is not flagged | EBIT reconciliation check catches most such errors. Found while preparing Phase 3 | Open | Phase 3 |
| LIM-14 | No trapped-cash / minimum operating cash adjustment; all cash is added in the bridge. | Overstates equity when part of the cash is needed for operations or is trapped abroad | The user can lower `cash`, or add the amount as an other debt-like claim, with a note | Open | P1 |
| LIM-15 | Hamada unlever/relever is implemented but not yet wired into a peer-beta workflow. | Beta must be entered directly | `unlever_beta` / `relever_beta` functions tested (KA-BETA-01) | Planned | P1 |
| LIM-16 | Banks and insurers are out of scope (D-17). | No valuation for financial institutions | `FINANCIAL_INSTITUTION_NOT_SUPPORTED` error with an explanation | Accepted | P2 (P/BV, dividend discount) |
