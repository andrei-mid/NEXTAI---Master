"""Identity sheet: who the company is, built ONLY from official sources (never the web).

FROZEN. Changing anything here needs a DECIDED entry in docs/DECISIONS.md first.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field

from verifirm.schema.signals import SourceRef

# Legal forms of natural persons: flagged and routed to a separate flow (AI Act).
NATURAL_PERSON_FORMS: frozenset[str] = frozenset({"PFA", "II", "IF"})


class CompanyStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE_ANAF = "inactive_anaf"  # fiscal inactivity declared by ANAF
    SUSPENDED = "suspended"
    IN_DISSOLUTION = "in_dissolution"
    INSOLVENCY = "insolvency"
    BANKRUPTCY = "bankruptcy"
    DEREGISTERED = "deregistered"  # radiată
    UNKNOWN = "unknown"


class PersonRole(str, Enum):
    ADMINISTRATOR = "administrator"
    LEGAL_REPRESENTATIVE = "legal_representative"
    SHAREHOLDER = "shareholder"
    CENSOR = "censor"
    OTHER = "other"


class Address(BaseModel):
    raw: str  # address exactly as the source publishes it
    county: str | None = None  # județ; "București" for Bucharest sectors
    locality: str | None = None
    street: str | None = None
    number: str | None = None
    postal_code: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None  # None = current


class Person(BaseModel):
    """A person or a company linked to the subject.

    No CNP and no personal data beyond what the source publishes.
    Shareholders are MOCK (ONRC open data has no shareholders): check `source.type`.
    """

    name: str
    role: PersonRole
    is_company: bool = False
    cui: str | None = None  # when the linked party is a company
    share_pct: float | None = Field(default=None, ge=0, le=100)
    valid_from: date | None = None
    valid_to: date | None = None  # None = current
    source: SourceRef


class CompanyName(BaseModel):
    name: str
    valid_from: date | None = None
    valid_to: date | None = None  # None = current name


class IdentitySheet(BaseModel):
    cui: str
    fictional: bool = False
    trade_register_no: str | None = None  # e.g. J40/123/2010; fictional data uses J99
    current_name: str
    names: list[CompanyName] = Field(default_factory=list)  # full history, incl. current
    legal_form: str | None = None  # SRL, SA, PFA, II, IF, ...
    status: CompanyStatus = CompanyStatus.UNKNOWN
    registration_date: date | None = None
    registered_office: Address | None = None
    office_history: list[Address] = Field(default_factory=list)
    caen_code: str | None = None  # main activity code as published
    caen_revision: str | None = None  # "rev2" | "rev3"
    authorized_caen_codes: list[str] = Field(default_factory=list)
    administrators: list[Person] = Field(default_factory=list)  # current + historical
    shareholders: list[Person] = Field(default_factory=list)  # MOCK source
    vat_registered: bool | None = None
    anaf_inactive: bool | None = None
    sources: list[SourceRef] = Field(default_factory=list)

    @property
    def is_natural_person(self) -> bool:
        return (self.legal_form or "").upper() in NATURAL_PERSON_FORMS
