"""Build every port implementation from Settings. The ONE place that maps config -> infrastructure.

Owner: @role-2-core. API and worker call build_infra() once per process.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

import httpx

from verifirm.adapters.base import AdapterDeps, BaseAdapter
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import SystemClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.impl_local.queue import MemoryQueue
from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter
from verifirm.core.impl_local.repository import MemoryRepository
from verifirm.core.impl_local.web_search import FixtureWebSearch
from verifirm.core.ports import (
    Cache,
    Clock,
    LLMClient,
    ObjectStore,
    Queue,
    RateLimiter,
    Repository,
    WebSearch,
)
from verifirm.core.registry import discover_adapters

RUNS_TOPIC = "runs"


def run_events_topic(run_id: str) -> str:
    return f"run-events:{run_id}"


def _queue(s: Settings) -> Queue:
    if s.queue_backend == "redis":
        from verifirm.core.impl_cloud.queue import RedisQueue

        return RedisQueue(s.redis_url)
    if s.queue_backend == "sqs":
        from verifirm.core.impl_cloud.queue import SqsQueue

        if not s.sqs_queue_url:
            raise ValueError("QUEUE_BACKEND=sqs needs SQS_QUEUE_URL")
        return SqsQueue(s.sqs_queue_url, s.aws_region)
    return MemoryQueue()


def _cache(s: Settings) -> Cache:
    if s.cache_backend == "redis":
        from verifirm.core.impl_cloud.cache import RedisCache

        return RedisCache(s.redis_url)
    return MemoryCache()


def _object_store(s: Settings) -> ObjectStore:
    if s.object_store_backend == "s3":
        from verifirm.core.impl_cloud.object_store import S3ObjectStore

        if not s.s3_bucket:
            raise ValueError("OBJECT_STORE_BACKEND=s3 needs S3_BUCKET")
        return S3ObjectStore(s.s3_bucket, s.aws_region)
    return FilesystemObjectStore(s.object_store_path)


def _rate_limiter(s: Settings) -> RateLimiter:
    if s.rate_limiter_backend == "redis":
        from verifirm.core.impl_cloud.rate_limiter import RedisRateLimiter

        return RedisRateLimiter(s.redis_url)
    return MemoryRateLimiter()


def _repository(s: Settings) -> Repository:
    if s.repository_backend == "postgres":
        from verifirm.persistence.repositories.sql_repository import SqlRepository

        return SqlRepository()
    return MemoryRepository()


@dataclass
class Infra:
    settings: Settings
    queue: Queue
    cache: Cache
    object_store: ObjectStore
    rate_limiter: RateLimiter
    repository: Repository
    clock: Clock
    http: httpx.AsyncClient = field(default_factory=httpx.AsyncClient)

    @cached_property
    def llm(self) -> LLMClient:
        from verifirm.llm import get_llm_client

        return get_llm_client(self.settings)

    @cached_property
    def adapters(self) -> dict[str, BaseAdapter]:
        """One instance of every registered adapter, sharing rate limiter/cache/archive/http."""
        deps = AdapterDeps(
            settings=self.settings,
            cache=self.cache,
            object_store=self.object_store,
            rate_limiter=self.rate_limiter,
            clock=self.clock,
            http=self.http,
        )
        return {name: cls(deps) for name, cls in discover_adapters().items()}

    @cached_property
    def web_search(self) -> WebSearch:
        if self.settings.fixture_mode or self.settings.web_search_provider == "fixture":
            return FixtureWebSearch(self.settings.fixtures_dir)
        adapter = self.adapters["web_search"]
        assert isinstance(adapter, WebSearch)
        return adapter

    async def aclose(self) -> None:
        await self.http.aclose()


def build_infra(settings: Settings) -> Infra:
    return Infra(
        settings=settings,
        queue=_queue(settings),
        cache=_cache(settings),
        object_store=_object_store(settings),
        rate_limiter=_rate_limiter(settings),
        repository=_repository(settings),
        clock=SystemClock(),
        http=httpx.AsyncClient(timeout=settings.http_timeout_s),
    )
