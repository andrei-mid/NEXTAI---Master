"""seap: SEAP contracts. Fixture mode reads presence.json; live is unavailable until ingest."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from verifirm.adapters.base import AdapterDeps, SourceUnavailable
from verifirm.adapters.seap import SeapAdapter
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter
from verifirm.schema.signals import SourceType

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def adapter(tmp_path: Path, *, fixture_mode: bool = True, fixtures: Path = FIXTURES) -> SeapAdapter:
    return SeapAdapter(
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


async def test_zephyria_has_no_contracts(tmp_path: Path) -> None:
    result = await adapter(tmp_path).contracts_for("99000025")
    assert result.data == []  # checked, none found
    assert result.source.type is SourceType.OFFICIAL
    assert (
        result.source.raw_ref == "fixture:companies/99000025_zephyria_logistic_nova/presence.json"
    )


async def test_no_presence_file_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailable):
        await adapter(tmp_path).contracts_for("99000041")


async def test_live_is_unavailable_never_empty(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailable, match="ingest"):
        await adapter(tmp_path, fixture_mode=False).contracts_for("2816464")


@pytest.mark.parametrize("content", [{"seap": "none"}, {"jobs": []}, [1]])
async def test_wrong_shape_is_unavailable(tmp_path: Path, content: Any) -> None:
    with pytest.raises(SourceUnavailable):
        await adapter(tmp_path, fixtures=broken(tmp_path, content)).contracts_for("99000999")
