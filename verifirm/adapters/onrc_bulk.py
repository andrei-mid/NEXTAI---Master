"""STUB. Owner: @role-1-database. ONRC trade-register open data (OFFICIAL, bulk).

Facts:
- data.gov.ro, licence CC BY 4.0 (attribute "ONRC"), refreshed roughly monthly.
- Files: OD_FIRME.CSV (~675 MB: name, CUI, reg. no., address, ...), OD_STARE_FIRMA.CSV
  (status codes), OD_CAEN_AUTORIZAT.CSV (authorized CAEN per company, Rev.2 and/or Rev.3),
  OD_REPREZENTANTI_LEGALI.CSV (administrators / legal representatives),
  OD_SUCURSALE_ALTE_STATE_MEMBRE.CSV (branches of EU companies).
- Has administrators, NO shareholders (shareholders are mocked: mocks/shareholders.py).
- BULK-LOAD it, NEVER call per company. Discover the current file URLs from the data.gov.ro
  dataset page / CKAN API at ingest time. Don't hard-code monthly URLs.
- Check the delimiter and encoding per file on download (historically `^`-separated).
  Stream line by line. The 675 MB file must never be read into memory.
- CAEN Rev.2 -> Rev.3 migration: keep both codes. The "CAEN not authorized" rule needs a
  Rev.2<->Rev.3 mapping table (put it in fixtures/sources/caen_rev2_rev3.csv).

Ingestion (apps/worker/jobs/ingest_onrc.py) writes local tables. Lookups read those tables.
Fixture mode: fixtures/sources/onrc/*.csv (same columns, fictional rows, J99 numbers) plus
fixtures/companies/<cui>_<slug>/onrc.json for the per-company view.

Local-first (docs/LOCAL_DATA.md): bulk: the ingest_onrc job downloads and COPYs into Postgres. sync() stays the default no-op. READ methods query the local tables only.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx

from verifirm.adapters.base import BaseAdapter, Sourced, SourceUnavailable
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType


async def _no_network(client: httpx.AsyncClient) -> httpx.Response:
    raise SourceUnavailable("onrc_bulk", "ONRC is bulk-only: never fetched per company")


def _norm_address(address: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", address.casefold()).strip()


DATASET_PAGE = (
    "https://data.gov.ro/dataset/firme-inregistrate-la-registrul-comertului-pana-la-data-de"
)
FILES = (
    "OD_FIRME.CSV",
    "OD_STARE_FIRMA.CSV",
    "OD_CAEN_AUTORIZAT.CSV",
    "OD_REPREZENTANTI_LEGALI.CSV",
    "OD_SUCURSALE_ALTE_STATE_MEMBRE.CSV",
)


@register_adapter("onrc_bulk")
class OnrcBulkAdapter(BaseAdapter):
    source_label = "ONRC open data (data.gov.ro)"
    source_type = SourceType.OFFICIAL
    mirror_max_age_s = 30 * 86_400

    async def download(self, dest_dir: Path) -> dict[str, Path]:
        """Stream every file in FILES to dest_dir (httpx streaming, chunked). Return name -> path.
        Archive a manifest (file names, sizes, sha256, source URLs) via the ObjectStore."""
        raise NotImplementedError

    async def iter_rows(self, path: Path) -> AsyncIterator[dict[str, str]]:
        """Stream one CSV as dicts (header row = keys), skipping malformed lines and counting them."""
        raise NotImplementedError
        yield {}  # pragma: no cover (makes this an async generator)

    async def company(self, cui: str) -> Sourced[dict[str, Any] | None]:
        """Per-company view from the ingested tables: names (with history if available),
        reg. no., address, status, CAEN (main + authorized), legal representatives.

        Implemented for FIXTURE_MODE (fixtures/companies/<cui>_<slug>/onrc.json, None if the
        company has no ONRC fixture). Live: TODO role 1, read the onrc_* tables written by
        ingest_onrc. Until then it reports unavailable, never clean."""
        if not self.settings.fixture_mode:
            raise SourceUnavailable(
                self.name, "ONRC bulk tables not ingested yet (ingest_onrc, role 1)"
            )
        fixture = self.company_fixture(cui, "onrc.json")
        if fixture is None:
            if self.company_fixture_dir(cui) is None:
                raise SourceUnavailable(self.name, f"no ONRC fixture for {cui}")
            return Sourced(
                data=None, source=self._source_ref(None, None, None, self.deps.clock.now())
            )
        result = await self.fetch(cache_key=f"company:{cui}", request=_no_network, fixture=fixture)
        return Sourced(data=result.json(), source=result.source)

    async def companies_at_address(self, normalized_address: str) -> Sourced[list[str]]:
        """CUIs registered at the same normalized address (rule ID-SHARED-OFFICE-01).

        Implemented for FIXTURE_MODE (fixtures/sources/onrc/OD_FIRME_sample.csv). Live: TODO
        role 1, query the onrc_companies table by address_normalized."""
        if not self.settings.fixture_mode:
            raise SourceUnavailable(
                self.name, "ONRC bulk tables not ingested yet (ingest_onrc, role 1)"
            )
        sample = self.shared_fixture("onrc/OD_FIRME_sample.csv")
        if sample is None:
            raise SourceUnavailable(self.name, "no ONRC sample fixture")
        result = await self.fetch(cache_key="od_firme_sample", request=_no_network, fixture=sample)
        wanted = _norm_address(normalized_address)
        rows = csv.DictReader(io.StringIO(result.text()), delimiter="^")
        cuis = [r["CUI"] for r in rows if _norm_address(r.get("ADRESA_COMPLETA", "")) == wanted]
        return Sourced(data=cuis, source=result.source)

    async def companies_of_person(self, person_name: str) -> Sourced[list[dict[str, Any]]]:
        """Companies where this person is or was a legal representative (network agent).
        Matching is by name only: return the match method/score so the agent can lower confidence."""
        raise NotImplementedError
