"""Migration 0002 (plan §4.10): immutability triggers survive; basis triggers enforce A4–A6."""

from __future__ import annotations

import importlib.util
import logging
import sqlite3
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.migrate import downgrade, upgrade
from app.db.models import (
    Assumption,
    Company,
    FinancialPeriod,
    LineItem,
    Scenario,
    Source,
    User,
    ValuationProject,
    ValuationRun,
)
from app.db.session import make_engine

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "0002_run_idempotency_basis_rules.py"
)
IMMUTABILITY = {"valuation_runs_no_update", "valuation_runs_no_delete"}
BASIS = {
    f"{name}_{ev}"
    for name in (
        "line_items_basis_rules",
        "assumptions_basis_rules",
        "scenarios_market_basis_rules",
    )
    for ev in ("insert", "update")
}


def triggers(url: str) -> set[str]:
    engine = make_engine(url)
    with engine.connect() as c:
        rows = c.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='trigger'").all()
    engine.dispose()
    return {r[0] for r in rows}


def columns(url: str, table: str) -> set[str]:
    engine = make_engine(url)
    with engine.connect() as c:
        rows = c.exec_driver_sql(f"PRAGMA table_info({table})").all()
    engine.dispose()
    return {r[1] for r in rows}


def raw(url: str) -> sqlite3.Connection:
    con = sqlite3.connect(url.removeprefix("sqlite:///"), isolation_level=None)
    con.execute("PRAGMA foreign_keys=ON")
    return con


def test_upgrade_adds_columns_indexes_and_triggers(db_url: str) -> None:
    assert {"idempotency_key", "request_fingerprint", "inputs_schema_version"} <= columns(
        db_url, "valuation_runs"
    )
    assert "market_rationale" in columns(db_url, "scenarios")
    assert triggers(db_url) == IMMUTABILITY | BASIS
    con = raw(db_url)
    idx = {r[1]: r[2] for r in con.execute("PRAGMA index_list(valuation_runs)")}
    assert idx["uq_runs_owner_idempotency"] == 1  # unique
    assert "ix_runs_owner_created" in idx
    con.close()


def test_downgrade_keeps_immutability_triggers_and_round_trips(db_url: str) -> None:
    downgrade(db_url, "0001")
    assert triggers(db_url) == IMMUTABILITY  # native DROP COLUMN: no table rebuild
    assert "idempotency_key" not in columns(db_url, "valuation_runs")
    assert "market_rationale" not in columns(db_url, "scenarios")
    upgrade(db_url)
    assert triggers(db_url) == IMMUTABILITY | BASIS


def seed(session: Session) -> dict[str, int]:
    u = User(email="a@example.com", password_hash="x")
    other = User(email="b@example.com", password_hash="x")
    session.add_all([u, other])
    session.flush()
    c = Company(
        owner_id=u.id,
        name="Co (SYNTHETIC)",
        currency="INR",
        scale="crores",
        fiscal_year_end_month=3,
        is_financial_institution=False,
        is_synthetic=True,
    )
    session.add(c)
    session.flush()
    p = FinancialPeriod(company_id=c.id, fiscal_year=2025, period_end=date(2025, 3, 31))
    srcs = {
        k: Source(owner_id=u.id, kind=k, title=k)
        for k in ("csv_import", "filing", "market_data", "synthetic", "manual")
    }
    foreign = Source(owner_id=other.id, kind="filing", title="theirs")
    session.add_all([p, foreign, *srcs.values()])
    session.flush()
    pr = ValuationProject(owner_id=u.id, company_id=c.id, name="P")
    session.add(pr)
    session.flush()
    sc = Scenario(project_id=pr.id, name="Base", kind="base")
    session.add(sc)
    session.commit()
    ids = {f"src_{k}": s.id for k, s in srcs.items()}
    ids.update(period=p.id, scenario=sc.id, project=pr.id, foreign=foreign.id)
    return ids


def rejects(con: sqlite3.Connection, sql: str, params: tuple[object, ...]) -> bool:
    try:
        con.execute(sql, params)
    except sqlite3.IntegrityError as exc:
        return "violates" in str(exc)
    return False


LI = "INSERT INTO line_items (period_id, item_code, value, basis, source_id, note) VALUES (?,?,?,?,?,?)"
AS = (
    "INSERT INTO assumptions (scenario_id, key, year_index, value, basis, source_id, rationale) "
    "VALUES (?,?,?,?,?,?,?)"
)


def test_line_item_triggers_reject_direct_sql(session: Session, db_url: str) -> None:
    ids = seed(session)
    con = raw(db_url)
    p = ids["period"]
    for kind in ("csv_import", "filing", "market_data", "synthetic"):  # A4 qualifying kinds
        con.execute(LI, (p, f"x_{kind}", 1.0, "reported", ids[f"src_{kind}"], None))
    assert rejects(con, LI, (p, "a", 1.0, "reported", ids["src_manual"], None))  # A4 kind
    assert rejects(con, LI, (p, "b", 1.0, "reported", ids["foreign"], None))  # A4 owner
    assert rejects(con, LI, (p, "c", 1.0, "derived", ids["src_filing"], None))  # A6
    assert rejects(con, LI, (p, "d", 1.0, "assumed", ids["src_manual"], "   "))  # A5
    con.execute(LI, (p, "e", None, "assumed", ids["src_manual"], "analyst estimate"))
    assert rejects(con, "UPDATE line_items SET basis='derived' WHERE item_code='e'", ())
    assert rejects(con, "UPDATE line_items SET basis='reported' WHERE item_code='e'", ())
    con.close()


