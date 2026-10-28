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
- `sync(cui)`: today + the last day of each of the previous `history_months` months, only
  the entries not in the mirror yet, in as few requests as possible (100 entries each).
  First sync of a company: 1 request with 13 entries. Later: at most today's entry.
- `lookup_batch(cuis)` with network (sweep job): 100 entries per request, stores the latest
  record and today's snapshot per CUI. History builds up daily on its own.
- READ methods (`lookup`, `history`, `lookup_batch` without network) never call ANAF.
- No retry on HTTP 429: ANAF asking us to slow down is never answered with more requests.
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


def history_dates(today: date, months: int) -> list[date]:
    """The last day of each of the `months` months before today's month, newest first."""
    out, day = [], today.replace(day=1) - timedelta(days=1)
    for _ in range(months):
        out.append(day)
        day = day.replace(day=1) - timedelta(days=1)
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
    retry_statuses = frozenset({500, 502, 503, 504})  # never retry a 429 (see docstring)
    history_months = 12  # month-end snapshots kept per company (13 entries with today)

    # ------------------------------------------------------------------ sync (network)
    async def sync(self, cui: str) -> SyncReport:
        """Download what's missing for one company: today's record if the latest entry is not
        fresh, plus every month-end snapshot not in the mirror yet. As few requests as possible."""
        report = SyncReport(adapter=self.name, cui=cui)
        today = self.deps.clock.today()
        latest = await self.from_mirror(cui)
        latest_ok = latest is not None and _record_of(latest, cui)[0]
        need_today = not (latest_ok and latest is not None and self._fresh(latest))
        wanted = [today] if need_today else []
        for day in history_dates(today, self.history_months):
            snapshot = await self.from_mirror(_dated(cui, day))
            if snapshot is None or not _record_of(snapshot, cui)[0]:
                wanted.append(day)
        report.reused = 1 + self.history_months - len(wanted)
        if not wanted:
            return report
        try:
            records, calls = await self._download([(cui, day) for day in wanted])
        except SourceUnavailable:
            report.failed.append(cui)
            return report
        report.downloaded = calls
        report.failed = [_dated(cui, day) for day in wanted if (cui, day) not in records]
        return report

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
        the month-ends `sync` keeps. Dates without a snapshot are left out (unknown). Fixture
        mode has today's fixture only. Never calls the network."""
        today = self.deps.clock.today()
        days = dates or [today, *history_dates(today, self.history_months)]
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

        - Network adapter (sweep job): 100 entries per request, one request at a time,
          then the latest entry and the dated snapshot per CUI.
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

        records, _ = await self._download([(cui, on_date) for cui in unique])
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

    async def _download(
        self, entries: list[Entry]
    ) -> tuple[dict[Entry, dict[str, Any] | None], int]:
        """POST `entries` in chunks of MAX_BATCH, ONE rate-limited request at a time. Stores each
        answer as a dated snapshot, and as the latest record when the date is today.
        Returns (answers, number of requests made)."""
        today = self.deps.clock.today()
        answers: dict[Entry, dict[str, Any] | None] = {}
        calls = 0
        unique = list(dict.fromkeys(entries))
        for start in range(0, len(unique), MAX_BATCH):
            chunk = unique[start : start + MAX_BATCH]
            raw = await self._call_with_retry(self._request(chunk))  # 1 req/s globally
            calls += 1
            try:
                got = split_entries(json.loads(raw), chunk)
            except ValueError as exc:
                raise SourceUnavailable(self.name, f"invalid v9 response: {exc}") from exc
            for (cui, day), record in got.items():
                body = _single_body(cui, record)
                await self.store_in_mirror(_dated(cui, day), body, URL)
                if day == today:
                    await self.store_in_mirror(cui, body, URL)
            answers.update(got)
        return answers, calls

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
