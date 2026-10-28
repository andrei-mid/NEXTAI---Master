"""AnalystStore: one opinion per run (upsert), latest by generated_at, the dossier kept for audit."""

from datetime import UTC, datetime, timedelta
from typing import Any

from verifirm.core.config import Settings
from verifirm.persistence.engine import session_scope
from verifirm.persistence.repositories.analyst import AnalystStore
from verifirm.persistence.repositories.sql_repository import SqlRepository
from verifirm.schema.analyst import (
    AnalystFlag,
    AnalystOpinion,
    Citation,
    CompanyDossier,
    FlagCategory,
    OfficialScore,
)
from verifirm.schema.scoring import Band
from verifirm.schema.signals import Severity

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def dossier(cui: str, run_id: str) -> CompanyDossier:
    return CompanyDossier(
        cui=cui,
        fictional=True,
        run_id=run_id,
        generated_at=T0,
        name="EXEMPLU TEST SRL",
        legal_form="SRL",
        cross_checks={},
        anaf_snapshots={},
        anaf_changes=[],
        financials={},
        indicators={},
        administrators=[],
        sources={},
        agents={},
        signals={},
        official_score=OfficialScore(trust_score=60.0, band=Band.YELLOW, coverage="8/8 sources"),
    )


def opinion(cui: str, run_id: str, minutes: int = 0, **kw: Any) -> AnalystOpinion:
    return AnalystOpinion.model_validate(
        {
            "cui": cui,
            "run_id": run_id,
            "generated_at": T0 + timedelta(minutes=minutes),
            "model": "test-model",
            "flags": [
                AnalystFlag(
                    title="t",
                    claim="c",
                    category=FlagCategory.OTHER,
                    severity=Severity.LOW,
                    evidence=[Citation(path="name", value="EXEMPLU TEST SRL")],
                )
            ],
            "opinion_score": 50,
            "explanation": "e",
            "official_band": Band.YELLOW,
            "official_score": 60.0,
            **kw,
        }
    )


async def test_roundtrip_latest_and_upsert(repo: SqlRepository, ids: Any) -> None:
    cui = ids.cui()
    assert await repo.get_latest_analyst_opinion(cui) is None
    await repo.save_analyst_opinion(opinion(cui, ids.run(2), minutes=5), dossier(cui, ids.run(2)))
    await repo.save_analyst_opinion(opinion(cui, ids.run(1)), dossier(cui, ids.run(1)))
    latest = await repo.get_latest_analyst_opinion(cui)
    assert latest is not None and latest.run_id == ids.run(2)
    redone = opinion(cui, ids.run(2), minutes=5, opinion_score=20)
    await repo.save_analyst_opinion(redone, dossier(cui, ids.run(2)))  # re-run: no duplicate
    assert await repo.get_latest_analyst_opinion(cui) == redone


async def test_dossier_is_kept_for_audit(
    repo: SqlRepository, migrated_db: Settings, ids: Any
) -> None:
    cui, run_id = ids.cui(), ids.run()
    await repo.save_analyst_opinion(opinion(cui, run_id), dossier(cui, run_id))
    async with session_scope(migrated_db) as s:
        assert await AnalystStore(s).get_dossier(run_id) == dossier(cui, run_id)
        assert await AnalystStore(s).get_dossier(ids.run(9)) is None
