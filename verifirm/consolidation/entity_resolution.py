"""Entity resolution over all agents' signals.

1. Dedupe: the same signal_id keeps one copy. The same fact from two sources (same rule_id and
   same `data`) keeps the official one and names the other source in data["also_seen_in"].
2. Check each signal refers to THIS company, by its entity_match.method:
   - cui_exact: the signal's cui must equal the identity's.
   - name+county: data["county"] must equal the registered office's county (or a past one).
   - name_fuzzy: data["matched_name"] (or "name") must resemble a name of the company.
   - person_name: data["person"] must be one of its administrators / shareholders.
   A missing key can't be checked, so the match becomes ambiguous (never silently trusted).
3. Ambiguous matches get a lower `confidence` and entity_match.ambiguous=True. Clear
   non-matches are DROPPED and counted in AgentResult.notes.
4. An AgentResult's status is never changed: resolution can't turn a failure into clean.
Inputs are not mutated.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from verifirm.schema.identity import IdentitySheet
from verifirm.schema.signals import AgentResult, EntityMatch, Signal, SourceType

# Higher = preferred when the same fact comes from two sources.
_SOURCE_RANK = {
    SourceType.OFFICIAL: 5,
    SourceType.AGGREGATOR: 4,
    SourceType.SUBMITTED: 3,
    SourceType.MOCK: 2,
    SourceType.WEB: 1,
}


@dataclass(frozen=True)
class ResolutionConfig:
    """Tunables. PENDING (DECISIONS.md): move to scoring/config/weights.yaml (role 2)."""

    ambiguous_factor: float = 0.5  # confidence multiplier for ambiguous matches
    name_match_min: float = 0.90  # similarity at/above which a fuzzy name is a match
    name_drop_below: float = 0.60  # similarity below which it is a clear non-match


def _norm(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", folded.lower()).strip()


def _county_norm(text: str) -> str:
    return re.sub(r"^(judetul|jud|municipiul)\s+", "", _norm(text))


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _first_str(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _identity_names(identity: IdentitySheet) -> list[str]:
    return [identity.current_name, *[n.name for n in identity.names]]


def _identity_people(identity: IdentitySheet) -> list[str]:
    return [p.name for p in [*identity.administrators, *identity.shareholders]]


def _verdict(identity: IdentitySheet, signal: Signal, cfg: ResolutionConfig) -> str:
    """'match' | 'ambiguous' | 'drop'"""
    method = signal.entity_match.method
    data = signal.data
    if method == "cui_exact":
        return "match" if signal.cui == identity.cui else "drop"
    if method == "name+county":
        county = _first_str(data, "county")
        counties = [a.county for a in [identity.registered_office, *identity.office_history] if a]
        known = {_county_norm(c) for c in counties if c}
        if county is None or not known:
            return "ambiguous"
        return "match" if _county_norm(county) in known else "drop"
    if method == "name_fuzzy":
        name = _first_str(data, "matched_name", "name")
        if name is None:
            return "ambiguous"
        best = max((_similarity(name, n) for n in _identity_names(identity)), default=0.0)
        if best >= cfg.name_match_min:
            return "match"
        return "ambiguous" if best >= cfg.name_drop_below else "drop"
    if method == "person_name":
        person = _first_str(data, "person", "person_name")
        people = _identity_people(identity)
        if person is None or not people:
            return "ambiguous"
        best = max(_similarity(person, p) for p in people)
        if best >= cfg.name_match_min:
            return "match"
        return "ambiguous" if best >= cfg.name_drop_below else "drop"
    return "ambiguous"  # a method we don't know can't be trusted


def _fact_key(signal: Signal) -> tuple[str, str]:
    return signal.rule_id, json.dumps(signal.data, sort_keys=True, default=str)


def _rank(signal: Signal) -> tuple[int, float]:
    return _SOURCE_RANK[signal.source.type], signal.confidence


def _mark_ambiguous(signal: Signal, cfg: ResolutionConfig) -> Signal:
    if signal.entity_match.ambiguous:
        return signal  # the agent already said so (and lowered the confidence itself)
    match = EntityMatch(
        method=signal.entity_match.method, score=signal.entity_match.score, ambiguous=True
    )
    return signal.model_copy(
        update={
            "entity_match": match,
            "confidence": round(signal.confidence * cfg.ambiguous_factor, 4),
        }
    )


def resolve(
    identity: IdentitySheet,
    results: list[AgentResult],
    config: ResolutionConfig | None = None,
) -> list[AgentResult]:
    cfg = config or ResolutionConfig()

    # --- 2/3: is it this company? (per signal, keeps the result structure)
    kept: dict[int, list[Signal]] = {}
    dropped_entity: dict[int, int] = {}
    for i, result in enumerate(results):
        signals: list[Signal] = []
        for signal in result.signals:
            verdict = _verdict(identity, signal, cfg)
            if verdict == "drop":
                dropped_entity[i] = dropped_entity.get(i, 0) + 1
            elif verdict == "ambiguous":
                signals.append(_mark_ambiguous(signal, cfg))
            else:
                signals.append(signal)
        kept[i] = signals

    # --- 1: dedupe across all results. The best copy of each fact wins.
    dupes: dict[int, int] = {}
    by_id: dict[str, tuple[int, Signal]] = {}
    for i, signals in kept.items():
        for signal in signals:
            current = by_id.get(signal.signal_id)
            if current is None:
                by_id[signal.signal_id] = (i, signal)
            elif _rank(signal) > _rank(current[1]):
                dupes[current[0]] = dupes.get(current[0], 0) + 1
                by_id[signal.signal_id] = (i, signal)
            else:
                dupes[i] = dupes.get(i, 0) + 1

    groups: dict[tuple[str, str], list[tuple[int, Signal]]] = {}
    for entry in by_id.values():
        groups.setdefault(_fact_key(entry[1]), []).append(entry)

    survivors: dict[str, tuple[int, Signal]] = {}
    for entries in groups.values():
        entries.sort(key=lambda e: _rank(e[1]), reverse=True)
        top_owner, top = entries[0]
        also_seen: set[str] = set()
        survivors_here = [entries[0]]
        for owner, other in entries[1:]:
            if other.source.name != top.source.name:  # same fact, another source: merge
                also_seen.add(other.source.name)
                dupes[owner] = dupes.get(owner, 0) + 1
            else:
                survivors_here.append((owner, other))
        if also_seen:
            top = top.model_copy(update={"data": {**top.data, "also_seen_in": sorted(also_seen)}})
        survivors[top.signal_id] = (top_owner, top)
        for owner, other in survivors_here[1:]:
            survivors[other.signal_id] = (owner, other)

    out: list[AgentResult] = []
    for i, result in enumerate(results):
        # Original order, each surviving signal in the result that owns it.
        signals = [survivors[s.signal_id][1] for s in kept[i] if survivors[s.signal_id][0] == i]
        seen_ids: set[str] = set()
        signals = [s for s in signals if not (s.signal_id in seen_ids or seen_ids.add(s.signal_id))]
        notes = [result.notes] if result.notes else []
        if dropped_entity.get(i):
            notes.append(
                f"entity resolution dropped {dropped_entity[i]} signal(s) that do not refer to this company"
            )
        if dupes.get(i):
            notes.append(f"entity resolution merged {dupes[i]} duplicate signal(s)")
        out.append(
            result.model_copy(update={"signals": signals, "notes": "; ".join(notes) or None})
        )
    return out
