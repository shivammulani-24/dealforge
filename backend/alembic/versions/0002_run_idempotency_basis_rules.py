"""Run idempotency, inputs schema version, indexes, market rationale and basis-rule triggers.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-09

Hand-written (docs/phase-4-plan.md §4.10, conflict C3): only native ``ALTER TABLE ADD COLUMN``,
``CREATE INDEX`` and ``CREATE TRIGGER`` are used. Autogenerate would emit a batch table rebuild
of ``valuation_runs`` that silently drops its two immutability triggers. ``ADD COLUMN`` is not an
``UPDATE``, so those triggers neither fire nor change. The downgrade uses native
``DROP COLUMN`` (SQLite ≥ 3.35), which also leaves them in place.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

log = logging.getLogger("alembic.runtime.migration")

REPORTED_KINDS = "('csv_import', 'filing', 'market_data', 'synthetic')"

# Each trigger raises when a row breaks a basis rule (A4: reported needs a qualifying source owned
# by the same user; A5: assumed needs a rationale; A6: only 'reported' or 'assumed' are stored).
LINE_ITEM_VIOLATION = f"""
    NEW.basis NOT IN ('reported', 'assumed')
    OR (NEW.basis = 'reported' AND (
          COALESCE((SELECT kind FROM sources WHERE id = NEW.source_id), '') NOT IN {REPORTED_KINDS}
          OR (SELECT owner_id FROM sources WHERE id = NEW.source_id) IS NOT
             (SELECT c.owner_id FROM financial_periods fp JOIN companies c ON c.id = fp.company_id
              WHERE fp.id = NEW.period_id)))
    OR (NEW.basis = 'assumed' AND TRIM(COALESCE(NEW.note, '')) = '')
"""
ASSUMPTION_VIOLATION = f"""
    NEW.basis NOT IN ('reported', 'assumed')
    OR (NEW.basis = 'reported' AND (
          NEW.source_id IS NULL
          OR COALESCE((SELECT kind FROM sources WHERE id = NEW.source_id), '') NOT IN {REPORTED_KINDS}
          OR (SELECT owner_id FROM sources WHERE id = NEW.source_id) IS NOT
             (SELECT p.owner_id FROM scenarios s JOIN valuation_projects p ON p.id = s.project_id
              WHERE s.id = NEW.scenario_id)))
    OR (NEW.basis = 'assumed' AND TRIM(COALESCE(NEW.rationale, '')) = '')
"""
SCENARIO_VIOLATION = f"""
    (NEW.share_price IS NOT NULL AND NEW.market_source_id IS NULL
       AND TRIM(COALESCE(NEW.market_rationale, '')) = '')
    OR (NEW.market_source_id IS NOT NULL AND (
          COALESCE((SELECT kind FROM sources WHERE id = NEW.market_source_id), '')
             NOT IN {REPORTED_KINDS}
          OR (SELECT owner_id FROM sources WHERE id = NEW.market_source_id) IS NOT
             (SELECT owner_id FROM valuation_projects WHERE id = NEW.project_id)))
"""
TRIGGERS = [
    ("line_items", "line_items_basis_rules", LINE_ITEM_VIOLATION, "line item basis rule (A4-A6)"),
    (
        "assumptions",
        "assumptions_basis_rules",
        ASSUMPTION_VIOLATION,
        "assumption basis rule (A4-A6)",
    ),
    (
        "scenarios",
        "scenarios_market_basis_rules",
        SCENARIO_VIOLATION,
        "market input basis rule (A4/A5)",
    ),
]


def _create_basis_triggers() -> None:
    for table, name, condition, label in TRIGGERS:
        for event in ("INSERT", "UPDATE"):
            op.execute(
                f"CREATE TRIGGER {name}_{event.lower()} BEFORE {event} ON {table} "
                f"WHEN {condition} BEGIN SELECT RAISE(ABORT, 'violates {label}'); END"
            )


def _drop_basis_triggers() -> None:
    for _table, name, _condition, _label in TRIGGERS:
        for event in ("insert", "update"):
            op.execute(f"DROP TRIGGER IF EXISTS {name}_{event}")


PRECHECK_QUERIES = {
    "line_items": f"SELECT id FROM line_items NEW WHERE {LINE_ITEM_VIOLATION}",
    "assumptions": f"SELECT id FROM assumptions NEW WHERE {ASSUMPTION_VIOLATION}",
}


def precheck(bind: sa.Connection) -> dict[str, list[int]]:
    """Read-only: existing rows that would violate the new rules (they are not rewritten)."""
    return {t: [r[0] for r in bind.exec_driver_sql(q)] for t, q in PRECHECK_QUERIES.items()}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":  # pragma: no cover - PostgreSQL triggers are LIM-18
        raise NotImplementedError("0002 basis triggers are written for SQLite (LIM-18)")
    op.add_column("valuation_runs", sa.Column("idempotency_key", sa.String(128), nullable=True))
    op.add_column("valuation_runs", sa.Column("request_fingerprint", sa.String(80), nullable=True))
    op.add_column(
        "valuation_runs",
        sa.Column("inputs_schema_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("scenarios", sa.Column("market_rationale", sa.Text(), nullable=True))
    op.create_index(
        "uq_runs_owner_idempotency",
        "valuation_runs",
        ["created_by", "idempotency_key"],
        unique=True,
    )
    op.create_index("ix_runs_owner_created", "valuation_runs", ["created_by", "created_at"])
    op.create_index("ix_audit_user_created", "audit_events", ["user_id", "created_at"])
    found = precheck(bind)
    for table, ids in found.items():
        if ids:
            log.warning(
                "0002 pre-check: %d existing %s row(s) break the basis rules and are "
                "left unchanged (LIM-28): ids %s",
                len(ids),
                table,
                ids[:50],
            )
    _create_basis_triggers()


def downgrade() -> None:
    _drop_basis_triggers()
    op.drop_index("ix_audit_user_created", table_name="audit_events")
    op.drop_index("ix_runs_owner_created", table_name="valuation_runs")
    op.drop_index("uq_runs_owner_idempotency", table_name="valuation_runs")
    # Native DROP COLUMN (no table rebuild): the immutability triggers stay in place.
    for table, column in (
        ("scenarios", "market_rationale"),
        ("valuation_runs", "inputs_schema_version"),
        ("valuation_runs", "request_fingerprint"),
        ("valuation_runs", "idempotency_key"),
    ):
        op.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
