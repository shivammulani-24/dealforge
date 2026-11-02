# DealForge financial engine (Phase 2)

The engine is a pure, deterministic Python package at `backend/app/engine/`. It imports only the
standard library. It has no database, web framework, pandas, NumPy, network or clock access. A
test fails if any of those creep in (`tests/engine/test_purity.py`). Everything the later API and
UI show is computed here.

## 1. Architecture

```
                      ┌────────────────────────── valuation.run_dcf ──────────────────────────┐
 dates ─► schedule    │                                                                       │
 forecast ─► years ─► │ fcf.forecast_ufcf ─► dcf.terminal_value_gordon ─► dcf.discount_cash_flows
                      │        ▲                     ▲                           │            │
 wacc.compute_wacc ───┼────────┴─────────────────────┘                           ▼            │
   (market values via │                                       bridge.equity_from_enterprise   │
   shares.diluted_shares_at_price)                                               │            │
                      │                                    shares.implied_value_per_share     │
                      └───────────────────────────────────────────────────────────────────────┘
 sensitivity.dcf_sensitivity  = run_dcf re-executed per cell        scenarios = base ⊕ overrides
 comps.analyze_comps ─► comps.implied_valuation (same bridge + share logic as the DCF)
 mna.analyze_deal (shares at the offer price, same inverse bridge)  historical.analyze_historicals
 errors · validation · metrics · hashing · version   (shared foundations)
```

**Design rules**

| Rule | How it is enforced |
|---|---|
| Missing ≠ zero | `None` is *missing*. Required inputs raise `MissingInputError`. Analytical metrics return `Metric(status=MISSING)`. There are no defaults on financial inputs. Bridge claims must be entered as `0.0` explicitly. A test bans `fillna(`, `or 0` and similar patterns in engine source. |
| Errors vs warnings | Errors raise `EngineError` with *all* problems found. Warnings and info notes travel inside results with stable codes (`errors.Code`). Nothing is printed or swallowed. |
| Small functions | Every formula is its own function (`compute_ufcf`, `terminal_value_gordon`, `cost_of_equity`, `diluted_shares_at_price`, …). The orchestrator adds no new maths. |
| Immutability | All inputs and outputs are `frozen` dataclasses. Scenarios and sensitivity cells use `dataclasses.replace`, so the base case can never be mutated. |
| Reproducibility | No randomness or clock reads. `hashing.fingerprint` gives a SHA-256 of canonical JSON of the inputs. `ENGINE_VERSION` is stamped on every result. Identical inputs give identical results (property-tested). |
| Floats (D-01) | Python `float`. Rounding happens only at display. Tests use explicit tolerances. |

**Deviations from the Phase 1 plan (deliberate)**

1. *Engine models are standard-library `dataclasses`, not Pydantic.* The engine then has zero
   dependencies. Pydantic stays the validation layer at the API boundary (Phase 3), where JSON
   parsing happens. Trade-off: the same shapes will be declared twice (API schema → engine
   dataclass), with a conversion test.
2. *Known-answer fixtures are written inline in the tests, not as JSON files.* The hand derivation
   sits in each test's docstring right next to the assertion, which is easier to read and defend.
   JSON fixtures can be exported later if the API needs them.
3. *Diluted shares at the implied price are solved in closed form instead of by iteration*
   (refined D-10). See section 3.

## 2. Conventions

| Topic | Convention |
|---|---|
| Units | One currency and scale per valuation. Shares use the same scale as money, so per-share values come out in currency units. |
| Rates | Decimals (`0.25` = 25%). |
| Signs (D-02) | Revenue, COGS, OpEx, D&A, CapEx, tax, interest, cash, debt and working-capital balances are positive magnitudes (a negative value is a `SIGN_CONVENTION` error). EBIT, pre-tax income, net income, CFO, NWC, ΔNWC and FCF are signed. |
| Dates (D-07) | `statement_date` = `valuation_date` (the LFY year-end). Forecast years t = 1..5 end on its anniversaries and are discounted with exponent t. `market_data_date` is separate and its gap is always reported. |
| Horizon (D-16) | Exactly 5 forecast years. |
| Scope (D-17) | `is_financial_institution=True` → `FINANCIAL_INSTITUTION_NOT_SUPPORTED`. |

## 3. Implemented functions

