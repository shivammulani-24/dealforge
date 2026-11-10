"""Projects, scenarios, DCF input assembly, frozen runs and reproducibility checks.

Statement-derived inputs (base revenue, base NWC, bridge claims, basic shares) always come from
the latest fiscal year's line items (P3-03). Assumptions come from the scenario's rows. Every
input carries a provenance entry. Nothing is defaulted: a missing value reaches the engine as
``None`` and the engine reports ``MISSING_INPUT`` naming the field.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    Assumption,
    AuditEvent,
    Company,
    FinancialPeriod,
    LineItem,
    Scenario,
    ShareInstrument,
    Source,
    User,
    ValuationProject,
    ValuationRun,
    iso_utc,
)
from app.engine.bridge import BridgeInputs
from app.engine.consistency import driver_history_warnings
from app.engine.dates import ValuationDates
from app.engine.errors import Code, EngineError, Issue, MissingInputError, error
from app.engine.forecast import HORIZON_YEARS, ForecastInputs, ForecastYearDrivers
from app.engine.hashing import canonical_json, fingerprint, to_plain
from app.engine.historical import analyze_historicals, operating_nwc
from app.engine.presentation import margins_from_values
from app.engine.shares import (
    ConvertibleInstrument,
    InstrumentKind,
    OptionTranche,
    RsuGrant,
    ShareCapitalInputs,
)
from app.engine.valuation import DcfInputs, DcfResult, run_dcf
from app.engine.version import ENGINE_VERSION
from app.engine.wacc import DebtValueBasis, WaccAssumptions
from app.importers.line_items import BRIDGE_ITEMS
from app.schemas.dcf import DcfInputsIn

from .errors import NotFound, ServiceError
from .financials import to_engine_period

PER_YEAR_KEYS = (
    "revenue_growth",
    "ebitda_margin",
    "da_pct_revenue",
    "capex_pct_revenue",
    "nwc_pct_revenue",
)
WACC_KEYS = (
    "risk_free_rate",
    "levered_beta",
    "equity_risk_premium",
    "pre_tax_cost_of_debt",
    "size_premium",
    "cost_of_preferred",
    "target_debt_to_capital",
)
SCALAR_KEYS = ("tax_rate", "terminal_growth", "wacc_override", *WACC_KEYS)


def passthrough(value: float | bool | None) -> Any:
    """Hand a possibly-missing value to the engine unchanged.

    The engine dataclasses are typed for complete inputs; a ``None`` here is deliberate and makes
    the engine raise ``MISSING_INPUT`` naming the field, never a silent zero.
    """
    return value


#: A4: source kinds that can back a "reported" value. "manual" never can.
REPORTED_SOURCE_KINDS = frozenset({"csv_import", "filing", "market_data", "synthetic"})


class BasisRuleViolation(ServiceError):
    status = 422
    code = "BASIS_SOURCE_KIND"


def check_reported_source(session: Session, user: User, source_id: int, what: str) -> Source:
    """A4: the source must exist, belong to the user and be of a qualifying kind."""
    src = get_source(session, user, source_id)  # 404 when absent or not owned
    if src.kind not in REPORTED_SOURCE_KINDS:
        raise BasisRuleViolation(
            f"{what}: a reported value needs a source of kind "
            f"{sorted(REPORTED_SOURCE_KINDS)}; source {src.id} is '{src.kind}'.",
            detail={"source_id": src.id, "kind": src.kind},
        )
    return src


class InvalidAssumptions(ServiceError):
    status = 422
    code = "INVALID_ASSUMPTIONS"


# ------------------------------------------------------------------------------- ownership


def get_project(session: Session, user: User, project_id: int) -> ValuationProject:
    p = session.get(ValuationProject, project_id)
    if p is None or p.owner_id != user.id:
        raise NotFound(f"Project {project_id} not found.")
    return p


def get_scenario(session: Session, user: User, scenario_id: int) -> Scenario:
    s = session.get(Scenario, scenario_id)
    if s is None or s.project.owner_id != user.id:
        raise NotFound(f"Scenario {scenario_id} not found.")
    return s


def get_run(session: Session, user: User, run_id: int) -> ValuationRun:
    r = session.get(ValuationRun, run_id)
    if r is None or r.created_by != user.id:
        raise NotFound(f"Valuation run {run_id} not found.")
    return r


def get_source(session: Session, user: User, source_id: int) -> Source:
    s = session.get(Source, source_id)
    if s is None or s.owner_id != user.id:
        raise NotFound(f"Source {source_id} not found.")
    return s


# ------------------------------------------------------------------------------- scenarios


def validate_assumption_rows(rows: list[dict[str, Any]]) -> None:
    problems: list[str] = []
    seen: set[tuple[str, int | None]] = set()
    for i, r in enumerate(rows):
        key, year = r["key"], r.get("year_index")
        if key in PER_YEAR_KEYS:
            if not isinstance(year, int) or not 1 <= year <= HORIZON_YEARS:
                problems.append(f"assumptions[{i}]: '{key}' needs year_index 1..{HORIZON_YEARS}.")
        elif key in SCALAR_KEYS:
            if year is not None:
                problems.append(f"assumptions[{i}]: '{key}' is not per-year; omit year_index.")
        else:
            problems.append(f"assumptions[{i}]: unknown key '{key}'.")
        if (key, year) in seen:
            problems.append(f"assumptions[{i}]: duplicate '{key}' year {year}.")
        seen.add((key, year))
    if problems:
        raise InvalidAssumptions("Invalid assumption set.", detail=problems)


def apply_scenario_payload(
    session: Session,
    user: User,
    scenario: Scenario,
    settings: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    validate_assumption_rows(rows)
    for i, r in enumerate(rows):
        if r.get("basis") == "reported":
            check_reported_source(session, user, r["source_id"], f"assumptions[{i}]")
        elif r.get("source_id") is not None:
            get_source(session, user, r["source_id"])
    if settings.get("market_source_id") is not None:
        check_reported_source(session, user, settings["market_source_id"], "market_source_id")
    for k, v in settings.items():
        setattr(scenario, k, v)
    scenario.assumptions.clear()
    session.flush()
    for r in rows:
        scenario.assumptions.append(
            Assumption(
                key=r["key"],
                year_index=r.get("year_index"),
                value=r["value"],
                basis=r.get("basis", "assumed"),
                source_id=r.get("source_id"),
                rationale=r.get("rationale"),
            )
        )


def snapshot(scenario: Scenario) -> dict[str, Any]:
    return {
        "settings": {
            "market_data_date": None
            if scenario.market_data_date is None
            else scenario.market_data_date.isoformat(),
            "share_price": scenario.share_price,
            "debt_value_basis": scenario.debt_value_basis,
            "include_leases_in_debt": scenario.include_leases_in_debt,
            "market_source_id": scenario.market_source_id,
            "market_rationale": scenario.market_rationale,
        },
        "assumptions": [
            {
                "key": a.key,
                "year_index": a.year_index,
                "value": a.value,
                "basis": a.basis,
                "source_id": a.source_id,
                "rationale": a.rationale,
            }
            for a in scenario.assumptions
        ],
    }


def audit(
    session: Session, user: User, entity: str, entity_id: int, action: str, detail: dict[str, Any]
) -> None:
    session.add(
        AuditEvent(
            user_id=user.id, entity=entity, entity_id=entity_id, action=action, detail=detail
        )
    )


# ------------------------------------------------------------------------------- DCF inputs


def _li_prov(li: LineItem | None, code: str, fy: int) -> dict[str, Any]:
    if li is None:
        return {"status": "missing", "reason": f"no '{code}' line item for FY{fy}"}
    return {
        "status": "ok" if li.value is not None else "missing",
        "basis": li.basis,
        "fiscal_year": fy,
        "line_item_id": li.id,
        "source_id": li.source_id,
        "source_title": li.source.title,
        "source_ref": li.source_ref,
        "original_text": li.original_text,
    }


@dataclass(frozen=True)
class SettingsData:
    """Scenario market inputs and settings as plain data (no ORM object; C2)."""

    market_data_date: date | None
    share_price: float | None
    debt_value_basis: str | None
    include_leases_in_debt: bool | None
    market_source_id: int | None
    market_rationale: str | None


@dataclass(frozen=True)
class AssumptionData:
    key: str
    year_index: int | None
    value: float
    basis: str
    source_id: int | None
    rationale: str | None
    assumption_id: int | None  # None for an unsaved draft


def settings_of(scenario: Scenario) -> SettingsData:
    return SettingsData(
        scenario.market_data_date,
        scenario.share_price,
        scenario.debt_value_basis,
        scenario.include_leases_in_debt,
        scenario.market_source_id,
        scenario.market_rationale,
    )


def assumptions_of(scenario: Scenario) -> list[AssumptionData]:
    return [
        AssumptionData(a.key, a.year_index, a.value, a.basis, a.source_id, a.rationale, a.id)
        for a in scenario.assumptions
    ]


def build_dcf_inputs(
    session: Session, scenario: Scenario
) -> tuple[DcfInputs, dict[str, Any], tuple[Issue, ...]]:
    """Saved scenario → engine inputs (behaviour unchanged; delegates to the ORM-free core)."""
    return assemble_dcf_inputs(
        session, scenario.project.company, settings_of(scenario), assumptions_of(scenario)
    )


def assemble_dcf_inputs(
    session: Session,
    company: Company,
    settings: SettingsData,
    assumptions: list[AssumptionData],
    *,
    draft: bool = False,
) -> tuple[DcfInputs, dict[str, Any], tuple[Issue, ...]]:
    """Statements + settings + assumptions → engine inputs and provenance (plan §4.4, C2).

    Reads the company's statements and instruments only; it never creates or modifies an ORM
    object, so a draft preview can't autoflush anything into the session.
    """
    periods = list(
        session.scalars(
            select(FinancialPeriod)
            .where(FinancialPeriod.company_id == company.id)
            .order_by(FinancialPeriod.fiscal_year)
        )
    )
    missing: list[Issue] = []
    if not periods:
        missing.append(
            error(
                Code.MISSING_INPUT,
                "The company has no financial statements; import them first.",
                "financial_statements",
            )
        )
    if settings.market_data_date is None:
        missing.append(
            error(
                Code.MISSING_INPUT,
                "Scenario market_data_date is not set (D-07).",
                "market_data_date",
            )
        )
    if missing:
        raise MissingInputError(missing)
    assert settings.market_data_date is not None
    lfy = periods[-1]
    items = {li.item_code: li for li in lfy.line_items}
    fy = lfy.fiscal_year
    prov: dict[str, Any] = {}

    def item(code: str, path: str) -> float | None:
        li = items.get(code)
        prov[path] = _li_prov(li, code, fy)
        return None if li is None else li.value

    base_revenue = item("revenue", "forecast.base_revenue")
    nwc_metric, partial = operating_nwc(to_engine_period(lfy))
    nwc_codes = [
        "accounts_receivable",
        "inventory",
        "other_current_operating_assets",
        "accounts_payable",
        "other_current_operating_liabilities",
    ]
    prov["forecast.base_nwc"] = {
        "status": nwc_metric.status.value,
        "basis": "derived",
        "formula": "AR + inventory + other op. assets − AP − other op. liabilities",
        "partial": partial,
        "components": {c: _li_prov(items.get(c), c, fy) for c in nwc_codes},
    }
    bridge_vals: dict[str, Any] = {code: item(code, f"bridge.{code}") for code in BRIDGE_ITEMS}
    prov["bridge.include_leases_in_debt"] = {"basis": "assumed", "source": "scenario setting"}
    basic = item("basic_shares", "share_capital.basic_shares")

    opts, rsus, convs = [], [], []
    for ins in company.instruments:
        path = f"share_capital.{ins.kind}:{ins.label}"
        prov[path] = {
            "basis": "reported",
            "source_id": ins.source_id,
            "source_title": ins.source.title,
            "source_ref": ins.source_ref,
        }
        if ins.kind in ("option", "warrant"):
            opts.append(
                OptionTranche(
                    ins.label,
                    passthrough(ins.count),
                    passthrough(ins.strike),
                    InstrumentKind(ins.kind),
                )
            )
        elif ins.kind == "rsu":
            rsus.append(RsuGrant(ins.label, passthrough(ins.count)))
        else:
            convs.append(
                ConvertibleInstrument(
                    ins.label,
                    passthrough(ins.face_value),
                    passthrough(ins.conversion_price),
                    ins.coupon_rate,
                )
            )

    by_key: dict[tuple[str, int | None], AssumptionData] = {
        (a.key, a.year_index): a for a in assumptions
    }

    def assumed(key: str, year: int | None, path: str) -> Any:  # float, or None → engine
        a = by_key.get((key, year))
        if a is None:
            prov[path] = {"status": "missing", "reason": "assumption not set"}
            return None
        prov[path] = {
            "status": "ok",
            "basis": a.basis,
            "assumption_id": a.assumption_id,
            "draft": draft,
            "source_id": a.source_id,
            "rationale": a.rationale,
        }
        return a.value

    years = tuple(
        ForecastYearDrivers(*(assumed(k, t, f"forecast.years[{t}].{k}") for k in PER_YEAR_KEYS))
        for t in range(1, HORIZON_YEARS + 1)
    )
    tax = assumed("tax_rate", None, "tax_rate")
    g = assumed("terminal_growth", None, "terminal_growth")
    override = (
        assumed("wacc_override", None, "wacc_override")
        if ("wacc_override", None) in by_key
        else None
    )
    capm_given = any((k, None) in by_key for k in WACC_KEYS) or settings.debt_value_basis
    wacc = None
    if capm_given:
        vals = {k: assumed(k, None, f"wacc_assumptions.{k}") for k in WACC_KEYS}
        wacc = WaccAssumptions(
            debt_value_basis=passthrough(None)
            if settings.debt_value_basis is None
            else DebtValueBasis(settings.debt_value_basis),
            **vals,
        )
    # C5: the price is "reported" only when linked to a market source; otherwise "assumed",
    # with the rationale the analyst gave (A4/A5).
    prov["current_share_price"] = {
        "status": "ok" if settings.share_price is not None else "missing",
        "basis": "reported" if settings.market_source_id is not None else "assumed",
        "market_data_date": settings.market_data_date.isoformat(),
        "source_id": settings.market_source_id,
        "rationale": settings.market_rationale,
    }
    prov["dates"] = {
        "statement_date": lfy.period_end.isoformat(),
        "valuation_date": lfy.period_end.isoformat(),
        "market_data_date": settings.market_data_date.isoformat(),
        "convention": "valuation date = last fiscal year-end (D-07)",
        "statement_fiscal_year": fy,
    }

    forecast = ForecastInputs(passthrough(base_revenue), passthrough(nwc_metric.value), years)
    inputs = DcfInputs(
        dates=ValuationDates(lfy.period_end, lfy.period_end, settings.market_data_date),
        forecast=forecast,
        tax_rate=passthrough(tax),
        terminal_growth=passthrough(g),
        bridge=BridgeInputs(
            include_leases_in_debt=passthrough(settings.include_leases_in_debt),
            **bridge_vals,
        ),
        share_capital=ShareCapitalInputs(
            passthrough(basic), tuple(opts), tuple(rsus), tuple(convs)
        ),
        current_share_price=settings.share_price,
        wacc_assumptions=wacc,
        wacc_override=override,
        is_financial_institution=company.is_financial_institution,
    )

    extra: tuple[Issue, ...] = ()
    drivers_complete = all(getattr(y, k) is not None for y in years for k in PER_YEAR_KEYS)
    if drivers_complete:
        try:
            history = analyze_historicals([to_engine_period(p) for p in periods])
            extra = driver_history_warnings(forecast, history)
        except EngineError:
            extra = ()  # history problems surface in the historical-analysis endpoint
    return inputs, prov, extra


def issue_dicts(issues: tuple[Issue, ...]) -> list[dict[str, Any]]:
    return [{**asdict(i), "severity": i.severity.value} for i in issues]


def context_block(scenario: Scenario) -> dict[str, Any]:
    """B5: what every figure in a preview or run is about, including its units."""
    c = scenario.project.company
    return {
        "company": {
            "id": c.id,
            "name": c.name,
            "currency": c.currency,
            "scale": c.scale,
            "is_synthetic": c.is_synthetic,
        },
        "project": {"id": scenario.project.id, "name": scenario.project.name},
        "scenario": {"id": scenario.id, "name": scenario.name},
    }


def presentation_block(result: dict[str, Any]) -> dict[str, Any]:
    """B5 / D4-06: EBIT and UFCF margins per forecast year, computed on read from the result.
    Never written into result_json, so fingerprints and stored runs are unaffected."""
    years = margins_from_values(
        [y["revenue"] for y in result["forecast"]["years"]],
        [y["ebit"] for y in result["forecast"]["years"]],
        [u["ufcf"] for u in result["ufcf"]],
    )
    return {"basis": "derived", "years": to_plain(years)}


def preview(session: Session, scenario: Scenario) -> dict[str, Any]:
    inputs, prov, extra = build_dcf_inputs(session, scenario)
    return _preview_payload(scenario, inputs, prov, extra, draft=False)


def draft_preview(
    session: Session,
    user: User,
    scenario: Scenario,
    settings: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """B4 / D4-04: preview unsaved edits. Validates like a save, but writes nothing: no ORM
    object is created or changed, and no audit event is recorded."""
    validate_assumption_rows(rows)
    for i, r in enumerate(rows):
        if r.get("basis") == "reported":
            check_reported_source(session, user, r["source_id"], f"assumptions[{i}]")
        elif r.get("source_id") is not None:
            get_source(session, user, r["source_id"])
    if settings.get("market_source_id") is not None:
        check_reported_source(session, user, settings["market_source_id"], "market_source_id")
    data = SettingsData(
        settings["market_data_date"],
        settings["share_price"],
        settings["debt_value_basis"],
        settings["include_leases_in_debt"],
        settings.get("market_source_id"),
        settings.get("market_rationale"),
    )
    assumptions = [
        AssumptionData(
            r["key"],
            r.get("year_index"),
            r["value"],
            r.get("basis", "assumed"),
            r.get("source_id"),
            r.get("rationale"),
            None,
        )
        for r in rows
    ]
    inputs, prov, extra = assemble_dcf_inputs(
        session, scenario.project.company, data, assumptions, draft=True
    )
    return _preview_payload(scenario, inputs, prov, extra, draft=True)


def _preview_payload(
    scenario: Scenario,
    inputs: DcfInputs,
    prov: dict[str, Any],
    extra: tuple[Issue, ...],
    *,
    draft: bool,
) -> dict[str, Any]:
    result = run_dcf(inputs)
    plain = json.loads(canonical_json(result))
    return {
        "draft": draft,
        "context": context_block(scenario),
        "result": plain,
        "result_basis": "derived",
        "presentation": presentation_block(plain),
        "warnings": issue_dicts(result.issues + extra),
        "engine_version": result.engine_version,
        "input_hash": result.input_hash,
        "provenance": prov,
    }


class IdempotencyKeyReused(ServiceError):
    status = 409
    code = "IDEMPOTENCY_KEY_REUSED"


class DatabaseBusy(ServiceError):
    status = 503
    code = "DATABASE_BUSY"


def request_fingerprint(scenario_id: int, label: str | None) -> str:
    """Identifies a freeze request: the same key must always mean the same request."""
    body = {"scenario_id": scenario_id, "label": label}
    return "sha256:" + hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def _existing_run(session: Session, user_id: int, key: str) -> ValuationRun | None:
    return session.scalar(
        select(ValuationRun).where(
            ValuationRun.created_by == user_id, ValuationRun.idempotency_key == key
        )
    )


def _replay(run: ValuationRun, fingerprint_: str, key: str) -> ValuationRun:
    if run.request_fingerprint != fingerprint_:
        raise IdempotencyKeyReused(
            f"Idempotency-Key '{key}' was already used for a different freeze request "
            f"(run {run.id}). Use a new key for a new request.",
            detail={"run_id": run.id},
        )
    return run


def _before_write_phase() -> None:
    """Test seam between the read phase and BEGIN IMMEDIATE (plan §4.14); no-op in production."""


def freeze_run(
    session: Session,
    write_factory: sessionmaker,  # type: ignore[type-arg]
    user: User,
    scenario: Scenario,
    label: str | None,
    key: str,
) -> tuple[ValuationRun, bool]:
    """Freeze a run exactly once per (user, Idempotency-Key). Returns (run, replayed).

    Plan §4.14: (2) read phase with all computation outside the write lock; (3) BEGIN IMMEDIATE,
    re-check the key inside the transaction, insert run + audit event, commit; (4) the unique
    index is the backstop; (5) lock timeout → 503 DATABASE_BUSY, safe to retry with the same key.
    """
    user_id, scenario_id, project_id = user.id, scenario.id, scenario.project_id
    fp = request_fingerprint(scenario_id, label)

    # Step 2: read phase (deferred transaction, WAL snapshot)
    existing = _existing_run(session, user_id, key)
    if existing is not None:
        return _replay(existing, fp, key), True
    inputs, prov, extra = build_dcf_inputs(session, scenario)
    result = run_dcf(inputs)
    fields_ = {
        "scenario_id": scenario_id,
        "project_id": project_id,
        "created_by": user_id,
        "label": label,
        "engine_version": result.engine_version,
        "input_hash": result.input_hash,
        "inputs_json": canonical_json(inputs),
        "result_json": canonical_json(result),
        "provenance": {"inputs": prov, "scenario": snapshot(scenario)},
        "warnings": issue_dicts(result.issues + extra),
        "idempotency_key": key,
        "request_fingerprint": fp,
    }
    session.rollback()  # end the read transaction; nothing was written
    _before_write_phase()

    # Step 3: write phase under SQLite's RESERVED lock
    try:
        with write_factory() as ws, ws.begin():
            again = _existing_run(ws, user_id, key)
            if again is not None:
                return _replay(again, fp, key), True
            run = ValuationRun(**fields_)
            ws.add(run)
            ws.flush()
            ws.add(
                AuditEvent(
                    user_id=user_id,
                    entity="valuation_run",
                    entity_id=run.id,
                    action="create",
                    detail={"scenario_id": scenario_id, "input_hash": run.input_hash},
                )
            )
        return run, False
    except IntegrityError:
        # Step 4: backstop — another writer committed the same key; return its run.
        with write_factory() as ws:
            winner = _existing_run(ws, user_id, key)
            if winner is None:  # pragma: no cover - the unique index guarantees a winner
                raise
            return _replay(winner, fp, key), True
    except OperationalError as exc:
        if "locked" in str(exc).lower() or "busy" in str(exc).lower():
            raise DatabaseBusy(
                "The database is busy; nothing was saved. Retry with the same Idempotency-Key.",
                detail={"retry_after_seconds": 1},
            ) from exc
        raise  # pragma: no cover


def run_payload(run: ValuationRun) -> dict[str, Any]:
    result = json.loads(run.result_json)
    return {
        "context": context_block(run.scenario),
        "result_basis": "derived",
        "presentation": presentation_block(result),
        "engine_compatible": run.engine_version == ENGINE_VERSION,
        "id": run.id,
        "scenario_id": run.scenario_id,
        "project_id": run.project_id,
        "label": run.label,
        "engine_version": run.engine_version,
        "input_hash": run.input_hash,
        "created_at": iso_utc(run.created_at),
        "inputs": json.loads(run.inputs_json),
        "result": result,
        "warnings": run.warnings,
        "provenance": run.provenance,
    }


def rebuild_inputs(run: ValuationRun) -> DcfInputs:
    """Reconstruct the engine inputs from the frozen JSON (strict schema, no defaults)."""
    return DcfInputsIn.model_validate_json(run.inputs_json).to_engine()


def verify_run(run: ValuationRun) -> dict[str, Any]:
    inputs = rebuild_inputs(run)
    result: DcfResult = run_dcf(inputs)
    new_json = canonical_json(result)
    stored = json.loads(run.result_json)
    fresh = json.loads(new_json)
    differing = sorted(_diff_paths(stored, fresh))
    return {
        "run_id": run.id,
        "identical": new_json == run.result_json,
        "inputs_round_trip_exact": canonical_json(inputs) == run.inputs_json,
        "input_hash_matches": fingerprint(inputs) == run.input_hash,
        "engine_version_at_run": run.engine_version,
        "engine_version_now": ENGINE_VERSION,
        "engine_version_changed": run.engine_version != ENGINE_VERSION,
        "differing_paths": differing,
        "value_per_share": {
            "stored": stored["per_share"]["value_per_share"],
            "recomputed": fresh["per_share"]["value_per_share"],
        },
    }


def _diff_paths(a: Any, b: Any, path: str = "") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out: list[str] = []
        for k in sorted(set(a) | set(b)):
            out += _diff_paths(a.get(k), b.get(k), f"{path}.{k}" if path else k)
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        out = []
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            out += _diff_paths(x, y, f"{path}[{i}]")
        return out
    return [] if a == b else [path]


def replace_instruments(
    session: Session,
    user: User,
    company: Company,
    rows: list[dict[str, Any]],
    source: Source,
    *,
    commit: bool = True,
) -> None:
    old = [
        {
            "kind": i.kind,
            "label": i.label,
            "count": i.count,
            "strike": i.strike,
            "face_value": i.face_value,
            "conversion_price": i.conversion_price,
            "coupon_rate": i.coupon_rate,
        }
        for i in company.instruments
    ]
    company.instruments.clear()
    session.flush()
    for r in rows:
        company.instruments.append(ShareInstrument(source_id=source.id, **r))
    audit(
        session,
        user,
        "company",
        company.id,
        "share_instruments",
        {"old": old, "new": rows, "source_id": source.id},
    )
    if commit:
        session.commit()
    else:
        session.flush()
