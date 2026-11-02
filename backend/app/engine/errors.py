"""Issues, issue codes and exceptions used throughout the engine.

Design
------
* An **error** means "no number can be produced" — the engine raises :class:`EngineError`.
* A **warning** means "a number was produced, but an analyst should look at it" — warnings are
  returned inside results, never printed or swallowed.
* An **info** issue documents a convention that was applied (e.g. "debt valued at book").

Every issue has a stable machine-readable ``code`` (used by the API, UI and tests) and a
human-readable ``message`` that states the numbers involved.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    message: str
    severity: Severity
    field: str | None = None


class Code:
    """Stable issue codes. Grouped by module; values equal names for readability in JSON."""

    # Generic input validation
    MISSING_INPUT = "MISSING_INPUT"
    NON_FINITE_INPUT = "NON_FINITE_INPUT"
    INVALID_TYPE = "INVALID_TYPE"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    SIGN_CONVENTION = "SIGN_CONVENTION"

    # Dates (D-07)
    STUB_PERIOD_NOT_SUPPORTED = "STUB_PERIOD_NOT_SUPPORTED"
    MARKET_DATA_DATE_DIFFERS = "MARKET_DATA_DATE_DIFFERS"
    MARKET_DATA_STALE = "MARKET_DATA_STALE"
    MARKET_DATA_BEFORE_STATEMENTS = "MARKET_DATA_BEFORE_STATEMENTS"

    # Historical analysis
    PERIODS_NOT_CONTIGUOUS = "PERIODS_NOT_CONTIGUOUS"
    DUPLICATE_PERIOD = "DUPLICATE_PERIOD"
    NO_PERIODS = "NO_PERIODS"
    EBIT_RECONCILIATION = "EBIT_RECONCILIATION"
    NET_INCOME_RECONCILIATION = "NET_INCOME_RECONCILIATION"
    BALANCE_SHEET_IMBALANCE = "BALANCE_SHEET_IMBALANCE"
    UNUSUAL_TAX_RATE = "UNUSUAL_TAX_RATE"
    EARNINGS_CASH_DIVERGENCE = "EARNINGS_CASH_DIVERGENCE"
    NWC_PARTIAL = "NWC_PARTIAL"

    # EBITDA definitions (D-03)
    REPORTED_VS_STANDARDIZED_EBITDA = "REPORTED_VS_STANDARDIZED_EBITDA"
    ADJUSTED_EBITDA_UNRECONCILED = "ADJUSTED_EBITDA_UNRECONCILED"
    ADJUSTMENTS_NOT_DISCLOSED = "ADJUSTMENTS_NOT_DISCLOSED"
    ADJUSTMENTS_WITHOUT_ADJUSTED = "ADJUSTMENTS_WITHOUT_ADJUSTED"

    # Forecast / UFCF
    HORIZON_NOT_SUPPORTED = "HORIZON_NOT_SUPPORTED"
    EXTREME_GROWTH = "EXTREME_GROWTH"
    NEGATIVE_EBITDA_MARGIN = "NEGATIVE_EBITDA_MARGIN"
    CAPEX_BELOW_DA_TERMINAL = "CAPEX_BELOW_DA_TERMINAL"
    NWC_STEP_CHANGE = "NWC_STEP_CHANGE"
    NEGATIVE_EBIT_NO_TAX_CREDIT = "NEGATIVE_EBIT_NO_TAX_CREDIT"
    NEGATIVE_UFCF = "NEGATIVE_UFCF"

    # WACC
    INVALID_WACC = "INVALID_WACC"
    EXTREME_WACC = "EXTREME_WACC"
    WACC_OVERRIDDEN = "WACC_OVERRIDDEN"
    DEBT_AT_BOOK = "DEBT_AT_BOOK"
    TARGET_STRUCTURE_USED = "TARGET_STRUCTURE_USED"
    COST_OF_EQUITY_BELOW_DEBT = "COST_OF_EQUITY_BELOW_DEBT"
    UNUSUAL_BETA = "UNUSUAL_BETA"
    UNUSUAL_ERP = "UNUSUAL_ERP"
    UNUSUAL_RISK_FREE = "UNUSUAL_RISK_FREE"
    SIZE_PREMIUM_APPLIED = "SIZE_PREMIUM_APPLIED"

    # Terminal value / DCF
    TERMINAL_GROWTH_GE_WACC = "TERMINAL_GROWTH_GE_WACC"
    TERMINAL_FCF_NON_POSITIVE = "TERMINAL_FCF_NON_POSITIVE"
    TV_SPREAD_NARROW = "TV_SPREAD_NARROW"
    TERMINAL_GROWTH_HIGH = "TERMINAL_GROWTH_HIGH"
    TERMINAL_GROWTH_ABOVE_RF = "TERMINAL_GROWTH_ABOVE_RF"
    TERMINAL_GROWTH_NEGATIVE = "TERMINAL_GROWTH_NEGATIVE"
    TV_SHARE_HIGH = "TV_SHARE_HIGH"
    TV_MULTIPLE_INCONSISTENT = "TV_MULTIPLE_INCONSISTENT"
    ENTERPRISE_VALUE_NON_POSITIVE = "ENTERPRISE_VALUE_NON_POSITIVE"

    # Bridge / shares (D-09, D-10)
    EQUITY_VALUE_NON_POSITIVE = "EQUITY_VALUE_NON_POSITIVE"
    LEASES_EXCLUDED = "LEASES_EXCLUDED"
    CONVERTIBLE_CONVERTED = "CONVERTIBLE_CONVERTED"
    DILUTION_SOLVED = "DILUTION_SOLVED"

    # Comps (D-11)
    PERIOD_TYPE_MISMATCH = "PERIOD_TYPE_MISMATCH"
    FISCAL_PERIOD_MISALIGNED = "FISCAL_PERIOD_MISALIGNED"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    EXCLUSION_REASON_REQUIRED = "EXCLUSION_REASON_REQUIRED"
    POTENTIAL_OUTLIER = "POTENTIAL_OUTLIER"
    LOW_PEER_COUNT = "LOW_PEER_COUNT"
    NO_VALID_PEERS = "NO_VALID_PEERS"
    TARGET_METRIC_NOT_MEANINGFUL = "TARGET_METRIC_NOT_MEANINGFUL"
    PE_CONVERTIBLES_IGNORED = "PE_CONVERTIBLES_IGNORED"

    # Sensitivity
    BASE_NOT_IN_AXIS = "BASE_NOT_IN_AXIS"
    INVALID_AXIS = "INVALID_AXIS"

    # M&A
    SU_IMBALANCE = "SU_IMBALANCE"
    INSUFFICIENT_CASH = "INSUFFICIENT_CASH"
    MIX_INVALID = "MIX_INVALID"
    UNUSUAL_PREMIUM = "UNUSUAL_PREMIUM"
    HIGH_PRO_FORMA_LEVERAGE = "HIGH_PRO_FORMA_LEVERAGE"
    ACQUIRER_EPS_NON_POSITIVE = "ACQUIRER_EPS_NON_POSITIVE"
    NEGATIVE_DEBT_PLUG = "NEGATIVE_DEBT_PLUG"

    # Scope
    FINANCIAL_INSTITUTION_NOT_SUPPORTED = "FINANCIAL_INSTITUTION_NOT_SUPPORTED"


class EngineError(Exception):
    """Raised when inputs are invalid; carries every error found, not just the first."""

    def __init__(self, issues: Iterable[Issue]) -> None:
        self.issues: tuple[Issue, ...] = tuple(issues)
        if not self.issues:
            raise ValueError("EngineError requires at least one issue")
        super().__init__("; ".join(f"[{i.code}] {i.message}" for i in self.issues))

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(i.code for i in self.issues)


class MissingInputError(EngineError):
    """A required input was ``None``. Missing data is never replaced with zero."""


def error(code: str, message: str, field: str | None = None) -> Issue:
    return Issue(code, message, Severity.ERROR, field)


def warning(code: str, message: str, field: str | None = None) -> Issue:
    return Issue(code, message, Severity.WARNING, field)


def info(code: str, message: str, field: str | None = None) -> Issue:
    return Issue(code, message, Severity.INFO, field)


def dedupe(issues: Iterable[Issue]) -> tuple[Issue, ...]:
    """Remove exact duplicates while keeping first-seen order (deterministic)."""
    seen: set[Issue] = set()
    out: list[Issue] = []
    for i in issues:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return tuple(out)
