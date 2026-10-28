"""Factories shared by the consolidation tests (fictional data only)."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import pytest

from verifirm.schema.identity import (
    Address,
    CompanyName,
    CompanyStatus,
    IdentitySheet,
    Person,
    PersonRole,
)
from verifirm.schema.memo import ConsolidatedReport
from verifirm.schema.scoring import Band, ComponentScore, Coverage, Score
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

NOW = datetime(2026, 10, 28, 8, 0, tzinfo=UTC)
CUI = "99000033"


def source(name: str = "ANAF", type_: SourceType = SourceType.OFFICIAL) -> SourceRef:
    return SourceRef(
        name=name,
        type=type_,
        url=f"https://{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}.example/x",
        retrieved_at=NOW,
    )


@pytest.fixture
def make_signal() -> Callable[..., Signal]:
    def factory(
        sid: str = "TAX-ARREARS-01:aaaa",
        *,
        claim: str = "The company owes 412,560 RON principal.",
        method: str = "cui_exact",
        data: dict[str, Any] | None = None,
        severity: Severity = Severity.HIGH,
        validated: bool = True,
        src: SourceRef | None = None,
        confidence: float = 0.9,
        cui: str = CUI,
        agent: str = "tax",
        evidence_date: date | None = date(2026, 6, 30),
    ) -> Signal:
        return Signal(
            signal_id=sid,
            cui=cui,
            agent=agent,
            component=Component.TAX,
            rule_id=sid.split(":")[0],
            claim=claim,
            source=src or source(),
            evidence_date=evidence_date,
            confidence=confidence,
            severity=severity,
            validated=validated,
            entity_match=EntityMatch(method=method, score=1.0),
            data=data if data is not None else {"principal_ron": 412560},
        )

    return factory


@pytest.fixture
def make_result() -> Callable[..., AgentResult]:
    def factory(
        signals: list[Signal], agent: str = "tax", status: AgentStatus = AgentStatus.OK
    ) -> AgentResult:
        return AgentResult(
            agent=agent,
            component=Component.TAX,
            status=status,
            sources_checked=["anaf"],
            sources_failed=[] if status is AgentStatus.OK else ["anaf"],
            signals=signals,
            duration_ms=5,
        )

    return factory


@pytest.fixture
def identity() -> IdentitySheet:
    src = source("ONRC")
    return IdentitySheet(
        cui=CUI,
        fictional=True,
        current_name="BRUNALDO TRADE IMPEX SRL",
        names=[CompanyName(name="BRUNALDO TRADE IMPEX SRL")],
        legal_form="SRL",
        status=CompanyStatus.ACTIVE,
        registration_date=date(2012, 6, 11),
        registered_office=Address(raw="Bd. Inventat 42, Judetul Fictiv", county="Județul Fictiv"),
        administrators=[Person(name="SORIN IMAGINESCU", role=PersonRole.ADMINISTRATOR, source=src)],
        shareholders=[
            Person(
                name="CALBRONA HOLDING FICTIV SRL",
                role=PersonRole.SHAREHOLDER,
                is_company=True,
                cui="99000090",
                share_pct=100,
                source=source("Shareholders (MOCK)", SourceType.MOCK),
            )
        ],
        sources=[src],
    )


@pytest.fixture
def make_report(identity: IdentitySheet) -> Callable[[list[Signal]], ConsolidatedReport]:
    def factory(signals: list[Signal]) -> ConsolidatedReport:
        score = Score(
            cui=CUI,
            run_id="run_1",
            trust_score=64.8,
            band=Band.RED,
            components=[
                ComponentScore(
                    component=Component.TAX,
                    status=AgentStatus.OK,
                    available=True,
                    score=40,
                    weight=0.2,
                )
            ],
            coverage=Coverage(weight_pct=100.0, available=8, total=8),
            config_version="test",
            computed_at=NOW,
        )
        result = AgentResult(
            agent="tax",
            component=Component.TAX,
            status=AgentStatus.OK,
            sources_checked=["anaf"],
            sources_failed=[],
            signals=signals,
            duration_ms=5,
        )
        return ConsolidatedReport(
            cui=CUI,
            run_id="run_1",
            identity=identity,
            results=[result],
            signals=signals,
            score=score,
            generated_at=NOW,
        )

    return factory
