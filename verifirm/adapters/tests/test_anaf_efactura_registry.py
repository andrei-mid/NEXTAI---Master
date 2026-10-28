"""anaf_efactura_registry: derived from the v9 record, no call of its own."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from verifirm.adapters.anaf_efactura_registry import AnafEfacturaRegistryAdapter
from verifirm.adapters.base import AdapterDeps, SourceUnavailable
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def _adapter(
    tmp_path: Path, fixture_mode: bool = True, http: httpx.AsyncClient | None = None
) -> AnafEfacturaRegistryAdapter:
    return AnafEfacturaRegistryAdapter(
        AdapterDeps(
            settings=Settings(fixture_mode=fixture_mode, fixtures_dir=FIXTURES),
            cache=MemoryCache(),
            object_store=FilesystemObjectStore(tmp_path / "objects"),
            rate_limiter=MemoryRateLimiter(),
            clock=FixedClock(datetime(2026, 10, 28, tzinfo=UTC)),
            http=http,
        )
    )


@pytest.mark.parametrize(("cui", "expected"), [("99000033", True), ("99000058", False)])
async def test_flag_from_v9_fixture(tmp_path: Path, cui: str, expected: bool) -> None:
    result = await _adapter(tmp_path).is_registered(cui)
    assert result.data is expected
    assert result.source.name == "ANAF VAT registry v9"  # the real origin of the fact


async def test_flag_missing_is_unknown(tmp_path: Path) -> None:
    fixtures = tmp_path / "fixtures"
    company = fixtures / "companies" / "99000999_x"
    company.mkdir(parents=True)
    record = {"date_generale": {"cui": 99000999}, "stare_inactiv": {"statusInactivi": False}}
    (company / "anaf_v9.json").write_text(json.dumps({"found": [record], "notFound": []}))
    adapter = _adapter(tmp_path)
    adapter.settings.fixtures_dir = fixtures
    assert (await adapter.is_registered("99000999")).data is None


async def test_no_v9_data_is_unavailable_and_never_calls(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    transport = httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(500))
    adapter = _adapter(tmp_path, fixture_mode=False, http=httpx.AsyncClient(transport=transport))
    with pytest.raises(SourceUnavailable):
        await adapter.is_registered("99000025")
    assert calls == []


async def test_a_sync_adapter_still_never_calls_anaf(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    transport = httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(500))
    deps = _adapter(tmp_path, fixture_mode=False).deps
    deps.http = httpx.AsyncClient(transport=transport)
    deps.network = True
    with pytest.raises(SourceUnavailable):
        await AnafEfacturaRegistryAdapter(deps).is_registered("99000025")
    assert calls == []
