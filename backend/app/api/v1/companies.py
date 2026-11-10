from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Form, UploadFile, status
from sqlalchemy import select

from app.api.deps import SessionDep, UserDep
from app.db.models import Company, LineItem, Source
from app.engine.hashing import to_plain
from app.importers.csv_financials import parse_financials_csv
from app.importers.line_items import ITEMS
from app.schemas.api import CompanyIn, CompanyOut, InstrumentsIn, LineItemPatchIn
from app.services import financials as fin
from app.services.errors import Conflict, NotFound
from app.services.valuations import audit, replace_instruments

router = APIRouter(tags=["companies"])


@router.get("/line-items")
def line_item_dictionary() -> list[dict[str, Any]]:
    return [asdict(d) for d in ITEMS.values()]


@router.post("/companies", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company(body: CompanyIn, session: SessionDep, user: UserDep) -> CompanyOut:
    if session.scalar(
        select(Company).where(Company.owner_id == user.id, Company.name == body.name)
    ):
        raise Conflict(f"You already have a company named '{body.name}'.")
    c = Company(owner_id=user.id, **body.model_dump())
    session.add(c)
    session.commit()
    return CompanyOut.model_validate(c)


@router.get("/companies", response_model=list[CompanyOut])
def list_companies(session: SessionDep, user: UserDep) -> list[CompanyOut]:
    rows = session.scalars(select(Company).where(Company.owner_id == user.id).order_by(Company.id))
    return [CompanyOut.model_validate(c) for c in rows]


@router.get("/companies/{company_id}", response_model=CompanyOut)
def get_company(company_id: int, session: SessionDep, user: UserDep) -> CompanyOut:
    return CompanyOut.model_validate(fin.get_company(session, user, company_id))


def _preview_payload(p: Any) -> dict[str, Any]:
    return {
        "ok": p.ok,
        "file_name": p.file_name,
        "file_sha256": p.file_sha256,
        "currency": p.currency,
        "file_scale": p.file_scale,
        "stored_scale": p.target_scale,
        "errors": [asdict(i) for i in p.errors],
        "issues": [asdict(i) for i in p.issues],
        "periods": [
            {
                "fiscal_year": pp.fiscal_year,
                "period_end": pp.period_end.isoformat(),
                "values": {k: asdict(c) for k, c in sorted(pp.cells.items())},
            }
            for pp in p.periods
        ],
        "historical_metrics": None if p.analysis is None else to_plain(p.analysis.periods),
    }


@router.post("/companies/{company_id}/financials/import")
async def import_financials(
    company_id: int,
    session: SessionDep,
    user: UserDep,
    file: Annotated[UploadFile, File()],
    currency: Annotated[str, Form()],
    scale: Annotated[str, Form()],
    basis: Annotated[Literal["reported", "assumed"], Form()],
    rationale: Annotated[str | None, Form()] = None,  # A5: required when basis=assumed
    dry_run: Annotated[bool, Form()] = True,
    replace: Annotated[bool, Form()] = False,
) -> dict[str, Any]:
    company = fin.get_company(session, user, company_id)
    data = await file.read()
    preview = parse_financials_csv(
        data,
        file_name=file.filename or "upload.csv",
        currency=currency,
        file_scale=scale,
        company_currency=company.currency,
        company_scale=company.scale,
        fiscal_year_end_month=company.fiscal_year_end_month,
    )
    payload = _preview_payload(preview)
    if dry_run:
        return {"committed": False, "preview": payload}
    periods = fin.commit_import(
        session, user, company, preview, basis=basis, replace=replace, rationale=rationale
    )
    return {"committed": True, "fiscal_years": [p.fiscal_year for p in periods], "preview": payload}


@router.get("/companies/{company_id}/financials")
def get_financials(company_id: int, session: SessionDep, user: UserDep) -> dict[str, Any]:
    company = fin.get_company(session, user, company_id)
    return {
        "company_id": company.id,
        "currency": company.currency,
        "scale": company.scale,
        "periods": [
            {
                "fiscal_year": p.fiscal_year,
                "period_end": p.period_end.isoformat(),
                "line_items": [
                    {
                        "id": li.id,
                        "item_code": li.item_code,
                        "value": li.value,
                        "basis": li.basis,
                        "source_id": li.source_id,
                        "source_title": li.source.title,
                        "source_ref": li.source_ref,
                        "original_value": li.original_value,
                        "original_scale": li.original_scale,
                        "original_text": li.original_text,
                        "note": li.note,
                    }
                    for li in p.line_items
                ],
            }
            for p in fin.periods_for(session, company)
        ],
    }


@router.get("/companies/{company_id}/historical-analysis")
def get_historical_analysis(company_id: int, session: SessionDep, user: UserDep) -> dict[str, Any]:
    company = fin.get_company(session, user, company_id)
    a = fin.historical_analysis(session, company)
    return {"periods": to_plain(a.periods), "issues": to_plain(a.issues)}


@router.patch("/line-items/{line_item_id}")
def patch_line_item(
    line_item_id: int, body: LineItemPatchIn, session: SessionDep, user: UserDep
) -> dict[str, Any]:
    li = session.get(LineItem, line_item_id)
    if li is None or li.period.company.owner_id != user.id:
        raise NotFound(f"Line item {line_item_id} not found.")
    if body.value is not None and ITEMS[li.item_code].magnitude and body.value < 0:
        raise Conflict(f"{li.item_code} is a positive magnitude (D-02).")
    if body.basis == "reported":
        assert body.source is not None  # schema-validated
        src = Source(
            owner_id=user.id,
            kind="filing",
            title=body.source.title,
            uri=body.source.uri,
            notes=body.source.reference,
        )
        note = f"Reported correction from: {body.source.title}" + (
            f" ({body.source.reference})" if body.source.reference else ""
        )
        ref = body.source.reference or "filing"
    else:
        assert body.rationale is not None  # schema-validated
        src = Source(
            owner_id=user.id,
            kind="manual",
            title=f"Manual correction: {li.item_code}",
            notes=body.rationale,
        )
        note, ref = body.rationale.strip(), "manual entry"
    session.add(src)
    session.flush()
    old = {
        "value": li.value,
        "basis": li.basis,
        "source_id": li.source_id,
        "source_ref": li.source_ref,
    }
    li.value, li.basis, li.source_id, li.note = body.value, body.basis, src.id, note
    li.source_ref = ref
    li.original_value, li.original_text, li.original_scale = body.value, None, None
    audit(
        session,
        user,
        "line_item",
        li.id,
        "update",
        {"old": old, "new_value": body.value, "basis": body.basis, "note": note},
    )
    session.commit()
    return {
        "id": li.id,
        "item_code": li.item_code,
        "value": li.value,
        "basis": li.basis,
        "source_id": src.id,
    }


@router.put("/companies/{company_id}/share-instruments")
def put_instruments(
    company_id: int, body: InstrumentsIn, session: SessionDep, user: UserDep
) -> dict[str, Any]:
    company = fin.get_company(session, user, company_id)
    src = Source(
        owner_id=user.id, kind="manual", title=body.source_title, uri=None, notes=body.source_ref
    )
    session.add(src)
    session.flush()
    rows = [{**i.model_dump(), "source_ref": body.source_ref} for i in body.instruments]
    replace_instruments(session, user, company, rows, src)
    return {"company_id": company.id, "count": len(rows), "source_id": src.id}


@router.get("/companies/{company_id}/share-instruments")
def get_instruments(company_id: int, session: SessionDep, user: UserDep) -> list[dict[str, Any]]:
    company = fin.get_company(session, user, company_id)
    return [
        {
            "id": i.id,
            "kind": i.kind,
            "label": i.label,
            "count": i.count,
            "strike": i.strike,
            "face_value": i.face_value,
            "conversion_price": i.conversion_price,
            "coupon_rate": i.coupon_rate,
            "source_id": i.source_id,
        }
        for i in company.instruments
    ]
