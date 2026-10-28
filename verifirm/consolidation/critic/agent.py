"""Critic / verifier: removes any memo sentence whose claim or number is not in the report.

Two passes:
1. Deterministic (no LLM, always runs). Per sentence: every cited signal_id exists, red/yellow
   sentences cite something, every number and date appears in the cited signals or the score,
   media claims say "unvalidated", and decision/fraud wording only appears if a cited signal
   already uses it. Questions get the same id and number checks.
2. LLM pass (prompts/critic.md, settings.model_for("critic")): one call over the surviving
   sentences, "is every claim supported by the cited signals?". A sentence with no verdict is
   treated as unsupported. If this pass cannot run, nothing is silently approved: the report
   says it was not verified (passed=False).
Rejected sentences are REMOVED, the markdown is re-rendered from what is left.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from pydantic import BaseModel

from verifirm.consolidation.critic.facts import Evidence, unsupported
from verifirm.consolidation.evidence import score_view, signal_view
from verifirm.consolidation.memo.agent import render_markdown
from verifirm.core.logging import get_logger
from verifirm.core.ports.llm import LLMClient
from verifirm.llm.json_output import complete_validated, load_prompt, split_prompt
from verifirm.llm.untrusted import wrap_untrusted
from verifirm.schema.memo import (
    ClientQuestion,
    ConsolidatedReport,
    Memo,
    MemoSection,
    MemoSentence,
    RejectedSentence,
    SectionKind,
    VerifierReport,
)
from verifirm.schema.signals import Signal

log = get_logger(__name__)

PROMPT = Path(__file__).parent / "prompts" / "critic.md"
# Word stems the memo may not introduce on its own (the analyst decides; no accusations).
FORBIDDEN_STEMS = ("approv", "reject", "aprob", "respins", "fraud")
_NEEDS_CITATION = {SectionKind.RED_SIGNALS, SectionKind.YELLOW_SIGNALS}


class SentenceVerdict(BaseModel):
    index: int
    supported: bool
    reason: str = ""


class CriticVerdicts(BaseModel):
    verdicts: list[SentenceVerdict]


def _report_evidence(report: ConsolidatedReport) -> Evidence:
    """What any sentence may quote: the score, the identity, and simple counts of the report."""
    ev = Evidence().add(score_view(report))
    ev.add(report.identity.model_dump(mode="json", exclude={"sources"}))
    counts = Counter(s.severity.value for s in report.signals)
    ev.add([len(report.signals), len(report.results), *counts.values()])
    ev.add(list(Counter(r.status.value for r in report.results).values()))
    return ev


def _signal_evidence(signals: list[Signal]) -> Evidence:
    ev = Evidence()
    for s in signals:
        ev.add(signal_view(s))
    return ev


def _merged(*parts: Evidence) -> Evidence:
    out = Evidence()
    for p in parts:
        out.numbers |= p.numbers
        out.dates |= p.dates
        out.text += p.text
    return out


def _check(
    text: str,
    signal_ids: list[str],
    kind: SectionKind | None,
    by_id: dict[str, Signal],
    base: Evidence,
) -> str | None:
    """The reason this text can't stay in the memo, or None."""
    unknown = [sid for sid in signal_ids if sid not in by_id]
    if unknown:
        return f"cited signal {unknown[0]} is not in the consolidated JSON"
    cited = [by_id[sid] for sid in signal_ids]
    if not cited and kind in _NEEDS_CITATION:
        return "no cited signal"
    evidence = _merged(base, _signal_evidence(cited))
    lowered = text.lower()
    for stem in FORBIDDEN_STEMS:
        if stem in lowered and not evidence.mentions(stem):
            return f"wording '{stem}...' is not in any cited signal (the analyst decides)"
    if any(not s.validated for s in cited) and not ("unvalidated" in lowered or "nevalidat" in lowered):
        return "cites an unvalidated (media) signal without saying so"
    missing = unsupported(text, evidence)
    if missing:
        return f"number {missing[0]} not in consolidated JSON"
    return None


