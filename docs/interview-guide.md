# Interview guide: explaining the engine yourself

Each answer uses a number DealForge actually produces, and names the function and the test
where you can see it. Rehearse by running the named test, changing an input, and predicting the
new result *before* you run it again.

---

## 1. Why use FCFF rather than net income in a standard enterprise DCF?

**Short answer.** An enterprise DCF values the whole operating business: the claim of debt and
equity holders together. Net income only belongs to equity holders, because interest to lenders
has already been deducted. It is also an accounting number, not a cash number.

**The three problems with net income here:**
1. *Wrong claim-holder.* NI is after interest, so it is what is left for shareholders. Discount it
   and you get something closer to equity value, but by an inconsistent route.
2. *Depends on capital structure.* Two identical businesses with different debt levels have
   different NI but the same operations. FCFF is computed **before** financing
   (`compute_ufcf` has no interest parameter, and a test checks this), so it is the same for both.
3. *Not cash.* NI includes non-cash charges (D&A) and ignores cash the business must reinvest
   (CapEx, working capital). FCFF = EBIT(1−T) + D&A − CapEx − ΔNWC fixes both.

**In DealForge:** `fcf.compute_ufcf`; KA-UFCF-01: EBIT 200 → NOPAT 150 → +50 D&A − 70 CapEx − 10
ΔNWC = **120**.

**Follow-up you may get:** "Could you value equity directly?" Yes: discount free cash flow to
equity (FCFE, which is after interest and net borrowing) at the **cost of equity**. Done
consistently, it reaches the same equity value. The mistake to avoid is mixing them, for example
FCFF discounted at Ke, or FCFE at WACC.

---

## 2. Why is WACC used to discount FCFF?

**Short answer.** The discount rate must match the cash flow. FCFF is available to *all*
providers of capital, so it is discounted at the return all of them require together, weighted
by how much of the firm each one finances: the weighted average cost of capital.

**Why each piece is there:**
- **Ke** (CAPM: Rf + β × ERP) is the return equity holders need for bearing market risk.
- **Kd × (1 − T)**: interest is tax-deductible, so debt really costs less after tax. That tax
  shield is counted **once**, here, which is exactly why FCFF is computed before interest.
  Deducting interest in the cash flow *and* using after-tax Kd would double-count financing.
- **Market-value weights** (D-08): what investors could sell their claims for today, not
  historical book values. Book value of debt is allowed as an approximation and flagged
  `DEBT_AT_BOOK`.

**In DealForge:** `wacc.compute_wacc`; KA-WACC-01: Ke 4% + 1.2 × 5.5% = 10.6%;
Kd 6% × 0.75 = 4.5%; weights 80/20 → **WACC 9.38%**. With zero debt, WACC = Ke (test
`test_zero_debt_wacc_equals_cost_of_equity`).

**Follow-up:** "Why not use the company's actual borrowing rate for everything?" Because
equity is riskier than debt (it is paid last), so Ke > Kd. The engine warns
`COST_OF_EQUITY_BELOW_DEBT` if your inputs say otherwise.

---

## 3. Why add cash and subtract debt when moving from EV to equity value?

**Short answer.** EV is the value of the operating business to all claim-holders. Shareholders
are paid last. So you subtract every claim that ranks ahead of them, and add assets they own that
the operating cash flows did not value.

- **Subtract debt** (and preferred, NCI, debt-like leases, unconverted convertibles, unfunded
  pensions): lenders and these other holders must be paid before ordinary shareholders get anything.
- **Add cash**: UFCF excludes interest income on cash, so the DCF has not valued it, yet it
  belongs to shareholders. Equity-method investments are added for the same reason: their income
  sits below EBITDA.
- **The rule that keeps it consistent:** subtract a claim *if and only if* the cash flows that
  service it are inside UFCF/EBITDA. Example: consolidated EBITDA includes 100% of a
  70%-owned subsidiary, so the 30% minority interest must be deducted. Under IFRS 16, lease cost is
  outside EBITDA, so the lease liability is debt-like. If lease cost is already inside EBITDA,
  deducting the liability as well would double-count (D-09).

**In DealForge:** `bridge.equity_from_enterprise`; KA-BRIDGE-01: EV 1,613.64 − debt 300 + cash
100 − NCI 20 = **equity 1,393.64**, or 13.94 per share on 100 shares. Comps use the exact inverse
(`enterprise_from_equity`), so a peer's EV is defined the same way as the target's.

**Follow-up:** "Does buying back shares with cash change EV?" No. Cash falls and so does equity
value, by the same amount. EV is unchanged, which is why EV multiples are
capital-structure-neutral.

---

## 4. Why must terminal growth be lower than WACC?

