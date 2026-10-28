"""Deterministic checks on the AI analyst's flags (no LLM). A flag survives only if:
1. every evidence path exists in the dossier and points at a value, not a whole section;
2. the cited value equals the dossier value (numbers by value, text case/diacritics-insensitive);
3. every number and date in its title and claim appears in its own evidence;
4. it uses no decision wording (the analyst decides) and no "fraud" unless the evidence says so.
Severity is capped at `high`: `critical` belongs to the official rules that can stop a file.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from verifirm.adapters.onrc_bulk import fold
from verifirm.consolidation.critic.facts import Evidence, number_tokens, unsupported
from verifirm.schema.analyst import AnalystFlag, RejectedFlag
from verifirm.schema.signals import SEVERITY_ORDER, Severity

_PATH_TOKEN = re.compile(r"\[(\d+)\]|([^.\[\]]+)")
_DECISION = re.compile(r"\b(approv\w*|reject\w*|declin\w*)\b", re.IGNORECASE)
_FRAUD = re.compile(r"\bfraud\w*\b", re.IGNORECASE)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_MISSING = object()


def resolve(document: Any, path: str) -> Any:
    """The value at a dotted path ('financials.2024.equity', 'administrators[0].alias' or
    'administrators.0.alias'), or _MISSING."""
    node = document
    for index, key in _PATH_TOKEN.findall(path.strip()):
        part = index or key
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return _MISSING
    return node


def value_matches(cited: str, actual: Any) -> bool:
    text = cited.strip()
    if actual is None:
        return text.lower() in {"null", "none", ""}
    if isinstance(actual, bool):
        return text.lower() == str(actual).lower()
    if isinstance(actual, int | float):
        if actual < 0 and "-" not in text:
            return False  # a loss cited as a profit
        target = abs(Decimal(str(actual)))
        return any(target in values for _, values in number_tokens(text))
    if isinstance(actual, str):
        a, c = fold(actual), fold(text)
        return bool(c) and (a == c or (len(c) >= 4 and c in a))
    return False


def _cap(flag: AnalystFlag) -> AnalystFlag:
    if SEVERITY_ORDER[flag.severity] > SEVERITY_ORDER[Severity.HIGH]:
        return flag.model_copy(update={"severity": Severity.HIGH})
    return flag


def check_flag(flag: AnalystFlag, dossier: dict[str, Any]) -> str | None:
    """None if the flag checks out, otherwise the reason it is rejected."""
    evidence = Evidence()
    for citation in flag.evidence:
        actual = resolve(dossier, citation.path)
        if actual is _MISSING:
            return f"evidence path {citation.path!r} does not exist in the dossier"
        if isinstance(actual, dict | list):
            return f"evidence path {citation.path!r} is a section, not a value"
        if not value_matches(citation.value, actual):
            return f"{citation.path} is {actual!r} in the dossier, not {citation.value!r}"
        evidence.add(actual)
        for index, key in _PATH_TOKEN.findall(citation.path):
            evidence.add(index or key)  # the year / date in the path is evidence too
    text = f"{flag.title}. {flag.claim}"
    missing = unsupported(text, evidence)
    if missing:
        return f"states {', '.join(missing)}, which is not in its evidence"
    if _DECISION.search(text):
        return "decision wording: the analyst decides"
    if _FRAUD.search(text) and not evidence.mentions("fraud"):
        return "says fraud without evidence that says so"
    return None


def check_flags(
    flags: list[AnalystFlag], dossier: dict[str, Any]
) -> tuple[list[AnalystFlag], list[RejectedFlag]]:
    accepted: list[AnalystFlag] = []
    rejected: list[RejectedFlag] = []
    for flag in flags:
        reason = check_flag(flag, dossier)
        if reason is None:
            accepted.append(_cap(flag))
        else:
            rejected.append(RejectedFlag(flag=flag, reason=reason))
    return accepted, rejected


def clean_explanation(text: str, dossier: dict[str, Any]) -> str:
    """Drop every sentence that states a number or date absent from the dossier, or uses
    decision wording. Never rewrites what is left."""
    evidence = Evidence().add(dossier)
    kept = [
        s
        for s in _SENTENCE.split(text.strip())
        if s and not unsupported(s, evidence) and not _DECISION.search(s)
    ]
    return " ".join(kept)
