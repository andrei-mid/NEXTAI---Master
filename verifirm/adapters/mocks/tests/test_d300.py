from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from verifirm.adapters.base import AdapterDeps, SourceUnavailable
from verifirm.adapters.mocks.d300 import MockD300Adapter
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter
from verifirm.schema.signals import SourceType

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures"


def deps(tmp_path: Path, fixtures: Path = FIXTURES, fixture_mode: bool = True) -> AdapterDeps:
    return AdapterDeps(
        settings=Settings(fixture_mode=fixture_mode, fixtures_dir=fixtures),
        cache=MemoryCache(),
        object_store=FilesystemObjectStore(tmp_path / "objects"),
        rate_limiter=MemoryRateLimiter(),
        clock=FixedClock(datetime(2026, 10, 28, tzinfo=UTC)),
    )


def broken_fixtures(tmp_path: Path, filename: str, content: Any) -> Path:
    """A fixtures dir where company 99000999 has `filename` with `content`."""
    root = tmp_path / "fixtures"
    target = root / "companies" / "99000999_broken" / filename
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(content), encoding="utf-8")
    return root


async def test_brunaldo_returns(tmp_path: Path) -> None:
    result = await MockD300Adapter(deps(tmp_path)).returns("99000033")
    assert [r["period"] for r in result.data] == ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"]
    assert sum(r["taxable_base_ron"] for r in result.data) == 12_464_000
    assert result.source.type is SourceType.MOCK


async def test_missing_file_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailable):
        await MockD300Adapter(deps(tmp_path)).returns("99000041")


async def test_wrong_shape_is_unavailable(tmp_path: Path) -> None:
    fixtures = broken_fixtures(tmp_path, "d300.json", {"returns": "none"})
    with pytest.raises(SourceUnavailable):
        await MockD300Adapter(deps(tmp_path, fixtures)).returns("99000999")
