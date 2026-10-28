"""Every rule_id declared by an agent is documented in docs/RULES.md, and the auto-stop list
in weights.yaml matches the rules flagged auto_stop."""

from __future__ import annotations

import importlib
from pathlib import Path

from verifirm.agents.base import RuleSpec
from verifirm.core.config import get_settings
from verifirm.scoring.engine import load_scoring_config

ROOT = Path(__file__).resolve().parents[2]
AGENTS = [
    "identity",
    "financials",
    "tax",
    "litigation",
    "network",
    "sanctions",
    "media",
    "presence",
]


def all_rules() -> dict[str, RuleSpec]:
    rules: dict[str, RuleSpec] = {}
    for agent in AGENTS:
        module = importlib.import_module(f"verifirm.agents.{agent}.rules")
        for rule_id, spec in module.RULES.items():
            assert rule_id not in rules, f"duplicate rule_id {rule_id}"
            assert spec.component.value == agent
            rules[rule_id] = spec
    return rules


def test_every_rule_is_in_rules_md() -> None:
    doc = (ROOT / "docs" / "RULES.md").read_text(encoding="utf-8")
    missing = [r for r in all_rules() if f"`{r}`" not in doc]
    assert missing == []


def test_auto_stop_list_matches_rules() -> None:
    config = load_scoring_config(get_settings().scoring_config_path)
    flagged = {r for r, spec in all_rules().items() if spec.auto_stop}
    assert set(config.auto_stop_rules) == flagged
    assert not any(r.startswith("MED-") for r in flagged), "media can never trigger STOP"
