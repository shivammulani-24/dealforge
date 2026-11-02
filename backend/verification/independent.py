"""Independent re-computation of DealForge's core calculations.

This module deliberately does NOT import ``app.engine`` (a test enforces it). It recomputes the
same finance from first principles with ``fractions.Fraction`` — exact rational arithmetic, so
there is no floating-point rounding at all — and renders every intermediate step to Markdown.
``tests/engine/test_independent_verification.py`` then checks the engine's float results against
these exact values, and checks that ``docs/verification/independent-verification.md`` is
up to date with this script.

Regenerate the document with::

    python -m verification.independent > ../docs/verification/independent-verification.md
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction as F

# ----------------------------------------------------------------------------- formatting


def n(x: F, dp: int = 4) -> str:
    """Fixed-point rendering of an exact fraction (round half away from zero)."""
    scaled = abs(x) * 10**dp
    q, r = divmod(scaled.numerator, scaled.denominator)
    if 2 * r >= scaled.denominator:
        q += 1
    s = f"{q:,}" if dp == 0 else f"{q // 10**dp:,}.{q % 10**dp:0{dp}d}"
    return ("-" if x < 0 and q else "") + s


def pct(x: F, dp: int = 4) -> str:
    return n(x * 100, dp) + "%"


# ----------------------------------------------------------------------------- KA-DCF-03 inputs
# A deliberately non-trivial synthetic case: varying drivers, CAPM WACC with market weights,
# debt-like leases, NCI, pension deficit, non-operating assets, options and RSUs.

BASE_REVENUE = F(2000)
BASE_NWC = F(300)  # 15.0% of revenue
GROWTH = [F("0.08"), F("0.07"), F("0.06"), F("0.05"), F("0.04")]
EBITDA_MARGIN = [F("0.18"), F("0.185"), F("0.19"), F("0.195"), F("0.20")]
DA_PCT = [F("0.04")] * 5
CAPEX_PCT = [F("0.05"), F("0.05"), F("0.045"), F("0.045"), F("0.045")]
NWC_PCT = [F("0.15")] * 5
TAX = F("0.25")
TERMINAL_G = F("0.025")

RF, BETA, ERP, KD, SIZE = F("0.045"), F("1.1"), F("0.055"), F("0.07"), F(0)
PRICE = F(20)  # market price on the market-data date
BASIC = F(100)
OPTIONS = [(F(5), F(12))]  # (count, strike)
RSUS = F(1)

CASH, DEBT, LEASES, PREF, NCI = F(150), F(400), F(50), F(0), F(30)
PENSION_DEFICIT, NON_OP = F(20), F(40)


@dataclass
class DcfCheck:
    rows: list[dict[str, F]]
    ke: F
    kd_at: F
    e_mkt: F
    d_mkt: F
    diluted_mkt: F
    wacc: F
    tv: F
    pv_tv: F
    sum_pv: F
    ev: F
    equity_pre: F
    per_share: F
    diluted_implied: F
    tv_share: F
    exit_multiple: F


def tsm_shares(price: F) -> F:
    return BASIC + RSUS + sum((c * (1 - k / price) for c, k in OPTIONS if k < price), F(0))


def dcf_check() -> DcfCheck:
    rows: list[dict[str, F]] = []
    rev, nwc_prev = BASE_REVENUE, BASE_NWC
    for t in range(5):
        rev = rev * (1 + GROWTH[t])
        ebitda = rev * EBITDA_MARGIN[t]
        da = rev * DA_PCT[t]
        ebit = ebitda - da
        tax = max(ebit, F(0)) * TAX
        nopat = ebit - tax
        capex = rev * CAPEX_PCT[t]
        nwc = rev * NWC_PCT[t]
        dnwc = nwc - nwc_prev
        ufcf = nopat + da - capex - dnwc
        rows.append(
            {
                "t": F(t + 1),
                "revenue": rev,
                "ebitda": ebitda,
                "da": da,
                "ebit": ebit,
                "tax": tax,
                "nopat": nopat,
                "capex": capex,
                "nwc": nwc,
                "dnwc": dnwc,
                "ufcf": ufcf,
            }
        )
        nwc_prev = nwc

    ke = RF + BETA * ERP + SIZE
    kd_at = KD * (1 - TAX)
    diluted_mkt = tsm_shares(PRICE)
    e_mkt = PRICE * diluted_mkt
    d_mkt = DEBT + LEASES  # leases are debt-like (EBITDA before lease cost)
    v = e_mkt + d_mkt + PREF
    wacc = e_mkt / v * ke + d_mkt / v * kd_at

    for r in rows:
        r["df"] = 1 / (1 + wacc) ** int(r["t"])
        r["pv"] = r["ufcf"] * r["df"]
    sum_pv = sum((r["pv"] for r in rows), F(0))
    tv = rows[-1]["ufcf"] * (1 + TERMINAL_G) / (wacc - TERMINAL_G)
    pv_tv = tv * rows[-1]["df"]
    ev = sum_pv + pv_tv
    equity_pre = ev - DEBT - LEASES - PREF - NCI - PENSION_DEFICIT + CASH + NON_OP

    # Implied price: options are in the money iff strike < P. Try "none ITM", then "all ITM".
    p_none = equity_pre / (BASIC + RSUS)
    if all(k >= p_none for _, k in OPTIONS):
        per_share = p_none
    else:
        num = equity_pre + sum((c * k for c, k in OPTIONS), F(0))
        den = BASIC + RSUS + sum((c for c, _ in OPTIONS), F(0))
        per_share = num / den
        assert all(k < per_share for _, k in OPTIONS)
    diluted_implied = tsm_shares(per_share)
    assert equity_pre / diluted_implied == per_share  # exact TSM self-consistency

    return DcfCheck(
        rows,
        ke,
        kd_at,
        e_mkt,
        d_mkt,
        diluted_mkt,
        wacc,
        tv,
        pv_tv,
        sum_pv,
        ev,
        equity_pre,
        per_share,
        diluted_implied,
        pv_tv / ev,
        tv / rows[-1]["ebitda"],
    )


# ----------------------------------------------------------------------------- KA-MA-01 / 02


@dataclass
class DealCheck:
    offer: F
    equity_price: F
    new_shares: F
    pf_ni: F
    pf_shares: F
    eps_a: F
    pf_eps: F
    accretion: F
    breakeven: F


def all_stock_check(synergies: F) -> DealCheck:
    p_a, s_a, ni_a = F(50), F(100), F(500)
    p_t, s_t, ni_t, premium, tax = F(20), F(50), F(100), F("0.30"), F("0.25")
    offer = p_t * (1 + premium)
    equity_price = offer * s_t
    new_shares = equity_price / p_a
    pf_ni_ex = ni_a + ni_t
    pf_ni = pf_ni_ex + synergies * (1 - tax)
    pf_shares = s_a + new_shares
    eps_a = ni_a / s_a
    pf_eps = pf_ni / pf_shares
    breakeven = (eps_a * pf_shares - pf_ni_ex) / (1 - tax)
    return DealCheck(
        offer,
        equity_price,
        new_shares,
        pf_ni,
        pf_shares,
        eps_a,
        pf_eps,
        pf_eps / eps_a - 1,
        breakeven,
    )


# ----------------------------------------------------------------------------- report


def render() -> str:
    d = dcf_check()
    L: list[str] = []
    w = L.append
    w("# Independent verification (generated)\n")
    w("> Generated by `backend/verification/independent.py` with exact rational arithmetic")
    w("> (`fractions.Fraction`), without importing the engine. Do not edit by hand —")
    w("> `test_independent_verification.py` fails if this file is stale, and checks the engine's")
    w("> results against every figure below (relative tolerance 1e-12). Values shown to 4 dp;")
    w("> currency in millions; synthetic data.\n")

    w("## 1. Complete DCF — KA-DCF-03\n")
    w("### 1.1 Inputs\n")
    w("| Input | Value |\n|---|---|")
    w(f"| Base (LFY) revenue | {n(BASE_REVENUE)} |")
    w(
        f"| Base (LFY) operating NWC | {n(BASE_NWC)} ({pct(BASE_NWC / BASE_REVENUE, 1)} of revenue) |"
    )
    w(f"| Valuation tax rate | {pct(TAX, 1)} |")
    w(f"| Terminal growth g | {pct(TERMINAL_G, 1)} |")
    w(
        f"| Rf / β / ERP / size premium | {pct(RF, 1)} / {n(BETA, 2)} / {pct(ERP, 1)} / {pct(SIZE, 1)} |"
    )
    w(f"| Pre-tax cost of debt | {pct(KD, 1)} |")
    w(f"| Share price (market-data date) | {n(PRICE, 2)} |")
    w(f"| Basic shares / RSUs | {n(BASIC, 1)} / {n(RSUS, 1)} |")
    w(f"| Options | {', '.join(f'{n(c, 1)}m @ {n(k, 2)}' for c, k in OPTIONS)} |")
    w(f"| Debt / debt-like leases / preferred | {n(DEBT)} / {n(LEASES)} / {n(PREF)} |")
    w(f"| NCI / pension deficit | {n(NCI)} / {n(PENSION_DEFICIT)} |")
    w(f"| Cash / non-operating assets | {n(CASH)} / {n(NON_OP)} |\n")
    w("| Driver | Y1 | Y2 | Y3 | Y4 | Y5 |\n|---|---|---|---|---|---|")
    for label, xs in (
        ("Revenue growth", GROWTH),
        ("EBITDA margin", EBITDA_MARGIN),
        ("D&A % revenue", DA_PCT),
        ("CapEx % revenue", CAPEX_PCT),
        ("NWC % revenue", NWC_PCT),
    ):
        w(f"| {label} | " + " | ".join(pct(x, 1) for x in xs) + " |")

    w("\n### 1.2 Operating forecast and unlevered free cash flow\n")
    w("Revenue_t = Revenue_{t−1} × (1 + g_t); EBITDA, D&A, CapEx and NWC are % of revenue;")
    w("EBIT = EBITDA − D&A; tax = max(EBIT, 0) × 25%; UFCF = NOPAT + D&A − CapEx − ΔNWC.\n")
    w("| | Y1 | Y2 | Y3 | Y4 | Y5 |\n|---|---|---|---|---|---|")
    for key, label in (
        ("revenue", "Revenue"),
        ("ebitda", "EBITDA"),
        ("da", "D&A"),
        ("ebit", "EBIT"),
        ("tax", "Taxes on EBIT"),
        ("nopat", "NOPAT"),
        ("capex", "CapEx"),
        ("nwc", "NWC"),
        ("dnwc", "ΔNWC"),
        ("ufcf", "**UFCF**"),
    ):
        w(f"| {label} | " + " | ".join(n(r[key]) for r in d.rows) + " |")
    r1 = d.rows[0]
    w(
        f"\nWorked Y1: revenue 2,000 × 1.08 = {n(r1['revenue'])}; EBITDA × 18% = {n(r1['ebitda'])};"
        f" D&A × 4% = {n(r1['da'])}; EBIT = {n(r1['ebit'])}; NOPAT = {n(r1['ebit'])} × 0.75 ="
        f" {n(r1['nopat'])}; CapEx × 5% = {n(r1['capex'])}; NWC × 15% = {n(r1['nwc'])}, so"
        f" ΔNWC = {n(r1['nwc'])} − 300 = {n(r1['dnwc'])}; UFCF = {n(r1['nopat'])} + {n(r1['da'])}"
        f" − {n(r1['capex'])} − {n(r1['dnwc'])} = **{n(r1['ufcf'])}**.\n"
    )

    w("### 1.3 WACC (market-value weights)\n")
    w(
        f"- Diluted shares at the market price 20 (TSM): 100 + 1 RSU + 5 × (1 − 12/20) ="
        f" {n(d.diluted_mkt)}"
    )
    w(
        f"- E = 20 × {n(d.diluted_mkt)} = {n(d.e_mkt)}; D = debt 400 + leases 50 = {n(d.d_mkt)};"
        f" V = {n(d.e_mkt + d.d_mkt)}"
    )
    w(f"- Ke = 4.5% + 1.1 × 5.5% = {pct(d.ke)}; Kd after tax = 7% × 0.75 = {pct(d.kd_at)}")
    w(
        f"- WACC = {n(d.e_mkt)}/{n(d.e_mkt + d.d_mkt)} × {pct(d.ke)} + {n(d.d_mkt)}/"
        f"{n(d.e_mkt + d.d_mkt)} × {pct(d.kd_at)} = **{pct(d.wacc, 6)}**\n"
    )

    w("### 1.4 Discounting, terminal value and enterprise value\n")
    w("| | Y1 | Y2 | Y3 | Y4 | Y5 |\n|---|---|---|---|---|---|")
    w("| Discount factor 1/(1+WACC)^t | " + " | ".join(n(r["df"], 6) for r in d.rows) + " |")
    w("| PV of UFCF | " + " | ".join(n(r["pv"]) for r in d.rows) + " |")
    w(f"\n- Σ PV(UFCF) = {n(d.sum_pv)}")
    w(
        f"- TV = UFCF_5 × (1 + g) / (WACC − g) = {n(d.rows[-1]['ufcf'])} × 1.025 /"
        f" ({pct(d.wacc)} − 2.5%) = {n(d.tv)}"
    )
    w(f"- PV(TV) = {n(d.tv)} × {n(d.rows[-1]['df'], 6)} = {n(d.pv_tv)}")
    w(
        f"- **EV = {n(d.sum_pv)} + {n(d.pv_tv)} = {n(d.ev)}**; TV share {pct(d.tv_share, 2)};"
        f" implied exit multiple {n(d.exit_multiple, 2)}x EBITDA_5\n"
    )

    w("### 1.5 Enterprise value → equity value\n")
    w("| Item | Amount |\n|---|---|")
    for label, amt in (
        ("Enterprise value", d.ev),
        ("Less: debt", -DEBT),
        ("Less: lease liabilities (debt-like)", -LEASES),
        ("Less: preferred equity", -PREF),
        ("Less: non-controlling interest", -NCI),
        ("Less: pension deficit", -PENSION_DEFICIT),
        ("Plus: cash", CASH),
        ("Plus: non-operating assets", NON_OP),
        ("**Equity value**", d.equity_pre),
    ):
        w(f"| {label} | {n(amt)} |")

    w("\n### 1.6 Diluted shares and implied value per share\n")
    p_none = d.equity_pre / (BASIC + RSUS)
    w(
        f"- Without options: {n(d.equity_pre)} / 101 = {n(p_none)} > strike 12, so the options are"
        " in the money at the implied value — the share count depends on the answer (circular)."
    )
    w(
        f"- Closed form with the options exercised: P = (equity + 5 × 12) / (100 + 1 + 5) ="
        f" ({n(d.equity_pre)} + 60) / 106 = **{n(d.per_share)}**"
    )
    w(
        f"- Check by TSM at that price: 101 + 5 × (1 − 12/{n(d.per_share)}) = {n(d.diluted_implied)}"
        f" diluted shares; {n(d.equity_pre)} / {n(d.diluted_implied)} = {n(d.per_share)} (exact).\n"
    )

    w("## 2. WACC — KA-WACC-01\n")
    ke = F("0.04") + F("1.2") * F("0.055")
    wacc = F(1000, 1250) * ke + F(250, 1250) * F("0.06") * F("0.75")
    w(
        f"Ke = 4% + 1.2 × 5.5% = {pct(ke)}; Kd(1 − T) = 6% × 0.75 = 4.5000%;"
        f" WACC = 0.8 × {pct(ke)} + 0.2 × 4.5000% = **{pct(wacc)}**\n"
    )

    w("## 3. Bridge — KA-BRIDGE-01\n")
    ev = F(100, 1) / F("1.1") * F("17.75")
    eq = ev - 300 + 100 - 20
    w(
        f"EV = (100/1.1) × (5 + 12.75) = {n(ev, 6)}; equity = EV − 300 + 100 − 20 ="
        f" **{n(eq, 6)}**; per share on 100 shares = **{n(eq / 100, 6)}**\n"
    )

    w("## 4. Diluted shares — KA-TSM-01 and KA-SH-02\n")
    tsm = 100 + F(4) * (1 - F(30, 50)) + 0 + 1
    w(
        f"At price 50: 100 basic + 4 × (1 − 30/50) + 0 (strike 60 out of the money) + 1 RSU ="
        f" **{n(tsm)}**\n"
    )
    p = F(1050, 110)
    w(
        f"Implied, equity 1,000, basic 100, options 10 @ 5: P = 1,050 / 110 = **{n(p, 6)}**;"
        f" TSM shares 100 + 10 × (1 − 5/P) = {n(100 + 10 * (1 - 5 / p), 6)};"
        f" 1,000 / that = {n(1000 / (100 + 10 * (1 - 5 / p)), 6)}\n"
    )

    w("## 5. All-stock accretion/dilution — KA-MA-01 and KA-MA-02\n")
    for label, syn in (("No synergies", F(0)), ("Pre-tax synergies = breakeven 40", F(40))):
        x = all_stock_check(syn)
        w(
            f"**{label}:** offer 20 × 1.30 = {n(x.offer, 2)}; equity price × 50 shares ="
            f" {n(x.equity_price, 2)}; new shares = {n(x.equity_price, 2)} / 50 ="
            f" {n(x.new_shares, 2)}; PF NI = 500 + 100 + {n(syn, 0)} × 0.75 = {n(x.pf_ni, 2)};"
            f" PF shares {n(x.pf_shares, 2)}; PF EPS = {n(x.pf_eps, 6)} vs 5.000000 →"
            f" **{pct(x.accretion, 4)}**; breakeven synergies = (5 × {n(x.pf_shares, 0)} − 600) /"
            f" 0.75 = {n(x.breakeven, 2)}\n"
        )
    return "\n".join(L)


if __name__ == "__main__":
    print(render(), end="")
