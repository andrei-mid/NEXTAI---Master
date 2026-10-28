"""Presence rules. Severities and thresholds are PROPOSALS (docs/RULES.md)."""

from __future__ import annotations

from typing import Any

from verifirm.agents.base import RuleSpec
from verifirm.schema.signals import Component, Severity

C = Component.PRESENCE

RULES: dict[str, RuleSpec] = {
    r.rule_id: r
    for r in [
        RuleSpec(
            "PRE-NO-FOOTPRINT-01",
            C,
            Severity.MEDIUM,
            "Turnover > 5M RON but no website, no job postings, no SEAP contracts and no EU funds",
            "presence sources",
        ),
        RuleSpec(
            "PRE-ADDRESS-MISMATCH-01",
            C,
            Severity.LOW,
            "Address on the company website differs from the ONRC registered office",
            "website vs onrc_bulk",
        ),
        RuleSpec(
            "PRE-PUBLIC-CONTRACTS-01",
            C,
            Severity.INFO,
            "Company has SEAP contracts or EU-funded projects (positive footprint)",
            "seap, kohesio",
        ),
    ]
}


def check_no_footprint(
    turnover_ron: int | None, footprint: dict[str, Any], min_turnover: int = 5_000_000
) -> dict[str, Any] | None:
    """PRE-NO-FOOTPRINT-01. footprint = {website, jobs, seap, kohesio}. Zephyria: 18.6M, nothing."""
    raise NotImplementedError


def check_address_mismatch(
    website_address: str | None, onrc_address: str | None
) -> dict[str, Any] | None:
    """PRE-ADDRESS-MISMATCH-01. Normalize both addresses first. None if either is missing."""
    raise NotImplementedError
