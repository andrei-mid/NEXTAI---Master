from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from itertools import count
from typing import Any

import pytest

from verifirm.core.config import get_settings
from verifirm.schema.signals import (
    AgentResult,
    AgentStatus,
    Component,
    EntityMatch,
    Severity,
    Signal,
    SourceRef,
    SourceType,
)
from verifirm.scoring.engine import ScoringConfig, load_scoring_config

_ids = count()

MakeSignal = Callable[..., Signal]
MakeResults = Callable[..., list[AgentResult]]


@pytest.fixture
def config() -> ScoringConfig:
    return load_scoring_config(get_settings().scoring_config_path)


@pytest.fixture
def make_signal() -> MakeSignal:
    def make(
        component: Component,
        severity: Severity = Severity.MEDIUM,
        *,
        rule_id: str = "TEST-RULE-01",
        confidence: float = 1.0,
        match: float = 1.0,
        validated: bool = True,
        auto_stop: bool = False,
    ) -> Signal:
        return Signal(
            signal_id=f"s{next(_ids)}",
            cui="99000017",
            agent=component.value,
            component=component,
            rule_id=rule_id,
            claim="test",
            source=SourceRef(name="test", type=SourceType.OFFICIAL, retrieved_at=datetime.now(UTC)),
            evidence_date=None,
            confidence=confidence,
            severity=severity,
            validated=validated,
            auto_stop_candidate=auto_stop,
            entity_match=EntityMatch(method="cui_exact", score=match),
        )

    return make


@pytest.fixture
def make_results() -> MakeResults:
    """All 8 components OK and clean, unless overridden:
    make_results(statuses={Component.MEDIA: AgentStatus.TIMEOUT}, signals=[...], omit={...})."""

    def make(
        *,
        statuses: dict[Component, AgentStatus] | None = None,
        signals: list[Signal] | None = None,
        omit: set[Component] | None = None,
    ) -> list[AgentResult]:
        statuses = statuses or {}
        out = []
        for c in Component:
            if omit and c in omit:
                continue
            status = statuses.get(c, AgentStatus.OK)
            mine: list[Any] = [s for s in signals or [] if s.component == c]
            out.append(
                AgentResult(
                    agent=c.value,
                    component=c,
                    status=status,
                    sources_checked=["x"],
                    sources_failed=[] if status == AgentStatus.OK else ["y"],
                    signals=mine,
                    duration_ms=1,
                )
            )
        return out

    return make
