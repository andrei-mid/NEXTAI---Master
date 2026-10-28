"""BaseAdapter: everything an external source needs, so each adapter only knows its own API.

`fetch()` gives every adapter, in order:
  1. FIXTURE_MODE=1 -> read fixtures/ (no network). Missing fixture -> last-known-good copy
     -> SourceUnavailable.
  2. cache hit (TTL per adapter, default 24h)  -> archived raw bytes
  3. rate limit (shared across workers via the RateLimiter port)
  4. HTTP call with retry + exponential backoff on timeouts, 429 and 5xx
  5. archive raw bytes in the ObjectStore (content hash -> audit + replay)
  6. remember it as last-known-good (fallback when the source is down later)
On failure after retries: last-known-good copy (stale=True) or SourceUnavailable.

A missing source is NEVER clean. Agents catch SourceUnavailable and put the adapter
in `sources_failed`.

Adapters never import agents (tests/architecture/test_imports.py).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

import httpx

from verifirm.core.config import Settings
from verifirm.core.logging import get_logger
from verifirm.core.ports.cache import Cache
from verifirm.core.ports.clock import Clock
from verifirm.core.ports.object_store import ObjectStore, content_hash
from verifirm.core.ports.rate_limiter import RateLimit, RateLimiter
from verifirm.schema.signals import SourceRef, SourceType

log = get_logger(__name__)


RequestFn = Callable[[httpx.AsyncClient], Awaitable[httpx.Response]]


class SourceUnavailable(Exception):
    """The source could not be read (down, timeout, no fixture, switched off...)."""

    def __init__(self, adapter: str, reason: str) -> None:
        super().__init__(f"{adapter}: {reason}")
        self.adapter = adapter
        self.reason = reason


@dataclass
class AdapterDeps:
    settings: Settings
    cache: Cache
    object_store: ObjectStore
    rate_limiter: RateLimiter
    clock: Clock
    http: httpx.AsyncClient | None = None  # shared client. Created lazily if None.


@dataclass(frozen=True)
class FetchResult:
    body: bytes
    source: SourceRef
    from_cache: bool = False
    stale: bool = False  # served from the last-known-good copy after a live failure
    fixture: bool = False

    def json(self) -> Any:
        return json.loads(self.body)

    def text(self, encoding: str = "utf-8") -> str:
        return self.body.decode(encoding)


@dataclass(frozen=True)
class Sourced[T]:
    """Parsed adapter output plus where it came from. Agents copy `source` into signals."""

    data: T
    source: SourceRef
    stale: bool = False


class BaseAdapter:
    """Subclass, decorate with @register_adapter("<name>"), set the class attributes,
    and implement source-specific methods on top of `fetch()`."""

    name: ClassVar[str] = "base"  # set by @register_adapter
    source_label: ClassVar[str] = ""  # human readable, shown in the UI ("ANAF VAT v9")
    source_type: ClassVar[SourceType] = SourceType.OFFICIAL
    rate_limit: ClassVar[RateLimit | None] = None
    rate_limit_key: ClassVar[str | None] = None  # share a limit across adapters (same host)
    cache_ttl_s: ClassVar[int | None] = None  # None -> settings.cache_ttl_s
    retry_statuses: ClassVar[frozenset[int]] = frozenset({429, 500, 502, 503, 504})

    def __init__(self, deps: AdapterDeps) -> None:
        self.deps = deps
        self.settings = deps.settings
        self._http = deps.http

    # ------------------------------------------------------------------ fixtures
    @property
    def fixtures_dir(self) -> Path:
        return self.settings.fixtures_dir

    def company_fixture_dir(self, cui: str) -> Path | None:
        """fixtures/companies/<cui>_<slug>/, or None."""
        matches = sorted((self.fixtures_dir / "companies").glob(f"{cui}_*"))
        return matches[0] if matches else None

    def company_fixture(self, cui: str, filename: str) -> Path | None:
        directory = self.company_fixture_dir(cui)
        if directory is None:
            return None
        path = directory / filename
        return path if path.exists() else None

    def shared_fixture(self, relative: str) -> Path | None:
        path = self.fixtures_dir / "sources" / relative
        return path if path.exists() else None

    # ------------------------------------------------------------------ main entry
    async def fetch(
        self,
        *,
        cache_key: str,
        request: RequestFn,
        url: str | None = None,
        fixture: Path | None = None,
    ) -> FetchResult:
        """Fetch one resource. `cache_key` must uniquely identify the request
        (e.g. f"{cui}:{date}"). `fixture` is the file to serve in FIXTURE_MODE."""
        if self.settings.fixture_mode:
            return await self._from_fixture(cache_key, fixture, url)

        cached = await self._from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            body = await self._call_with_retry(request)
        except SourceUnavailable as exc:
            fallback = await self._last_good(cache_key)
            if fallback is not None:
                log.warning("serving last-known-good copy", extra={"adapter": self.name})
                return fallback
            raise exc

        return await self._archive(cache_key, body, url)

    # ------------------------------------------------------------------ internals
    def _source_ref(
        self, url: str | None, raw_ref: str | None, digest: str | None, at: datetime
    ) -> SourceRef:
        return SourceRef(
            name=self.source_label or self.name,
            type=self.source_type,
            url=url,  # pydantic coerces str -> HttpUrl
            retrieved_at=at,
            raw_ref=raw_ref,
            content_hash=digest,
        )

    def _key(self, kind: str, cache_key: str) -> str:
        digest = hashlib.sha256(cache_key.encode()).hexdigest()[:32]
        return f"{kind}/{self.name}/{digest}"

    async def _from_fixture(
        self, cache_key: str, fixture: Path | None, url: str | None
    ) -> FetchResult:
        if fixture is not None and await asyncio.to_thread(fixture.exists):
            body = await asyncio.to_thread(fixture.read_bytes)
            rel = fixture.relative_to(self.fixtures_dir).as_posix()
            return FetchResult(
                body=body,
                source=self._source_ref(
                    url, f"fixture:{rel}", content_hash(body), self.deps.clock.now()
                ),
                fixture=True,
            )
        fallback = await self._last_good(cache_key)
        if fallback is not None:
            return fallback
        raise SourceUnavailable(self.name, f"no fixture for {cache_key!r}")

    async def _from_cache(self, cache_key: str) -> FetchResult | None:
        meta_raw = await self.deps.cache.get(self._key("cache", cache_key))
        if meta_raw is None:
            return None
        meta = json.loads(meta_raw)
        body = await self.deps.object_store.get(meta["raw_ref"])
        if body is None:
            return None
        return FetchResult(
            body=body,
            source=self._source_ref(
                meta.get("url"),
                meta["raw_ref"],
                meta["content_hash"],
                datetime.fromisoformat(meta["retrieved_at"]),
            ),
            from_cache=True,
        )

    async def _last_good(self, cache_key: str) -> FetchResult | None:
        meta_raw = await self.deps.object_store.get(self._key("lastgood", cache_key))
        if meta_raw is None:
            return None
        meta = json.loads(meta_raw)
        body = await self.deps.object_store.get(meta["raw_ref"])
        if body is None:
            return None
        return FetchResult(
            body=body,
            source=self._source_ref(
                meta.get("url"),
                meta["raw_ref"],
                meta["content_hash"],
                datetime.fromisoformat(meta["retrieved_at"]),
            ),
            stale=True,
        )

    async def _archive(self, cache_key: str, body: bytes, url: str | None) -> FetchResult:
        at = self.deps.clock.now()
        raw_ref = await self.deps.object_store.put(body, prefix=f"raw/{self.name}")
        digest = content_hash(body)
        meta = json.dumps(
            {"raw_ref": raw_ref, "content_hash": digest, "retrieved_at": at.isoformat(), "url": url}
        ).encode()
        ttl = self.settings.ttl_for(self.name, self.cache_ttl_s)
        await self.deps.cache.set(self._key("cache", cache_key), meta, ttl_s=ttl)
        await self.deps.object_store.put_named(self._key("lastgood", cache_key), meta)
        return FetchResult(body=body, source=self._source_ref(url, raw_ref, digest, at))

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self.settings.http_timeout_s)
        return self._http

    async def _call_with_retry(self, request: RequestFn) -> bytes:
        attempts = max(1, self.settings.http_max_retries + 1)
        last_error = "unknown error"
        for attempt in range(attempts):
            if self.rate_limit is not None:
                await self.deps.rate_limiter.acquire(
                    self.rate_limit_key or self.name, self.rate_limit
                )
            try:
                response = await request(await self._client())
            except httpx.TransportError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code < 400:
                    return response.content
                if response.status_code not in self.retry_statuses:
                    raise SourceUnavailable(self.name, f"HTTP {response.status_code}")
                last_error = f"HTTP {response.status_code}"
            if attempt < attempts - 1:
                await asyncio.sleep(0.5 * 2**attempt)
        raise SourceUnavailable(self.name, f"failed after {attempts} attempts: {last_error}")
