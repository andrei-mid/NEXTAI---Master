"""web_search: the presence footprint (website + job postings). Tavily search() is still TODO."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from verifirm.adapters.base import AdapterDeps, SourceUnavailable
from verifirm.adapters.web_search import TavilyWebSearch
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter
from verifirm.schema.signals import SourceType

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def adapter(
    tmp_path: Path, *, fixture_mode: bool = True, fixtures: Path = FIXTURES
) -> TavilyWebSearch:
    return TavilyWebSearch(
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


async def test_aurora_has_a_website_and_jobs(tmp_path: Path) -> None:
    result = await adapter(tmp_path).footprint("99000017", "AURORA SOFT LABS SRL")
    assert result.data["website"]["url"] == "https://aurora-soft-labs.example"
    assert len(result.data["jobs"]) == 2
    assert result.source.type is SourceType.WEB


async def test_zephyria_has_nothing(tmp_path: Path) -> None:
    result = await adapter(tmp_path).footprint("99000025", "ZEPHYRIA LOGISTIC NOVA SRL")
    assert result.data == {"website": None, "jobs": []}  # searched, nothing found


async def test_live_is_unavailable_never_empty(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailable, match="Tavily"):
        await adapter(tmp_path, fixture_mode=False).footprint("2816464", "DEDEMAN SRL")


@pytest.mark.parametrize("content", [{"website": "yes", "jobs": []}, {"website": None}])
async def test_wrong_shape_is_unavailable(tmp_path: Path, content: Any) -> None:
    with pytest.raises(SourceUnavailable):
        await adapter(tmp_path, fixtures=broken(tmp_path, content)).footprint("99000999", "X")


def test_tavily_search_todo() -> None:
    pytest.skip("TODO: @role-4-external-agents TavilyWebSearch.search (media agent)")
