"""BaseAdapter: everything an external source needs, so each adapter only knows its own API.

LOCAL-FIRST (docs/LOCAL_DATA.md). Every external response lives in a local MIRROR on our
server. Agents only ever read the mirror. Only sync code (jobs + the pipeline's sync step)
is allowed to call external APIs.

    adapter instance with network=False  (agents, identity sheet)  -> mirror only
    adapter instance with network=True   (sync jobs, sync step)    -> may download

`fetch()` gives every adapter, in order:
  1. FIXTURE_MODE=1 -> read fixtures/ (no network). Missing fixture -> mirror -> SourceUnavailable.
  2. mirror hit that is fresh (age < mirror_max_age_s)       -> served, no network
  3. no network allowed (agents)  -> stale mirror copy (stale=True) or SourceUnavailable
                                     ("not in the local mirror yet: run sync")
  4. network allowed (sync)       -> rate limit (global, RateLimiter port) -> HTTP with retry
                                     -> raw bytes archived content-addressed in the ObjectStore
                                     -> mirror entry updated
     live failure                 -> stale mirror copy (stale=True) or SourceUnavailable
A missing source is NEVER clean. Agents catch SourceUnavailable and put the adapter in
`sources_failed`.

Per-company adapters implement `sync(cui)` (download what the agents will need) plus READ
methods that call `fetch()`. Bulk sources (ONRC, sanctions, SEAP, Kohesio) are downloaded by
apps/worker/jobs/ingest_* instead, and their `sync()` stays a no-op.

Adapters never import agents (tests/architecture/test_imports.py).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
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
    """The source could not be read (down, not synced yet, no fixture, switched off...)."""

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
    network: bool = False  # True ONLY for sync code. Agents get network=False.


@dataclass(frozen=True)
class FetchResult:
    body: bytes
    source: SourceRef
    from_mirror: bool = False  # served from the local mirror (no network call)
    stale: bool = False  # mirror copy older than mirror_max_age_s, or served after a live failure
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


@dataclass
class SyncReport:
    """What one adapter's sync() did for one company."""

    adapter: str
    cui: str
    downloaded: int = 0  # network calls that succeeded
    reused: int = 0  # already in the mirror and still valid: no call made
    failed: list[str] = field(default_factory=list)  # cache keys that could not be downloaded
    skipped: str | None = None  # reason when the adapter has nothing to sync per company


class BaseAdapter:
    """Subclass, decorate with @register_adapter("<name>"), set the class attributes,
    implement READ methods on top of `fetch()` and, for per-company sources, `sync()`."""

    name: ClassVar[str] = "base"  # set by @register_adapter
    source_label: ClassVar[str] = ""  # human readable, shown in the UI ("ANAF VAT v9")
    source_type: ClassVar[SourceType] = SourceType.OFFICIAL
    rate_limit: ClassVar[RateLimit | None] = None
    rate_limit_key: ClassVar[str | None] = None  # share a limit across adapters (same host)
    mirror_max_age_s: ClassVar[int | None] = None  # None -> settings.mirror_max_age_s
    retry_statuses: ClassVar[frozenset[int]] = frozenset({429, 500, 502, 503, 504})

    def __init__(self, deps: AdapterDeps) -> None:
        self.deps = deps
        self.settings = deps.settings
        self._http = deps.http

    @property
    def network(self) -> bool:
        return self.deps.network and not self.settings.fixture_mode

    # ------------------------------------------------------------------ sync (override)
    async def sync(self, cui: str) -> SyncReport:
        """Download into the mirror everything the agents will read for `cui`.
        Default: nothing per company (bulk source, synced by an ingest job)."""
        return SyncReport(adapter=self.name, cui=cui, skipped="no per-company sync")

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
        max_age_s: int | None = None,
    ) -> FetchResult:
        """Fetch one resource. `cache_key` must uniquely identify the request
        (e.g. f"{cui}:{year}"). `fixture` is the file to serve in FIXTURE_MODE.
        `max_age_s` overrides the freshness of the mirror copy for this call."""
        if self.settings.fixture_mode:
            return await self._from_fixture(cache_key, fixture, url)

        mirrored = await self.from_mirror(cache_key)
        max_age = max_age_s if max_age_s is not None else self._max_age()
        if mirrored is not None and self._age_s(mirrored) < max_age:
            return mirrored

        if not self.network:
            if mirrored is not None:
                return self._as_stale(mirrored)
            raise SourceUnavailable(
                self.name, f"{cache_key!r} is not in the local mirror yet (run sync)"
            )

        try:
            body = await self._call_with_retry(request)
        except SourceUnavailable:
            if mirrored is not None:
                log.warning(
                    "live call failed, serving the mirror copy", extra={"adapter": self.name}
                )
                return self._as_stale(mirrored)
            raise
        return await self.store_in_mirror(cache_key, body, url)

    async def from_mirror(self, cache_key: str) -> FetchResult | None:
        """The mirror copy for `cache_key`, whatever its age, or None. Never calls the network."""
        meta_raw = await self.deps.object_store.get(self._key(cache_key))
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
            from_mirror=True,
        )

    async def store_in_mirror(self, cache_key: str, body: bytes, url: str | None) -> FetchResult:
        """Archive raw bytes (content-addressed) and point the mirror entry at them. Public so
        batch downloads (e.g. v9 with 100 CUIs per call) can store one entry per company."""
        at = self.deps.clock.now()
        raw_ref = await self.deps.object_store.put(body, prefix=f"raw/{self.name}")
        digest = content_hash(body)
        meta = json.dumps(
            {"raw_ref": raw_ref, "content_hash": digest, "retrieved_at": at.isoformat(), "url": url}
        ).encode()
        await self.deps.object_store.put_named(self._key(cache_key), meta)
        return FetchResult(body=body, source=self._source_ref(url, raw_ref, digest, at))

    # ------------------------------------------------------------------ internals
    def _max_age(self) -> int:
        return self.settings.max_age_for(self.name, self.mirror_max_age_s)

    def _age_s(self, result: FetchResult) -> float:
        return (self.deps.clock.now() - result.source.retrieved_at).total_seconds()

    @staticmethod
    def _as_stale(result: FetchResult) -> FetchResult:
        return FetchResult(body=result.body, source=result.source, from_mirror=True, stale=True)

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

    def _key(self, cache_key: str) -> str:
        digest = hashlib.sha256(cache_key.encode()).hexdigest()[:32]
        return f"mirror/{self.name}/{digest}"

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
        mirrored = await self.from_mirror(cache_key)
        if mirrored is not None:
            return mirrored
        raise SourceUnavailable(self.name, f"no fixture for {cache_key!r}")

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
