"""Committing a CSV preview: provenance on every value, NULL for missing, conflicts, audit."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Company, LineItem, Source, User
from app.importers.csv_financials import parse_financials_csv
from app.services.errors import Conflict, ImportRejected, NotFound
from app.services.financials import commit_import, get_company, historical_analysis

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "ardent_precision_synthetic.csv"


def setup(session: Session) -> tuple[User, Company]:
    u = User(email="a@example.com", password_hash="x")
    session.add(u)
    session.flush()
    c = Company(
        owner_id=u.id,
        name="Ardent Precision Components (SYNTHETIC)",
        currency="INR",
        scale="crores",
        fiscal_year_end_month=3,
        is_financial_institution=False,
        is_synthetic=True,
    )
    session.add(c)
    session.commit()
    return u, c


def preview(data: bytes):  # type: ignore[no-untyped-def]
    return parse_financials_csv(
        data,
        file_name=SAMPLE.name,
        currency="INR",
        file_scale="crores",
        company_currency="INR",
        company_scale="crores",
        fiscal_year_end_month=3,
    )


def test_every_stored_value_has_provenance(session: Session) -> None:
    u, c = setup(session)
    commit_import(session, u, c, preview(SAMPLE.read_bytes()), basis="reported", replace=False)
    items = session.scalars(select(LineItem)).all()
    assert len(items) == 3 * 28  # 28 item rows × 3 years; blank cells stored as NULL
    src = session.scalars(select(Source)).one()
    assert src.kind == "csv_import" and src.file_sha256 and src.file_name == SAMPLE.name
    for li in items:
        assert li.source_id == src.id and li.basis == "reported"
        assert li.source_ref and li.source_ref.startswith(SAMPLE.name + ": row ")
    blank = session.scalars(select(LineItem).where(LineItem.item_code == "reported_ebitda")).all()
    assert sorted((li.value is None, li.original_text) for li in blank) == [
        (False, "400"),
        (True, ""),
        (True, ""),
    ]
    a = historical_analysis(session, c)
    assert a.metric(2025, "nwc").value == pytest.approx(300.0)


def test_re_import_requires_replace_and_is_audited(session: Session) -> None:
    u, c = setup(session)
    commit_import(session, u, c, preview(SAMPLE.read_bytes()), basis="reported", replace=False)
    with pytest.raises(Conflict):
        commit_import(session, u, c, preview(SAMPLE.read_bytes()), basis="reported", replace=False)
    session.rollback()
    changed = SAMPLE.read_bytes().replace(b'"2,000.0"', b"2010")
    commit_import(session, u, c, preview(changed), basis="reported", replace=True)
    rev = session.scalars(select(LineItem).where(LineItem.item_code == "revenue")).all()
    assert sorted(li.value for li in rev) == [1600.0, 1800.0, 2010.0]
    replaced = session.scalars(select(AuditEvent).where(AuditEvent.action == "replace")).all()
    assert len(replaced) == 3
    fy25 = next(e for e in replaced if e.detail["fiscal_year"] == 2025)
    assert fy25.detail["old_values"]["revenue"] == 2000.0


def test_preview_with_errors_cannot_be_committed(session: Session) -> None:
    u, c = setup(session)
    bad = preview(b"item_code,FY2025\nperiod_end,2025-03-31\ncapex,-1\n")
    with pytest.raises(ImportRejected):
        commit_import(session, u, c, bad, basis="reported", replace=False)
    assert session.scalars(select(LineItem)).all() == []


def test_other_users_company_is_not_found(session: Session) -> None:
    _, c = setup(session)
    other = User(email="b@example.com", password_hash="x")
    session.add(other)
    session.commit()
    with pytest.raises(NotFound):
        get_company(session, other, c.id)
