import asyncio
import time
from pathlib import Path

from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.impl_local.queue import MemoryQueue
from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter
from verifirm.core.impl_local.web_search import FixtureWebSearch
from verifirm.core.ports.rate_limiter import RateLimit

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


async def test_queue_dedupe_ack_nack() -> None:
    q = MemoryQueue()
    a = await q.enqueue("runs", {"cui": "1"}, dedupe_key="run-1")
    b = await q.enqueue("runs", {"cui": "1"}, dedupe_key="run-1")
    assert a == b
    msg = await q.dequeue("runs", wait_s=0.01)
    assert msg is not None and msg.attempts == 1
    await q.nack(msg)
    again = await q.dequeue("runs", wait_s=0.01)
    assert again is not None and again.attempts == 2
    await q.ack(again)
    assert await q.dequeue("runs", wait_s=0.01) is None


async def test_cache_ttl() -> None:
    c = MemoryCache()
    await c.set("k", b"v", ttl_s=0)
    assert await c.get("k") is None
    await c.set("k", b"v", ttl_s=60)
    assert await c.get("k") == b"v"


async def test_object_store_content_addressed(tmp_path: Path) -> None:
    store = FilesystemObjectStore(tmp_path)
    k1 = await store.put(b"raw", prefix="anaf_v9")
    k2 = await store.put(b"raw", prefix="anaf_v9")
    assert k1 == k2 and await store.get(k1) == b"raw"
    assert await store.get("missing/key") is None


async def test_rate_limiter_is_global_across_tasks() -> None:
    rl = MemoryRateLimiter()
    limit = RateLimit(max_calls=2, period_s=0.2)
    start = time.monotonic()
    await asyncio.gather(*(rl.acquire("anaf", limit) for _ in range(5)))
    # 5 calls at 2 per 0.2 s need at least two full windows
    assert time.monotonic() - start >= 0.38


async def test_fixture_web_search_reads_media_fixtures() -> None:
    results = await FixtureWebSearch(FIXTURES).search("ZEPHYRIA LOGISTIC NOVA")
    assert results and all(r.url.startswith("https://") and ".example/" in r.url for r in results)
