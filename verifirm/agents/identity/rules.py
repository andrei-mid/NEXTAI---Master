"""Identity rules. Severities are PROPOSALS (docs/RULES.md). Thresholds come from settings/config.

Each check is a pure function: facts in -> Signal-ready facts out (or None). No I/O here.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from verifirm.agents.base import RuleSpec
from verifirm.schema.signals import Component, Severity

C = Component.IDENTITY

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
            "ONRC status is not active (dissolution, suspension, deregistered...)",
            "onrc_bulk",
        ),
        RuleSpec(
            "ID-NATURAL-PERSON-01",
            C,
            Severity.INFO,
            "Legal form PFA/II/IF: route to the natural-person flow (AI Act)",
            "onrc_bulk, anaf_v9",
        ),
    ]
}


def check_inactive(v9_record: dict[str, Any]) -> dict[str, Any] | None:
    """ID-INACTIVE-01. Input: an anaf_v9 found[] record. Return facts {inactive_since} or None."""
    raise NotImplementedError


def check_reactivated(
    v9_record: dict[str, Any], today: date, window_days: int = 365
) -> dict[str, Any] | None:
    """ID-REACTIVATED-01. Use stare_inactiv.dataReactivare within window_days."""
    raise NotImplementedError


def check_admin_change(
    administrators: list[dict[str, Any]], today: date, window_days: int = 365
) -> dict[str, Any] | None:
    """ID-ADMIN-CHANGE-01. Facts: {previous, current, changed_on}. Zephyria: 2025-11-02."""
    raise NotImplementedError


def check_office_change(
    office_history: list[dict[str, Any]], today: date, window_days: int = 365
) -> dict[str, Any] | None:
    """ID-OFFICE-CHANGE-01."""
    raise NotImplementedError


def check_shared_office(n_companies_at_address: int, threshold: int = 20) -> dict[str, Any] | None:
    """ID-SHARED-OFFICE-01. Zephyria's office is shared by 63 companies."""
    raise NotImplementedError


def check_caen_authorized(
    main_caen: str, authorized: list[str], rev2_to_rev3: dict[str, list[str]]
) -> dict[str, Any] | None:
    """ID-CAEN-UNAUTH-01. Compare in BOTH revisions: a Rev.2 main code is authorized if any
    mapped Rev.3 code is authorized, and vice versa."""
    raise NotImplementedError


def check_status(onrc_status: str) -> dict[str, Any] | None:
    """ID-STATUS-01."""
    raise NotImplementedError


def check_natural_person(legal_form: str | None) -> dict[str, Any] | None:
    """ID-NATURAL-PERSON-01. Uses schema.identity.NATURAL_PERSON_FORMS."""
    raise NotImplementedError
