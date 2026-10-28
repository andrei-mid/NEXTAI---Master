from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from verifirm.adapters.base import AdapterDeps, SourceUnavailable
from verifirm.adapters.mocks.restante import MockRestanteAdapter
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


async def test_brunaldo_has_arrears(tmp_path: Path) -> None:
    result = await MockRestanteAdapter(deps(tmp_path)).arrears("99000033")
    assert result.data["list_period"] == "2026-Q2"
    assert sum(o["amount_ron"] for o in result.data["obligations"]) == 412_560 + 96_300
    assert result.source.type is SourceType.MOCK
    assert result.source.name == "ANAF tax arrears list (MOCK)"


async def test_aurora_checked_and_clean(tmp_path: Path) -> None:
    result = await MockRestanteAdapter(deps(tmp_path)).arrears("99000017")
    assert result.data["obligations"] == []


async def test_works_the_same_outside_fixture_mode(tmp_path: Path) -> None:
    result = await MockRestanteAdapter(deps(tmp_path, fixture_mode=False)).arrears("99000033")
    assert result.data["obligations"]


async def test_missing_file_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailable):
        await MockRestanteAdapter(deps(tmp_path)).arrears("2816464")


@pytest.mark.parametrize("content", [{"list_period": "2026-Q2"}, {"obligations": []}, [1, 2]])
async def test_wrong_shape_is_unavailable(tmp_path: Path, content: Any) -> None:
    fixtures = broken_fixtures(tmp_path, "restante.json", content)
    with pytest.raises(SourceUnavailable):
        await MockRestanteAdapter(deps(tmp_path, fixtures)).arrears("99000999")
