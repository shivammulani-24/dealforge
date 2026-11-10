"""B9: the synthetic sample company (plan §4.9). Loaded through the normal importer and services
in ONE write transaction (BEGIN IMMEDIATE): either everything is created or nothing is."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.models import AuditEvent, Company, Scenario, Source, User, ValuationProject
from app.importers.csv_financials import parse_financials_csv

from .errors import Conflict, ImportRejected
from .financials import commit_import

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"

SAMPLES: dict[str, dict[str, Any]] = {
    "ardent-precision": {
        "id": "ardent-precision",
        "name": "Ardent Precision Components (SYNTHETIC)",
        "description": (
            "A fictional Indian industrial components maker (INR crores, March year-end). Every "
            "figure was constructed for demonstration and is not real company data."
        ),
        "is_synthetic": True,
        "includes": [
            "3 fiscal years of statements (FY2023–FY2025), including liquidity items",
            "Share instruments: 5.0m options at 12.00, 1.0m RSUs",
            "Base scenario with the independently verified KA-DCF-03 assumptions",
        ],
        "csv": "ardent_precision_synthetic.csv",
        "scenario": "ardent_base_scenario.json",
        "company": {
            "sector": "Industrials",
            "currency": "INR",
            "scale": "crores",
            "fiscal_year_end_month": 3,
            "is_financial_institution": False,
        },
        "instruments": [
            {"kind": "option", "label": "ESOP 2021", "count": 5.0, "strike": 12.0},
            {"kind": "rsu", "label": "RSU plan", "count": 1.0},
        ],
    },
}


class SampleAlreadyLoaded(Conflict):
    code = "SAMPLE_ALREADY_LOADED"


def public(sample: dict[str, Any]) -> dict[str, Any]:
    return {k: sample[k] for k in ("id", "name", "description", "is_synthetic", "includes")}


def load_sample(
    write_factory: sessionmaker,  # type: ignore[type-arg]
    user_id: int,
    sample_id: str,
) -> dict[str, int]:
    from . import valuations as svc  # local import: valuations imports this module indirectly

    spec = SAMPLES[sample_id]
    with write_factory() as ws, ws.begin():  # BEGIN IMMEDIATE: one atomic transaction
        user = ws.get(User, user_id)
        assert user is not None
        existing = ws.scalar(
            select(Company).where(Company.owner_id == user_id, Company.name == spec["name"])
        )
        if existing is not None:
            project = ws.scalar(
                select(ValuationProject)
                .where(ValuationProject.company_id == existing.id)
                .order_by(ValuationProject.id)
            )
            scenario = (
                None
                if project is None
                else ws.scalar(
                    select(Scenario).where(Scenario.project_id == project.id).order_by(Scenario.id)
                )
            )
            raise SampleAlreadyLoaded(
                f"The sample '{spec['name']}' is already loaded.",
                detail={
                    "company_id": existing.id,
                    "project_id": None if project is None else project.id,
                    "scenario_id": None if scenario is None else scenario.id,
                },
            )
        company = Company(owner_id=user_id, name=spec["name"], is_synthetic=True, **spec["company"])
        ws.add(company)
        ws.flush()

        data = (SAMPLES_DIR / spec["csv"]).read_bytes()
        preview = parse_financials_csv(
            data,
            file_name=spec["csv"],
            currency=company.currency,
            file_scale=company.scale,
            company_currency=company.currency,
            company_scale=company.scale,
            fiscal_year_end_month=company.fiscal_year_end_month,
        )
        if not preview.ok:  # pragma: no cover - the bundled file is tested to be clean
            raise ImportRejected("The bundled sample file failed validation.")
        commit_import(
            ws,
            user,
            company,
            preview,
            basis="reported",
            replace=False,
            source_kind="synthetic",
            commit=False,
        )

        inst_source = Source(
            owner_id=user_id,
            kind="synthetic",
            title="Synthetic sample: share instruments",
            notes="Constructed for the KA-DCF-03 demonstration",
        )
        ws.add(inst_source)
        ws.flush()
        rows = [{**r, "source_ref": "synthetic sample"} for r in spec["instruments"]]
        svc.replace_instruments(ws, user, company, rows, inst_source, commit=False)

        project = ValuationProject(
            owner_id=user_id,
            company_id=company.id,
            name="Ardent valuation (sample)",
            description="Synthetic demonstration project",
        )
        ws.add(project)
        ws.flush()
        scen = json.loads((SAMPLES_DIR / spec["scenario"]).read_text(encoding="utf-8"))
        scenario = Scenario(
            project_id=project.id,
            name="Base",
            kind="base",
            description="KA-DCF-03 assumptions (synthetic)",
        )
        ws.add(scenario)
        ws.flush()
        settings = dict(scen["settings"])
        settings["market_data_date"] = date.fromisoformat(settings["market_data_date"])
        svc.apply_scenario_payload(ws, user, scenario, settings, scen["assumptions"])
        ws.add(
            AuditEvent(
                user_id=user_id,
                entity="company",
                entity_id=company.id,
                action="sample_load",
                detail={"sample_id": sample_id},
            )
        )
        ws.flush()
        return {"company_id": company.id, "project_id": project.id, "scenario_id": scenario.id}
