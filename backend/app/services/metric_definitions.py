"""B10: what each derived historical metric means and which line items it uses, so the UI can
show a derived value's formula and its components' provenance without computing anything."""

from __future__ import annotations

from typing import Any

from app.engine.historical import LIQUIDITY_FORMULAS

NWC_ITEMS = [
    "accounts_receivable",
    "inventory",
    "other_current_operating_assets",
    "accounts_payable",
    "other_current_operating_liabilities",
]

_DEFS: dict[str, tuple[str, list[str], str]] = {
    # metric: (formula, items, not-meaningful rule)
    "revenue_growth": (
        "revenue_t / revenue_(t-1) − 1",
        ["revenue"],
        "NM for the first year, after a gap, or when prior revenue ≤ 0",
    ),
    "gross_profit": ("revenue − cogs", ["revenue", "cogs"], "—"),
    "gross_margin": ("(revenue − cogs) / revenue", ["revenue", "cogs"], "NM when revenue ≤ 0"),
    "ebitda": ("ebit + da (standardised, D-03)", ["ebit", "da"], "—"),
    "ebitda_margin": ("(ebit + da) / revenue", ["ebit", "da", "revenue"], "NM when revenue ≤ 0"),
    "ebit_margin": ("ebit / revenue", ["ebit", "revenue"], "NM when revenue ≤ 0"),
    "net_margin": ("net_income / revenue", ["net_income", "revenue"], "NM when revenue ≤ 0"),
    "effective_tax_rate": (
        "tax_expense / pretax_income",
        ["tax_expense", "pretax_income"],
        "NM when pre-tax income ≤ 0",
    ),
    "simple_fcf": ("cfo − capex", ["cfo", "capex"], "—"),
    "fcf_conversion": (
        "(cfo − capex) / net_income",
        ["cfo", "capex", "net_income"],
        "NM when net income ≤ 0",
    ),
    "capex_pct_revenue": ("capex / revenue", ["capex", "revenue"], "NM when revenue ≤ 0"),
    "da_pct_revenue": ("da / revenue", ["da", "revenue"], "NM when revenue ≤ 0"),
    "capex_to_da": ("capex / da", ["capex", "da"], "NM when D&A ≤ 0"),
    "nwc": (
        "AR + inventory + other op. current assets − AP − other op. current liabilities "
        "(operating NWC)",
        NWC_ITEMS,
        "—; the two 'other' items are optional and disclosed",
    ),
    "nwc_pct_revenue": ("operating NWC / revenue", [*NWC_ITEMS, "revenue"], "NM when revenue ≤ 0"),
    "change_in_nwc": ("NWC_t − NWC_(t-1)", NWC_ITEMS, "NM for the first year or after a gap"),
    "net_debt": ("total_debt − cash", ["total_debt", "cash"], "—"),
    "net_debt_to_ebitda": (
        "(total_debt − cash) / (ebit + da)",
        ["total_debt", "cash", "ebit", "da"],
        "NM when EBITDA ≤ 0",
    ),
    "interest_coverage": (
        "ebit / interest_expense",
        ["ebit", "interest_expense"],
        "NM when interest expense ≤ 0",
    ),
}
for _metric, (_formula, _num, _den) in LIQUIDITY_FORMULAS.items():
    _DEFS[_metric] = (
        _formula,
        [*_num, *_den],
        "NM when total current liabilities are 0; missing if any input is missing",
    )


def metric_definitions() -> dict[str, dict[str, Any]]:
    return {
        m: {"formula": f, "items": items, "not_meaningful": nm, "basis": "derived"}
        for m, (f, items, nm) in _DEFS.items()
    }
