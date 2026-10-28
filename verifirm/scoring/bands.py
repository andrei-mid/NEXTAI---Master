"""STUB. Owner: @role-2-core. Band assignment (deterministic, config-driven)."""

from __future__ import annotations

from verifirm.schema.scoring import Band, Coverage
from verifirm.schema.signals import AgentResult, Signal
from verifirm.scoring.engine import ScoringConfig


def auto_stop_signals(signals: list[Signal], config: ScoringConfig) -> list[Signal]:
    """Signals that force STOP: validated, auto_stop_candidate, rule_id in config.auto_stop_rules,
    component NOT in config.never_stop_components (media can never STOP)."""
    raise NotImplementedError


def assign_band(
    *,
    trust_score: float | None,
    coverage: Coverage,
    results: list[AgentResult],
    config: ScoringConfig,
) -> tuple[Band, list[str]]:
    """Return (band, reasons). Order:
    STOP   any auto-stop signal
    GREY   coverage < 60%
    RED    score < 50, or >= 2 HIGH signals in different components
    YELLOW 50-74, or 1 HIGH signal, or coverage < 80%
    GREEN  >= 75, no high/critical, coverage >= 80%, identity AND sanctions available
    Anything that doesn't qualify for GREEN is at least YELLOW: an outage never yields GREEN.
    Expected demo bands: Dedeman GREEN (8/8), Aurora GREEN, Zephyria RED, Brunaldo RED,
    Dedeman with one source off -> YELLOW (7/8)."""
    raise NotImplementedError