| Module | Function | Formula / behaviour |
|---|---|---|
| `metrics` | `safe_ratio` | n/d. Missing input → MISSING. d ≤ 0 → NM (or d = 0 only, when signed denominators are allowed). |
| `dates` | `build_schedule`, `add_years` | Separates the four kinds of date. Rejects stub periods and market data dated before the statements. Warns on market data > 92 days from the valuation date. Handles 29 Feb. |
| `ebitda` | `standardized_ebitda` | EBIT + D&A |
| | `reconcile_ebitda` | Checks reported vs standardised (info). Checks base + Σ adjustments vs adjusted (warning if unreconciled). Flags adjusted EBITDA without disclosed adjustments, and adjustments without an adjusted figure. |
| | `select_ebitda` | Returns exactly the requested basis, or MISSING. Never substitutes another basis. |
| `historical` | `analyze_historicals` | Growth, gross/EBITDA/EBIT/net margins, effective tax rate, simple FCF = CFO − CapEx, FCF conversion, CapEx and D&A % of revenue, CapEx/D&A, operating NWC, ΔNWC, net debt, net debt/EBITDA, interest coverage. Checks: EBIT and net income reconciliation, balance sheet, contiguous years, unusual tax rate, and **earnings up while FCF down**. |
| `forecast` | `build_forecast` | Rev_t = Rev_{t−1}(1+g). EBITDA, D&A, CapEx and NWC as % of revenue. EBIT = EBITDA − D&A. ΔNWC = NWC_t − NWC_{t−1}, with NWC_0 = LFY actual. |
| `fcf` | `compute_ufcf` | UFCF = EBIT − max(EBIT,0)·T + D&A − CapEx − ΔNWC. No tax credit on losses (D-06). |
| `wacc` | `cost_of_equity` | Rf + β·ERP + size premium |
| | `compute_wacc` | E/V·Ke + D/V·Kd(1−T) + P/V·Kp. Market weights, or a target D/V. Flags debt held at book value. |
| | `unlever_beta`, `relever_beta` | Hamada: β_U = β_L / (1 + (1−T)D/E) |
| `dcf` | `discount_factor` | 1/(1+r)^t |
| | `terminal_value_gordon` | UFCF_N(1+g)/(WACC−g). Error if g ≥ WACC or UFCF_N ≤ 0. Warns on a narrow spread, g > 4%, g > Rf, or g < 0. |
| | `discount_cash_flows` | EV = Σ PV + PV(TV). Reports TV share of EV (warning > 75%). |
| | `implied_exit_multiple`, `implied_perpetual_growth` | Cross-checks: TV/EBITDA_N, and g = (TV·W − UFCF)/(TV + UFCF). |
| `bridge` | `equity_from_enterprise` | EV − debt − leases (only if debt-like, D-09) − convertibles at face − preferred − NCI − other claims + cash + non-operating assets. |
| | `enterprise_from_equity` | The exact inverse, used for peers and deal EV. |
| `shares` | `diluted_shares_at_price` | At an observed price: TSM n(1 − K/P) for in-the-money options and warrants, RSUs added in full, convertibles if-converted. **Direct, never iterative.** |
| | `implied_value_per_share` | DCF implied price. Direct when there are no options or convertibles. Otherwise the circularity is solved exactly: P = (E + Σ nK + Σ F)/(B + R + Σ n + Σ F/C) for the in-the-money set, trying sets in threshold order. Re-verified by TSM at the solved P. |
| `valuation` | `run_dcf`, `market_capital_structure` | Full pipeline. WACC weights use market values on the market-data date. Debt includes debt-like leases and unconverted convertibles. |
| `comps` | `compute_peer` | Peer market cap (diluted at its price), EV via the inverse bridge, EV/Revenue, EV/EBITDA on the chosen basis, P/E. |
| | `analyze_comps`, `multiple_stats`, `percentile_inc` | Period-type consistency (error). Fiscal-period alignment and currency (flags). Analyst exclusions need a reason. NM values are automatically left out, with the reason recorded. n, min, 25th, median, mean, 75th, max. Percentiles match Excel `PERCENTILE.INC`. |
| | `implied_valuation` | Low/mid/high EV → equity → per share using the same bridge and share logic. The P/E route goes straight to equity. |
| `sensitivity` | `dcf_sensitivity`, `two_way_grid`, `centered_axis` | Each cell is a full `run_dcf`. Invalid cells carry error codes, never numbers. The base value must sit on each axis, and the base cell equals the base run exactly. |
| `scenarios` | `apply_overrides`, `run_scenarios` | Dotted-path overrides (`forecast.years[5].ebitda_margin`). Unknown paths are rejected. Overrides are applied in sorted order, so results are deterministic. |
| `mna` | `analyze_deal` | Offer price and target dilution *at the offer*. Equity price and EV paid. Sources = Uses (`SU_IMBALANCE` otherwise). New shares. Run-rate and Year-1 pro forma NI. EPS and accretion. Breakeven synergies. Ownership. Pro forma leverage. |
| | `new_debt_to_balance`, `accretion_sensitivity` | Debt plug. Premium × % stock grid. |
| `hashing` | `canonical_json`, `fingerprint` | Sorted keys, ISO dates, enum values, exact float repr. Rejects NaN. |

## 4. Test suite

238 tests in `backend/tests/engine/`. Run them with:

```bash
cd backend && pip install -e ".[dev]" && pytest --cov
```

