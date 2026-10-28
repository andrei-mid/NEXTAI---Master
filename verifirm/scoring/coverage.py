"""STUB. Owner: @role-2-core. Coverage computation."""

from __future__ import annotations

from verifirm.schema.scoring import Coverage
from verifirm.schema.signals import AgentResult, AgentStatus
from verifirm.scoring.engine import ScoringConfig

AVAILABLE_STATUSES = frozenset({AgentStatus.OK, AgentStatus.PARTIAL})


def compute_coverage(results: list[AgentResult], config: ScoringConfig) -> Coverage:
    """weight_pct = sum of config.weights for components whose agent status is in
    AVAILABLE_STATUSES. available/total count components (total = 8). `missing` lists the rest.
    A component with no AgentResult at all counts as missing."""
    raise NotImplementedError
