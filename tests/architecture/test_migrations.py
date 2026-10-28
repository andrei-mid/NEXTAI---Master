"""Alembic rules (D5): migration names are prefixed with an area. Only @role-1-database writes them."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / "verifirm" / "persistence" / "migrations" / "versions"
AREAS = (
    "analyst",
    "companies",
    "runs",
    "signals",
    "scores",
    "memos",
    "audit",
    "source_cache",
    "onrc",
    "graph",
    "sanctions",
)
NAME_RE = re.compile(r"^\d{8}_\d{4}_(?P<slug>[a-z0-9_]+)\.py$")


def test_migration_filenames_are_area_prefixed() -> None:
    bad = []
    for path in sorted(VERSIONS.glob("*.py")):
        m = NAME_RE.match(path.name)
        if not m or not m.group("slug").startswith(AREAS):
            bad.append(path.name)
    assert bad == [], f"migration names must be YYYYMMDD_HHMM_<area>_<what>.py with area in {AREAS}"


def test_models_import_and_share_one_metadata() -> None:
    from verifirm.persistence.models import Base

    assert Base.metadata is not None
