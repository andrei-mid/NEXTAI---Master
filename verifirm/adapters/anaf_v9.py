"""Owner: @role-3-official-agents. ANAF VAT registry web service, version 9 (OFFICIAL, free).

Facts:
- POST https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva
- Body: [{"cui": 123, "data": "YYYY-MM-DD"}, ...]. The CUI is an int, the date is the reference date.
- Max 100 CUIs per request. Max 1 request/second (declared below, enforced globally).
- Response: {"found": [...], "notFound": [...]}. Each found item has `date_generale`
  (denumire, adresa, nrRegCom, cod_CAEN, forma_juridica, stare_inregistrare,
  statusRO_e_Factura, ...), `inregistrare_scop_Tva` (scpTVA + perioade_TVA history),
  `stare_inactiv` (statusInactivi, dataInactivare, dataReactivare, dataRadiere),
  `inregistrare_RTVAI`, `adresa_sediu_social`, `adresa_domiciliu_fiscal`.
- There is NO cod/message wrapper on live 200 responses. A wrapper is tolerated anyway.
- Fixture: fixtures/companies/<cui>_<slug>/anaf_v9.json, the exact response shape.

Used by: identity sheet (official), identity agent (inactive/reactivated), tax agent
(VAT cancelled), and the background sweep (batches of 100: cheap change detection).

Local-first (docs/LOCAL_DATA.md): the mirror holds ONE entry per company (cache_key = the CUI),
always shaped like a v9 response for that single CUI: {"found": [record]} or {"notFound": [cui]}.
- `sync(cui)`: one POST for that company (applications, rechecks, sync_portfolio).
- `lookup_batch(cuis)` with network (sweep job): 100 CUIs per POST, then one mirror entry per CUI.
- `lookup(cui)`: what agents call. Mirror only (no network), so it never calls ANAF.
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


def _cui_of(record: dict[str, Any]) -> str:
    return str((record.get("date_generale") or {}).get("cui", "")).strip()


def split_response(payload: dict[str, Any], cuis: list[str]) -> dict[str, dict[str, Any] | None]:
    """{cui: found record, or None if ANAF lists it in notFound}. A CUI ANAF says nothing about
    is left out: the caller treats it as unavailable, never as 'not inactive'."""
    out: dict[str, dict[str, Any] | None] = {}
    found = {_cui_of(r): r for r in payload.get("found") or [] if isinstance(r, dict)}
    not_found = {str(c).strip() for c in payload.get("notFound") or []}
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


@register_adapter("anaf_v9")
class AnafV9Adapter(BaseAdapter):
    source_label = "ANAF VAT registry v9"
    source_type = SourceType.OFFICIAL
    rate_limit = RateLimit.per_second(1)
    rate_limit_key = "anaf_webservicesp"  # same host as /bilant, so they share one limit
    mirror_max_age_s = 86_400  # inactive / VAT status can change any day

    async def sync(self, cui: str) -> SyncReport:
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
        """One company: its v9 record, or None if ANAF lists it in `notFound`."""
        result = await self._load(cui, on_date)
        try:
            records = split_response(result.json(), [cui])
        except (ValueError, AttributeError) as exc:
            raise SourceUnavailable(self.name, f"invalid v9 payload for {cui}") from exc
        if cui not in records:
            raise SourceUnavailable(self.name, f"ANAF returned nothing about {cui}")
        return Sourced(data=records[cui], source=result.source, stale=result.stale)

    async def lookup_batch(
        self, cuis: list[str], on_date: date
    ) -> Sourced[dict[str, dict[str, Any] | None]]:
        """Up to 100 CUIs per POST (sweep job). Stores one mirror entry per CUI.
        CUIs ANAF says nothing about are missing from the result (unavailable, not clean).
        Without network (or in fixture mode) it reads the per-company entries instead."""
        if not self.network:
            data: dict[str, dict[str, Any] | None] = {}
            source = None
            for cui in cuis:
                try:
                    one = await self.lookup(cui, on_date)
                except SourceUnavailable:
                    continue
                data[cui], source = one.data, source or one.source
            if source is None:
                raise SourceUnavailable(self.name, "none of the CUIs is in the local mirror")
            return Sourced(data=data, source=source)

        merged: dict[str, dict[str, Any] | None] = {}
        first_source = None
        for start in range(0, len(cuis), MAX_BATCH):
            chunk = cuis[start : start + MAX_BATCH]
            body = await self._call_with_retry(self._request(chunk, on_date))
            try:
                records = split_response(json.loads(body), chunk)
            except (ValueError, AttributeError) as exc:
                raise SourceUnavailable(self.name, "invalid v9 batch payload") from exc
            for cui, record in records.items():
                stored = await self.store_in_mirror(cui, _single_body(cui, record), URL)
                first_source = first_source or stored.source
                merged[cui] = record
        if first_source is None:
            raise SourceUnavailable(self.name, "ANAF returned no records for the batch")
        return Sourced(data=merged, source=first_source)

    # ------------------------------------------------------------------ internals
    @staticmethod
    def _request(cuis: list[str], on_date: date) -> RequestFn:
        body = [{"cui": int(c), "data": on_date.isoformat()} for c in cuis]

        async def request(client: httpx.AsyncClient) -> httpx.Response:
            return await client.post(URL, json=body)

        return request

    async def _load(self, cui: str, on_date: date) -> FetchResult:
        return await self.fetch(
            cache_key=cui,
            request=self._request([cui], on_date),
            url=URL,
            fixture=self.company_fixture(cui, "anaf_v9.json"),
        )
