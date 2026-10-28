from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from verifirm.adapters.base import AdapterDeps, BaseAdapter, SourceUnavailable
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter

T0 = datetime(2026, 10, 28, tzinfo=UTC)


class _Demo(BaseAdapter):
    name = "demo"
    mirror_max_age_s = 3600


def _deps(
    tmp_path: Path,
    *,
    fixture_mode: bool = False,
    network: bool = False,
    handler: httpx.MockTransport | None = None,
    clock: FixedClock | None = None,
) -> AdapterDeps:
    return AdapterDeps(
        settings=Settings(
            fixture_mode=fixture_mode, fixtures_dir=tmp_path / "fx", http_max_retries=0
        ),
        cache=MemoryCache(),
        object_store=FilesystemObjectStore(tmp_path / "objects"),  # shared on disk = the mirror
        rate_limiter=MemoryRateLimiter(),
        clock=clock or FixedClock(T0),
        http=httpx.AsyncClient(transport=handler) if handler else None,
        network=network,
    )


async def _get(c: httpx.AsyncClient) -> httpx.Response:
    return await c.get("https://example.test/x")


class _Counter:
    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        return httpx.Response(503) if self.fail else httpx.Response(200, content=b'{"ok": 1}')


async def test_fixture_mode_reads_fixture(tmp_path: Path) -> None:
    fx = tmp_path / "fx" / "companies" / "99000017_aurora"
    fx.mkdir(parents=True)
    (fx / "anaf_v9.json").write_text('{"found": []}')
    adapter = _Demo(_deps(tmp_path, fixture_mode=True, network=True))
    result = await adapter.fetch(
        cache_key="k", request=_get, fixture=adapter.company_fixture("99000017", "anaf_v9.json")
    )
    assert result.fixture and result.json() == {"found": []}
    assert result.source.raw_ref == "fixture:companies/99000017_aurora/anaf_v9.json"


async def test_fixture_mode_without_fixture_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailable):
        await _Demo(_deps(tmp_path, fixture_mode=True)).fetch(cache_key="k", request=_get)


async def test_agents_never_call_the_network(tmp_path: Path) -> None:
    counter = _Counter()
    reader = _Demo(_deps(tmp_path, network=False, handler=httpx.MockTransport(counter)))
    with pytest.raises(SourceUnavailable, match="not in the local mirror"):
        await reader.fetch(cache_key="k", request=_get)
    assert counter.calls == 0


async def test_sync_fills_the_mirror_then_readers_use_it(tmp_path: Path) -> None:
    counter = _Counter()
    syncer = _Demo(_deps(tmp_path, network=True, handler=httpx.MockTransport(counter)))
    first = await syncer.fetch(cache_key="k", request=_get, url="https://example.test/x")
    assert counter.calls == 1 and first.source.content_hash and not first.from_mirror

    again = await syncer.fetch(cache_key="k", request=_get)  # fresh -> no second call
    assert again.from_mirror and counter.calls == 1

    reader = _Demo(_deps(tmp_path, network=False))  # another process, same mirror
    local = await reader.fetch(cache_key="k", request=_get)
    assert local.from_mirror and not local.stale and local.json() == {"ok": 1}
    assert local.source.retrieved_at == T0


async def test_old_mirror_copy_is_served_as_stale_to_agents(tmp_path: Path) -> None:
    counter = _Counter()
    await _Demo(_deps(tmp_path, network=True, handler=httpx.MockTransport(counter))).fetch(
        cache_key="k", request=_get
    )
    later = FixedClock(T0 + timedelta(hours=2))  # > mirror_max_age_s
    result = await _Demo(_deps(tmp_path, network=False, clock=later)).fetch(
        cache_key="k", request=_get
    )
    assert result.stale and result.from_mirror and counter.calls == 1


async def test_sync_refreshes_old_copy_and_falls_back_when_source_is_down(tmp_path: Path) -> None:
    counter = _Counter()
    mock = httpx.MockTransport(counter)
    await _Demo(_deps(tmp_path, network=True, handler=mock)).fetch(cache_key="k", request=_get)
    later = FixedClock(T0 + timedelta(hours=2))
    refreshed = await _Demo(_deps(tmp_path, network=True, handler=mock, clock=later)).fetch(
        cache_key="k", request=_get
    )
    assert counter.calls == 2 and not refreshed.from_mirror

    counter.fail = True
    much_later = FixedClock(T0 + timedelta(hours=5))
    fallback = await _Demo(_deps(tmp_path, network=True, handler=mock, clock=much_later)).fetch(
        cache_key="k", request=_get
    )
    assert fallback.stale and fallback.json() == {"ok": 1}
    with pytest.raises(SourceUnavailable):
        await _Demo(_deps(tmp_path, network=True, handler=mock)).fetch(
            cache_key="other", request=_get
        )


async def test_default_sync_is_a_noop(tmp_path: Path) -> None:
    report = await _Demo(_deps(tmp_path, network=True)).sync("2816464")
    assert report.skipped and report.downloaded == 0
