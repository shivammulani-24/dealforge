"""Pydantic mirrors of the engine's DCF input dataclasses (structure only; field names identical).

``to_engine()`` is a mechanical copy. No arithmetic, rounding, unit conversion or defaults are
applied, so the engine receives exactly what the client sent. ``tests/api/test_contract.py``
asserts the field sets match the dataclasses one for one.
"""

from __future__ import annotations

from app.engine.bridge import BridgeInputs
from app.engine.dates import ValuationDates
from app.engine.forecast import ForecastInputs, ForecastYearDrivers
from app.engine.shares import (
    ConvertibleInstrument,
    InstrumentKind,
    OptionTranche,
    RsuGrant,
    ShareCapitalInputs,
)
from app.engine.valuation import DcfInputs
from app.engine.wacc import DebtValueBasis, WaccAssumptions

from .common import ExactEnum, IsoDate, Num, StrictModel

InstrumentKindIn = ExactEnum(InstrumentKind)
DebtValueBasisIn = ExactEnum(DebtValueBasis)


class ValuationDatesIn(StrictModel):
    statement_date: IsoDate
    valuation_date: IsoDate
    market_data_date: IsoDate

    def to_engine(self) -> ValuationDates:
        return ValuationDates(self.statement_date, self.valuation_date, self.market_data_date)


class ForecastYearDriversIn(StrictModel):
    revenue_growth: Num | None
    ebitda_margin: Num | None
    da_pct_revenue: Num | None
    capex_pct_revenue: Num | None
    nwc_pct_revenue: Num | None

    def to_engine(self) -> ForecastYearDrivers:
        return ForecastYearDrivers(
            self.revenue_growth,  # type: ignore[arg-type]  # None → engine MISSING_INPUT
            self.ebitda_margin,  # type: ignore[arg-type]
            self.da_pct_revenue,  # type: ignore[arg-type]
            self.capex_pct_revenue,  # type: ignore[arg-type]
            self.nwc_pct_revenue,  # type: ignore[arg-type]
        )


class ForecastInputsIn(StrictModel):
    base_revenue: Num | None
    base_nwc: Num | None
    years: list[ForecastYearDriversIn]

    def to_engine(self) -> ForecastInputs:
        return ForecastInputs(
            self.base_revenue,  # type: ignore[arg-type]
            self.base_nwc,  # type: ignore[arg-type]
            tuple(y.to_engine() for y in self.years),
        )


class BridgeInputsIn(StrictModel):
    cash: Num | None
    total_debt: Num | None
    lease_liabilities: Num | None
    include_leases_in_debt: bool | None
    preferred_equity: Num | None
    non_controlling_interest: Num | None
    other_debt_like_claims: Num | None
    non_operating_assets: Num | None

    def to_engine(self) -> BridgeInputs:
        return BridgeInputs(**self.model_dump())


class OptionTrancheIn(StrictModel):
    label: str
    count: Num | None
    strike: Num | None
    kind: InstrumentKindIn  # type: ignore[valid-type]

    def to_engine(self) -> OptionTranche:
        return OptionTranche(self.label, self.count, self.strike, self.kind)  # type: ignore[arg-type]


class RsuGrantIn(StrictModel):
    label: str
    count: Num | None

    def to_engine(self) -> RsuGrant:
        return RsuGrant(self.label, self.count)  # type: ignore[arg-type]


class ConvertibleInstrumentIn(StrictModel):
    label: str
    face_value: Num | None
    conversion_price: Num | None
    coupon_rate: Num | None

    def to_engine(self) -> ConvertibleInstrument:
        return ConvertibleInstrument(
            self.label,
            self.face_value,  # type: ignore[arg-type]
            self.conversion_price,  # type: ignore[arg-type]
            self.coupon_rate,
        )


class ShareCapitalInputsIn(StrictModel):
    basic_shares: Num | None
    options: list[OptionTrancheIn]
    rsus: list[RsuGrantIn]
    convertibles: list[ConvertibleInstrumentIn]

    def to_engine(self) -> ShareCapitalInputs:
        return ShareCapitalInputs(
            self.basic_shares,  # type: ignore[arg-type]
            tuple(o.to_engine() for o in self.options),
            tuple(r.to_engine() for r in self.rsus),
            tuple(c.to_engine() for c in self.convertibles),
        )


class WaccAssumptionsIn(StrictModel):
    risk_free_rate: Num | None
    levered_beta: Num | None
    equity_risk_premium: Num | None
    pre_tax_cost_of_debt: Num | None
    size_premium: Num | None
    debt_value_basis: DebtValueBasisIn | None  # type: ignore[valid-type]
    cost_of_preferred: Num | None
    target_debt_to_capital: Num | None

    def to_engine(self) -> WaccAssumptions:
        return WaccAssumptions(**self.model_dump())


class DcfInputsIn(StrictModel):
    dates: ValuationDatesIn
    forecast: ForecastInputsIn
    tax_rate: Num | None
    terminal_growth: Num | None
    bridge: BridgeInputsIn
    share_capital: ShareCapitalInputsIn
    current_share_price: Num | None
    wacc_assumptions: WaccAssumptionsIn | None
    wacc_override: Num | None
    is_financial_institution: bool
    peer_ev_ebitda_range: tuple[Num, Num] | None

    def to_engine(self) -> DcfInputs:
        return DcfInputs(
            dates=self.dates.to_engine(),
            forecast=self.forecast.to_engine(),
            tax_rate=self.tax_rate,  # type: ignore[arg-type]
            terminal_growth=self.terminal_growth,  # type: ignore[arg-type]
            bridge=self.bridge.to_engine(),
            share_capital=self.share_capital.to_engine(),
            current_share_price=self.current_share_price,
            wacc_assumptions=None
            if self.wacc_assumptions is None
            else self.wacc_assumptions.to_engine(),
            wacc_override=self.wacc_override,
            is_financial_institution=self.is_financial_institution,
            peer_ev_ebitda_range=self.peer_ev_ebitda_range,
        )
