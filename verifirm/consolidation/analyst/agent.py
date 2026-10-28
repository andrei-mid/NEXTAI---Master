"""AI analyst agent: the LLM's educated opinion on a CompanyDossier (docs/DECISIONS.md).

The model sees only the dossier (built by code, people under aliases, wrapped as untrusted
data) and returns an AnalystDraft. Code then keeps the flags whose evidence checks out
(citations.py), cleans the explanation, and adds the disclaimer and the official score. The
opinion never changes the official score or band, and never decides.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel

from verifirm.adapters.base import BaseAdapter
from verifirm.consolidation.analyst.citations import check_flags, clean_explanation
from verifirm.consolidation.analyst.dossier import build_dossier, collect_inputs
from verifirm.core.ports.llm import LLMClient
from verifirm.llm.json_output import complete_validated, load_prompt, split_prompt
from verifirm.llm.untrusted import wrap_untrusted
from verifirm.schema.analyst import AnalystDraft, AnalystOpinion, CompanyDossier
from verifirm.schema.memo import ConsolidatedReport

PROMPT = Path(__file__).parent / "prompts" / "analyst.md"
CONFIG_PATH = Path(__file__).parent / "config.yaml"
NO_EXPLANATION = "No explanation passed verification."


class AnalystConfig(BaseModel):
    years_of_history: int
    filing_available_from_month: int
    max_dossier_chars: int


def load_config(path: Path = CONFIG_PATH) -> AnalystConfig:
    return AnalystConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def last_expected_year(today: date, cfg: AnalystConfig) -> int:
    """Latest /bilant year that should be filed by `today`."""
    return today.year - 1 if today.month >= cfg.filing_available_from_month else today.year - 2


async def write_opinion(
    dossier: CompanyDossier, llm: LLMClient, model: str, cfg: AnalystConfig | None = None
) -> AnalystOpinion:
    cfg = cfg or load_config()
    payload = dossier.model_dump(mode="json")
    text = json.dumps(payload, ensure_ascii=False, indent=1)
    if len(text) > cfg.max_dossier_chars:
        # A cut dossier would let the model miss facts silently: refuse instead.
        raise ValueError(f"dossier is {len(text)} chars, over max_dossier_chars")
    system, user = split_prompt(
        load_prompt(
            PROMPT,
            dossier_json=wrap_untrusted(
                text, source="company_dossier", max_chars=cfg.max_dossier_chars
            ),
        )
    )
    draft = await complete_validated(
        llm, system=system, user=user, schema=AnalystDraft, model=model
    )
    flags, rejected = check_flags(draft.flags, payload)
    return AnalystOpinion(
        cui=dossier.cui,
        run_id=dossier.run_id,
        generated_at=dossier.generated_at,
        model=model,
        flags=flags,
        rejected=rejected,
        opinion_score=draft.opinion_score,
        explanation=clean_explanation(draft.explanation, payload) or NO_EXPLANATION,
        official_band=dossier.official_score.band,
        official_score=dossier.official_score.trust_score,
    )


async def analyse(
    report: ConsolidatedReport,
    adapters: Mapping[str, BaseAdapter],
    llm: LLMClient,
    model: str,
    *,
    today: date,
    disabled: frozenset[str] = frozenset(),
    cfg: AnalystConfig | None = None,
) -> tuple[CompanyDossier, AnalystOpinion]:
    """The pipeline step: dossier (mirror only) -> opinion. Raises on an invalid LLM answer or
    a missing provider, like the memo step: the caller keeps the run and the official score."""
    cfg = cfg or load_config()
    inputs = await collect_inputs(
        report.cui,
        adapters,
        today,
        last_year=last_expected_year(today, cfg),
        years=cfg.years_of_history,
        disabled=disabled,
    )
    dossier = build_dossier(report, inputs)
    return dossier, await write_opinion(dossier, llm, model, cfg)
