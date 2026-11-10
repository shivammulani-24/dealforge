from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.deps import SessionDep, UserDep
from app.db.models import Scenario, ValuationProject, ValuationRun, iso_utc
from app.engine.hashing import canonical_json
from app.engine.valuation import run_dcf
from app.schemas.api import CloneIn, ProjectIn, ProjectOut, RunIn, ScenarioIn, ScenarioUpdateIn
from app.schemas.dcf import DcfInputsIn
from app.services import valuations as svc
from app.services.errors import Conflict
from app.services.financials import get_company

router = APIRouter(tags=["valuations"])


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectIn, session: SessionDep, user: UserDep) -> ProjectOut:
    get_company(session, user, body.company_id)
    p = ValuationProject(owner_id=user.id, **body.model_dump())
    session.add(p)
    session.commit()
    return ProjectOut.model_validate(p)


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(session: SessionDep, user: UserDep) -> list[ProjectOut]:
    rows = session.scalars(
        select(ValuationProject)
        .where(ValuationProject.owner_id == user.id)
        .order_by(ValuationProject.id)
    )
    return [ProjectOut.model_validate(p) for p in rows]


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, session: SessionDep, user: UserDep) -> ProjectOut:
    return ProjectOut.model_validate(svc.get_project(session, user, project_id))


def _scenario_out(s: Scenario) -> dict[str, Any]:
    return {
        "id": s.id,
        "project_id": s.project_id,
        "name": s.name,
        "kind": s.kind,
        "description": s.description,
        **svc.snapshot(s),
    }


@router.post("/projects/{project_id}/scenarios", status_code=status.HTTP_201_CREATED)
def create_scenario(
    project_id: int, body: ScenarioIn, session: SessionDep, user: UserDep
) -> dict[str, Any]:
    project = svc.get_project(session, user, project_id)
    if any(s.name == body.name for s in project.scenarios):
        raise Conflict(f"Scenario '{body.name}' already exists in this project.")
    s = Scenario(
        project_id=project.id, name=body.name, kind=body.kind, description=body.description
    )
    session.add(s)
    session.flush()
    svc.apply_scenario_payload(
        session, user, s, body.settings.model_dump(), [a.model_dump() for a in body.assumptions]
    )
    svc.audit(session, user, "scenario", s.id, "create", svc.snapshot(s))
    session.commit()
    return _scenario_out(s)


@router.get("/projects/{project_id}/scenarios")
def list_scenarios(project_id: int, session: SessionDep, user: UserDep) -> list[dict[str, Any]]:
    return [_scenario_out(s) for s in svc.get_project(session, user, project_id).scenarios]


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: int, session: SessionDep, user: UserDep) -> dict[str, Any]:
    return _scenario_out(svc.get_scenario(session, user, scenario_id))


@router.put("/scenarios/{scenario_id}")
def update_scenario(
    scenario_id: int, body: ScenarioUpdateIn, session: SessionDep, user: UserDep
) -> dict[str, Any]:
    s = svc.get_scenario(session, user, scenario_id)
    before = svc.snapshot(s)
    svc.apply_scenario_payload(
        session, user, s, body.settings.model_dump(), [a.model_dump() for a in body.assumptions]
    )
    svc.audit(
        session, user, "scenario", s.id, "update", {"before": before, "after": svc.snapshot(s)}
    )
    session.commit()
    return _scenario_out(s)


@router.post("/scenarios/{scenario_id}/clone", status_code=status.HTTP_201_CREATED)
def clone_scenario(
    scenario_id: int, body: CloneIn, session: SessionDep, user: UserDep
) -> dict[str, Any]:
    src = svc.get_scenario(session, user, scenario_id)
    if any(s.name == body.name for s in src.project.scenarios):
        raise Conflict(f"Scenario '{body.name}' already exists in this project.")
    snap = svc.snapshot(src)
    s = Scenario(
        project_id=src.project_id,
        name=body.name,
        kind=body.kind,
        description=f"Cloned from scenario {src.id} ({src.name})",
    )
    session.add(s)
    session.flush()
    settings = dict(snap["settings"])
    settings["market_data_date"] = src.market_data_date
    svc.apply_scenario_payload(session, user, s, settings, snap["assumptions"])
    svc.audit(session, user, "scenario", s.id, "clone", {"from": src.id})
    session.commit()
    return _scenario_out(s)


@router.post("/scenarios/{scenario_id}/preview")
def preview(scenario_id: int, session: SessionDep, user: UserDep) -> dict[str, Any]:
    return svc.preview(session, svc.get_scenario(session, user, scenario_id))


IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9_-]+$"


@router.post(
    "/scenarios/{scenario_id}/runs",
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {
            "description": "Replay: this Idempotency-Key already froze this request; the "
            "same run is returned (header Idempotent-Replayed: true)."
        },
        409: {"description": "IDEMPOTENCY_KEY_REUSED: the key was used for another request."},
        503: {"description": "DATABASE_BUSY: nothing saved; retry with the same key."},
    },
)
def create_run(
    scenario_id: int,
    body: RunIn,
    session: SessionDep,
    user: UserDep,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=8,
            max_length=128,
            pattern=IDEMPOTENCY_KEY_PATTERN,
            description="Mandatory (A7). A new random key per user action; reuse it to retry.",
        ),
    ],
) -> JSONResponse:
    scenario = svc.get_scenario(session, user, scenario_id)
    run, replayed = svc.freeze_run(
        session,
        request.app.state.write_session_factory,
        user,
        scenario,
        body.label,
        idempotency_key,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        content=svc.run_payload(run),
        headers={"Idempotent-Replayed": "true"} if replayed else None,
    )


@router.get("/scenarios/{scenario_id}/runs")
def list_runs(scenario_id: int, session: SessionDep, user: UserDep) -> list[dict[str, Any]]:
    s = svc.get_scenario(session, user, scenario_id)
    rows = session.scalars(
        select(ValuationRun).where(ValuationRun.scenario_id == s.id).order_by(ValuationRun.id)
    )
    return [
        {
            "id": r.id,
            "label": r.label,
            "input_hash": r.input_hash,
            "engine_version": r.engine_version,
            "created_at": iso_utc(r.created_at),
            "value_per_share": json.loads(r.result_json)["per_share"]["value_per_share"],
        }
        for r in rows
    ]


@router.get("/runs/{run_id}")
def get_run(run_id: int, session: SessionDep, user: UserDep) -> dict[str, Any]:
    return svc.run_payload(svc.get_run(session, user, run_id))


@router.post("/runs/{run_id}/verify")
def verify_run(run_id: int, session: SessionDep, user: UserDep) -> dict[str, Any]:
    return svc.verify_run(svc.get_run(session, user, run_id))


@router.post("/calculate/dcf")
def calculate_dcf(body: DcfInputsIn, user: UserDep) -> dict[str, Any]:
    """Stateless DCF: exactly the engine's result for exactly these inputs. Nothing is saved."""
    result = run_dcf(body.to_engine())
    return json.loads(canonical_json(result))  # type: ignore[no-any-return]
