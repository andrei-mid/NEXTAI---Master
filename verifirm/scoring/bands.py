"""Band assignment: deterministic and config-driven (weights.yaml). Owner: @role-2-core."""

from __future__ import annotations

from typing import TYPE_CHECKING

from verifirm.schema.scoring import Band, Coverage
from verifirm.schema.signals import SEVERITY_ORDER, AgentResult, AgentStatus, Severity, Signal
from verifirm.scoring.coverage import AVAILABLE_STATUSES, component_statuses

if TYPE_CHECKING:
    from verifirm.scoring.engine import ScoringConfig


def auto_stop_signals(signals: list[Signal], config: ScoringConfig) -> list[Signal]:
    """Signals that force STOP: validated, auto_stop_candidate, rule_id in config.auto_stop_rules,
    and component NOT in config.never_stop_components (media can never STOP)."""
    return [
        s
        for s in signals
        if s.validated
        and s.auto_stop_candidate
        and s.rule_id in config.auto_stop_rules
        and s.component not in config.never_stop_components
    ]


def _is_high(s: Signal) -> bool:
    return SEVERITY_ORDER[s.severity] >= SEVERITY_ORDER[Severity.HIGH]


def assign_band(
    *,
    trust_score: float | None,
    coverage: Coverage,
    results: list[AgentResult],
    config: ScoringConfig,
) -> tuple[Band, list[str]]:
    """Return (band, reasons). The first matching band wins:
    STOP   any auto-stop signal (from any result, even a partial one: a confirmed fact is a fact)
    GREY   coverage < 60%, or nothing available to score
    RED    score < 50, or HIGH+ signals in >= 2 different components
    YELLOW 50-74, or >= 1 HIGH+ signal, or coverage < 80%, or any GREEN condition missing
    GREEN  >= 75, no HIGH+ signals, coverage >= 80%, required components available and,
           with green_requires_all_ok, every component OK (an outage never yields GREEN)
    """
    t = config.bands
    all_signals = [s for r in results for s in r.signals]
    scored_signals = [s for r in results if r.status in AVAILABLE_STATUSES for s in r.signals]

    stops = auto_stop_signals(all_signals, config)
    if stops:
        return Band.STOP, sorted({f"AUTO_STOP:{s.rule_id}" for s in stops})

    if trust_score is None or coverage.weight_pct < t.grey_coverage_below:
        return Band.GREY, [f"COVERAGE<{t.grey_coverage_below:g}"]

    high = [s for s in scored_signals if _is_high(s)]
    high_components = sorted({s.component.value for s in high})

    red: list[str] = []
    if trust_score < t.red_score_below:
        red.append(f"SCORE<{t.red_score_below:g}")
    if len(high_components) >= t.red_min_high_components:
        red.append(f"HIGH_SIGNALS:{','.join(high_components)}")
    if red:
        return Band.RED, red

    statuses = component_statuses(results)
    yellow: list[str] = []
    if trust_score < t.yellow_score_below:
        yellow.append(f"SCORE<{t.yellow_score_below:g}")
    if len(high) >= t.yellow_min_high_signals:
        yellow.append(f"HIGH_SIGNALS:{','.join(high_components)}")
    if coverage.weight_pct < t.yellow_coverage_below:
        yellow.append(f"COVERAGE<{t.yellow_coverage_below:g}")
    for c in t.green_requires_components:
        if statuses.get(c) not in AVAILABLE_STATUSES:
            yellow.append(f"REQUIRED_MISSING:{c.value}")
    if t.green_requires_all_ok:
        not_ok = [c.value for c in config.weights if statuses.get(c) != AgentStatus.OK]
        if not_ok:
            yellow.append(f"OUTAGE:{','.join(not_ok)}")
    if yellow:
        return Band.YELLOW, yellow

    return Band.GREEN, []
