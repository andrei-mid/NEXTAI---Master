from datetime import UTC, datetime
from typing import Any

import pytest

from verifirm.consolidation.analyst.agent import (
    NO_EXPLANATION,
    AnalystConfig,
    last_expected_year,
    load_config,
    write_opinion,
)
from verifirm.core.impl_local.llm import FakeLLMClient
from verifirm.schema.analyst import (
    DISCLAIMER,
    CompanyDossier,
    CrossCheck,
    DossierYear,
    OfficialScore,
)
from verifirm.schema.scoring import Band

NOW = datetime(2026, 10, 28, tzinfo=UTC)


def dossier() -> CompanyDossier:
    return CompanyDossier(
        cui="99000025",
        fictional=True,
        run_id="run_1",
        generated_at=NOW,
        name="ZEPHYRIA LOGISTIC NOVA SRL",
        legal_form="SRL",
        cross_checks={"name": CrossCheck(anaf="A SRL", onrc="A SRL", match=True)},
        anaf_snapshots={},
        anaf_changes=[],
        financials={
            "2025": DossierYear(filed=True, turnover=18600000, equity=-111000, employees=2)
        },
        indicators={},
        administrators=[],
        sources={},
        agents={},
        signals={},
        official_score=OfficialScore(trust_score=55.0, band=Band.YELLOW, coverage="8/8 sources"),
    )


def draft(**over: Any) -> dict[str, Any]:
    return {
        "flags": [
            {
                "title": "Negative equity",
                "claim": "Equity was -111000 RON in 2025 on a turnover of 18600000 RON.",
                "category": "financial_inconsistency",
                "severity": "high",
                "evidence": [
                    {"path": "financials.2025.equity", "value": "-111000"},
                    {"path": "financials.2025.turnover", "value": "18600000"},
                ],
            },
            {
                "title": "Invented figure",
                "claim": "Debts were 99000000 RON.",
                "category": "other",
                "severity": "medium",
                "evidence": [{"path": "financials.2025.total_debts", "value": "99000000"}],
            },
        ],
        "opinion_score": 35,
        "explanation": "Turnover of 18600000 RON is carried by 2 employees. Margins look thin.",
        **over,
    }


async def test_opinion_keeps_backed_flags_and_adds_the_disclaimer() -> None:
    llm = FakeLLMClient(json_responses={"AnalystDraft": draft()})
    opinion = await write_opinion(dossier(), llm, "test-model")
    assert [f.title for f in opinion.flags] == ["Negative equity"]
    assert opinion.rejected[0].flag.title == "Invented figure"
    assert opinion.disclaimer == DISCLAIMER
    assert opinion.official_band == Band.YELLOW and opinion.official_score == 55.0  # unchanged
    assert opinion.opinion_score == 35 and opinion.model == "test-model"
    sent = llm.calls[0]["messages"][0].content
    assert "<untrusted_data" in sent and "18600000" in sent


async def test_explanation_that_fails_every_check_is_replaced() -> None:
    llm = FakeLLMClient(json_responses={"AnalystDraft": draft(explanation="Debts hit 5 billion.")})
    assert (await write_opinion(dossier(), llm, "m")).explanation == NO_EXPLANATION


async def test_invalid_llm_output_raises_never_returns_unchecked() -> None:
    llm = FakeLLMClient(json_responses={"AnalystDraft": draft(opinion_score=250)})
    with pytest.raises(ValueError):
        await write_opinion(dossier(), llm, "m")


async def test_oversized_dossier_is_refused_not_cut() -> None:
    cfg = AnalystConfig(years_of_history=5, filing_available_from_month=7, max_dossier_chars=100)
    with pytest.raises(ValueError, match="max_dossier_chars"):
        await write_opinion(
            dossier(), FakeLLMClient(json_responses={"AnalystDraft": draft()}), "m", cfg
        )


def test_last_expected_year_follows_the_filing_month() -> None:
    cfg = load_config()
    assert last_expected_year(datetime(2026, 10, 1).date(), cfg) == 2025
    assert last_expected_year(datetime(2026, 3, 1).date(), cfg) == 2024
