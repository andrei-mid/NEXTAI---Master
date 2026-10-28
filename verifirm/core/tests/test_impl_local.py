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


async def test_memory_repository_time_travel_matches_postgres_semantics() -> None:
    from datetime import UTC, date, datetime

    from verifirm.core.impl_local.repository import MemoryRepository
    from verifirm.schema.api import DecisionKind, DecisionRecord
    from verifirm.schema.scoring import Band, Coverage, Score

    def at(month: int) -> datetime:
        return datetime(2026, month, 15, tzinfo=UTC)

    def score(cui: str, run_id: str, band: Band, month: int) -> Score:
        return Score(
            cui=cui,
            run_id=run_id,
            band=band,
            components=[],
            coverage=Coverage(weight_pct=0, available=0, total=8),
            config_version="t",
            computed_at=at(month),
        )

    repo = MemoryRepository()
    await repo.save_score(score("99000017", "r2", Band.RED, 9))  # saved out of order
    await repo.save_score(score("99000017", "r1", Band.GREEN, 1))
    await repo.save_score(score("99000025", "r3", Band.YELLOW, 6))

    assert [s.run_id for s in await repo.list_score_history("99000017")] == ["r1", "r2"]
    assert (await repo.get_score_as_of("99000017", at(3))).band == Band.GREEN  # type: ignore[union-attr]
    assert await repo.get_score_as_of("99000017", at(1).replace(day=1)) is None
    assert await repo.list_portfolio_as_of(
        as_of=at(3), band=None, q=None, page=1, page_size=10
    ) == (["99000017"], 1)
    assert await repo.list_portfolio_as_of(
        as_of=at(10), band=Band.YELLOW, q=None, page=1, page_size=10
    ) == (["99000025"], 1)

    def decision(did: str, month: int) -> DecisionRecord:
        return DecisionRecord(
            decision_id=did,
            cui="99000017",
            decision=DecisionKind.ESCALATE,
            comment="c",
            analyst="a",
            run_id=None,
            band_at_decision=None,
            recorded_at=at(month),
        )

    await repo.record_decision(decision("d2", 6))
    await repo.record_decision(decision("d1", 2))
    between = await repo.list_decisions_between("99000017", since=at(1), until=at(12))
    assert [d.decision_id for d in between] == ["d1", "d2"]
    assert await repo.list_events("99000017", since=date(2026, 1, 1)) == []  # no signals stored
