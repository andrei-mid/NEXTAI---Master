from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from verifirm.adapters.base import AdapterDeps, BaseAdapter, SourceUnavailable
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter


class _Demo(BaseAdapter):
    name = "demo"


def _deps(
    tmp_path: Path, *, fixture_mode: bool, handler: httpx.MockTransport | None = None
) -> AdapterDeps:
    settings = Settings(fixture_mode=fixture_mode, fixtures_dir=tmp_path / "fx", http_max_retries=1)
    return AdapterDeps(
        settings=settings,
        cache=MemoryCache(),
        object_store=FilesystemObjectStore(tmp_path / "objects"),
        rate_limiter=MemoryRateLimiter(),
        clock=FixedClock(datetime(2026, 10, 28, tzinfo=UTC)),
        http=httpx.AsyncClient(transport=handler) if handler else None,
    )


async def _get(c: httpx.AsyncClient) -> httpx.Response:
    return await c.get("https://example.test/x")


async def test_fixture_mode_reads_fixture(tmp_path: Path) -> None:
    fx = tmp_path / "fx" / "companies" / "99000017_aurora"
    fx.mkdir(parents=True)
    (fx / "anaf_v9.json").write_text('{"found": []}')
    adapter = _Demo(_deps(tmp_path, fixture_mode=True))
    result = await adapter.fetch(
        cache_key="k", request=_get, fixture=adapter.company_fixture("99000017", "anaf_v9.json")
    )
    assert result.fixture and result.json() == {"found": []}
    assert result.source.raw_ref == "fixture:companies/99000017_aurora/anaf_v9.json"


async def test_fixture_mode_without_fixture_is_unavailable(tmp_path: Path) -> None:
    adapter = _Demo(_deps(tmp_path, fixture_mode=True))
    with pytest.raises(SourceUnavailable):
        await adapter.fetch(cache_key="k", request=_get, fixture=None)


async def test_live_archives_caches_and_falls_back(tmp_path: Path) -> None:
    calls = {"n": 0, "fail": False}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503) if calls["fail"] else httpx.Response(200, content=b'{"ok": 1}')

    deps = _deps(tmp_path, fixture_mode=False, handler=httpx.MockTransport(handler))
    adapter = _Demo(deps)
    first = await adapter.fetch(cache_key="k", request=_get, url="https://example.test/x")
    assert first.source.content_hash and first.source.raw_ref
    second = await adapter.fetch(cache_key="k", request=_get)
    assert second.from_cache and calls["n"] == 1

    # cache expired + source down -> last-known-good copy, flagged stale
    await deps.cache.delete(adapter._key("cache", "k"))
    calls["fail"] = True
    third = await adapter.fetch(cache_key="k", request=_get)
    assert third.stale and third.json() == {"ok": 1}

    with pytest.raises(SourceUnavailable):
        await adapter.fetch(cache_key="other", request=_get)
