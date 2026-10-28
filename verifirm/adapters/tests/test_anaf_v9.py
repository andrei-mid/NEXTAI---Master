"""anaf_v9: fixture reads, mirror-only reads, sync, the 100-CUI batch and the 429 rule.

Every network test uses httpx.MockTransport (a fake ANAF that counts requests). Nothing here
ever reaches the real ANAF.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from verifirm.adapters.anaf_v9 import MAX_BATCH, AnafV9Adapter
from verifirm.adapters.base import AdapterDeps, SourceUnavailable
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.ports.rate_limiter import RateLimit, RateLimiter

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
NOW = datetime(2026, 10, 28, 4, 0, tzinfo=UTC)
TODAY = NOW.date()


class _CountingLimiter(RateLimiter):
    def __init__(self) -> None:
        self.acquired: list[str] = []

    async def acquire(self, key: str, limit: RateLimit) -> None:
        self.acquired.append(key)


class _Anaf:
    """Fake v9. Every CUI below 99000100 is found, others are notFound. Records requests."""

    def __init__(self, status: int = 200, body: Any = None) -> None:
        self.requests: list[list[dict[str, Any]]] = []
        self.status, self.body = status, body

    def __call__(self, request: httpx.Request) -> httpx.Response:
        sent: list[dict[str, Any]] = json.loads(request.content)
        self.requests.append(sent)
        if self.status != 200:
            return httpx.Response(self.status)
        if self.body is not None:
            return httpx.Response(200, json=self.body)
        found = [_record(item["cui"]) for item in sent if item["cui"] < 99000100]
        missing = [item["cui"] for item in sent if item["cui"] >= 99000100]
        return httpx.Response(200, json={"found": found, "notFound": missing})


def _record(cui: int, inactive: bool = False) -> dict[str, Any]:
    return {
        "date_generale": {"cui": cui, "denumire": f"FIRMA {cui} SRL"},
        "stare_inactiv": {"statusInactivi": inactive, "dataInactivare": ""},
    }


def _adapter(
    tmp_path: Path,
    *,
    fixture_mode: bool = False,
    anaf: _Anaf | None = None,
    network: bool = False,
    now: datetime = NOW,
    limiter: RateLimiter | None = None,
    retries: int = 3,
) -> AnafV9Adapter:
    return AnafV9Adapter(
        AdapterDeps(
            settings=Settings(
                fixture_mode=fixture_mode, fixtures_dir=FIXTURES, http_max_retries=retries
            ),
            cache=MemoryCache(),
            object_store=FilesystemObjectStore(tmp_path / "objects"),
            rate_limiter=limiter or _CountingLimiter(),
            clock=FixedClock(now),
            http=httpx.AsyncClient(transport=httpx.MockTransport(anaf)) if anaf else None,
            network=network,
        )
    )


# ---------------------------------------------------------------------------- fixtures
async def test_fixture_lookup(tmp_path: Path) -> None:
    result = await _adapter(tmp_path, fixture_mode=True).lookup("99000025", TODAY)
    assert result.data is not None
    assert result.data["date_generale"]["denumire"] == "ZEPHYRIA LOGISTIC NOVA SRL"
    assert result.source.raw_ref is not None and result.source.raw_ref.startswith("fixture:")
    assert result.source.name == "ANAF VAT registry v9"


async def test_fixture_missing_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailable):
        await _adapter(tmp_path, fixture_mode=True).lookup("2816464", TODAY)


async def test_fixture_batch(tmp_path: Path) -> None:
    result = await _adapter(tmp_path, fixture_mode=True).lookup_batch(
        ["99000025", "99000074", "2816464"], TODAY
    )
    assert set(result.data) == {"99000025", "99000074"}  # Dedeman: unknown, left out
    vantiro = result.data["99000074"]
    assert vantiro is not None and vantiro["stare_inactiv"]["statusInactivi"] is True


# ---------------------------------------------------------- agents: mirror only, no calls
async def test_read_path_never_calls_anaf(tmp_path: Path) -> None:
    anaf = _Anaf()
    reader = _adapter(tmp_path, anaf=anaf, network=False)
    with pytest.raises(SourceUnavailable, match="not in the local mirror"):
        await reader.lookup("99000025", TODAY)
    with pytest.raises(SourceUnavailable):
        await reader.lookup_batch(["99000025", "99000033"], TODAY)
    assert anaf.requests == []


# ------------------------------------------------------------------------------ sync
async def test_sync_once_then_reuse_then_agents_read_it(tmp_path: Path) -> None:
    anaf = _Anaf()
    syncer = _adapter(tmp_path, anaf=anaf, network=True)
    first = await syncer.sync("99000025")
    second = await syncer.sync("99000025")
    assert (first.downloaded, second.reused) == (1, 1)
    assert anaf.requests == [[{"cui": 99000025, "data": "2026-10-28"}]]

    reader = _adapter(tmp_path, network=False)  # same mirror, no network
    record = await reader.lookup("99000025", TODAY)
    assert record.data is not None and record.data["date_generale"]["cui"] == 99000025
    assert record.source.content_hash is not None


async def test_not_found_is_none_not_an_error(tmp_path: Path) -> None:
    syncer = _adapter(tmp_path, anaf=_Anaf(), network=True)
    await syncer.sync("99000555")
    result = await _adapter(tmp_path).lookup("99000555", TODAY)
    assert result.data is None


async def test_old_entry_is_served_stale(tmp_path: Path) -> None:
    await _adapter(tmp_path, anaf=_Anaf(), network=True).sync("99000025")
    later = _adapter(tmp_path, now=NOW + timedelta(days=2))
    result = await later.lookup("99000025", TODAY + timedelta(days=2))
    assert result.stale is True


# ------------------------------------------------------------------ the sweep's batch
async def test_batch_sends_at_most_100_cuis_per_request(tmp_path: Path) -> None:
    anaf = _Anaf()
    limiter = _CountingLimiter()
    sweeper = _adapter(tmp_path, anaf=anaf, network=True, limiter=limiter)
    cuis = [str(99000000 + i) for i in range(1, 251)]
    result = await sweeper.lookup_batch(cuis + cuis[:10], TODAY)  # duplicates are dropped

    assert [len(r) for r in anaf.requests] == [MAX_BATCH, MAX_BATCH, 50]
    assert limiter.acquired == ["anaf_webservicesp"] * 3  # every request waits for the limiter
    assert len(result.data) == 250
    assert result.data["99000150"] is None  # notFound

    reader = _adapter(tmp_path)  # every CUI got its own mirror entry
    one = await reader.lookup("99000042", TODAY)
    assert one.data is not None and one.data["date_generale"]["cui"] == 99000042
    assert len(anaf.requests) == 3


# -------------------------------------------------------------------- the ANAF rules
async def test_429_is_never_retried(tmp_path: Path) -> None:
    anaf = _Anaf(status=429)
    report = await _adapter(tmp_path, anaf=anaf, network=True, retries=3).sync("99000025")
    assert report.failed == ["99000025"]
    assert len(anaf.requests) == 1


async def test_corrupt_mirror_entry_is_downloaded_again(tmp_path: Path) -> None:
    await _adapter(tmp_path, anaf=_Anaf(body={"oops": True}), network=True).sync("99000025")
    healthy = _Anaf()
    report = await _adapter(tmp_path, anaf=healthy, network=True).sync("99000025")
    assert report.downloaded == 1 and len(healthy.requests) == 1
    record = await _adapter(tmp_path).lookup("99000025", TODAY)
    assert record.data is not None


async def test_server_error_is_retried_through_the_limiter(tmp_path: Path) -> None:
    anaf = _Anaf(status=503)
    limiter = _CountingLimiter()
    report = await _adapter(tmp_path, anaf=anaf, network=True, retries=2, limiter=limiter).sync(
        "99000025"
    )
    assert report.failed == ["99000025"]
    assert len(anaf.requests) == 3 and len(limiter.acquired) == 3


async def test_malformed_response_is_unavailable(tmp_path: Path) -> None:
    anaf = _Anaf(body={"cod": 200, "message": "unexpected wrapper"})
    report = await _adapter(tmp_path, anaf=anaf, network=True).sync("99000025")
    assert report.failed == ["99000025"]
    with pytest.raises(SourceUnavailable):
        await _adapter(tmp_path).lookup("99000025", TODAY)


def test_request_body_shape() -> None:
    from verifirm.adapters.anaf_v9 import _body

    assert _body(["99000025"], date(2026, 10, 28)) == [{"cui": 99000025, "data": "2026-10-28"}]
