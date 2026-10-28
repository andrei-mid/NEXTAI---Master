"""anaf_v9: fixture reads, mirror-only reads, dated snapshots, sync, the 100-entry batch and
the 429 rule.

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

from verifirm.adapters.anaf_v9 import (
    MAX_BATCH,
    AnafV9Adapter,
    _body,
    history_dates,
    split_entries,
    split_response,
)
from verifirm.adapters.base import AdapterDeps, SourceUnavailable
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.ports.rate_limiter import RateLimit, RateLimiter

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
NOW = datetime(2026, 10, 28, 4, 0, tzinfo=UTC)
TODAY = NOW.date()
HISTORY = 4  # quarter-ends


class _CountingLimiter(RateLimiter):
    def __init__(self) -> None:
        self.acquired: list[str] = []

    async def acquire(self, key: str, limit: RateLimit) -> None:
        self.acquired.append(key)


def _record(cui: int, day: str | None = None, inactive: bool = False) -> dict[str, Any]:
    general: dict[str, Any] = {
        "cui": cui,
        "denumire": f"FIRMA {cui} SRL",
        "adresa": f"Str. Data nr. {day or 'x'}",  # a different address for every date
    }
    if day is not None:
        general["data"] = day
    return {"date_generale": general, "stare_inactiv": {"statusInactivi": inactive}}


class _Anaf:
    """Fake v9. CUIs below 99000100 are found (answered per entry, with that entry's date),
    others are notFound. Records every request body."""

    def __init__(self, status: int = 200, body: Any = None, wrap: bool = False) -> None:
        self.requests: list[list[dict[str, Any]]] = []
        self.status, self.body, self.wrap = status, body, wrap

    def __call__(self, request: httpx.Request) -> httpx.Response:
        sent: list[dict[str, Any]] = json.loads(request.content)
        self.requests.append(sent)
        if self.status != 200:
            return httpx.Response(self.status)
        if self.body is not None:
            return httpx.Response(200, json=self.body)
        found = [_record(e["cui"], e["data"]) for e in sent if e["cui"] < 99000100]
        missing = sorted({e["cui"] for e in sent if e["cui"] >= 99000100})
        payload: dict[str, Any] = {"found": found, "notFound": missing}
        if self.wrap:  # the shape ANAF's documentation shows
            payload = {"cod": 200, "message": "SUCCESS", **payload}
        return httpx.Response(200, json=payload)


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


# ----------------------------------------------------------------------- pure helpers
def test_request_body_shape() -> None:
    entries = [("99000025", date(2026, 10, 28)), ("99000025", date(2025, 10, 31))]
    assert _body(entries) == [
        {"cui": 99000025, "data": "2026-10-28"},
        {"cui": 99000025, "data": "2025-10-31"},
    ]


def test_history_dates_are_quarter_ends() -> None:
    assert history_dates(date(2026, 10, 28), 4) == [
        date(2026, 9, 30),
        date(2026, 6, 30),
        date(2026, 3, 31),
        date(2025, 12, 31),
    ]
    assert history_dates(date(2026, 1, 1), 1) == [date(2025, 12, 31)]  # first day of a quarter
    assert history_dates(date(2024, 4, 5), 1) == [date(2024, 3, 31)]
    assert history_dates(date(2026, 12, 31), 2) == [date(2026, 9, 30), date(2026, 6, 30)]


def test_split_response_never_invents_a_clean_answer() -> None:
    payload = {"found": [{"date_generale": {"cui": 2816464}}], "notFound": [123]}
    out = split_response(payload, ["2816464", "123", "999"])
    assert out["2816464"] is not None and out["123"] is None and "999" not in out


def test_split_entries_keeps_dates_apart() -> None:
    a, b = date(2026, 10, 28), date(2025, 10, 31)
    payload = {
        "found": [_record(99000025, "2026-10-28"), _record(99000025, "2025-10-31")],
        "notFound": [99000555],
    }
    out = split_entries(payload, [("99000025", a), ("99000025", b), ("99000555", a)])
    first, second = out[("99000025", a)], out[("99000025", b)]
    assert first is not None and second is not None
    assert first["date_generale"]["adresa"] != second["date_generale"]["adresa"]
    assert out[("99000555", a)] is None


def test_split_entries_undated_record() -> None:
    a, b = date(2026, 10, 28), date(2025, 10, 31)
    payload = {"found": [_record(99000025)], "notFound": []}
    assert ("99000025", a) in split_entries(payload, [("99000025", a)])  # asked once: unique
    assert split_entries(payload, [("99000025", a), ("99000025", b)]) == {}  # ambiguous: unknown


@pytest.mark.parametrize("payload", [{"cod": 200, "message": "no data"}, [1, 2], {"found": "x"}])
def test_not_a_v9_response(payload: Any) -> None:
    with pytest.raises(ValueError):
        split_entries(payload, [("1", TODAY)])


# ---------------------------------------------------------------------------- fixtures
async def test_fixture_lookup(tmp_path: Path) -> None:
    result = await _adapter(tmp_path, fixture_mode=True).lookup("99000025", TODAY)
    assert result.data is not None
    assert result.data["date_generale"]["denumire"] == "ZEPHYRIA LOGISTIC NOVA SRL"
    assert result.source.raw_ref is not None and result.source.raw_ref.startswith("fixture:")


async def test_fixture_history_has_today_only(tmp_path: Path) -> None:
    result = await _adapter(tmp_path, fixture_mode=True).history("99000025")
    assert list(result.data) == [TODAY.isoformat()]


async def test_fixture_missing_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailable):
        await _adapter(tmp_path, fixture_mode=True).lookup("2816464", TODAY)


async def test_fixture_batch(tmp_path: Path) -> None:
    result = await _adapter(tmp_path, fixture_mode=True).lookup_batch(
        ["99000025", "99000074", "2816464"], TODAY
    )
    assert set(result.data) == {"99000025", "99000074"}  # Dedeman: unknown, left out


# ---------------------------------------------------------- agents: mirror only, no calls
async def test_read_path_never_calls_anaf(tmp_path: Path) -> None:
    anaf = _Anaf()
    reader = _adapter(tmp_path, anaf=anaf, network=False)
    with pytest.raises(SourceUnavailable, match="not in the local mirror"):
        await reader.lookup("99000025", TODAY)
    with pytest.raises(SourceUnavailable):
        await reader.history("99000025")
    with pytest.raises(SourceUnavailable):
        await reader.lookup_batch(["99000025", "99000033"], TODAY)
    assert anaf.requests == []


# --------------------------------------------------- sync: multiple dated entries per firm
async def test_first_sync_is_one_request_with_today_and_4_quarter_ends(tmp_path: Path) -> None:
    anaf = _Anaf()
    report = await _adapter(tmp_path, anaf=anaf, network=True).sync("99000025")

    assert len(anaf.requests) == 1
    sent = anaf.requests[0]
    assert [e["data"] for e in sent] == [
        TODAY.isoformat(),
        *(d.isoformat() for d in history_dates(TODAY, HISTORY)),
    ]
    assert {e["cui"] for e in sent} == {99000025}
    assert (report.downloaded, report.reused, report.failed) == (1, 0, [])


async def test_every_date_is_stored_separately(tmp_path: Path) -> None:
    await _adapter(tmp_path, anaf=_Anaf(), network=True).sync("99000025")
    snapshots = (await _adapter(tmp_path).history("99000025")).data

    assert len(snapshots) == 1 + HISTORY
    addresses = {
        day: rec["date_generale"]["adresa"] for day, rec in snapshots.items() if rec is not None
    }
    assert addresses["2025-12-31"] == "Str. Data nr. 2025-12-31"
    assert addresses[TODAY.isoformat()] == f"Str. Data nr. {TODAY.isoformat()}"
    assert len(set(addresses.values())) == 1 + HISTORY  # nothing overwrote anything

    latest = await _adapter(tmp_path).lookup("99000025", TODAY)
    assert latest.data is not None
    assert latest.data["date_generale"]["data"] == TODAY.isoformat()


async def test_second_sync_same_day_makes_no_request(tmp_path: Path) -> None:
    anaf = _Anaf()
    await _adapter(tmp_path, anaf=anaf, network=True).sync("99000025")
    again = await _adapter(tmp_path, anaf=anaf, network=True).sync("99000025")
    assert len(anaf.requests) == 1
    assert (again.downloaded, again.reused) == (0, 1 + HISTORY)


async def test_next_day_only_today_is_asked_again(tmp_path: Path) -> None:
    anaf = _Anaf()
    await _adapter(tmp_path, anaf=anaf, network=True).sync("99000025")
    tomorrow = NOW + timedelta(days=1)
    await _adapter(tmp_path, anaf=anaf, network=True, now=tomorrow).sync("99000025")
    assert anaf.requests[1] == [{"cui": 99000025, "data": "2026-10-29"}]  # past never again


async def test_new_quarter_adds_one_quarter_end(tmp_path: Path) -> None:
    anaf = _Anaf()
    await _adapter(tmp_path, anaf=anaf, network=True).sync("99000025")
    january = datetime(2027, 1, 3, 4, 0, tzinfo=UTC)
    await _adapter(tmp_path, anaf=anaf, network=True, now=january).sync("99000025")
    assert [e["data"] for e in anaf.requests[1]] == ["2027-01-03", "2026-12-31"]


async def test_more_than_100_missing_entries_wait_for_the_next_sync(tmp_path: Path) -> None:
    anaf = _Anaf()
    syncer = _adapter(tmp_path, anaf=anaf, network=True)
    syncer.history_quarters = 150  # 151 entries wanted
    first = await syncer.sync("99000025")
    assert [len(r) for r in anaf.requests] == [MAX_BATCH]  # ONE request, never a second one
    assert first.downloaded == 1
    await syncer.sync("99000025")  # the next (scheduled) sync takes the rest
    assert [len(r) for r in anaf.requests] == [MAX_BATCH, 51]


async def test_not_found_is_none_for_every_date(tmp_path: Path) -> None:
    await _adapter(tmp_path, anaf=_Anaf(), network=True).sync("99000555")
    assert (await _adapter(tmp_path).lookup("99000555", TODAY)).data is None
    snapshots = (await _adapter(tmp_path).history("99000555")).data
    assert len(snapshots) == 1 + HISTORY and set(snapshots.values()) == {None}


async def test_old_latest_entry_is_served_stale(tmp_path: Path) -> None:
    await _adapter(tmp_path, anaf=_Anaf(), network=True).sync("99000025")
    later = _adapter(tmp_path, now=NOW + timedelta(days=2))
    result = await later.lookup("99000025", TODAY + timedelta(days=2))
    assert result.stale is True


async def test_network_lookup_makes_exactly_one_request(tmp_path: Path) -> None:
    anaf = _Anaf()
    result = await _adapter(tmp_path, anaf=anaf, network=True).lookup("99000025", TODAY)
    assert result.data is not None
    assert len(anaf.requests) == 1  # never once through fetch() and again through _download


# ------------------------------------------------------------------ the sweep's batch
async def test_batch_is_one_request_for_at_most_100_cuis(tmp_path: Path) -> None:
    anaf = _Anaf()
    limiter = _CountingLimiter()
    sweeper = _adapter(tmp_path, anaf=anaf, network=True, limiter=limiter)
    cuis = [str(99000050 + i) for i in range(100)]
    result = await sweeper.lookup_batch(cuis + cuis[:10], TODAY)  # duplicates are dropped

    assert [len(r) for r in anaf.requests] == [MAX_BATCH]
    assert limiter.acquired == ["anaf_webservicesp"]  # the request waited for the limiter
    assert len(result.data) == 100
    assert result.data["99000149"] is None  # notFound

    reader = _adapter(tmp_path)  # latest entry and today's snapshot, per CUI
    assert (await reader.lookup("99000060", TODAY)).data is not None
    assert TODAY.isoformat() in (await reader.history("99000060", [TODAY])).data
    assert len(anaf.requests) == 1


async def test_more_than_100_cuis_is_refused_before_sending(tmp_path: Path) -> None:
    anaf = _Anaf()
    sweeper = _adapter(tmp_path, anaf=anaf, network=True)
    cuis = [str(99000000 + i) for i in range(1, 102)]
    with pytest.raises(ValueError, match="100 per request"):
        await sweeper.lookup_batch(cuis, TODAY)
    assert anaf.requests == []


# -------------------------------------------------------------------- the ANAF rules
async def test_429_is_never_retried_with_retries_configured(tmp_path: Path) -> None:
    anaf = _Anaf(status=429)
    report = await _adapter(tmp_path, anaf=anaf, network=True, retries=3).sync("99000025")
    assert report.failed == ["99000025"]
    assert len(anaf.requests) == 1


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
async def test_no_error_is_ever_retried(tmp_path: Path, status: int) -> None:
    anaf = _Anaf(status=status)
    limiter = _CountingLimiter()
    report = await _adapter(tmp_path, anaf=anaf, network=True, retries=3, limiter=limiter).sync(
        "99000025"
    )
    assert report.failed == ["99000025"]
    assert len(anaf.requests) == 1 and len(limiter.acquired) == 1


async def test_timeout_is_not_retried(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []

    def timeout(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ReadTimeout("slow", request=request)

    deps = _adapter(tmp_path, network=True).deps
    deps.http = httpx.AsyncClient(transport=httpx.MockTransport(timeout))
    report = await AnafV9Adapter(deps).sync("99000025")
    assert report.failed == ["99000025"]
    assert len(calls) == 1


async def test_a_failed_live_call_serves_the_old_copy(tmp_path: Path) -> None:
    await _adapter(tmp_path, anaf=_Anaf(), network=True).sync("99000025")
    down = _Anaf(status=503)
    later = _adapter(tmp_path, anaf=down, network=True, now=NOW + timedelta(days=2))
    result = await later.lookup("99000025", TODAY + timedelta(days=2))
    assert result.stale is True and result.data is not None
    assert len(down.requests) == 1


async def test_every_network_method_makes_at_most_one_request(tmp_path: Path) -> None:
    """The rule in one place: ONE CALL = AT MOST ONE REQUEST to ANAF."""
    for call in (
        lambda a: a.sync("99000025"),
        lambda a: a.lookup("99000033", TODAY),
        lambda a: a.lookup_batch([str(99000000 + i) for i in range(1, 101)], TODAY),
    ):
        anaf = _Anaf()
        await call(_adapter(tmp_path / str(id(call)), anaf=anaf, network=True))
        assert len(anaf.requests) == 1


async def test_malformed_response_stores_nothing(tmp_path: Path) -> None:
    anaf = _Anaf(body={"cod": 200, "message": "unexpected"})
    report = await _adapter(tmp_path, anaf=anaf, network=True).sync("99000025")
    assert report.failed == ["99000025"]
    with pytest.raises(SourceUnavailable):
        await _adapter(tmp_path).lookup("99000025", TODAY)


async def test_corrupt_entries_are_downloaded_again(tmp_path: Path) -> None:
    syncer = _adapter(tmp_path, anaf=_Anaf(), network=True)
    await syncer.sync("99000025")
    await syncer.store_in_mirror("99000025:2026-06-30", b"not json", None)  # corrupt one date
    healthy = _Anaf()
    report = await _adapter(tmp_path, anaf=healthy, network=True).sync("99000025")
    assert healthy.requests == [[{"cui": 99000025, "data": "2026-06-30"}]]
    assert report.downloaded == 1


async def test_documented_cod_message_wrapper_is_accepted(tmp_path: Path) -> None:
    report = await _adapter(tmp_path, anaf=_Anaf(wrap=True), network=True).sync("99000025")
    assert report.failed == []
    assert (await _adapter(tmp_path).lookup("99000025", TODAY)).data is not None
