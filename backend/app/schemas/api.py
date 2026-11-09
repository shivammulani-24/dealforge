"""Request/response schemas for auth, companies, projects, scenarios and instruments."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from .common import IsoDate, Num, ResponseModel, StrictModel

Scale = Literal["units", "thousands", "lakhs", "millions", "crores", "billions"]


class RegisterIn(StrictModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(max_length=200)


class LoginIn(StrictModel):
    email: str
    password: str


class TokenOut(ResponseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime


class UserOut(ResponseModel):
    id: int
    email: str


class CompanyIn(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    sector: str | None
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    scale: Scale
    fiscal_year_end_month: int = Field(ge=1, le=12)
    is_financial_institution: bool
    is_synthetic: bool


class CompanyOut(ResponseModel):
    id: int
    name: str
    sector: str | None
    currency: str
    scale: str
    fiscal_year_end_month: int
    is_financial_institution: bool
    is_synthetic: bool


class InstrumentIn(StrictModel):
    kind: Literal["option", "warrant", "rsu", "convertible"]
    label: str = Field(min_length=1, max_length=100)
    count: Num | None = None
    strike: Num | None = None
    face_value: Num | None = None
    conversion_price: Num | None = None
    coupon_rate: Num | None = None

    @model_validator(mode="after")
    def _fields_match_kind(self) -> InstrumentIn:
        needed = {
            "option": ("count", "strike"),
            "warrant": ("count", "strike"),
            "rsu": ("count",),
            "convertible": ("face_value", "conversion_price"),
        }[self.kind]
        allowed = set(needed) | ({"coupon_rate"} if self.kind == "convertible" else set())
        for f in ("count", "strike", "face_value", "conversion_price", "coupon_rate"):
            v = getattr(self, f)
            if f in needed and v is None:
                raise ValueError(f"{self.kind} requires '{f}'")
            if f not in allowed and v is not None:
                raise ValueError(f"'{f}' does not apply to a {self.kind}")
        return self


class InstrumentsIn(StrictModel):
    source_title: str = Field(min_length=1, max_length=300)
    source_ref: str | None
    instruments: list[InstrumentIn]


class ProjectIn(StrictModel):
    company_id: int
    name: str = Field(min_length=1, max_length=200)
    description: str | None


class ProjectOut(ResponseModel):
    id: int
    company_id: int
    name: str
    description: str | None


MAX_RATIONALE = 2000


def rationale_ok(text: str | None) -> bool:
    return text is not None and 0 < len(text.strip()) <= MAX_RATIONALE


class AssumptionIn(StrictModel):
    key: str
    year_index: int | None
    value: Num  # an assumption is always an explicit number
    # A6: clients may only submit "assumed" or "reported"; "derived" is computed, never entered.
    basis: Literal["assumed", "reported"] = "assumed"
    source_id: int | None = None
    rationale: str | None = None

    @model_validator(mode="after")
    def _basis_rules(self) -> AssumptionIn:
        # A5: an assumed value needs a rationale. A4: a reported value needs a linked source
        # (its owner and kind are checked by the service and, from migration 0002, the database).
        if self.basis == "assumed" and not rationale_ok(self.rationale):
            raise PydanticCustomError(
                "rationale_required",
                "An assumed value needs a rationale (1–2,000 non-blank characters).",
            )
        if self.basis == "reported" and self.source_id is None:
            raise PydanticCustomError(
                "basis_source_required", "A reported value needs a linked source_id."
            )
        return self


class ScenarioSettingsIn(StrictModel):
    market_data_date: IsoDate | None
    share_price: Num | None
    debt_value_basis: Literal["market", "book"] | None
    include_leases_in_debt: bool | None
    market_source_id: int | None = None


class ScenarioIn(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["base", "upside", "downside", "custom"]
    description: str | None = None
    settings: ScenarioSettingsIn
    assumptions: list[AssumptionIn]


class ScenarioUpdateIn(StrictModel):
    settings: ScenarioSettingsIn
    assumptions: list[AssumptionIn]


class CloneIn(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["base", "upside", "downside", "custom"]


class RunIn(StrictModel):
    label: str | None = None


class LineItemPatchIn(StrictModel):
    value: Num | None  # null = mark as missing; never coerced to 0
    note: str = Field(min_length=1, max_length=1000)
