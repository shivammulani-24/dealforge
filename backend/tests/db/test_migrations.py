"""Migrations build exactly the ORM schema; frozen runs are immutable at two levels."""

from __future__ import annotations

from datetime import date

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.db.migrate import downgrade, upgrade
from app.db.models import (
    Base,
    Company,
    FinancialPeriod,
    ImmutableRunError,
    LineItem,
    Scenario,
    Source,
    User,
    ValuationProject,
    ValuationRun,
)
from app.db.session import make_engine

TABLES = {
    "users",
    "api_tokens",
    "companies",
    "sources",
    "financial_periods",
    "line_items",
    "share_instruments",
    "valuation_projects",
    "scenarios",
    "assumptions",
    "valuation_runs",
    "audit_events",
    "alembic_version",
}


def tables(url: str) -> set[str]:
    engine = make_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_creates_every_table(db_url: str) -> None:
    assert tables(db_url) == TABLES


def test_migration_matches_orm_models(db_url: str) -> None:
    engine = make_engine(db_url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == [], diff


def test_downgrade_and_upgrade_round_trip(db_url: str) -> None:
    downgrade(db_url)
    assert tables(db_url) == {"alembic_version"}
    upgrade(db_url)
    assert tables(db_url) == TABLES


def seed(session: Session) -> tuple[User, Company, Source]:
    u = User(email="analyst@example.com", password_hash="x")
    session.add(u)
    session.flush()
    c = Company(
        owner_id=u.id,
        name="Ardent (SYNTHETIC)",
        currency="INR",
        scale="crores",
        fiscal_year_end_month=3,
        is_financial_institution=False,
        is_synthetic=True,
    )
    s = Source(owner_id=u.id, kind="csv_import", title="test")  # A4: reported needs csv/filing
    session.add_all([c, s])
    session.flush()
    return u, c, s


def test_missing_values_are_stored_as_null_not_zero(session: Session) -> None:
    _, c, s = seed(session)
    p = FinancialPeriod(company_id=c.id, fiscal_year=2025, period_end=date(2025, 3, 31))
    session.add(p)
    session.flush()
    session.add(
        LineItem(period_id=p.id, item_code="cogs", value=None, basis="reported", source_id=s.id)
    )
    session.commit()
    raw = session.execute(text("SELECT value, value IS NULL FROM line_items")).one()
    assert raw == (None, 1)


def test_foreign_keys_are_enforced(session: Session) -> None:
    session.add(FinancialPeriod(company_id=9999, fiscal_year=2025, period_end=date(2025, 3, 31)))
    with pytest.raises(IntegrityError):
        session.commit()


def make_run(session: Session) -> ValuationRun:
    u, c, _ = seed(session)
    pr = ValuationProject(owner_id=u.id, company_id=c.id, name="P")
    session.add(pr)
    session.flush()
    sc = Scenario(project_id=pr.id, name="Base", kind="base")
    session.add(sc)
    session.flush()
    run = ValuationRun(
        scenario_id=sc.id,
        project_id=pr.id,
        created_by=u.id,
        engine_version="0.1.0",
        input_hash="sha256:x",
        inputs_json="{}",
        result_json="{}",
        provenance={},
        warnings=[],
    )
    session.add(run)
    session.commit()
    return run


def test_orm_refuses_to_modify_or_delete_a_run(session: Session) -> None:
    run = make_run(session)
    run.result_json = '{"tampered": true}'
    with pytest.raises(ImmutableRunError):
        session.commit()
    session.rollback()
    session.delete(run)
    with pytest.raises(ImmutableRunError):
        session.commit()


def test_database_trigger_refuses_raw_sql_changes(session: Session) -> None:
    run = make_run(session)
    with pytest.raises(DBAPIError, match="immutable"):
        session.execute(
            text("UPDATE valuation_runs SET result_json='{}' WHERE id=:i"), {"i": run.id}
        )
    session.rollback()
    with pytest.raises(DBAPIError, match="immutable"):
        session.execute(text("DELETE FROM valuation_runs WHERE id=:i"), {"i": run.id})