**Short answer.** The Gordon formula is the sum of an infinite series:
UFCF_N × Σ_{k≥1} ((1+g)/(1+WACC))^k. It has a finite value only if (1+g)/(1+WACC) < 1, i.e.
**g < WACC**. At g = WACC the sum is infinite. Above it, the formula returns a *negative* number
with no economic meaning.

**Economic intuition.** g is growth *forever*. A company growing faster than its cost of capital
forever would eventually be bigger than the whole economy. Realistic long-run g is around nominal
GDP growth (the engine warns above 4%, and above the risk-free rate).

**See the sensitivity** (final UFCF 146.41, WACC 10%):

| g | TV = 146.41 × (1+g) / (10% − g) |
|---|---|
| 2.0% | 1,866.7 |
| 3.0% | 2,154.3 |
| 9.5% | 32,063.8 |
| 10.0% | **rejected**: `TERMINAL_GROWTH_GE_WACC` |

As g approaches WACC, the denominator approaches zero and TV explodes. That is why the engine
also warns when WACC − g < 1pp (`TV_SPREAD_NARROW`), and when TV is more than 75% of EV.

**In DealForge:** `dcf.terminal_value_gordon`; tests `test_ka_tv_err_01_*`,
`test_invalid_cells_are_marked_not_numbers` (a sensitivity cell with g ≥ WACC shows INVALID, not
a number).

---

## 5. Why can a deal be EPS-dilutive even when it creates strategic value?

**Short answer.** EPS is a one-year accounting ratio. Value is the present value of *all* future
cash flows net of what you paid. Things that create value can depress next year's EPS.

**The P/E mechanic (all-stock deal).** You issue shares priced at *your* P/E to buy earnings at
the *target's* P/E. If the target's P/E at the offer is higher than yours, you get fewer
earnings per new share issued than your existing shares earn, so EPS falls.

**In DealForge:** KA-MA-01: the acquirer trades at 10x (EPS 5.00). The target at a 30% premium
costs 13x (1,300 for 100 of earnings). All stock: 26 new shares, PF NI 600 on 126 shares →
EPS **4.76, −4.76% dilutive**. Breakeven synergies = (5.00 × 126 − 600)/0.75 = **40 pre-tax**.
KA-MA-02 adds exactly 40 and shows 0.00%.

**Why the deal may still be right:**
- The target grows faster, so year-1 EPS understates later years.
- Synergies phase in over time (`synergy_phase_in_year1`), and integration costs hit year 1
  (D-13 shows run-rate and Year-1 EPS separately).
- Strategic value (market access, capabilities) does not appear in next year's earnings.

**The reverse trap:** a cash deal funded with cheap after-tax debt is often *accretive* (KA-MA-03:
+6.33%) even when the price is too high. EPS charges debt at its after-tax interest rate but
charges nothing for the risk equity holders take on. Accretion is not value creation. Compare
the price paid with the DCF value plus the present value of synergies.

---

## 6. Why can a company report rising profits but deteriorating cash flow?

**Short answer.** Profit is recognised when earned (accrual accounting). Cash arrives when
customers pay. Growth, or aggressive revenue recognition, ties cash up in receivables and
inventory. Investment spending (CapEx) reduces cash but only reaches the P&L slowly, through
depreciation.

**In DealForge:** KA-HIST-02 (`test_historical.py`):

| | FY2023 | FY2024 |
|---|---|---|
| Net income | 105.0 | **127.5** (up 21%) |
| Receivables + inventory | 200 | 310 |
| ΔNWC | — | **+100** (cash absorbed) |
| CFO − CapEx | 110.0 | **30.0** |
| FCF conversion (FCF / NI) | 105% | 24% |

The engine raises `EARNINGS_CASH_DIVERGENCE`: "net income rose … while free cash flow fell …
Working capital absorbed 100.00 of cash this year."

**Common causes to name:** receivables growing faster than sales (looser credit terms or channel
stuffing); inventory build; a CapEx cycle; capitalising costs that used to be expensed; non-cash
gains (asset revaluations, disposal gains) in net income.

**Why it matters for valuation:** the DCF uses cash (UFCF), not profit. A forecast that keeps NWC
at a high % of revenue (`nwc_pct_revenue`) permanently lowers UFCF. A step change in NWC % is
flagged `NWC_STEP_CHANGE`.

---

## How to practise

1. `pytest tests/engine/test_mna.py::test_ka_ma_01_all_stock_buying_higher_pe_is_dilutive -q`
2. Change the premium to 0% in the test's inputs. Predict: target P/E 10x = acquirer P/E 10x, so
   accretion is about 0%. Run it.
3. Repeat for WACC, g, the bridge items and NWC. If your prediction is wrong, find out why
   before moving on.
