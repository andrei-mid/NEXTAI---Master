"""Scoring engine. Owner: @role-2-core.

Deterministic rules only: no LLM, no network. The same inputs + the same config version give
the same Score.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from verifirm.schema.identity import IdentitySheet
from verifirm.schema.scoring import ComponentScore, Score
from verifirm.schema.signals import AgentResult, AgentStatus, Component, Severity, Signal
from verifirm.scoring.bands import assign_band, auto_stop_signals
from verifirm.scoring.coverage import AVAILABLE_STATUSES, component_statuses, compute_coverage


class BandThresholds(BaseModel):
    grey_coverage_below: float
    red_score_below: float
    red_min_high_components: int
    yellow_score_below: float
    yellow_min_high_signals: int
    yellow_coverage_below: float
    green_requires_components: list[Component]
    green_requires_all_ok: bool = True  # any outage (unavailable/timeout/partial) blocks GREEN


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
    """1. Component score = max(0, 100 - sum(penalty[severity] * confidence * match_score)) over
          the signals of AVAILABLE results (OK / PARTIAL), after entity resolution.
    2. Trust score = weighted mean over available components, weights re-normalized
       (effective_weight). None if nothing is available.
    3. Coverage + band (coverage.py, bands.py). Band reasons are machine-readable strings.
    Invariants (tested): an outage never yields GREEN, media never yields STOP, adding a
    signal never raises a score.
    """
    statuses = component_statuses(results)
    signals_by_component: dict[Component, list[Signal]] = {c: [] for c in config.weights}
    for r in results:
        if r.status in AVAILABLE_STATUSES:
            signals_by_component.setdefault(r.component, []).extend(r.signals)

    available_weight = sum(
        w for c, w in config.weights.items() if statuses.get(c) in AVAILABLE_STATUSES
    )
    components: list[ComponentScore] = []
    weighted_sum = 0.0
    for c, weight in config.weights.items():
        status = statuses.get(c)
        available = status in AVAILABLE_STATUSES
        signals = signals_by_component.get(c, [])
        value: float | None = None
        effective = 0.0
        if available:
            value = component_score(signals, config)
            effective = weight / available_weight if available_weight else 0.0
            weighted_sum += value * effective
        components.append(
            ComponentScore(
                component=c,
                status=status if status is not None else _MISSING,
                available=available,
                score=value,
                weight=weight,
                effective_weight=round(effective, 6),
                signal_ids=[s.signal_id for s in signals],
            )
        )

    trust = round(weighted_sum, 1) if available_weight else None
    coverage = compute_coverage(results, config)
    band, reasons = assign_band(
        trust_score=trust, coverage=coverage, results=results, config=config
    )
    all_signals = [s for r in results for s in r.signals]
    return Score(
        cui=cui,
        run_id=run_id,
        trust_score=trust,
        band=band,
        band_reasons=reasons,
        components=components,
        coverage=coverage,
        auto_stop_signal_ids=[s.signal_id for s in auto_stop_signals(all_signals, config)],
        natural_person_flow=(identity.legal_form or "").upper()
        in {f.upper() for f in config.natural_person_legal_forms},
        config_version=config.version,
        computed_at=now,
    )


_MISSING = AgentStatus.UNAVAILABLE  # a component with no AgentResult at all


def component_score(signals: list[Signal], config: ScoringConfig) -> float:
    penalty = sum(
        config.penalties[s.severity] * s.confidence * s.entity_match.score for s in signals
    )
    return round(max(0.0, 100.0 - penalty), 1)