def test_assumption_and_market_triggers_reject_direct_sql(session: Session, db_url: str) -> None:
    ids = seed(session)
    con = raw(db_url)
    s = ids["scenario"]
    con.execute(AS, (s, "tax_rate", None, 0.25, "assumed", None, "normalised"))
    con.execute(AS, (s, "terminal_growth", None, 0.02, "reported", ids["src_filing"], None))
    assert rejects(con, AS, (s, "levered_beta", None, 1.1, "assumed", None, None))  # A5
    assert rejects(con, AS, (s, "levered_beta", None, 1.1, "reported", None, None))  # A4
    assert rejects(con, AS, (s, "levered_beta", None, 1.1, "reported", ids["src_manual"], None))
    assert rejects(con, AS, (s, "levered_beta", None, 1.1, "reported", ids["foreign"], None))
    assert rejects(con, AS, (s, "levered_beta", None, 1.1, "derived", None, "x"))  # A6
    upd = "UPDATE scenarios SET share_price=?, market_source_id=?, market_rationale=? WHERE id=?"
    assert rejects(con, upd, (20.0, None, None, s))  # A5: price with neither source nor reason
    assert rejects(con, upd, (20.0, ids["src_manual"], None, s))  # A4: manual can't back it
    con.execute(upd, (20.0, None, "synthetic price", s))
    con.execute(upd, (20.0, ids["src_market_data"], None, s))
    con.close()


def test_orm_writes_are_checked_too(session: Session) -> None:
    ids = seed(session)
    session.add(
        LineItem(
            period_id=ids["period"],
            item_code="z",
            value=1.0,
            basis="reported",
            source_id=ids["src_manual"],
        )
    )
    with pytest.raises(Exception, match="violates"):
        session.commit()
    session.rollback()
    session.add(
        Assumption(
            scenario_id=ids["scenario"],
            key="tax_rate",
            year_index=None,
            value=0.25,
            basis="assumed",
            rationale="",
        )
    )
    with pytest.raises(Exception, match="violates"):
        session.commit()


def test_immutability_still_enforced_after_0002(session: Session, db_url: str) -> None:
    ids = seed(session)
    user_id = session.execute(text("SELECT id FROM users LIMIT 1")).scalar_one()
    session.add(
        ValuationRun(
            scenario_id=ids["scenario"],
            project_id=ids["project"],
            created_by=user_id,
            engine_version="0.1.0",
            input_hash="h",
            inputs_json="{}",
            result_json="{}",
            provenance={},
            warnings=[],
            idempotency_key="k-00000001",
            request_fingerprint="f",
        )
    )
    session.commit()
    con = raw(db_url)
    for sql in ("UPDATE valuation_runs SET result_json='x'", "DELETE FROM valuation_runs"):
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            con.execute(sql)
    con.close()


def test_precheck_lists_legacy_violations_without_changing_them(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    url = f"sqlite:///{tmp_path / 'legacy.sqlite3'}"
    upgrade(url, "0001")
    con = raw(url)
    con.execute(
        "INSERT INTO users (email, password_hash, created_at) VALUES ('a@x.io','x','2026-01-01')"
    )
    con.execute(
        "INSERT INTO companies (owner_id, name, currency, scale, fiscal_year_end_month,"
        " is_financial_institution, is_synthetic, created_at) VALUES "
        "(1,'C','INR','crores',3,0,1,'2026-01-01')"
    )
    con.execute(
        "INSERT INTO sources (owner_id, kind, title, created_at) VALUES "
        "(1,'manual','m','2026-01-01')"
    )
    con.execute(
        "INSERT INTO financial_periods (company_id, fiscal_year, period_end, period_type)"
        " VALUES (1, 2025, '2025-03-31', 'annual')"
    )
    con.execute(LI, (1, "revenue", 100.0, "reported", 1, None))  # legal in 0001, not in 0002
    con.close()

    spec = importlib.util.spec_from_file_location("mig0002", MIGRATION)
    assert spec is not None and spec.loader is not None
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)
    engine = make_engine(url)
    with engine.connect() as c:
        assert mig.precheck(c) == {"line_items": [1], "assumptions": []}
    engine.dispose()

    with caplog.at_level(logging.WARNING):
        upgrade(url)  # 0001 -> 0002
    assert any(
        "pre-check" in r.getMessage() and "line_items" in r.getMessage() for r in caplog.records
    )
    con = raw(url)
    assert con.execute("SELECT value, basis, source_id FROM line_items").fetchall() == [
        (100.0, "reported", 1)
    ]  # left unchanged (LIM-28)
    assert rejects(con, "UPDATE line_items SET value = 101 WHERE id = 1", ())  # now guarded
    con.close()
