"""Media rules. Media signals are ALWAYS validated=False: max severity medium, never STOP
(enforced by the Signal model validator AND by the scoring engine)."""

from __future__ import annotations

from verifirm.agents.base import RuleSpec
from verifirm.schema.signals import Component, Severity

C = Component.MEDIA

RULES: dict[str, RuleSpec] = {
    r.rule_id: r
    for r in [
        RuleSpec(
            "MED-ADVERSE-01",
            C,
            Severity.MEDIUM,
            "Article with URL + date reports fraud, tax evasion, investigation or searches involving the company or its administrators (unvalidated)",
            "web_search",
        ),
        RuleSpec(
            "MED-NEGATIVE-01",
            C,
            Severity.LOW,
            "Article with URL + date reports other negative news (unpaid suppliers, disputes) (unvalidated)",
            "web_search",
        ),
    ]
}
