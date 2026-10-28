"""Sanctions rules. Severities and thresholds are PROPOSALS (docs/RULES.md)."""

from __future__ import annotations

from typing import Any

from verifirm.agents.base import RuleSpec
from verifirm.schema.signals import Component, Severity

C = Component.SANCTIONS

RULES: dict[str, RuleSpec] = {
    r.rule_id: r
    for r in [
        RuleSpec(
            "SAN-MATCH-CONFIRMED-01",
            C,
            Severity.CRITICAL,
            "Company or administrator matches a sanctions entry (score >= 0.95 AND a second identifier agrees: country, birth date, registration no.)",
            "sanctions_eu, sanctions_un, sanctions_ofac",
            auto_stop=True,
        ),
        RuleSpec(
            "SAN-MATCH-POSSIBLE-01",
            C,
            Severity.MEDIUM,
            "Possible fuzzy match (0.85 <= score < 0.95, or no second identifier): human review",
            "sanctions_eu, sanctions_un, sanctions_ofac",
        ),
        RuleSpec(
            "SAN-PEP-01",
            C,
            Severity.MEDIUM,
            "Administrator/shareholder matches a PEP entry",
            "mock_pep",
        ),
    ]
}


def classify_match(
    score: float, second_identifier_agrees: bool, confirmed: float = 0.95, possible: float = 0.85
) -> str | None:
    """Return "SAN-MATCH-CONFIRMED-01", "SAN-MATCH-POSSIBLE-01" or None."""
    raise NotImplementedError


def check_pep(person_name: str, pep_entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """SAN-PEP-01."""
    raise NotImplementedError
