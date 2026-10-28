"""ANAF VAT registry web service, version 9 (OFFICIAL, free). Owner: @role-3-official-agents.

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
- There is NO cod/message wrapper on live 200 responses. Don't expect one.
- Fixture: fixtures/companies/<cui>_<slug>/anaf_v9.json, the exact response shape.

Used by: identity sheet (official), identity agent (inactive/reactivated), tax agent
(VAT cancelled), anaf_efactura_registry, and the background sweep (change detection).

Local-first (docs/LOCAL_DATA.md):
- Mirror: ONE entry per company, cache_key = the CUI ("latest known record"), holding that
  company's slice of a response ({"found": [record], "notFound": []} or the reverse). Freshness
  is mirror_max_age_s (default 24h): an older entry is served stale=True, never dropped.
  (Not keyed by date: a run before the daily sweep would otherwise find nothing for "today".)
- sync(cui): one request for a single applicant (reuses a fresh entry: no call).
- lookup_batch with a network adapter (sweep job): chunks of MAX_BATCH = one request each,
  then store_in_mirror once per CUI. Agents' adapters have network=False: mirror only.
- No retry on HTTP 429: ANAF asking us to slow down is never answered with more requests.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import httpx

from verifirm.adapters.base import BaseAdapter, FetchResult, Sourced, SourceUnavailable, SyncReport
from verifirm.core.ports.rate_limiter import RateLimit
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType

URL = "https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva"
MAX_BATCH = 100


def _body(cuis: list[str], on_date: date) -> list[dict[str, Any]]:
    return [{"cui": int(c), "data": on_date.isoformat()} for c in cuis]


def _split(payload: Any, cuis: list[str]) -> dict[str, dict[str, Any]]:
    """A {found, notFound} response -> per-CUI slices in the same shape. Missing CUIs are
    absent from the result (the response didn't mention them: unknown, not "not found")."""
    if not isinstance(payload, dict) or not isinstance(payload.get("found"), list):
        raise ValueError("not a v9 {found, notFound} response")
    slices: dict[str, dict[str, Any]] = {}
    for record in payload["found"]:
        cui = str((record.get("date_generale") or {}).get("cui", ""))
        if cui in cuis:
            slices[cui] = {"found": [record], "notFound": []}
    for missing in payload.get("notFound") or []:
        cui = str(missing.get("cui") if isinstance(missing, dict) else missing)
        if cui in cuis and cui not in slices:
            slices[cui] = {"found": [], "notFound": [int(cui)]}
    return slices


def _slice(result: FetchResult, cui: str) -> dict[str, Any] | None:
    """This company's {found, notFound} slice, or None if the body is not usable."""
    try:
        return _split(result.json(), [cui]).get(cui)
    except ValueError:
        return None


@register_adapter("anaf_v9")
class AnafV9Adapter(BaseAdapter):
    source_label = "ANAF VAT registry v9"
    source_type = SourceType.OFFICIAL
    rate_limit = RateLimit.per_second(1)
    rate_limit_key = "anaf_webservicesp"  # same host as /bilant, so they share one limit
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
        """One company: its `found[0]` record, or None if ANAF lists it in `notFound`.
        Agents: mirror (or fixture) only. Never "not inactive" by default: an unreadable
        entry raises SourceUnavailable."""
        result = await self._load(cui, on_date)
        try:
            slices = _split(result.json(), [cui])
        except ValueError as exc:
            raise SourceUnavailable(self.name, f"invalid v9 data for {cui}: {exc}") from exc
        if cui not in slices:
            raise SourceUnavailable(self.name, f"{cui} is neither found nor notFound")
        found = slices[cui]["found"]
        return Sourced(data=found[0] if found else None, source=result.source, stale=result.stale)

    async def lookup_batch(
        self, cuis: list[str], on_date: date
    ) -> Sourced[dict[str, dict[str, Any] | None]]:
        """{cui: record or None}. CUIs that can't be read are left out (unknown, never clean).

        - Network adapter (sweep job): chunks of MAX_BATCH CUIs, ONE rate-limited request
          each, then store_in_mirror once per CUI.
        - Otherwise (agents, fixture mode): one mirror / fixture read per CUI, no network.
        The returned source is the last chunk's (or entry's); per-CUI sources live in the mirror.
        """
        unique = list(dict.fromkeys(str(c) for c in cuis))
        out: dict[str, dict[str, Any] | None] = {}
        last: Sourced[Any] | None = None
        if not self.network:
            for cui in unique:
                try:
                    one = await self.lookup(cui, on_date)
                except SourceUnavailable:
                    continue
                out[cui], last = one.data, one
            if last is None:
                raise SourceUnavailable(self.name, "none of the CUIs is in the local mirror")
            return Sourced(data=out, source=last.source, stale=last.stale)

        stored: FetchResult | None = None
        for start in range(0, len(unique), MAX_BATCH):
            chunk = unique[start : start + MAX_BATCH]
            payload = _body(chunk, on_date)

            async def request(
                client: httpx.AsyncClient, body: list[dict[str, Any]] = payload
            ) -> httpx.Response:
                return await client.post(URL, json=body)

            raw = await self._call_with_retry(request)  # rate limited, 1 req/s globally
            try:
                slices = _split(json.loads(raw), chunk)
            except ValueError as exc:
                raise SourceUnavailable(self.name, f"invalid v9 batch response: {exc}") from exc
            for cui, piece in slices.items():
                stored = await self.store_in_mirror(cui, json.dumps(piece).encode(), URL)
                found = piece["found"]
                out[cui] = found[0] if found else None
        if stored is None:
            raise SourceUnavailable(self.name, "ANAF returned none of the requested CUIs")
        return Sourced(data=out, source=stored.source)

    async def _load(self, cui: str, on_date: date) -> FetchResult:
        async def request(client: httpx.AsyncClient) -> httpx.Response:
            return await client.post(URL, json=_body([cui], on_date))

        fixture = self.company_fixture(cui, "anaf_v9.json")
        result = await self.fetch(cache_key=cui, request=request, url=URL, fixture=fixture)
        if result.fixture:
            return result
        if result.from_mirror:
            if _slice(result, cui) is not None or not self.network:
                return result  # lookup() reports an unreadable entry as unavailable
            # A corrupt entry must not be "reused" until it expires: download it again.
            result = await self.fetch(
                cache_key=cui, request=request, url=URL, fixture=fixture, max_age_s=0
            )
            if result.from_mirror:
                return result  # live call failed, the old copy was served
        # Fresh download of a single CUI: keep only this company's slice in the mirror,
        # the same shape the batch sweep stores. fetch() already archived the raw answer.
        piece = _slice(result, cui)
        if piece is None:
            raise SourceUnavailable(self.name, f"invalid v9 response for {cui}")
        return await self.store_in_mirror(cui, json.dumps(piece).encode(), URL)
