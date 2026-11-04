"""Canonical line-item dictionary: the only item codes DealForge accepts.

Sign rules follow D-02 and reuse the engine's own lists, so the importer and the engine can
never disagree about which items are magnitudes.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.engine.historical import MAGNITUDE_ITEMS, SIGNED_ITEMS


@dataclass(frozen=True)
class ItemDef:
    code: str
    label: str
    statement: str  # income|balance|cash_flow|equity|memo
    magnitude: bool  # True → must be ≥ 0 (D-02)
    used_by: str  # where the value is consumed


_DEFS = [
    ("revenue", "Revenue", "income", "historicals, DCF base revenue"),
    ("cogs", "Cost of goods sold (incl. embedded D&A)", "income", "historicals"),
    ("opex", "Operating expenses (incl. embedded D&A)", "income", "historicals"),
    ("ebit", "EBIT (operating profit)", "income", "historicals"),
    ("da", "Depreciation & amortisation (cash-flow statement)", "cash_flow", "historicals"),
    ("pretax_income", "Pre-tax income", "income", "historicals"),
    ("tax_expense", "Income tax expense", "income", "historicals"),
    ("net_income", "Net income", "income", "historicals"),
    ("interest_expense", "Interest expense", "income", "historicals"),
    ("reported_ebitda", "EBITDA as reported by the company", "memo", "EBITDA reconciliation"),
    ("adjusted_ebitda", "Adjusted EBITDA as reported", "memo", "EBITDA reconciliation"),
    ("cfo", "Cash flow from operations", "cash_flow", "historicals"),
    ("capex", "Capital expenditure", "cash_flow", "historicals"),
    ("accounts_receivable", "Accounts receivable", "balance", "NWC"),
    ("inventory", "Inventory", "balance", "NWC"),
    ("other_current_operating_assets", "Other operating current assets", "balance", "NWC"),
    ("accounts_payable", "Accounts payable", "balance", "NWC"),
    (
        "other_current_operating_liabilities",
        "Other operating current liabilities",
        "balance",
        "NWC",
    ),
    ("cash", "Cash and cash equivalents", "balance", "bridge"),
    ("total_debt", "Total debt (excluding convertibles and leases)", "balance", "bridge, WACC"),
    ("lease_liabilities", "Lease liabilities", "balance", "bridge (if debt-like, D-09)"),
    ("preferred_equity", "Preferred equity", "balance", "bridge, WACC"),
    ("non_controlling_interest", "Non-controlling interest", "balance", "bridge"),
    (
        "other_debt_like_claims",
        "Other debt-like claims (e.g. pension deficit)",
        "balance",
        "bridge",
    ),
    ("non_operating_assets", "Non-operating assets (e.g. equity investments)", "balance", "bridge"),
    ("total_assets", "Total assets", "balance", "balance-sheet check"),
    ("total_liabilities", "Total liabilities", "balance", "balance-sheet check"),
    ("total_equity", "Total equity", "balance", "balance-sheet check"),
    ("basic_shares", "Basic shares outstanding (same scale as money)", "equity", "value per share"),
]

EXTRA_MAGNITUDES = {
    "reported_ebitda": False,
    "adjusted_ebitda": False,
    "lease_liabilities": True,
    "preferred_equity": True,
    "non_controlling_interest": True,
    "other_debt_like_claims": True,
    "non_operating_assets": True,
    "basic_shares": True,
}


def _is_magnitude(code: str) -> bool:
    if code in MAGNITUDE_ITEMS:
        return True
    if code in SIGNED_ITEMS:
        return False
    return EXTRA_MAGNITUDES[code]


ITEMS: dict[str, ItemDef] = {
    code: ItemDef(code, label, statement, _is_magnitude(code), used_by)
    for code, label, statement, used_by in _DEFS
}

BRIDGE_ITEMS = (
    "cash",
    "total_debt",
    "lease_liabilities",
    "preferred_equity",
    "non_controlling_interest",
    "other_debt_like_claims",
    "non_operating_assets",
)
