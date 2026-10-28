"""Owner: @role-3-official-agents. ANAF VAT registry web service, version 9 (OFFICIAL, free).

Facts:
- POST https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva
- Body: [{"cui": 123, "data": "YYYY-MM-DD"}, ...]. The CUI is an int, the date is the reference date.
- Max 100 CUIs per request. Max 1 request/second (declared below, enforced globally).
  ANAF: "any attempt to overload the server is punished". These limits are not negotiable.
- Response: {"found": [...], "notFound": [...]}. Each found item has `date_generale`
  (denumire, adresa, nrRegCom, cod_CAEN, forma_juridica, stare_inregistrare,
  statusRO_e_Factura, ...), `inregistrare_scop_Tva` (scpTVA + perioade_TVA history),
  `stare_inactiv` (statusInactivi, dataInactivare, dataReactivare, dataRadiere),
  `inregistrare_RTVAI`, `adresa_sediu_social`, `adresa_domiciliu_fiscal`.
- There is NO cod/message wrapper on live 200 responses. A wrapper is tolerated anyway.
- Fixture: fixtures/companies/<cui>_<slug>/anaf_v9.json, the exact response shape.

Used by: identity sheet (official), identity agent (inactive/reactivated), tax agent
(VAT cancelled), anaf_efactura_registry, and the background sweep (change detection).

Local-first (docs/LOCAL_DATA.md): the mirror holds ONE entry per company (cache_key = the CUI),
always shaped like a v9 response for that single CUI: {"found": [record]} or {"notFound": [cui]}.
Freshness is mirror_max_age_s (24h): an older entry is served stale=True, never dropped. (Not
keyed by date: a run before the daily sweep would otherwise find nothing for "today".)
- `sync(cui)`: one POST for that company (applications, rechecks, sync_portfolio). A fresh
  entry is reused (no call). A corrupt entry is downloaded again, never "reused" until it expires.
- `lookup_batch(cuis)` with network (sweep job): 100 CUIs per POST, one mirror entry per CUI.
- `lookup(cui)`: what agents call. Mirror only (no network), so it never calls ANAF.
- No retry on HTTP 429: ANAF asking us to slow down is never answered with more requests.
"""

from __future__ import annotations

import json
from datetime import date
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
MAX_BATCH = 100


def _body(cuis: list[str], on_date: date) -> list[dict[str, Any]]:
    return [{"cui": int(c), "data": on_date.isoformat()} for c in cuis]


def _cui_of(record: dict[str, Any]) -> str:
    return str((record.get("date_generale") or {}).get("cui", "")).strip()


def split_response(payload: dict[str, Any], cuis: list[str]) -> dict[str, dict[str, Any] | None]:
    """{cui: found record, or None if ANAF lists it in notFound}. A CUI ANAF says nothing about
    is left out: the caller treats it as unavailable, never as 'not inactive'.
    Raises ValueError if the payload is not a v9 response at all."""
    if not isinstance(payload, dict) or not isinstance(payload.get("found", []), list):
        raise ValueError("not a v9 {found, notFound} response")
    if "found" not in payload and "notFound" not in payload:
        raise ValueError("not a v9 {found, notFound} response")
    found = {_cui_of(r): r for r in payload.get("found") or [] if isinstance(r, dict)}
    not_found = {
        str(c.get("cui") if isinstance(c, dict) else c).strip()
        for c in payload.get("notFound") or []
    }
    out: dict[str, dict[str, Any] | None] = {}
    for cui in cuis:
        if cui in found:
            out[cui] = found[cui]
        elif cui in not_found:
            out[cui] = None
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


