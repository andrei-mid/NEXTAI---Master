"""kohesio: EU-funded projects. Fixture mode reads presence.json; live is unavailable until ingest."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from verifirm.adapters.base import AdapterDeps, SourceUnavailable
from verifirm.adapters.kohesio import KohesioAdapter
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter
from verifirm.schema.signals import SourceType

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def adapter(
    tmp_path: Path, *, fixture_mode: bool = True, fixtures: Path = FIXTURES
) -> KohesioAdapter:
    return KohesioAdapter(
        AdapterDeps(
            settings=Settings(fixture_mode=fixture_mode, fixtures_dir=fixtures),
            cache=MemoryCache(),
            object_store=FilesystemObjectStore(tmp_path / "objects"),
            rate_limiter=MemoryRateLimiter(),
            clock=FixedClock(datetime(2026, 10, 28, tzinfo=UTC)),
        )
    )


def broken(tmp_path: Path, content: Any) -> Path:
    """A fixtures dir where company 99000999 has presence.json = `content`."""
    root = tmp_path / "fixtures"
    target = root / "companies" / "99000999_broken" / "presence.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(content), encoding="utf-8")
    return root


async def test_zephyria_has_no_projects(tmp_path: Path) -> None:
    result = await adapter(tmp_path).projects_for("ZEPHYRIA LOGISTIC NOVA SRL", "99000025")
    assert result.data == []
    assert result.source.type is SourceType.OFFICIAL


async def test_fixture_needs_a_cui(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailable, match="CUI"):
        await adapter(tmp_path).projects_for("ZEPHYRIA LOGISTIC NOVA SRL", None)


async def test_live_is_unavailable_never_empty(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailable, match="ingest"):
        await adapter(tmp_path, fixture_mode=False).projects_for("DEDEMAN SRL", "2816464")


async def test_wrong_shape_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailable):
        await adapter(tmp_path, fixtures=broken(tmp_path, {"kohesio": {}})).projects_for(
            "X", "99000999"
        )
