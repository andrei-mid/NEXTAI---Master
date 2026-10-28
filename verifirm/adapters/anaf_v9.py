"""Owner: @role-3-official-agents. ANAF VAT registry web service, version 9 (OFFICIAL, free).

Facts:
- POST https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva
- Body: [{"cui": 123, "data": "YYYY-MM-DD"}, ...]. The CUI is an int, `data` is the date the
  answer is for, so ONE request can ask the same CUI for several dates.
- Max 100 ENTRIES per request (an entry = one cui+date). Max 1 request/second (declared below,
  enforced globally). ANAF: "any attempt to overload the server is punished". Not negotiable.
- Response: {"found": [...], "notFound": [cui, ...]}. Each found item has `date_generale`
  (cui, data = the date asked, denumire, adresa, nrRegCom, cod_CAEN, forma_juridica,
  stare_inregistrare, statusRO_e_Factura, ...), `inregistrare_scop_Tva` (scpTVA + perioade_TVA),
  `inregistrare_RTVAI`, `stare_inactiv`, `inregistrare_SplitTVA`, `adresa_sediu_social`,
  `adresa_domiciliu_fiscal`. `notFound` lists CUIs only (no date).
- ANAF's doc shows a cod/message wrapper. Live answers come without it. Both are accepted.
- Fixture: fixtures/companies/<cui>_<slug>/anaf_v9.json, the exact response shape (today only).

Used by: identity sheet (official), identity agent (inactive/reactivated), tax agent
(VAT cancelled), anaf_efactura_registry, and the background sweep (change detection).

Local-first (docs/LOCAL_DATA.md). Mirror entries, each shaped like a v9 response for one CUI
({"found": [record]} or {"notFound": [cui]}):
- `CUI`        the latest record. Freshness mirror_max_age_s (24h), older -> stale=True.
               (Not keyed by date only: a run before the daily sweep would find nothing.)
- `CUI:date`   a dated snapshot: what ANAF answered for that date. A past date never changes,
               so it is downloaded ONCE, ever (like a filed balance sheet).
- `sync(cui)`: ONE request with today + the last day of each of the previous
  `history_quarters` quarters, only the entries not in the mirror yet. First sync of a company:
  5 entries. Later: at most today's entry (plus a new quarter-end once a quarter).
- `lookup_batch(cuis)` with network (sweep job): ONE request for at most 100 CUIs, stores the
  latest record and today's snapshot per CUI. History builds up on its own.
- READ methods (`lookup`, `history`, `lookup_batch` without network) never call ANAF.

SAFETY (ANAF: max 100 CUIs per request, max 1 request/second, overloading is punished):
- ONE CALL = AT MOST ONE REQUEST. No method sends requests in a loop: no chunking, no retries.
  More than MAX_BATCH entries is refused BEFORE anything is sent (ValueError). A caller that
  needs more (the sweep job) makes separate, scheduled calls.
- MAX_BATCH counts ENTRIES (cui+date), so both readings of "100 de CUI-uri" hold.
- Every request first waits for the global RateLimiter (`anaf_webservicesp`, shared with /bilant).
- No retry of any kind (429, 5xx, timeout): the failure is reported, the old mirror copy is
  served stale, and the next scheduled sync tries again.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

import httpx

from verifirm.adapters.base import (
    BaseAdapter,
    FetchResult,
    RequestFn,
    Sourced,
    SourceUnavailable,
    SyncReport,
)
from verifirm.core.ports.rate_limiter import RateLimit
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType

URL = "https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva"
MAX_BATCH = 100  # entries (cui+date) per request, ANAF's limit

Entry = tuple[str, date]


def _body(entries: list[Entry]) -> list[dict[str, Any]]:
    return [{"cui": int(cui), "data": day.isoformat()} for cui, day in entries]


def _cui_of(record: dict[str, Any]) -> str:
    return str((record.get("date_generale") or {}).get("cui", "")).strip()


def _date_of(record: dict[str, Any]) -> str:
    return str((record.get("date_generale") or {}).get("data", "")).strip()[:10]


def _check_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or not ("found" in payload or "notFound" in payload):
        raise ValueError("not a v9 {found, notFound} response")
    if not isinstance(payload.get("found", []), list):
        raise ValueError("v9 `found` is not a list")
    return payload


def _not_found(payload: dict[str, Any]) -> set[str]:
    return {
        str(c.get("cui") if isinstance(c, dict) else c).strip()
        for c in payload.get("notFound") or []
    }


def split_response(payload: dict[str, Any], cuis: list[str]) -> dict[str, dict[str, Any] | None]:
    """{cui: found record, or None if ANAF lists it in notFound}. A CUI ANAF says nothing about
    is left out: the caller treats it as unavailable, never as 'not inactive'.
    Raises ValueError if the payload is not a v9 response at all."""
    payload = _check_payload(payload)
    found = {_cui_of(r): r for r in payload.get("found") or [] if isinstance(r, dict)}
    not_found = _not_found(payload)
    out: dict[str, dict[str, Any] | None] = {}
    for cui in cuis:
        if cui in found:
            out[cui] = found[cui]
        elif cui in not_found:
            out[cui] = None
    return out


def split_entries(
    payload: dict[str, Any], entries: list[Entry]
) -> dict[Entry, dict[str, Any] | None]:
    """{(cui, date): record, or None if ANAF lists the CUI in notFound}. Records are matched on
    date_generale.cui AND date_generale.data, so several dates of one CUI never overwrite each
    other. If a record has no date and its CUI was asked for one date only, it is that date.
    An entry ANAF says nothing about is left out (unknown, never clean)."""
    payload = _check_payload(payload)
    records = [r for r in payload.get("found") or [] if isinstance(r, dict)]
    by_entry = {(_cui_of(r), _date_of(r)): r for r in records}
    undated = {_cui_of(r): r for r in records if not _date_of(r)}
    asked: dict[str, int] = {}
    for cui, _ in entries:
        asked[cui] = asked.get(cui, 0) + 1
    not_found = _not_found(payload)
    out: dict[Entry, dict[str, Any] | None] = {}
    for cui, day in entries:
        record = by_entry.get((cui, day.isoformat()))
        if record is None and asked[cui] == 1:
            record = undated.get(cui)
        if record is not None:
            out[(cui, day)] = record
        elif cui in not_found:
            out[(cui, day)] = None
    return out


def history_dates(today: date, quarters: int) -> list[date]:
    """The last day of each of the `quarters` quarters before today's quarter, newest first.
    2026-10-28 -> 2026-09-30, 2026-06-30, 2026-03-31, 2025-12-31."""
    first_month = (today.month - 1) // 3 * 3 + 1
    out, day = [], today.replace(month=first_month, day=1) - timedelta(days=1)
    for _ in range(quarters):
        out.append(day)
        day = day.replace(month=day.month - 2, day=1) - timedelta(days=1)
    return out


def _single_body(cui: str, record: dict[str, Any] | None) -> bytes:
    payload = (
        {"found": [record], "notFound": []}
        if record is not None
        else {"found": [], "notFound": [int(cui)]}
    )
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _record_of(result: FetchResult, cui: str) -> tuple[bool, dict[str, Any] | None]:
    """(usable, record). usable=False when the body isn't valid v9 or doesn't mention `cui`."""
    try:
        records = split_response(result.json(), [cui])
    except (ValueError, AttributeError):
        return False, None
    return (cui in records), records.get(cui)


def _dated(cui: str, day: date) -> str:
    return f"{cui}:{day.isoformat()}"


@register_adapter("anaf_v9")
class AnafV9Adapter(BaseAdapter):
    source_label = "ANAF VAT registry v9"
    source_type = SourceType.OFFICIAL
    rate_limit = RateLimit.per_second(1)
    rate_limit_key = "anaf_webservicesp"  # same host as /bilant, so they share one limit
    mirror_max_age_s = 86_400  # inactive / VAT status can change any day
    retry_statuses = frozenset[int]()  # never retry anything (see SAFETY)
    history_quarters = 4  # quarter-end snapshots kept per company (5 entries with today)

    # ------------------------------------------------------------------ sync (network)
    async def sync(self, cui: str) -> SyncReport:
        """ONE request for what's missing for one company: today's record if the latest entry is
        not fresh, plus the quarter-end snapshots not in the mirror yet (newest first). Capped at
        MAX_BATCH entries; anything beyond waits for the next sync, never a second request."""
        report = SyncReport(adapter=self.name, cui=cui)
        wanted = await self.missing(cui)
        report.reused = 1 + self.history_quarters - len(wanted)
        wanted = wanted[:MAX_BATCH]  # the rest goes in the next sync's single request
        if not wanted:
            return report
        try:
            records = await self.download([(cui, day) for day in wanted])
        except SourceUnavailable:
            report.failed.append(cui)
            return report
        report.downloaded = 1
        report.failed = [_dated(cui, day) for day in wanted if (cui, day) not in records]
        return report

    async def missing(self, cui: str) -> list[date]:
        """Dates `sync` would ask for (newest first): today if the latest entry is missing, stale
        or corrupt, plus the quarter-ends without a usable snapshot. Mirror only, no network."""
        today = self.deps.clock.today()
        latest = await self.from_mirror(cui)
        fresh = latest is not None and _record_of(latest, cui)[0] and self._fresh(latest)
        wanted = [] if fresh else [today]
        for day in history_dates(today, self.history_quarters):
            snapshot = await self.from_mirror(_dated(cui, day))
            if snapshot is None or not _record_of(snapshot, cui)[0]:
                wanted.append(day)
        return wanted

    async def download(self, entries: list[Entry]) -> dict[Entry, dict[str, Any] | None]:
        """EXACTLY ONE request for these entries (max MAX_BATCH, else ValueError before sending).
        For sync code and the fetch tool only: agents never get a network adapter."""
        if not self.network:
            raise SourceUnavailable(self.name, "this adapter has no network (agents never call)")
        return await self._download(entries)

    # ------------------------------------------------------------------ READ (mirror only)
    async def lookup(self, cui: str, on_date: date) -> Sourced[dict[str, Any] | None]:
        """One company: its latest v9 record, or None if ANAF lists it in `notFound`.
        Agents: mirror (or fixture) only. Never "not inactive" by default: an unreadable
        entry raises SourceUnavailable."""
        result = await self._load(cui, on_date)
        usable, record = _record_of(result, cui)
        if not usable:
            raise SourceUnavailable(self.name, f"no usable v9 data about {cui}")
        return Sourced(data=record, source=result.source, stale=result.stale)

    async def history(
        self, cui: str, dates: list[date] | None = None
    ) -> Sourced[dict[str, dict[str, Any] | None]]:
        """{ISO date: record or None} for the snapshots in the mirror. Default dates: today plus
        the quarter-ends `sync` keeps. Dates without a snapshot are left out (unknown). Fixture
        mode has today's fixture only. Never calls the network."""
        today = self.deps.clock.today()
        days = dates or [today, *history_dates(today, self.history_quarters)]
        out: dict[str, dict[str, Any] | None] = {}
        source = None
        for day in days:
            if self.settings.fixture_mode:
                if day != today:
                    continue
                result: FetchResult | None = await self._load(cui, day)
            else:
                result = await self.from_mirror(_dated(cui, day))
            if result is None:
                continue
            usable, record = _record_of(result, cui)
            if usable:
                out[day.isoformat()] = record
                source = source or result.source
        if source is None:
            raise SourceUnavailable(self.name, f"no v9 snapshot of {cui} in the local mirror")
        return Sourced(data=out, source=source)

    async def lookup_batch(
        self, cuis: list[str], on_date: date
    ) -> Sourced[dict[str, dict[str, Any] | None]]:
        """{cui: record or None}. CUIs that can't be read are left out (unknown, never clean).

        - Network adapter (sweep job): ONE request for at most MAX_BATCH CUIs (more raises
          ValueError before anything is sent), then the latest entry and the dated snapshot per
          CUI. The caller schedules the next batch; this method never loops over requests.
        - Otherwise (agents, fixture mode): one mirror / fixture read per CUI, no network.
        """
        unique = list(dict.fromkeys(str(c) for c in cuis))
        if not self.network:
            out: dict[str, dict[str, Any] | None] = {}
            source = None
            for cui in unique:
                try:
                    one = await self.lookup(cui, on_date)
                except SourceUnavailable:
                    continue
                out[cui], source = one.data, source or one.source
            if source is None:
                raise SourceUnavailable(self.name, "none of the CUIs is in the local mirror")
            return Sourced(data=out, source=source)

        records = await self._download([(cui, on_date) for cui in unique])
        if not records:
            raise SourceUnavailable(self.name, "ANAF returned none of the requested CUIs")
        stored = await self.from_mirror(_dated(next(iter(records))[0], on_date))
        assert stored is not None
        return Sourced(data={cui: rec for (cui, _), rec in records.items()}, source=stored.source)

    # ------------------------------------------------------------------ internals
    def _fresh(self, result: FetchResult) -> bool:
        return self._age_s(result) < self._max_age()

    @staticmethod
    def _request(entries: list[Entry]) -> RequestFn:
        body = _body(entries)

        async def request(client: httpx.AsyncClient) -> httpx.Response:
            return await client.post(URL, json=body)

        return request

    async def _download(self, entries: list[Entry]) -> dict[Entry, dict[str, Any] | None]:
        """EXACTLY ONE rate-limited POST for at most MAX_BATCH entries (more: ValueError, nothing
        sent). Stores each answer as a dated snapshot, and as the latest record when the date is
        today. Answers ANAF didn't give are left out (unknown, never clean)."""
        unique = list(dict.fromkeys(entries))
        if len(unique) > MAX_BATCH:
            raise ValueError(
                f"{len(unique)} entries: ANAF allows {MAX_BATCH} per request. Split them and "
                "schedule the requests (never in a loop here)."
            )
        today = self.deps.clock.today()
        raw = await self._call_with_retry(self._request(unique))  # single attempt, 1 req/s
        try:
            answers = split_entries(json.loads(raw), unique)
        except ValueError as exc:
            raise SourceUnavailable(self.name, f"invalid v9 response: {exc}") from exc
        for (cui, day), record in answers.items():
            body = _single_body(cui, record)
            await self.store_in_mirror(_dated(cui, day), body, URL)
            if day == today:
                await self.store_in_mirror(cui, body, URL)
        return answers

    async def _call_with_retry(self, request: RequestFn) -> bytes:
        """ANAF override of BaseAdapter's retry loop: ONE attempt, after the global rate limiter.
        Any failure (HTTP error, 429, 5xx, timeout) is reported, never retried."""
        if self.rate_limit is not None:
            await self.deps.rate_limiter.acquire(self.rate_limit_key or self.name, self.rate_limit)
        try:
            response = await request(await self._client())
        except httpx.TransportError as exc:
            raise SourceUnavailable(self.name, f"{type(exc).__name__}: {exc}") from exc
        if response.status_code >= 400:
            raise SourceUnavailable(self.name, f"HTTP {response.status_code} (not retried)")
        return response.content

    async def _load(self, cui: str, on_date: date) -> FetchResult:
        """The latest entry (fixture in FIXTURE_MODE). Without network: mirror only (fresh, or
        stale=True). A network adapter downloads a missing, stale or corrupt entry through
        `_download` ONLY (never also through fetch(): that would be a second request)."""
        if not self.network:  # agents, and always in FIXTURE_MODE
            fixture = self.company_fixture(cui, "anaf_v9.json")
            request = self._request([(cui, on_date)])  # unused: fetch() can't call without network
            return await self.fetch(cache_key=cui, request=request, url=URL, fixture=fixture)
        key = cui if on_date == self.deps.clock.today() else _dated(cui, on_date)
        stored = await self.from_mirror(key)
        if stored is not None and _record_of(stored, cui)[0]:
            if key != cui or self._fresh(stored):
                return stored  # fresh latest, or a past snapshot (never changes)
        try:
            await self._download([(cui, on_date)])
        except SourceUnavailable:
            if stored is not None:
                return self._as_stale(stored)  # live call failed: serve the old copy
            raise
        fresh = await self.from_mirror(key)
        if fresh is None or not _record_of(fresh, cui)[0]:
            raise SourceUnavailable(self.name, f"ANAF returned nothing about {cui}")
        return fresh
