"""B6: response models for every endpoint the frontend calls (plan §4.6).

They document the API in OpenAPI (and so in the generated TypeScript types) without changing a
single response byte: routes keep serialising through the canonical JSON path, and the models are
attached as ``responses={…: {"model": …}}``. ``tests/api/conftest.py`` validates every successful
response in the test suite against its declared model, so the documentation can't drift from
reality. Engine structures (DCF result, EBITDA reconciliation) reuse the engine dataclasses
directly, so they aren't hand-copied. Models forbid unknown fields.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.engine.ebitda import EbitdaReconciliation
from app.engine.valuation import DcfResult

Basis = Literal["reported", "assumed", "derived"]


class Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IssueOut(Out):
    code: str
    message: str
    severity: Literal["info", "warning", "error"]
    field: str | None


class MetricOut(Out):
    value: float | None
    status: Literal["ok", "missing", "not_meaningful"]
    reason: str | None


class DerivedMetricOut(MetricOut):
    basis: Literal["derived"]


class CompanyRef(Out):
    id: int
    name: str
    currency: str
    scale: str
    is_synthetic: bool


class NamedRef(Out):
    id: int
    name: str


class ContextOut(Out):
    company: CompanyRef
    project: NamedRef
    scenario: NamedRef


class PresentationYearOut(Out):
    t: int
    ebit_margin: MetricOut
    ufcf_margin: MetricOut


class PresentationOut(Out):
    basis: Literal["derived"]
    years: list[PresentationYearOut]


class HealthOut(Out):
    status: Literal["ok"]
    engine_version: str


# ------------------------------------------------------------------ companies and statements


class LineItemDefOut(Out):
    code: str
    label: str
    statement: str
    magnitude: bool
    used_by: str


class LineItemOut(Out):
    id: int
    item_code: str
    value: float | None
    basis: Basis
    source_id: int
    source_title: str
    source_ref: str | None
    original_value: float | None
    original_scale: str | None
    original_text: str | None
    note: str | None


class CompletenessGroupOut(Out):
    required: list[str]
    missing: list[str]
    complete: bool


class CompletenessOut(Out):
    present: int
    missing: int
    absent: int
    groups: dict[str, CompletenessGroupOut]


class PeriodOut(Out):
    fiscal_year: int
    period_end: str
    line_items: list[LineItemOut]
    completeness: CompletenessOut


class FinancialsOut(Out):
    company_id: int
    currency: str
    scale: str
    periods: list[PeriodOut]


class MetricDefinitionOut(Out):
    formula: str
    items: list[str]
    not_meaningful: str
    basis: Literal["derived"]


class PeriodAnalysisOut(Out):
    fiscal_year: int
    metrics: dict[str, DerivedMetricOut]
    ebitda: EbitdaReconciliation


class HistoricalAnalysisOut(Out):
    periods: list[PeriodAnalysisOut]
    issues: list[IssueOut]
    metric_definitions: dict[str, MetricDefinitionOut]


class ImportIssueOut(Out):
    code: str
    message: str
    severity: Literal["error", "warning", "info"]
    row: int | None
    column: str | None


class ParsedCellOut(Out):
    value: float | None
    original_text: str
    original_value: float | None
    row: int
    column: str


class ParsedPeriodOut(Out):
    fiscal_year: int
    period_end: str
    values: dict[str, ParsedCellOut]


class ImportPreviewOut(Out):
    ok: bool
    file_name: str
    file_sha256: str
    currency: str
    file_scale: str
    stored_scale: str
    errors: list[ImportIssueOut]
    issues: list[ImportIssueOut]
    periods: list[ParsedPeriodOut]
    historical_metrics: list[dict[str, Any]] | None


class ImportOut(Out):
    committed: bool
    fiscal_years: list[int] | None = None
    preview: ImportPreviewOut


class PatchLineItemOut(Out):
    id: int
    item_code: str
    value: float | None
    basis: Basis
    source_id: int


class InstrumentOut(Out):
    id: int
    kind: Literal["option", "warrant", "rsu", "convertible"]
    label: str
    count: float | None
    strike: float | None
    face_value: float | None
    conversion_price: float | None
    coupon_rate: float | None
    source_id: int


class InstrumentsPutOut(Out):
    company_id: int
    count: int
    source_id: int


class SourceOut(Out):
    id: int
    kind: str
    title: str
    file_name: str | None
    file_sha256: str | None
    uri: str | None
    notes: str | None
    created_at: str


# ------------------------------------------------------------------ scenarios and runs


class ScenarioSettingsOut(Out):
    market_data_date: str | None
    share_price: float | None
    debt_value_basis: Literal["market", "book"] | None
    include_leases_in_debt: bool | None
    market_source_id: int | None
    market_rationale: str | None


class AssumptionOut(Out):
    key: str
    year_index: int | None
    value: float
    basis: Literal["reported", "assumed"]
    source_id: int | None
    rationale: str | None


class ScenarioOut(Out):
    id: int
    project_id: int
    name: str
    kind: str
    description: str | None
    settings: ScenarioSettingsOut
    assumptions: list[AssumptionOut]


class PreviewOut(Out):
    draft: bool
    context: ContextOut
    result: DcfResult
    result_basis: Literal["derived"]
    presentation: PresentationOut
    warnings: list[IssueOut]
    engine_version: str
    input_hash: str
    provenance: dict[str, Any]


class RunOut(Out):
    context: ContextOut
    result_basis: Literal["derived"]
    presentation: PresentationOut
    engine_compatible: bool
    id: int
    scenario_id: int
    project_id: int
    label: str | None
    engine_version: str
    input_hash: str
    created_at: str
    inputs: dict[str, Any]
    result: DcfResult
    warnings: list[IssueOut]
    provenance: dict[str, Any]


class ScenarioRunOut(Out):
    id: int
    label: str | None
    input_hash: str
    engine_version: str
    created_at: str
    value_per_share: float


class VerifyValuesOut(Out):
    stored: float
    recomputed: float


class VerifyOut(Out):
    run_id: int
    identical: bool
    inputs_round_trip_exact: bool
    input_hash_matches: bool
    engine_version_at_run: str
    engine_version_now: str
    engine_version_changed: bool
    differing_paths: list[str]
    value_per_share: VerifyValuesOut


class RunsPageItemOut(Out):
    id: int
    label: str | None
    created_at: str
    engine_version: str
    engine_compatible: bool
    input_hash: str
    valuation_date: str
    company: CompanyRef
    project: NamedRef
    scenario: NamedRef
    enterprise_value: float
    equity_value: float
    value_per_share: float
    warning_count: int


class RunsPageOut(Out):
    page: int
    page_size: int
    total: int
    items: list[RunsPageItemOut]


class SensitivityCellOut(Out):
    value: float | None
    status: Literal["ok", "invalid"]
    codes: list[str]
    change_abs: float | None
    change_pct: MetricOut


class SensitivityOut(Out):
    run_id: int
    input_hash: str
    engine_version: str
    basis: Literal["derived"]
    context: ContextOut
    row_variable: str
    col_variable: str
    output: str
    row_values: list[float]
    col_values: list[float]
    base_row: int
    base_col: int
    base_value: float
    base_matches_run: bool
    cells: list[list[SensitivityCellOut]]


# ------------------------------------------------------------------ dashboard and samples


class OnboardingStepOut(Out):
    key: Literal["company", "statements", "scenario", "run"]
    label: str
    done: bool


class OnboardingOut(Out):
    complete: bool
    steps: list[OnboardingStepOut]
    sample_available: bool
    sample_loaded: bool


class DashboardRunOut(Out):
    id: int
    label: str | None
    created_at: str
    company: CompanyRef
    scenario: NamedRef
    value_per_share: float
    engine_version: str
    engine_compatible: bool


class DashboardCompanyOut(Out):
    id: int
    name: str
    is_synthetic: bool
    last_activity_at: str
    fiscal_years: list[int]


class ActivityOut(Out):
    at: str
    entity: str
    entity_id: int
    action: str
    company_id: int | None
    summary: str


class CountsOut(Out):
    companies: int
    projects: int
    scenarios: int
    runs: int


class DashboardOut(Out):
    counts: CountsOut
    onboarding: OnboardingOut
    recent_runs: list[DashboardRunOut]
    recent_companies: list[DashboardCompanyOut]
    recent_activity: list[ActivityOut]


class SampleOut(Out):
    id: str
    name: str
    description: str
    is_synthetic: bool
    includes: list[str]


class SampleLoadOut(Out):
    company_id: int
    project_id: int
    scenario_id: int


def documented(model: Any, status_code: int = 200) -> dict[int | str, dict[str, Any]]:
    """``responses=`` entry documenting a route's success body without changing serialisation."""
    return {status_code: {"model": model, "description": "Success"}}