@register_adapter("anaf_v9")
class AnafV9Adapter(BaseAdapter):
    source_label = "ANAF VAT registry v9"
    source_type = SourceType.OFFICIAL
    rate_limit = RateLimit.per_second(1)
    rate_limit_key = "anaf_webservicesp"  # same host as /bilant, so they share one limit
    mirror_max_age_s = 86_400  # inactive / VAT status can change any day
    retry_statuses = frozenset({500, 502, 503, 504})  # never retry a 429 (see docstring)

    async def sync(self, cui: str) -> SyncReport:
        """Download one applicant into the mirror (one request, or none if the entry is fresh)."""
        report = SyncReport(adapter=self.name, cui=cui)
        try:
            result = await self._load(cui, self.deps.clock.today())
        except SourceUnavailable:
            report.failed.append(cui)
            return report
        if result.from_mirror and not result.stale:
            report.reused += 1
        else:
            report.downloaded += 1
        return report

    async def lookup(self, cui: str, on_date: date) -> Sourced[dict[str, Any] | None]:
        """One company: its v9 record, or None if ANAF lists it in `notFound`.
        Agents: mirror (or fixture) only. Never "not inactive" by default: an unreadable
        entry raises SourceUnavailable."""
        result = await self._load(cui, on_date)
        usable, record = _record_of(result, cui)
        if not usable:
            raise SourceUnavailable(self.name, f"no usable v9 data about {cui}")
        return Sourced(data=record, source=result.source, stale=result.stale)

    async def lookup_batch(
        self, cuis: list[str], on_date: date
    ) -> Sourced[dict[str, dict[str, Any] | None]]:
        """{cui: record or None}. CUIs that can't be read are left out (unknown, never clean).

        - Network adapter (sweep job): chunks of MAX_BATCH CUIs, ONE rate-limited request
          each, then store_in_mirror once per CUI.
        - Otherwise (agents, fixture mode): one mirror / fixture read per CUI, no network.
        """
        unique = list(dict.fromkeys(str(c) for c in cuis))
        out: dict[str, dict[str, Any] | None] = {}
        source = None
        if not self.network:
            for cui in unique:
                try:
                    one = await self.lookup(cui, on_date)
                except SourceUnavailable:
                    continue
                out[cui], source = one.data, source or one.source
            if source is None:
                raise SourceUnavailable(self.name, "none of the CUIs is in the local mirror")
            return Sourced(data=out, source=source)

        for start in range(0, len(unique), MAX_BATCH):
            chunk = unique[start : start + MAX_BATCH]
            raw = await self._call_with_retry(self._request(chunk, on_date))  # 1 req/s globally
            try:
                records = split_response(json.loads(raw), chunk)
            except ValueError as exc:
                raise SourceUnavailable(self.name, f"invalid v9 batch response: {exc}") from exc
            for cui, record in records.items():
                stored = await self.store_in_mirror(cui, _single_body(cui, record), URL)
                source = source or stored.source
                out[cui] = record
        if source is None:
            raise SourceUnavailable(self.name, "ANAF returned none of the requested CUIs")
        return Sourced(data=out, source=source)

    # ------------------------------------------------------------------ internals
    @staticmethod
    def _request(cuis: list[str], on_date: date) -> RequestFn:
        body = _body(cuis, on_date)

        async def request(client: httpx.AsyncClient) -> httpx.Response:
            return await client.post(URL, json=body)

        return request

    async def _load(self, cui: str, on_date: date) -> FetchResult:
        request = self._request([cui], on_date)
        fixture = self.company_fixture(cui, "anaf_v9.json")
        result = await self.fetch(cache_key=cui, request=request, url=URL, fixture=fixture)
        if result.fixture:
            return result
        if result.from_mirror:
            if _record_of(result, cui)[0] or not self.network:
                return result  # lookup() reports an unreadable entry as unavailable
            # A corrupt entry must not be "reused" until it expires: download it again.
            result = await self.fetch(
                cache_key=cui, request=request, url=URL, fixture=fixture, max_age_s=0
            )
            if result.from_mirror:
                return result  # live call failed, the old copy was served
        # Fresh download: keep only this company's slice in the mirror, the same shape the
        # batch sweep stores. fetch() already archived the raw answer.
        usable, record = _record_of(result, cui)
        if not usable:
            raise SourceUnavailable(self.name, f"invalid v9 response for {cui}")
        return await self.store_in_mirror(cui, _single_body(cui, record), URL)
