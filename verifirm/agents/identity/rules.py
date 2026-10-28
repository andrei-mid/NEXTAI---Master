"""Identity rules. Severities are PROPOSALS (docs/RULES.md). Thresholds come from settings/config.

Each check is a pure function: facts in -> Signal-ready facts out (or None). No I/O here.
`None` means "checked and nothing found". Input that can't be checked (missing blocks, empty
lists) raises ValueError so the agent reports the source as failed instead of clean.

Source authority (which source wins per fact): legal status and administrators -> ONRC;
fiscal inactivity, VAT, e-Factura -> ANAF; deregistration -> both (a real cross-check).
ANAF "INREGISTRAT" next to ONRC "faliment" is NOT a conflict: a company stays a registered
taxpayer during insolvency and bankruptcy, until it is deregistered.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from verifirm.agents.base import RuleSpec
from verifirm.schema.identity import NATURAL_PERSON_FORMS, CompanyStatus
from verifirm.schema.signals import Component, Severity

C = Component.IDENTITY
CONFIG_PATH = Path(__file__).with_name("config.yaml")

RULES: dict[str, RuleSpec] = {
    r.rule_id: r
    for r in [
        RuleSpec(
            "ID-INACTIVE-01",
            C,
            Severity.CRITICAL,
            "ANAF declares the company fiscally inactive (stare_inactiv.statusInactivi = true)",
            "anaf_v9",
            auto_stop=True,
        ),
        RuleSpec(
            "ID-REACTIVATED-01",
            C,
            Severity.MEDIUM,
            "Company reactivated by ANAF in the last 12 months (dataReactivare)",
            "anaf_v9",
        ),
        RuleSpec(
            "ID-ADMIN-CHANGE-01",
            C,
            Severity.MEDIUM,
            "Administrator changed in the last 12 months",
            "onrc_bulk",
        ),
        RuleSpec(
            "ID-OFFICE-CHANGE-01",
            C,
            Severity.LOW,
            "Registered office changed in the last 12 months",
            "onrc_bulk, anaf_v9",
        ),
        RuleSpec(
            "ID-SHARED-OFFICE-01",
            C,
            Severity.MEDIUM,
            "Registered office shared by >= 20 companies (threshold configurable)",
            "onrc_bulk",
        ),
        RuleSpec(
            "ID-CAEN-UNAUTH-01",
            C,
            Severity.MEDIUM,
            "Main CAEN activity not among authorized CAEN codes (Rev.2<->Rev.3 mapped)",
            "onrc_bulk",
        ),
        RuleSpec(
            "ID-STATUS-01",
            C,
            Severity.HIGH,
            "ONRC status is not active (dissolution, suspension, deregistered...); "
            "severity per status, ANAF deregistration cross-checked",
            "onrc_bulk, anaf_v9",
        ),
        RuleSpec(
            "ID-NATURAL-PERSON-01",
            C,
            Severity.INFO,
            "Legal form PFA/II/IF: route to the natural-person flow (AI Act)",
            "onrc_bulk, anaf_v9",
        ),
        RuleSpec(
            "ID-SOURCE-MISMATCH-01",
            C,
            Severity.HIGH,
            "ANAF and ONRC disagree on CUI, register number or name (possible wrong entity)",
            "anaf_v9, onrc_bulk",
        ),
    ]
}


class IdentityConfig(BaseModel):
    """Thresholds from config.yaml (PROPOSAL)."""

    window_days: int = Field(gt=0)
    shared_office_min_companies: int = Field(gt=1)
    conflict_confidence: float = Field(ge=0, le=1)
    stale_confidence: float = Field(ge=0, le=1)


def load_config(path: Path = CONFIG_PATH) -> IdentityConfig:
    return IdentityConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


# ID-STATUS-01 severity per status (PROPOSAL). Unknown statuses take the rule default (high):
# the analyst must check them, they are never treated as active.
STATUS_SEVERITY: dict[CompanyStatus, Severity] = {
    CompanyStatus.DEREGISTERED: Severity.CRITICAL,
    CompanyStatus.BANKRUPTCY: Severity.CRITICAL,
    CompanyStatus.INSOLVENCY: Severity.HIGH,
    CompanyStatus.IN_DISSOLUTION: Severity.HIGH,
    CompanyStatus.SUSPENDED: Severity.MEDIUM,
    CompanyStatus.UNKNOWN: Severity.HIGH,
}

# ONRC status text (normalized) -> status. Order matters: first keyword found wins, most
# severe first ("radiata" can appear next to "dizolvare" in long status strings).
_ONRC_STATUS_KEYWORDS: tuple[tuple[str, CompanyStatus], ...] = (
    ("radiat", CompanyStatus.DEREGISTERED),
    ("faliment", CompanyStatus.BANKRUPTCY),
    ("insolvent", CompanyStatus.INSOLVENCY),
    ("reorganizare", CompanyStatus.INSOLVENCY),
    ("dizolv", CompanyStatus.IN_DISSOLUTION),
    ("lichidare", CompanyStatus.IN_DISSOLUTION),
    ("suspend", CompanyStatus.SUSPENDED),
    ("intrerupere", CompanyStatus.SUSPENDED),
    ("functiune", CompanyStatus.ACTIVE),
    ("activ", CompanyStatus.ACTIVE),
)

# ANAF publishes the legal form in full words; ONRC uses the abbreviation.
_NATURAL_PERSON_LONG_FORMS: dict[str, str] = {
    "PERSOANA FIZICA AUTORIZATA": "PFA",
    "INTREPRINDERE INDIVIDUALA": "II",
    "INTREPRINDERE FAMILIALA": "IF",
}

_OLD_REG_NO = re.compile(r"^J\d{2}/\d+/\d{4}$")


# ---------------------------------------------------------------------------- helpers
def _fold(text: str) -> str:
    """Uppercase, no diacritics, single spaces. For comparing official text across sources."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.upper().split())


