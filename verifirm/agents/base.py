"""BaseAgent: the interface every one of the 8 agents implements.

    @register_agent("identity")
    class IdentityAgent(BaseAgent):
        component = Component.IDENTITY
        sources = ("anaf_v9", "onrc_bulk")
        rules = RULES
        async def run(self, ctx: AgentContext) -> AgentResult: ...

Rules for agents:
- Never import another agent. Talk to the world only through ctx (adapters, llm, web search).
- Return an AgentResult. A failed source goes into `sources_failed` and is never clean.
- Every signal's rule_id is declared in the agent's rules.py and documented in docs/RULES.md.
- Signal ids are deterministic (make_signal_id), so re-running a job never duplicates signals.
"""

from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any, ClassVar

from verifirm.adapters.base import BaseAdapter, SourceUnavailable
from verifirm.core.config import Settings
from verifirm.core.ports.clock import Clock
from verifirm.core.ports.llm import LLMClient
from verifirm.core.ports.web_search import WebSearch
from verifirm.schema.financials import SubmittedFinancials
from verifirm.schema.identity import IdentitySheet
from verifirm.schema.signals import (
    AgentResult,
    AgentStatus,
    Component,
    EntityMatch,
    Severity,
    Signal,
    SourceRef,
)


@dataclass(frozen=True)
class RuleSpec:
    """One documented rule. Severity values are PROPOSALS until DECISIONS.md says otherwise."""

    rule_id: str
    component: Component
    severity: Severity
    condition: str  # human-readable condition, copied to docs/RULES.md
    source: str  # adapter name(s)
    auto_stop: bool = False


@dataclass
class AgentContext:
    run_id: str
    cui: str
    identity: IdentitySheet
    settings: Settings
    clock: Clock
    adapters: Mapping[str, BaseAdapter]
    llm: LLMClient | None = None
    web_search: WebSearch | None = None
    submitted: SubmittedFinancials | None = None
    disabled_sources: frozenset[str] = field(default_factory=frozenset)

    def adapter(self, name: str) -> BaseAdapter:
        """The adapter, or SourceUnavailable if it's missing or switched off (demo step 7)."""
        if name in self.disabled_sources:
            raise SourceUnavailable(name, "switched off for this run")
        try:
            return self.adapters[name]
        except KeyError:
            raise SourceUnavailable(name, "adapter not configured") from None


def make_signal_id(cui: str, rule_id: str, discriminator: str = "") -> str:
    """Stable id: the same fact found again in a later run gets the same id."""
    raw = f"{cui}|{rule_id}|{discriminator}".encode()
    return f"{rule_id}:{hashlib.sha256(raw).hexdigest()[:16]}"


class BaseAgent(ABC):
    name: ClassVar[str] = "base"  # set by @register_agent
    component: ClassVar[Component]
    sources: ClassVar[tuple[str, ...]] = ()  # adapter names this agent reads
    rules: ClassVar[Mapping[str, RuleSpec]] = {}
    timeout_s: ClassVar[float | None] = None  # None -> settings.timeout_for(name)

    @abstractmethod
    async def run(self, ctx: AgentContext) -> AgentResult:
        """Check the company and return signals. Must finish within the time budget."""

    # ------------------------------------------------------------------ helpers
    def signal(
        self,
        ctx: AgentContext,
        *,
        rule_id: str,
        claim: str,
        source: SourceRef,
        evidence_date: date | None,
        confidence: float,
        entity_match: EntityMatch,
        discriminator: str = "",
        severity: Severity | None = None,
        validated: bool = True,
        data: dict[str, Any] | None = None,
    ) -> Signal:
        """Build a Signal for one of this agent's declared rules (severity defaults to the rule's)."""
        rule = self.rules[rule_id]  # KeyError = undeclared rule, so add it to rules.py + RULES.md
        return Signal(
            signal_id=make_signal_id(ctx.cui, rule_id, discriminator),
            cui=ctx.cui,
            agent=self.name,
            component=self.component,
            rule_id=rule_id,
            claim=claim,
            source=source,
            evidence_date=evidence_date,
            confidence=confidence,
            severity=severity or rule.severity,
            validated=validated,
            auto_stop_candidate=rule.auto_stop,
            entity_match=entity_match,
            data=data or {},
        )

    def result(
        self,
        *,
        started: float,
        sources_checked: list[str],
        sources_failed: list[str],
        signals: list[Signal],
        notes: str | None = None,
    ) -> AgentResult:
        """Status derived honestly: all failed -> UNAVAILABLE, some failed -> PARTIAL."""
        if sources_failed and not sources_checked:
            status = AgentStatus.UNAVAILABLE
        elif sources_failed:
            status = AgentStatus.PARTIAL
        else:
            status = AgentStatus.OK
        return AgentResult(
            agent=self.name,
            component=self.component,
            status=status,
            sources_checked=sources_checked,
            sources_failed=sources_failed,
            signals=signals,
            duration_ms=int((time.monotonic() - started) * 1000),
            notes=notes,
        )
