"""STUB. Owner: @role-4-external-agents. Deterministic fuzzy name matching (stdlib only, no LLM).

Implement:
- normalize_name: casefold, strip diacritics (ș/ş, ț/ţ, ă, â, î), drop legal-form tokens
  (SRL, SA, S.R.L., LTD, LLC...), collapse punctuation/whitespace, sort tokens.
- similarity: token-set ratio via difflib.SequenceMatcher on the normalized forms, in [0, 1].
- best_matches: screen a name against normalized entries (names + aliases). Return the top
  hits with their score and the entry. Pre-index entries by first-token / initials so the whole
  portfolio can be re-screened quickly when a list changes.
"""

from __future__ import annotations

from typing import Any


def normalize_name(name: str) -> str:
    raise NotImplementedError


def similarity(a: str, b: str) -> float:
    raise NotImplementedError


def best_matches(
    name: str, entries: list[dict[str, Any]], *, min_score: float = 0.85, limit: int = 5
) -> list[tuple[float, dict[str, Any]]]:
    raise NotImplementedError
