"""Scoring engine. Config loading is real. `score()` is a STUB (owner: scoring area).

Deterministic rules only. The same inputs + the same config version give the same Score.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from verifirm.schema.identity import IdentitySheet
from verifirm.schema.scoring import Score
from verifirm.schema.signals import AgentResult, Component, Severity


class BandThresholds(BaseModel):
    grey_coverage_below: float
    red_score_below: float
    red_min_high_components: int
    yellow_score_below: float
    yellow_min_high_signals: int
    yellow_coverage_below: float
    green_requires_components: list[Component]


class ScoringConfig(BaseModel):
    version: str
    weights: dict[Component, float]
    penalties: dict[Severity, float]
    bands: BandThresholds
    auto_stop_rules: list[str]
    never_stop_components: list[Component] = Field(default_factory=list)
    natural_person_legal_forms: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _complete(self) -> ScoringConfig:
        if set(self.weights) != set(Component):
            raise ValueError("weights must list every component exactly once")
        if abs(sum(self.weights.values()) - 100) > 1e-6:
            raise ValueError("weights must sum to 100")
        if set(self.penalties) != set(Severity):
            raise ValueError("penalties must list every severity")
        return self


def load_scoring_config(path: Path) -> ScoringConfig:
    return ScoringConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def score(
    *,
    cui: str,
    run_id: str,
    identity: IdentitySheet,
    results: list[AgentResult],
    config: ScoringConfig,
    now: datetime,
) -> Score:
    """STUB. Implement:

    1. Per component (coverage.py decides availability: status OK or PARTIAL):
       component score = max(0, 100 - sum(penalties[s.severity] * s.confidence * s.entity_match.score))
       over that component's signals (after entity resolution).
    2. Trust score = weighted mean over AVAILABLE components with re-normalized weights
       (effective_weight). None if nothing is available.
    3. Coverage = coverage.compute_coverage(results, config).
    4. Band = bands.assign_band(...). The order is STOP > GREY > RED > YELLOW > GREEN. See weights.yaml.
    5. natural_person_flow = identity.legal_form in config.natural_person_legal_forms.
    6. band_reasons: machine-readable strings, e.g. "AUTO_STOP:ID-INACTIVE-01",
       "COVERAGE<80", "HIGH_SIGNALS:tax,financials", "SCORE<50".
    Invariants (write tests): a source outage can never produce GREEN; media can never produce
    STOP; adding a signal can never raise the score.
    """
    raise NotImplementedError