**Known-answer cases (hand-verified; the derivation is in each test's docstring)**

| ID | What | Expected |
|---|---|---|
| KA-HIST-01 | Historical metrics | GM 40%, EBITDA 190, ETR 25%, NWC 100, ΔNWC 100, net debt 200 |
| KA-HIST-02 | Profit up, cash down | NI 105 → 127.5 while FCF 110 → 30; NWC absorbed 100 → `EARNINGS_CASH_DIVERGENCE` |
| KA-EBITDA-01 | Three EBITDA definitions | 800 + 200 = 1,000 standardised = reported; adjusted 1,150 = 1,000 + 100 + 50 |
| KA-FC-01 | Forecast build | Revenue 1,100 / 1,188; UFCF 102.75 / 112.97 |
| KA-UFCF-01 / 02 | UFCF; negative EBIT | 120; −25 (not −15, D-06) |
| KA-WACC-01 | CAPM WACC | Ke 10.60%, Kd(1−T) 4.50%, WACC 9.38% |
| KA-BETA-01 | Hamada | β_U = 1.010526; relevers to 1.20 |
| KA-DCF-01 | Discounting + Gordon | Each PV 90.909091; TV 1,866.7275; EV 1,613.636364; TV share 71.83% |
| KA-DCF-02 | Full pipeline from drivers | Same UFCF and EV as KA-DCF-01; equity 1,393.636364; 13.936364 per share |
| KA-BRIDGE-01 | Bridge | 1,613.64 − 300 + 100 − 20 = 1,393.64 |
| KA-TV-ERR-01 | g ≥ WACC | `TERMINAL_GROWTH_GE_WACC`, no value |
| KA-TSM-01 | TSM at observed price | 100 + 1.6 + 0 + 1 = 102.6 diluted shares |
| KA-SH-02 / 03 / 04 | Implied price with options / convertible / both | 9.545455 / 9.777778 / 9.387755 |
| KA-COMP-01 | Peer EV and multiples | EV 1,200; 2.0x / 8.0x / 12.5x |
| KA-COMP-02 | Stats and exclusions | Median 11.0x, mean 11.0x, 25th 9.5x, 75th 12.5x; implied EV 1,900–2,500 |
| KA-MA-01 | All-stock, higher-P/E target | EPS 5.00 → 4.761905 (−4.76%); breakeven synergies 40 |
| KA-MA-02 | At breakeven synergies | Accretion 0.00% |
| KA-MA-03 | 50% stock / 50% debt | PF NI 600.75; EPS 5.316372 (+6.33%) |
| KA-MA-04 | Fees and S&U | Uses 1,320; recurring EPS unchanged; new debt 640 → `SU_IMBALANCE` |
| Identities | Perpetuity; refinancing at the same rate | EV = NOPAT/WACC = 1,125; refinancing leaves EPS unchanged |

**Edge cases covered:** negative EBIT (history and forecast), loss-making early years, missing
inputs at every layer, zero debt (WACC = Ke), zero cash, zero interest (coverage NM), zero or
negative revenue, negative NWC businesses, negative and zero final-year FCF, WACC ≤ 0 or ≥ 100%,
g = WACC and g > WACC, negative g, extreme growth, extreme WACC, tax rate > 60%, NaN/∞/bool
inputs, net-cash peers with negative EV, loss-making peers, peers missing the chosen EBITDA basis,
mixed period types, ADR currency mismatch, analyst exclusion without a reason, stub-period
valuation dates, stale and pre-statement market data, 29 Feb anniversaries, at-the-money options,
out-of-the-money convertibles, convertibles converting at an M&A offer, acquirers with losses,
insufficient cash, negative debt plug, unbalanced sources and uses.

**Property tests (hypothesis, 150 examples each, derandomised so runs repeat exactly):** EV falls
as WACC rises; EV rises with g; scale invariance; a closed-form growing-annuity cross-check; the
implied price matches an independent **bisection oracle**; sources always equal uses with the
debt plug; accretion is exactly 0 at breakeven synergies; runs are deterministic.

**Mutation check (done once, by hand):** each of these planted bugs was caught by the suite —
symmetric tax on losses (2 failures), TV missing (1+g) (7), cash subtracted in the bridge (6), no
treasury-stock buyback (6), and interest not tax-effected in M&A (6).

## 5. Known limitations (MVP scope, documented rather than hidden)

- No NOL / tax-loss carry-forward asset (D-06): conservative for loss-makers.
- Year-end discounting only. No mid-year convention and no stub periods (D-07).
- Gordon growth is the only terminal method. The exit multiple is a cross-check, not an alternative TV.
- Market value of debt must be supplied by the user. If book value is used, it is flagged.
- P/E route in comps ignores convertibles in the per-share step (if-converted EPS, with the coupon
  added back, is not modelled). A `PE_CONVERTIBLES_IGNORED` warning is raised.
- Peer calendarisation is not implemented. Misaligned fiscal years are only flagged.
- Accretion/dilution covers a single pro forma year. There is no purchase-price allocation, so no
  goodwill or intangible amortisation. Advisory fees are treated as non-deductible in the Year-1 line.
- RSUs are added in full: no vesting conditions, no anti-dilution test.
- Options are assumed exercisable. There is no vesting split and no option-pricing (Black–Scholes) alternative.
- Floating-point arithmetic: results agree with hand calculations to ~1e-9 relative, and display rounding hides the rest.