def _as_date(value: Any) -> date | None:
    """date, ISO string or empty -> date | None. ANAF uses "" for "no date"."""
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _within(day: date | None, today: date, window_days: int) -> bool:
    return day is not None and 0 <= (today - day).days <= window_days


def _stare_inactiv(v9_record: dict[str, Any]) -> dict[str, Any]:
    block = v9_record.get("stare_inactiv")
    if not isinstance(block, dict) or "statusInactivi" not in block:
        raise ValueError("anaf_v9 record has no stare_inactiv.statusInactivi")
    return block


def _latest_change(history: list[dict[str, Any]], today: date, window_days: int) -> date | None:
    """Most recent change date in a valid_from/valid_to history, within the window.

    The earliest valid_from is the initial entry (registration), not a change. An end date
    without a replacement (resignation) still counts as a change.
    """
    starts = [d for d in (_as_date(h.get("valid_from")) for h in history) if d is not None]
    first = min(starts) if starts else None
    events = [d for d in starts if d != first]
    events += [d for d in (_as_date(h.get("valid_to")) for h in history) if d is not None]
    recent = [d for d in events if _within(d, today, window_days)]
    return max(recent) if recent else None


def _current(history: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    out = []
    for h in history:
        start, end = _as_date(h.get("valid_from")), _as_date(h.get("valid_to"))
        if (start is None or start <= today) and (end is None or end > today):
            out.append(h)
    return out


def _caen(code: str) -> str:
    """CAEN codes as 4 digits, no dots/spaces ("01.11" and "111" -> "0111")."""
    digits = re.sub(r"\D", "", code)
    return digits.zfill(4) if digits else ""


# ------------------------------------------------------------------------------ rules
def check_inactive(v9_record: dict[str, Any]) -> dict[str, Any] | None:
    """ID-INACTIVE-01. Input: an anaf_v9 found[] record. Return facts {inactive_since} or None."""
    block = _stare_inactiv(v9_record)
    if block["statusInactivi"] is not True:
        return None
    return {
        "inactive_since": _as_date(block.get("dataInactivare")),
        "published_on": _as_date(block.get("dataPublicare")),
    }


def check_reactivated(
    v9_record: dict[str, Any], today: date, window_days: int = 365
) -> dict[str, Any] | None:
    """ID-REACTIVATED-01. Use stare_inactiv.dataReactivare within window_days."""
    block = _stare_inactiv(v9_record)
    reactivated_on = _as_date(block.get("dataReactivare"))
    if not _within(reactivated_on, today, window_days):
        return None
    return {
        "reactivated_on": reactivated_on,
        "inactive_since": _as_date(block.get("dataInactivare")),
        "window_days": window_days,
    }


def check_admin_change(
    administrators: list[dict[str, Any]], today: date, window_days: int = 365
) -> dict[str, Any] | None:
    """ID-ADMIN-CHANGE-01. Facts: {previous, current, changed_on}. Zephyria: 2025-11-02.

    `administrators`: [{name, valid_from, valid_to}] (current + historical, dates or ISO).
    """
    if not administrators:
        raise ValueError("no administrators to check")
    changed_on = _latest_change(administrators, today, window_days)
    if changed_on is None:
        return None
    return {
        "previous": sorted(
            a["name"] for a in administrators if _as_date(a.get("valid_to")) == changed_on
        ),
        "current": sorted(a["name"] for a in _current(administrators, today)),
        "changed_on": changed_on,
        "window_days": window_days,
    }


def check_office_change(
    office_history: list[dict[str, Any]], today: date, window_days: int = 365
) -> dict[str, Any] | None:
    """ID-OFFICE-CHANGE-01. `office_history`: [{address, valid_from, valid_to}]."""
    if not office_history:
        raise ValueError("no office history to check")
    changed_on = _latest_change(office_history, today, window_days)
    if changed_on is None:
        return None
    previous = [o["address"] for o in office_history if _as_date(o.get("valid_to")) == changed_on]
    current = [o["address"] for o in _current(office_history, today)]
    return {
        "previous": previous[0] if previous else None,
        "current": current[0] if current else None,
        "changed_on": changed_on,
        "window_days": window_days,
    }


def check_shared_office(n_companies_at_address: int, threshold: int = 20) -> dict[str, Any] | None:
    """ID-SHARED-OFFICE-01. Zephyria's office is shared by 63 companies.

    The count includes the company itself (it is what ONRC lists at that address).
    """
    if n_companies_at_address < threshold:
        return None
    return {"n_companies": n_companies_at_address, "threshold": threshold}


def check_caen_authorized(
    main_caen: str, authorized: list[str], rev2_to_rev3: dict[str, list[str]]
) -> dict[str, Any] | None:
    """ID-CAEN-UNAUTH-01. Compare in BOTH revisions: a Rev.2 main code is authorized if any
    mapped Rev.3 code is authorized, and vice versa."""
    main = _caen(main_caen)
    allowed = {_caen(c) for c in authorized} - {""}
    if not main or not allowed:
        raise ValueError("main CAEN or authorized CAEN list missing")
    mapping = {_caen(k): {_caen(v) for v in vs} for k, vs in rev2_to_rev3.items()}
    equivalents = mapping.get(main, set()) | {r2 for r2, r3s in mapping.items() if main in r3s}
    if (equivalents | {main}) & allowed:
        return None
    return {
        "main_caen": main,
        "authorized": sorted(allowed),
        "mapped_equivalents": sorted(equivalents),
    }


def check_status(
    onrc_status: str, anaf_deregistered_on: date | str | None = None
) -> dict[str, Any] | None:
    """ID-STATUS-01. ONRC is the authority for legal status; deregistration is cross-checked
    with ANAF (stare_inactiv.dataRadiere). If they disagree, the worse value wins and
    `sources_agree` is False (the agent lowers confidence). Severity: STATUS_SEVERITY[status].
    """
    if not onrc_status or not onrc_status.strip():
        raise ValueError("empty ONRC status")
    folded = _fold(onrc_status).lower()
    status = next((s for kw, s in _ONRC_STATUS_KEYWORDS if kw in folded), CompanyStatus.UNKNOWN)
    anaf_dereg = _as_date(anaf_deregistered_on)
    onrc_dereg = status is CompanyStatus.DEREGISTERED
    sources_agree = onrc_dereg == (anaf_dereg is not None)
    if anaf_dereg is not None:
        status = CompanyStatus.DEREGISTERED  # worse value wins
    if status is CompanyStatus.ACTIVE:
        return None
    return {
        "status": status.value,
        "onrc_status": onrc_status,
        "anaf_deregistered_on": anaf_dereg,
        "sources_agree": sources_agree,
    }


def status_severity(facts: dict[str, Any]) -> Severity:
    """Severity for an ID-STATUS-01 hit (pass to BaseAgent.signal(severity=...))."""
    return STATUS_SEVERITY.get(CompanyStatus(facts["status"]), RULES["ID-STATUS-01"].severity)


def check_natural_person(legal_form: str | None) -> dict[str, Any] | None:
    """ID-NATURAL-PERSON-01. Uses schema.identity.NATURAL_PERSON_FORMS.

    Accepts the ONRC abbreviation (PFA) or ANAF's full wording (PERSOANA FIZICA AUTORIZATA).
    """
    if not legal_form:
        return None
    folded = _fold(legal_form).replace(".", "")
    form = folded if folded in NATURAL_PERSON_FORMS else None
    for long_form, short in _NATURAL_PERSON_LONG_FORMS.items():
        if long_form in folded:
            form = short
    if form is None:
        return None
    return {"legal_form": form, "published_as": legal_form}


def check_source_mismatch(v9_record: dict[str, Any], onrc: dict[str, Any]) -> dict[str, Any] | None:
    """ID-SOURCE-MISMATCH-01. Identity keys that must agree between ANAF v9 and ONRC.

    `onrc`: {cui, trade_register_no, name}. Names compare without diacritics, dots and case.
    Register numbers compare only when both use the old Jxx/nnn/yyyy format: ONRC moved to a
    new numbering in 2024 and ANAF may still show the old one, which is not a mismatch.
    """
    general = v9_record.get("date_generale")
    if not isinstance(general, dict):
        raise ValueError("anaf_v9 record has no date_generale")

    def _name(n: Any) -> str:
        return _fold(str(n or "")).replace(".", "").replace(" ", "")

    mismatches: dict[str, dict[str, Any]] = {}
    anaf_cui, onrc_cui = str(general.get("cui", "")).strip(), str(onrc.get("cui", "")).strip()
    if anaf_cui and onrc_cui and anaf_cui != onrc_cui:
        mismatches["cui"] = {"anaf": anaf_cui, "onrc": onrc_cui}

    anaf_reg = _fold(str(general.get("nrRegCom") or "")).replace(" ", "")
    onrc_reg = _fold(str(onrc.get("trade_register_no") or "")).replace(" ", "")
    if _OLD_REG_NO.match(anaf_reg) and _OLD_REG_NO.match(onrc_reg) and anaf_reg != onrc_reg:
        mismatches["trade_register_no"] = {"anaf": anaf_reg, "onrc": onrc_reg}

    anaf_name, onrc_name = general.get("denumire"), onrc.get("name")
    if anaf_name and onrc_name and _name(anaf_name) != _name(onrc_name):
        mismatches["name"] = {"anaf": anaf_name, "onrc": onrc_name}

    return {"mismatches": mismatches} if mismatches else None
