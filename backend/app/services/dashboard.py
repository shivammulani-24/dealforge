"""B1: dashboard, onboarding and recent activity (plan §4.1). Read-only; owner-scoped."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Company,
    FinancialPeriod,
    LineItem,
    Scenario,
    User,
    ValuationProject,
    ValuationRun,
    iso_utc,
)
from app.engine.version import ENGINE_VERSION

from .samples import SAMPLES

RECENT_RUNS, RECENT_COMPANIES, RECENT_ACTIVITY = 5, 5, 20


def _count(session: Session, stmt: Any) -> int:
    return int(session.scalar(stmt) or 0)


def counts(session: Session, user: User) -> dict[str, int]:
    return {
        "companies": _count(
            session, select(func.count(Company.id)).where(Company.owner_id == user.id)
        ),
        "projects": _count(
            session,
            select(func.count(ValuationProject.id)).where(ValuationProject.owner_id == user.id),
        ),
        "scenarios": _count(
            session,
            select(func.count(Scenario.id))
            .join(ValuationProject)
            .where(ValuationProject.owner_id == user.id),
        ),
        "runs": _count(
            session, select(func.count(ValuationRun.id)).where(ValuationRun.created_by == user.id)
        ),
    }


def company_of_event(session: Session, e: AuditEvent) -> int | None:
    """Resolve an audit event to the company it touched (D4-03: recently *active*)."""
    if e.entity == "company":
        return e.entity_id
    if e.entity == "line_item":
        li = session.get(LineItem, e.entity_id)
        return None if li is None else li.period.company_id
    if e.entity == "financial_period":
        p = session.get(FinancialPeriod, e.entity_id)  # may be gone after a replace
        return None if p is None else p.company_id
    if e.entity == "scenario":
        s = session.get(Scenario, e.entity_id)
        return None if s is None else s.project.company_id
    if e.entity == "valuation_run":
        r = session.get(ValuationRun, e.entity_id)
        return None if r is None else r.project.company_id
    return None


def summary(session: Session, e: AuditEvent) -> str:
    """Server-written text; the raw ``detail`` (which can hold old values) is never returned."""
    d = e.detail or {}
    if e.entity == "valuation_run" and e.action == "create":
        r = session.get(ValuationRun, e.entity_id)
        name = r.scenario.name if r is not None else "?"
        return f"Froze run {e.entity_id} for scenario '{name}' ({str(d.get('input_hash'))[:15]}…)"
    if e.entity == "company" and e.action == "import":
        years = d.get("fiscal_years") or []
        span = f"FY{min(years)}–FY{max(years)}" if years else "statements"
        return f"Imported financial statements ({span})"
    if e.entity == "company" and e.action == "sample_load":
        return "Loaded the synthetic sample company"
    if e.entity == "company" and e.action == "share_instruments":
        return "Updated share instruments"
    if e.entity == "financial_period" and e.action == "replace":
        return f"Replaced FY{d.get('fiscal_year')} statements"
    if e.entity == "line_item":
        li = session.get(LineItem, e.entity_id)
        return f"Corrected {li.item_code if li else 'a line item'} ({d.get('basis', 'n/a')})"
    if e.entity == "scenario":
        s = session.get(Scenario, e.entity_id)
        verb = {"create": "Created", "update": "Updated", "clone": "Cloned"}.get(e.action, e.action)
        return f"{verb} scenario '{s.name if s else e.entity_id}'"
    return f"{e.action} {e.entity} {e.entity_id}"


def dashboard(session: Session, user: User) -> dict[str, Any]:
    c = counts(session, user)
    has_statements = (
        _count(
            session,
            select(func.count(FinancialPeriod.id)).join(Company).where(Company.owner_id == user.id),
        )
        > 0
    )
    sample_names = {s["name"] for s in SAMPLES.values()}
    sample_loaded = (
        _count(
            session,
            select(func.count(Company.id)).where(
                Company.owner_id == user.id, Company.name.in_(sample_names)
            ),
        )
        > 0
    )
    steps = [
        {"key": "company", "label": "Create or load a company", "done": c["companies"] > 0},
        {"key": "statements", "label": "Import financial statements", "done": has_statements},
        {"key": "scenario", "label": "Create a valuation scenario", "done": c["scenarios"] > 0},
        {"key": "run", "label": "Freeze a valuation run", "done": c["runs"] > 0},
    ]

    runs = session.scalars(
        select(ValuationRun)
        .where(ValuationRun.created_by == user.id)
        .order_by(ValuationRun.created_at.desc(), ValuationRun.id.desc())
        .limit(RECENT_RUNS)
    ).all()
    recent_runs = []
    for r in runs:
        comp = r.project.company
        recent_runs.append(
            {
                "id": r.id,
                "label": r.label,
                "created_at": iso_utc(r.created_at),
                "company": {
                    "id": comp.id,
                    "name": comp.name,
                    "currency": comp.currency,
                    "scale": comp.scale,
                    "is_synthetic": comp.is_synthetic,
                },
                "scenario": {"id": r.scenario.id, "name": r.scenario.name},
                "value_per_share": json.loads(r.result_json)["per_share"]["value_per_share"],
                "engine_version": r.engine_version,
                "engine_compatible": r.engine_version == ENGINE_VERSION,
            }
        )

    events = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.user_id == user.id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(200)
    ).all()
    activity: list[dict[str, Any]] = []
    seen: list[tuple[int, Any]] = []
    for e in events:
        company_id = company_of_event(session, e)
        if len(activity) < RECENT_ACTIVITY:
            activity.append(
                {
                    "at": iso_utc(e.created_at),
                    "entity": e.entity,
                    "entity_id": e.entity_id,
                    "action": e.action,
                    "company_id": company_id,
                    "summary": summary(session, e),
                }
            )
        if company_id is not None and company_id not in [x[0] for x in seen]:
            seen.append((company_id, e.created_at))
    recent_companies = []
    for company_id, at in seen[:RECENT_COMPANIES]:
        found = session.get(Company, company_id)
        if found is None or found.owner_id != user.id:
            continue
        comp = found
        recent_companies.append(
            {
                "id": comp.id,
                "name": comp.name,
                "is_synthetic": comp.is_synthetic,
                "last_activity_at": iso_utc(at),
                "fiscal_years": [p.fiscal_year for p in comp.periods],
            }
        )
    return {
        "counts": c,
        "onboarding": {
            "complete": all(s["done"] for s in steps),
            "steps": steps,
            "sample_available": True,
            "sample_loaded": sample_loaded,
        },
        "recent_runs": recent_runs,
        "recent_companies": recent_companies,
        "recent_activity": activity,
    }