async def _llm_pass(
    sentences: list[tuple[int, MemoSentence]],
    by_id: dict[str, Signal],
    report: ConsolidatedReport,
    llm: LLMClient,
    model: str,
) -> dict[int, str]:
    """{sentence index: rejection reason} for sentences the LLM can't confirm."""
    cited = {sid for _, s in sentences for sid in s.signal_ids}
    evidence = {
        "signals": [signal_view(by_id[sid]) for sid in sorted(cited)],
        "score": score_view(report),
    }
    system, user = split_prompt(
        load_prompt(
            PROMPT,
            evidence_json=wrap_untrusted(
                json.dumps(evidence, ensure_ascii=False, indent=1, default=str),
                source="evidence",
                max_chars=400_000,
            ),
            sentences_json=json.dumps(
                [{"index": i, "text": s.text, "signal_ids": s.signal_ids} for i, s in sentences],
                ensure_ascii=False,
            ),
        )
    )
    verdicts = await complete_validated(
        llm, system=system, user=user, schema=CriticVerdicts, model=model
    )
    by_index = {v.index: v for v in verdicts.verdicts}
    rejected: dict[int, str] = {}
    for i, _ in sentences:
        verdict = by_index.get(i)
        if verdict is None:
            rejected[i] = "the fact-checker returned no verdict for this sentence"
        elif not verdict.supported:
            rejected[i] = verdict.reason or "not supported by the cited signals"
    return rejected


async def verify_memo(
    memo: Memo, report: ConsolidatedReport, llm: LLMClient | None, model: str
) -> Memo:
    by_id = {s.signal_id: s for s in report.signals}
    base = _report_evidence(report)
    rejected: list[RejectedSentence] = []

    # --- pass 1: deterministic
    survivors: list[tuple[int, MemoSentence]] = []  # flat index over all sentences
    verdict_by_index: dict[int, str] = {}
    flat: list[tuple[MemoSection, MemoSentence]] = [
        (sec, sen) for sec in memo.sections for sen in sec.sentences
    ]
    for i, (section, sentence) in enumerate(flat):
        reason = _check(sentence.text, sentence.signal_ids, section.kind, by_id, base)
        if reason is None:
            survivors.append((i, sentence))
        else:
            verdict_by_index[i] = reason

    questions: list[ClientQuestion] = []
    for question in memo.questions:
        reason = _check(question.question, question.reason_signal_ids, None, by_id, base)
        if reason is None and not question.reason_signal_ids:
            reason = "no cited signal"
        if reason is None:
            questions.append(question)
        else:
            rejected.append(RejectedSentence(text=question.question, reason=reason))

    # --- pass 2: LLM (only what pass 1 left)
    llm_unverified = False
    if llm is not None and survivors:
        try:
            verdict_by_index.update(await _llm_pass(survivors, by_id, report, llm, model))
        except (ValueError, RuntimeError):
            log.warning("critic LLM pass failed, memo is only partly verified", exc_info=True)
            llm_unverified = True

    # --- rebuild: only sentences without a rejection stay
    sections: list[MemoSection] = []
    for section in memo.sections:
        kept = []
        for sentence in section.sentences:
            i = next(j for j, (_, s) in enumerate(flat) if s is sentence)
            if i in verdict_by_index:
                rejected.append(RejectedSentence(text=sentence.text, reason=verdict_by_index[i]))
            else:
                kept.append(sentence)
        if kept:
            sections.append(section.model_copy(update={"sentences": kept}))
    if llm_unverified:
        rejected.append(
            RejectedSentence(
                text="(whole memo)",
                reason="LLM verification pass was unavailable: only the deterministic checks ran",
            )
        )

    cleaned = memo.model_copy(update={"sections": sections, "questions": questions})
    return cleaned.model_copy(
        update={
            "markdown": render_markdown(cleaned),
            "verifier_report": VerifierReport(
                passed=not rejected,
                checked_sentences=len(flat),
                rejected=rejected,
                verified_at=report.generated_at,
            ),
        }
    )
