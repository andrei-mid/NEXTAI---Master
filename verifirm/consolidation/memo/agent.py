"""Memo agent: writes ONLY from the ConsolidatedReport JSON.

The LLM returns a MemoDraft (sections + questions, every sentence citing signal ids). Numbers are
copied from signal.data, never computed. The memo never recommends approve/reject: the analyst
decides. The markdown is rendered deterministically from the sections, and again after the
critic pass (critic/agent.py) removes sentences.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from verifirm.consolidation.evidence import report_view
from verifirm.core.ports.llm import LLMClient
from verifirm.llm.json_output import complete_validated, load_prompt, split_prompt
from verifirm.llm.untrusted import wrap_untrusted
from verifirm.schema.memo import (
    ClientQuestion,
    ConsolidatedReport,
    Memo,
    MemoSection,
    MemoSentence,
    SectionKind,
)
from verifirm.schema.signals import AgentStatus

PROMPT = Path(__file__).parent / "prompts" / "memo.md"
# The JSON must stay whole: a truncated report would silently drop signals from the memo.
MAX_REPORT_CHARS = 400_000
_PARAGRAPH_KINDS = {SectionKind.SUMMARY, SectionKind.COVERAGE}


class MemoDraft(BaseModel):
    """LLM output schema."""

    sections: list[MemoSection]
    questions: list[ClientQuestion]


def _coverage_fallback(report: ConsolidatedReport) -> MemoSection:
    """Deterministic coverage section, used only if the model left it out."""
    failed = [r for r in report.results if r.status is not AgentStatus.OK]
    if failed:
        text = "; ".join(f"{r.agent}: {r.status.value}" for r in failed)
        sentences = [MemoSentence(text=f"Agents that did not complete normally: {text}.")]
    else:
        sentences = [MemoSentence(text=f"All {report.score.coverage.total} agents completed.")]
    return MemoSection(kind=SectionKind.COVERAGE, title="Coverage", sentences=sentences)


async def write_memo(report: ConsolidatedReport, llm: LLMClient, model: str) -> Memo:
    system, user = split_prompt(
        load_prompt(
            PROMPT,
            consolidated_report_json=wrap_untrusted(
                json.dumps(report_view(report), ensure_ascii=False, indent=1, default=str),
                source="consolidated_report",
                max_chars=MAX_REPORT_CHARS,
            ),
        )
    )
    draft = await complete_validated(llm, system=system, user=user, schema=MemoDraft, model=model)
    sections = [s for s in draft.sections if s.sentences]
    if not any(s.kind is SectionKind.COVERAGE for s in sections):
        sections.append(_coverage_fallback(report))
    memo = Memo(
        cui=report.cui,
        run_id=report.run_id,
        sections=sections,
        questions=draft.questions,
        markdown="",
        generated_at=report.generated_at,
        model=model,
    )
    return memo.model_copy(update={"markdown": render_markdown(memo)})


def _cite(sentence: MemoSentence) -> str:
    """Rule ids of the cited signals (signal ids are '<rule_id>:<hash>'), without repeats."""
    rules = list(dict.fromkeys(sid.split(":", 1)[0] for sid in sentence.signal_ids))
    return f" [{', '.join(rules)}]" if rules else ""


def render_markdown(memo: Memo) -> str:
    """Deterministic markdown rendering of the sections + questions (no LLM)."""
    blocks: list[str] = []
    for section in memo.sections:
        if not section.sentences:
            continue
        lines = [f"## {section.title}", ""]
        if section.kind in _PARAGRAPH_KINDS:
            lines.append(" ".join(s.text + _cite(s) for s in section.sentences))
        else:
            lines.extend(f"- {s.text}{_cite(s)}" for s in section.sentences)
        blocks.append("\n".join(lines))
    if memo.questions:
        lines = ["## Questions for the client", ""]
        lines.extend(f"{i}. {q.question}" for i, q in enumerate(memo.questions, start=1))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"
