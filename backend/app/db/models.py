"""SQLAlchemy ORM models (Phase 3). See docs/phase-3-design.md.

Monetary values are stored as REAL in the owning company's currency and scale. ``NULL`` means
*missing* and is never coerced to zero (``nullable=True`` on every financial value column).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApiToken(Base):
    __tablename__ = "api_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("owner_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    sector: Mapped[str | None] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3))  # ISO 4217
    scale: Mapped[str] = mapped_column(String(20))  # units|thousands|lakhs|millions|crores|billions
    fiscal_year_end_month: Mapped[int] = mapped_column(Integer)
    is_financial_institution: Mapped[bool] = mapped_column(Boolean)
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    periods: Mapped[list[FinancialPeriod]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        order_by="FinancialPeriod.fiscal_year",
    )
    instruments: Mapped[list[ShareInstrument]] = relationship(
        back_populates="company", cascade="all, delete-orphan", order_by="ShareInstrument.id"
    )


class Source(Base):
    """Where a value came from: a CSV file, a manual entry, a synthetic sample, a filing."""

    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # csv_import|manual|synthetic|filing|assumption
    title: Mapped[str] = mapped_column(String(300))
    uri: Mapped[str | None] = mapped_column(String(1000))
    file_name: Mapped[str | None] = mapped_column(String(300))
    file_sha256: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FinancialPeriod(Base):
    __tablename__ = "financial_periods"
    __table_args__ = (UniqueConstraint("company_id", "fiscal_year"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    fiscal_year: Mapped[int] = mapped_column(Integer)
    period_end: Mapped[date] = mapped_column(Date)
    period_type: Mapped[str] = mapped_column(String(10), default="annual")

    company: Mapped[Company] = relationship(back_populates="periods")
    line_items: Mapped[list[LineItem]] = relationship(
        back_populates="period", cascade="all, delete-orphan", order_by="LineItem.item_code"
    )


class LineItem(Base):
    __tablename__ = "line_items"
    __table_args__ = (UniqueConstraint("period_id", "item_code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("financial_periods.id", ondelete="CASCADE"))
    item_code: Mapped[str] = mapped_column(String(60))
    value: Mapped[float | None] = mapped_column(Float, nullable=True)  # NULL = missing
    basis: Mapped[str] = mapped_column(String(10))  # reported|derived|assumed
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    source_ref: Mapped[str | None] = mapped_column(
        String(300)
    )  # e.g. "file.csv: row 4, col FY2024"
    original_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    original_scale: Mapped[str | None] = mapped_column(String(20))
    original_text: Mapped[str | None] = mapped_column(String(100))  # the raw cell, for audit
    note: Mapped[str | None] = mapped_column(Text)

    period: Mapped[FinancialPeriod] = relationship(back_populates="line_items")
    source: Mapped[Source] = relationship()


class ShareInstrument(Base):
    """Options, warrants, RSUs and convertibles outstanding at the latest balance-sheet date."""

    __tablename__ = "share_instruments"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))  # option|warrant|rsu|convertible
    label: Mapped[str] = mapped_column(String(100))
    count: Mapped[float | None] = mapped_column(Float)  # options/warrants/RSUs
    strike: Mapped[float | None] = mapped_column(Float)  # options/warrants
    face_value: Mapped[float | None] = mapped_column(Float)  # convertibles
    conversion_price: Mapped[float | None] = mapped_column(Float)
    coupon_rate: Mapped[float | None] = mapped_column(Float)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    source_ref: Mapped[str | None] = mapped_column(String(300))

    company: Mapped[Company] = relationship(back_populates="instruments")
    source: Mapped[Source] = relationship()


class ValuationProject(Base):
    __tablename__ = "valuation_projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    company: Mapped[Company] = relationship()
    scenarios: Mapped[list[Scenario]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Scenario.id"
    )


class Scenario(Base):
    __tablename__ = "scenarios"
    __table_args__ = (UniqueConstraint("project_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("valuation_projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))  # base|upside|downside|custom
    description: Mapped[str | None] = mapped_column(Text)
    # Market inputs and settings (dated separately from the statements, D-07)
    market_data_date: Mapped[date | None] = mapped_column(Date)
    share_price: Mapped[float | None] = mapped_column(Float)
    debt_value_basis: Mapped[str | None] = mapped_column(String(10))  # market|book
    include_leases_in_debt: Mapped[bool | None] = mapped_column(Boolean)
    market_source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    project: Mapped[ValuationProject] = relationship(back_populates="scenarios")
    assumptions: Mapped[list[Assumption]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="(Assumption.key, Assumption.year_index)",
    )


class Assumption(Base):
    __tablename__ = "assumptions"
    __table_args__ = (UniqueConstraint("scenario_id", "key", "year_index"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenarios.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(60))
    year_index: Mapped[int | None] = mapped_column(Integer)  # 1..5 for per-year drivers
    value: Mapped[float] = mapped_column(Float)  # assumptions are always explicit numbers
    basis: Mapped[str] = mapped_column(String(10), default="assumed")
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"))
    rationale: Mapped[str | None] = mapped_column(Text)

    scenario: Mapped[Scenario] = relationship(back_populates="assumptions")


class ValuationRun(Base):
    """Frozen, immutable record of one DCF execution (P3-04)."""

    __tablename__ = "valuation_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenarios.id"))
    project_id: Mapped[int] = mapped_column(ForeignKey("valuation_projects.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    label: Mapped[str | None] = mapped_column(String(200))
    engine_version: Mapped[str] = mapped_column(String(20))
    input_hash: Mapped[str] = mapped_column(String(80), index=True)
    inputs_json: Mapped[str] = mapped_column(Text)  # canonical JSON of DcfInputs
    result_json: Mapped[str] = mapped_column(Text)  # canonical JSON of DcfResult
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON)
    warnings: Mapped[list[Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(20))
    detail: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImmutableRunError(RuntimeError):
    pass


@event.listens_for(Session, "before_flush")
def _forbid_run_mutation(session: Session, _ctx: object, _instances: object) -> None:
    for obj in list(session.dirty) + list(session.deleted):
        if isinstance(obj, ValuationRun) and (obj in session.deleted or session.is_modified(obj)):
            raise ImmutableRunError(f"Valuation run {obj.id} is frozen and cannot be changed.")
