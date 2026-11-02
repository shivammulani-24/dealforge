"""End-to-end DCF valuation: forecast → UFCF → WACC → TV → EV → equity → value per share.

This orchestrator only wires the small, separately tested functions together; it contains no
new formulas. Its output records every intermediate figure, all issues, the engine version
and a fingerprint of the inputs, so a run is fully auditable and reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass

from .bridge import BridgeInputs, BridgeResult, equity_from_enterprise
from .dates import DateSchedule, ValuationDates, build_schedule
from .dcf import (
    EnterpriseValue,
    TerminalValue,
    discount_cash_flows,
    implied_exit_multiple,
    terminal_value_gordon,
)
from .errors import Code, Issue, dedupe, warning
from .fcf import UfcfLine, forecast_ufcf, validate_tax_rate
from .forecast import HORIZON_YEARS, Forecast, ForecastInputs, build_forecast
from .hashing import fingerprint
from .metrics import Metric, missing, safe_ratio
from .shares import (
    ImpliedPerShare,
    ShareCapitalInputs,
    diluted_shares_at_price,
    implied_value_per_share,
)
from .validation import Checker
from .version import ENGINE_VERSION
from .wacc import (
    CapitalStructure,
    WaccAssumptions,
    WaccResult,
    compute_wacc,
    validate_discount_rate,
    wacc_override_issue,
)


@dataclass(frozen=True, slots=True)
class DcfInputs:
    dates: ValuationDates
    forecast: ForecastInputs
    tax_rate: float  # normalised valuation tax rate (D-05), used for UFCF and after-tax Kd
    terminal_growth: float
    bridge: BridgeInputs
    share_capital: ShareCapitalInputs
    current_share_price: float | None  # on dates.market_data_date
    wacc_assumptions: WaccAssumptions | None
    wacc_override: float | None
    is_financial_institution: bool
    peer_ev_ebitda_range: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class DcfResult:
    engine_version: str
    input_hash: str
    schedule: DateSchedule
    forecast: Forecast
    ufcf: tuple[UfcfLine, ...]
    wacc_build: WaccResult | None
    wacc: float
    terminal: TerminalValue
    valuation: EnterpriseValue
    implied_exit_multiple: Metric
    bridge: BridgeResult
    per_share: ImpliedPerShare
    current_share_price: float | None
    upside_vs_market: Metric
    issues: tuple[Issue, ...]

    @property
    def enterprise_value(self) -> float:
        return self.valuation.enterprise_value

    @property
    def equity_value(self) -> float:
        return self.per_share.equity_value_to_common

    @property
    def value_per_share(self) -> float:
        return self.per_share.value_per_share


def market_capital_structure(inp: DcfInputs) -> CapitalStructure:
    """Market values on the market-data date (D-08): E from price × diluted shares; D includes
    leases only if they are debt-like (D-09) and unconverted convertibles at face."""
    assert inp.current_share_price is not None
    dil = diluted_shares_at_price(inp.share_capital, inp.current_share_price)
    b = inp.bridge
    debt = b.total_debt + (b.lease_liabilities if b.include_leases_in_debt else 0.0)
    debt += dil.unconverted_face
    return CapitalStructure(
        equity_value=inp.current_share_price * dil.diluted_shares,
        debt_value=debt,
        preferred_value=b.preferred_equity,
    )


def run_dcf(inp: DcfInputs) -> DcfResult:
    c = Checker()
    if inp.is_financial_institution:
        c.error(
            Code.FINANCIAL_INSTITUTION_NOT_SUPPORTED,
            "Banks and insurers are not valued with an unlevered DCF: debt is part of their "
            "operations, so FCFF and EV are not meaningful. Use P/BV or a dividend model (D-17).",
        )
    validate_tax_rate(c, inp.tax_rate)
    if (inp.wacc_assumptions is None) == (inp.wacc_override is None):
        c.error(
            Code.MISSING_INPUT if inp.wacc_assumptions is None else Code.INVALID_TYPE,
            "Provide exactly one of wacc_assumptions (CAPM build-up) or wacc_override.",
            "wacc",
        )
    if inp.wacc_assumptions is not None or inp.current_share_price is not None:
        c.positive("current_share_price", inp.current_share_price)
    if inp.wacc_override is not None:
        validate_discount_rate(c, inp.wacc_override, "wacc_override")
    c.raise_if_errors()

    issues: list[Issue] = list(c.warnings())
    schedule = build_schedule(inp.dates, HORIZON_YEARS)
    issues.extend(schedule.issues)

    forecast = build_forecast(inp.forecast)
    issues.extend(forecast.issues)
    ufcf = forecast_ufcf(forecast, inp.tax_rate)
    for line in ufcf:
        issues.extend(line.issues)

    wacc_build: WaccResult | None = None
    rf: float | None = None
    if inp.wacc_assumptions is not None:
        wacc_build = compute_wacc(inp.wacc_assumptions, market_capital_structure(inp), inp.tax_rate)
        wacc = wacc_build.wacc
        rf = inp.wacc_assumptions.risk_free_rate
        issues.extend(wacc_build.issues)
    else:
        assert inp.wacc_override is not None
        wacc = inp.wacc_override
        issues.append(wacc_override_issue(wacc))

    terminal = terminal_value_gordon(ufcf[-1].ufcf, wacc, inp.terminal_growth, risk_free_rate=rf)
    issues.extend(terminal.issues)
    valuation = discount_cash_flows([u.ufcf for u in ufcf], wacc, terminal.value)
    issues.extend(valuation.issues)

    exit_mult = implied_exit_multiple(terminal.value, forecast.years[-1].ebitda)
    if inp.peer_ev_ebitda_range is not None and exit_mult.is_ok and exit_mult.value is not None:
        lo, hi = inp.peer_ev_ebitda_range
        if not lo <= exit_mult.value <= hi:
            issues.append(
                warning(
                    Code.TV_MULTIPLE_INCONSISTENT,
                    f"Implied exit multiple {exit_mult.value:.1f}x EBITDA is outside the peer "
                    f"range {lo:.1f}x–{hi:.1f}x.",
                )
            )

    bridge = equity_from_enterprise(
        valuation.enterprise_value, inp.bridge, inp.share_capital.convertible_face
    )
    issues.extend(bridge.issues)
    per_share = implied_value_per_share(inp.share_capital, bridge.equity_value)
    issues.extend(per_share.issues)

    if inp.current_share_price is not None:
        r = safe_ratio(
            per_share.value_per_share,
            inp.current_share_price,
            num_name="value_per_share",
            den_name="current_share_price",
        )
        upside = r if not r.is_ok or r.value is None else Metric(r.value - 1.0, r.status)
    else:
        upside = missing("current_share_price")

    return DcfResult(
        engine_version=ENGINE_VERSION,
        input_hash=fingerprint(inp),
        schedule=schedule,
        forecast=forecast,
        ufcf=ufcf,
        wacc_build=wacc_build,
        wacc=wacc,
        terminal=terminal,
        valuation=valuation,
        implied_exit_multiple=exit_mult,
        bridge=bridge,
        per_share=per_share,
        current_share_price=inp.current_share_price,
        upside_vs_market=upside,
        issues=dedupe(issues),
    )


__all__ = [
    "BridgeInputs",
    "DcfInputs",
    "DcfResult",
    "ShareCapitalInputs",
    "market_capital_structure",
    "run_dcf",
]
