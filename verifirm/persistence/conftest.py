"""Shared Postgres fixtures for every test under verifirm/persistence. No SQLite, not even in tests.

`migrated_db` checks DATABASE_URL is reachable (skip otherwise; CI always has postgres:17) and
runs `alembic upgrade head` once per session. Tests never truncate (audit_decisions refuses it):
each test uses fresh CUIs / run_ids from `ids` instead.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from verifirm.core.config import Settings
from verifirm.persistence import engine as db
from verifirm.persistence.repositories.sql_repository import SqlRepository
from verifirm.schema.api import DecisionKind, DecisionRecord
from verifirm.schema.identity import IdentitySheet
from verifirm.schema.memo import Memo, VerifierReport
from verifirm.schema.runs import RunState, RunStatus
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

ALEMBIC_INI = Path(__file__).parent / "alembic.ini"


async def _reachable(settings: Settings) -> Exception | None:
    engine = db.create_engine(settings)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # unreachable / auth / not started
        return exc
    finally:
        await engine.dispose()
    return None


@pytest.fixture(scope="session")
def migrated_db() -> Settings:
    settings = Settings()
    exc = asyncio.run(_reachable(settings))
    if exc is not None:
        pytest.skip(
            f"Postgres not reachable at DATABASE_URL ({type(exc).__name__}). Run `make up`."
        )
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    return settings


@pytest.fixture
async def repo(migrated_db: Settings) -> AsyncIterator[SqlRepository]:
    yield SqlRepository(migrated_db)
    await db.dispose_engine()  # the pool is bound to this test's event loop


class Ids:
    """Unique fictional ids per test (invalid-checksum 99000… CUIs), so tests never collide."""

    def __init__(self) -> None:
        self.tag = uuid.uuid4().hex[:8]
        self._num = int(self.tag, 16) % 1_000_000

    def cui(self, n: int = 0) -> str:
        return f"99000{self._num:06d}{n}"

    def run(self, n: int = 0) -> str:
        return f"run_test_{self.tag}_{n}"


@pytest.fixture
def ids() -> Ids:
    return Ids()


T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


class Make:
    """Minimal valid schema objects. Keyword overrides go straight to the model."""

    def sheet(self, cui: str, **kw: object) -> IdentitySheet:
        return IdentitySheet.model_validate(
            {"cui": cui, "fictional": True, "current_name": "EXEMPLU TEST SRL", **kw}
        )

    def run(self, run_id: str, cui: str, **kw: object) -> RunStatus:
        return RunStatus.model_validate(
            {"run_id": run_id, "cui": cui, "state": RunState.RUNNING, "started_at": T0, **kw}
        )

    def signal(self, cui: str, signal_id: str, agent: str = "tax", **kw: object) -> Signal:
        return Signal.model_validate(
            {
                "signal_id": signal_id,
                "cui": cui,
                "agent": agent,
                "component": Component.TAX,
                "rule_id": "TAX-TEST-01",
                "claim": "Test claim.",
                "source": SourceRef(
                    name="anaf_v9",
                    type=SourceType.OFFICIAL,
                    url="https://anaf.example/v9",
                    retrieved_at=T0,
                ),
                "evidence_date": date(2026, 9, 30),
                "confidence": 0.9,
                "severity": Severity.HIGH,
                "entity_match": EntityMatch(method="cui_exact", score=1.0),
                "data": {"amount": 1200},
                **kw,
            }
        )

    def result(self, agent: str, signals: list[Signal], **kw: object) -> AgentResult:
        return AgentResult.model_validate(
            {
                "agent": agent,
                "component": Component.TAX,
                "status": AgentStatus.OK,
                "sources_checked": ["anaf_v9"],
                "sources_failed": [],
                "signals": signals,
                "duration_ms": 42,
                **kw,
            }
        )

    def score(
        self, cui: str, run_id: str, band: Band = Band.YELLOW, minutes: int = 0, **kw: object
    ) -> Score:
        return Score.model_validate(
            {
                "cui": cui,
                "run_id": run_id,
                "trust_score": 61.5,
                "band": band,
                "components": [
                    ComponentScore(
                        component=Component.TAX,
                        status=AgentStatus.OK,
                        available=True,
                        score=61.5,
                        weight=1.0,
                        effective_weight=1.0,
                    )
                ],
                "coverage": Coverage(weight_pct=100, available=1, total=1),
                "config_version": "test-1",
                "computed_at": T0 + timedelta(minutes=minutes),
                **kw,
            }
        )

    def memo(self, cui: str, run_id: str, minutes: int = 0, **kw: object) -> Memo:
        return Memo.model_validate(
            {
                "cui": cui,
                "run_id": run_id,
                "sections": [],
                "markdown": "# Memo",
                "generated_at": T0 + timedelta(minutes=minutes),
                "model": "test-model",
                "verifier_report": VerifierReport(passed=True, checked_sentences=0, verified_at=T0),
                **kw,
            }
        )

    def decision(
        self, cui: str, decision_id: str, minutes: int = 0, **kw: object
    ) -> DecisionRecord:
        return DecisionRecord.model_validate(
            {
                "decision_id": decision_id,
                "cui": cui,
                "decision": DecisionKind.ESCALATE,
                "comment": "Need more documents.",
                "analyst": "analyst.test",
                "run_id": None,
                "band_at_decision": Band.YELLOW,
                "recorded_at": T0 + timedelta(minutes=minutes),
                **kw,
            }
        )


@pytest.fixture
def make() -> Make:
    return Make()
