"""Presence rules. Severities and thresholds are PROPOSALS (docs/RULES.md, config.yaml).

Each check is a pure function: facts in -> Signal-ready facts out (or None). No I/O here.
Input that can't be checked (a footprint part missing) raises ValueError: "we couldn't look"
is never the same as "there is nothing".
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from verifirm.agents.base import RuleSpec
from verifirm.schema.signals import Component, Severity

C = Component.PRESENCE
CONFIG_PATH = Path(__file__).with_name("config.yaml")

RULES: dict[str, RuleSpec] = {
    r.rule_id: r
    for r in [
        RuleSpec(
            "PRE-NO-FOOTPRINT-01",
            C,
            Severity.MEDIUM,
            "Turnover > 5M RON but no website, no job postings, no SEAP contracts and no EU funds",
            "presence sources",
        ),
        RuleSpec(
            "PRE-ADDRESS-MISMATCH-01",
            C,
            Severity.LOW,
            "Address on the company website differs from the ONRC registered office",
            "website vs onrc_bulk",
        ),
        RuleSpec(
            "PRE-PUBLIC-CONTRACTS-01",
            C,
            Severity.INFO,
            "Company has SEAP contracts or EU-funded projects (positive footprint)",
            "seap, kohesio",
        ),
    ]
}

FOOTPRINT_PARTS = ("website", "jobs", "seap", "kohesio")

# Address words that carry no meaning for the comparison, and common abbreviations.
_ABBREVIATIONS = {
    "str": "strada",
    "bd": "bulevardul",
    "bdul": "bulevardul",
    "b-dul": "bulevardul",
    "nr": "numar",
    "jud": "judetul",
    "mun": "municipiul",
    "sect": "sector",
    "sos": "soseaua",
    "cal": "calea",
}
_STOPWORDS = {"si", "de", "la", "ro", "romania"}


class PresenceConfig(BaseModel):
    """Thresholds from config.yaml (PROPOSAL)."""

    min_turnover_ron: int = Field(ge=0)
    no_footprint_confidence: float = Field(ge=0, le=1)
    address_min_similarity: float = Field(ge=0, le=1)
    address_mismatch_confidence: float = Field(ge=0, le=1)
    turnover_years_back: int = Field(ge=1)


def load_config(path: Path = CONFIG_PATH) -> PresenceConfig:
    return PresenceConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def address_words(address: str) -> set[str]:
    """Lowercase, no diacritics or punctuation, abbreviations expanded, filler words dropped."""
    folded = unicodedata.normalize("NFKD", address)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch)).lower()
    words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", folded)
    return {_ABBREVIATIONS.get(w, w) for w in words if w not in _STOPWORDS}


def check_no_footprint(
    turnover_ron: int | None, footprint: dict[str, Any], min_turnover: int = 5_000_000
) -> dict[str, Any] | None:
    """PRE-NO-FOOTPRINT-01. footprint = {website, jobs, seap, kohesio}. Zephyria: 18.6M, nothing.

    All four parts must be known (a missing part: ValueError). No turnover, or turnover at or
    below the threshold: None (a small company with no website is normal)."""
    missing = [p for p in FOOTPRINT_PARTS if p not in footprint]
    if missing:
        raise ValueError(f"footprint not fully checked: {missing}")
    if turnover_ron is None or turnover_ron <= min_turnover:
        return None
    website = bool(footprint["website"])
    counts = {p: len(footprint[p] or []) for p in ("jobs", "seap", "kohesio")}
    if website or any(counts.values()):
        return None
    return {"turnover": turnover_ron, "website": False, **counts}


def check_address_mismatch(
    website_address: str | None, onrc_address: str | None, min_similarity: float = 0.6
) -> dict[str, Any] | None:
    """PRE-ADDRESS-MISMATCH-01. Normalize both addresses first. None if either is missing.

    Similarity = shared words / all words (after normalizing). Below `min_similarity`: mismatch."""
    if not website_address or not onrc_address:
        return None
    site, onrc = address_words(website_address), address_words(onrc_address)
    if not site or not onrc:
        return None
    similarity = round(len(site & onrc) / len(site | onrc), 2)
    if similarity >= min_similarity:
        return None
    return {
        "website_address": website_address,
        "onrc_address": onrc_address,
        "similarity": similarity,
    }


def check_public_contracts(
    seap: list[dict[str, Any]] | None, kohesio: list[dict[str, Any]] | None
) -> dict[str, Any] | None:
    """PRE-PUBLIC-CONTRACTS-01 (info, positive). None (unknown) parts are skipped."""
    contracts, projects = seap or [], kohesio or []
    if not contracts and not projects:
        return None
    return {
        "seap_contracts": len(contracts),
        "seap_value_ron": sum(int(c.get("value_ron") or 0) for c in contracts),
        "kohesio_projects": len(projects),
        "eu_contribution_eur": sum(int(p.get("eu_contribution_eur") or 0) for p in projects),
    }
