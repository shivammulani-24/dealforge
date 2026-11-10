"""B1 dashboard, B2 global runs list, B3 sensitivity, B7 sources, B9 samples."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, status
from sqlalchemy import func, select

from app.api.deps import SessionDep, UserDep
from app.db.models import Source, ValuationProject, ValuationRun, iso_utc
from app.engine.sensitivity import AxisSpec, DcfOutput, DcfVariable
from app.engine.version import ENGINE_VERSION
from app.schemas.api import SensitivityIn, SourceIn
from app.schemas.responses import (
    DashboardOut,
    RunsPageOut,
    SampleLoadOut,
    SampleOut,
    SensitivityOut,
    SourceOut,
    documented,
)
from app.services import dashboard as dash
from app.services import samples as smp
from app.services import sensitivity as sens
from app.services import valuations as svc
from app.services.errors import NotFound

router = APIRouter(tags=["insights"])


@router.get("/dashboard", responses=documented(DashboardOut))
def get_dashboard(session: SessionDep, user: UserDep) -> dict[str, Any]:
    return dash.dashboard(session, user)


@router.get("/runs", responses=documented(RunsPageOut))
def list_all_runs(
    session: SessionDep,
    user: UserDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    company_id: int | None = None,
    project_id: int | None = None,
    scenario_id: int | None = None,
) -> dict[str, Any]:
    """Every frozen run of the current user. Values are read verbatim from the stored results
    (never recomputed), so they are available whatever the current engine version (R1)."""
    stmt = (
        select(ValuationRun)
        .join(ValuationProject, ValuationRun.project_id == ValuationProject.id)
        .where(ValuationRun.created_by == user.id)
    )
    if company_id is not None:
        stmt = stmt.where(ValuationProject.company_id == company_id)
    if project_id is not None:
        stmt = stmt.where(ValuationRun.project_id == project_id)
    if scenario_id is not None:
        stmt = stmt.where(ValuationRun.scenario_id == scenario_id)
    total = int(session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = session.scalars(
        stmt.order_by(ValuationRun.created_at.desc(), ValuationRun.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = []
    for r in rows:
        result, inputs = json.loads(r.result_json), json.loads(r.inputs_json)
        comp = r.project.company
        items.append(
            {
                "id": r.id,
                "label": r.label,
                "created_at": iso_utc(r.created_at),
                "engine_version": r.engine_version,
                "engine_compatible": r.engine_version == ENGINE_VERSION,
                "input_hash": r.input_hash,
                "valuation_date": inputs["dates"]["valuation_date"],
                "company": {
                    "id": comp.id,
                    "name": comp.name,
                    "currency": comp.currency,
                    "scale": comp.scale,
                    "is_synthetic": comp.is_synthetic,
                },
                "project": {"id": r.project.id, "name": r.project.name},
                "scenario": {"id": r.scenario.id, "name": r.scenario.name},
                "enterprise_value": result["valuation"]["enterprise_value"],
                "equity_value": result["per_share"]["equity_value_to_common"],
                "value_per_share": result["per_share"]["value_per_share"],
                "warning_count": len(r.warnings),
            }
        )
    return {"page": page, "page_size": page_size, "total": total, "items": items}


@router.post("/runs/{run_id}/sensitivity", responses=documented(SensitivityOut))
def run_sensitivity(
    run_id: int, body: SensitivityIn, session: SessionDep, user: UserDep
) -> dict[str, Any]:
    run = svc.get_run(session, user, run_id)
    return sens.run_sensitivity(
        run,
        AxisSpec(DcfVariable(body.row.variable), body.row.step, body.row.steps_each_side),
        AxisSpec(DcfVariable(body.col.variable), body.col.step, body.col.steps_each_side),
        DcfOutput(body.output),
    )


def _source_out(s: Source) -> dict[str, Any]:
    return {
        "id": s.id,
        "kind": s.kind,
        "title": s.title,
        "file_name": s.file_name,
        "file_sha256": s.file_sha256,
        "uri": s.uri,
        "notes": s.notes,
        "created_at": iso_utc(s.created_at),
    }


@router.get("/sources/{source_id}", responses=documented(SourceOut))
def get_source(source_id: int, session: SessionDep, user: UserDep) -> dict[str, Any]:
    return _source_out(svc.get_source(session, user, source_id))


@router.post("/sources", status_code=status.HTTP_201_CREATED, responses=documented(SourceOut, 201))
def create_source(body: SourceIn, session: SessionDep, user: UserDep) -> dict[str, Any]:
    notes = "; ".join(x for x in (body.reference, body.notes) if x) or None
    src = Source(owner_id=user.id, kind=body.kind, title=body.title, uri=body.uri, notes=notes)
    session.add(src)
    session.commit()
    return _source_out(src)


@router.get("/samples", responses=documented(list[SampleOut]))
def list_samples(user: UserDep) -> list[dict[str, Any]]:
    return [smp.public(s) for s in smp.SAMPLES.values()]


@router.post(
    "/samples/{sample_id}/load",
    status_code=status.HTTP_201_CREATED,
    responses=documented(SampleLoadOut, 201),
)
def load_sample(sample_id: str, request: Request, user: UserDep) -> dict[str, Any]:
    if sample_id not in smp.SAMPLES:
        raise NotFound(f"Sample '{sample_id}' not found.")
    return smp.load_sample(request.app.state.write_session_factory, user.id, sample_id)
