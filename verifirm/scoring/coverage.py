"""Coverage: which components could actually be checked. Owner: @role-2-core."""

from __future__ import annotations

from typing import TYPE_CHECKING

from verifirm.schema.scoring import Coverage
from verifirm.schema.signals import AgentResult, AgentStatus, Component

if TYPE_CHECKING:
    from verifirm.scoring.engine import ScoringConfig

AVAILABLE_STATUSES = frozenset({AgentStatus.OK, AgentStatus.PARTIAL})


def component_statuses(results: list[AgentResult]) -> dict[Component, AgentStatus]:
    """Best status per component (several results for one component: the best one counts)."""
    rank = [
        AgentStatus.OK,
        AgentStatus.PARTIAL,
        AgentStatus.TIMEOUT,
        AgentStatus.UNAVAILABLE,
        AgentStatus.SKIPPED,
    ]
    best: dict[Component, AgentStatus] = {}
    for r in results:
        current = best.get(r.component)
        if current is None or rank.index(r.status) < rank.index(current):
            best[r.component] = r.status
    return best


def available_components(results: list[AgentResult]) -> set[Component]:
    return {c for c, s in component_statuses(results).items() if s in AVAILABLE_STATUSES}


def compute_coverage(results: list[AgentResult], config: ScoringConfig) -> Coverage:
    """weight_pct = share of the configured weight whose component is OK or PARTIAL.
    A component with no AgentResult at all counts as missing (never as clean)."""
    available = available_components(results)
    total_weight = sum(config.weights.values())
    covered = sum(w for c, w in config.weights.items() if c in available)
    return Coverage(
        weight_pct=round(100 * covered / total_weight, 2) if total_weight else 0.0,
        available=len([c for c in config.weights if c in available]),
        total=len(config.weights),
        missing=[c for c in config.weights if c not in available],
    )
