from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from verifirm.adapters.base import AdapterDeps, SourceUnavailable
from verifirm.adapters.mocks.efactura import MockEfacturaAdapter
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


async def test_brunaldo_totals(tmp_path: Path) -> None:
    result = await MockEfacturaAdapter(deps(tmp_path)).invoice_flows("99000033")
    assert result.data["issued_total_ron"] == 15_200_000
    assert result.data["period"] == {"from": "2025-01-01", "to": "2025-12-31"}
    assert result.source.type is SourceType.MOCK


async def test_zephyria_has_flows(tmp_path: Path) -> None:
    result = await MockEfacturaAdapter(deps(tmp_path)).invoice_flows("99000025")
    assert len(result.data["flows"]) >= 3


async def test_missing_file_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailable):
        await MockEfacturaAdapter(deps(tmp_path)).invoice_flows("2816464")


async def test_wrong_shape_is_unavailable(tmp_path: Path) -> None:
    content = {"period": {}, "issued_total_ron": "a lot", "received_total_ron": 0, "flows": []}
    fixtures = broken_fixtures(tmp_path, "efactura.json", content)
    with pytest.raises(SourceUnavailable):
        await MockEfacturaAdapter(deps(tmp_path, fixtures)).invoice_flows("99000999")
