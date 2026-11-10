"""Persisting and reading historical statements, with provenance on every value."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Company, FinancialPeriod, LineItem, Source, User
from app.engine.historical import HistoricalAnalysis, HistoricalPeriod, analyze_historicals
from app.importers.csv_financials import ImportPreview
from app.importers.line_items import ITEMS

from .errors import Conflict, ImportRejected, NotFound


def get_company(session: Session, user: User, company_id: int) -> Company:
    c = session.get(Company, company_id)
    if c is None or c.owner_id != user.id:  # P3-06: other users' data reads as absent
        raise NotFound(f"Company {company_id} not found.")
    return c


def commit_import(
    session: Session,
    user: User,
    company: Company,
    preview: ImportPreview,
    *,
    basis: str,
    replace: bool,
    rationale: str | None = None,
    source_kind: str = "csv_import",
    commit: bool = True,
) -> list[FinancialPeriod]:
    """Persist a clean preview. ``source_kind="synthetic"`` is used only by the sample loader;
    ``commit=False`` lets a caller include the import in a larger atomic transaction."""
    if not preview.ok:
        raise ImportRejected(
            f"Import has {len(preview.errors)} error(s); fix the file and preview again.",
            detail=[e.__dict__ for e in preview.errors],
        )
    if basis not in ("reported", "assumed"):
        raise ImportRejected("basis must be 'reported' or 'assumed'.")
    note: str | None = None
    if basis == "assumed":  # A5
        if rationale is None or not 0 < len(rationale.strip()) <= 2000:
            raise ImportRejected("Importing values as 'assumed' needs a rationale (A5).")
        note = rationale.strip()
    existing = {p.fiscal_year: p for p in company.periods}
    clashes = sorted(y for y in (p.fiscal_year for p in preview.periods) if y in existing)
    if clashes and not replace:
        raise Conflict(
            f"Fiscal years {clashes} already exist; re-import with replace=true to overwrite.",
            detail={"fiscal_years": clashes},
        )

    source = Source(
        owner_id=user.id,
        kind=source_kind,
        title=f"CSV import: {preview.file_name}"
        if source_kind == "csv_import"
        else f"Synthetic sample data: {preview.file_name}",
        file_name=preview.file_name,
        file_sha256=preview.file_sha256,
        notes=f"currency {preview.currency}; file scale {preview.file_scale}; "
        f"stored in {preview.target_scale}" + (f"; rationale: {note}" if note else ""),
    )
    session.add(source)
    session.flush()
    for y in clashes:
        old = existing[y]
        session.add(
            AuditEvent(
                user_id=user.id,
                entity="financial_period",
                entity_id=old.id,
                action="replace",
                detail={
                    "fiscal_year": y,
                    "old_values": {li.item_code: li.value for li in old.line_items},
                    "new_source_id": source.id,
                },
            )
        )
        company.periods.remove(old)
        session.delete(old)
    session.flush()

    created: list[FinancialPeriod] = []
    for pp in preview.periods:
        period = FinancialPeriod(
            company_id=company.id,
            fiscal_year=pp.fiscal_year,
            period_end=pp.period_end,
            period_type="annual",
        )
        for code, cell in sorted(pp.cells.items()):
            period.line_items.append(
                LineItem(
                    item_code=code,
                    value=cell.value,  # None stays None
                    basis=basis,
                    source_id=source.id,
                    source_ref=f"{preview.file_name}: row {cell.row}, column {cell.column}",
                    original_value=cell.original_value,
                    original_scale=preview.file_scale,
                    original_text=cell.original_text,
                    note=note,  # the import rationale when basis is "assumed" (A5)
                )
            )
        company.periods.append(period)
        created.append(period)
    session.flush()
    session.add(
        AuditEvent(
            user_id=user.id,
            entity="company",
            entity_id=company.id,
            action="import",
            detail={
                "source_id": source.id,
                "fiscal_years": [p.fiscal_year for p in created],
                "file_sha256": preview.file_sha256,
            },
        )
    )
    if commit:
        session.commit()
    else:
        session.flush()
    return created


def periods_for(session: Session, company: Company) -> list[FinancialPeriod]:
    stmt = (
        select(FinancialPeriod)
        .where(FinancialPeriod.company_id == company.id)
        .order_by(FinancialPeriod.fiscal_year)
    )
    return list(session.scalars(stmt))


def to_engine_period(p: FinancialPeriod) -> HistoricalPeriod:
    values = {li.item_code: li.value for li in p.line_items}
    names = HistoricalPeriod.__dataclass_fields__
    return HistoricalPeriod(
        fiscal_year=p.fiscal_year,
        **{code: values.get(code) for code in ITEMS if code in names},  # type: ignore[arg-type]
    )


def historical_analysis(session: Session, company: Company) -> HistoricalAnalysis:
    periods = periods_for(session, company)
    return analyze_historicals([to_engine_period(p) for p in periods])
