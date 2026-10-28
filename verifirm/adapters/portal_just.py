"""STUB. Owner: @role-4-external-agents. Romanian courts portal (OFFICIAL, free, SOAP).

Facts:
- SOAP endpoint: http://portalquery.just.ro/query.asmx (WSDL at ?WSDL).
- Methods: CautareDosare (search cases by party name / case number / institution),
  CautareDosare2 (same, plus a last-modified date filter: use it for polling new cases),
  CautareSedinte (hearings).
- Max 1,000 results per query: split by institution or date range when you hit the cap,
  and report it in notes (truncated results are PARTIAL, not clean).
- Parties have NO CUI. Matching is by NAME ONLY, so return EntityMatch-friendly info
  (exact normalized name vs fuzzy, county of the court) and let entity resolution lower
  confidence for ambiguous matches.
- Write the SOAP envelopes by hand with httpx (no SOAP library dependency) and parse with
  xml.etree. The fixture is the raw SOAP response:
  fixtures/companies/<cui>_<slug>/portal_just.xml.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from verifirm.adapters.base import BaseAdapter, Sourced
from verifirm.core.ports.rate_limiter import RateLimit
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType

URL = "http://portalquery.just.ro/query.asmx"
MAX_RESULTS = 1000


@register_adapter("portal_just")
class PortalJustAdapter(BaseAdapter):
    source_label = "Portal Just (portal.just.ro)"
    source_type = SourceType.OFFICIAL
    rate_limit = RateLimit.per_second(2)  # PROPOSAL: no published limit, so be polite

    async def search_cases(self, party_name: str) -> Sourced[list[dict[str, Any]]]:
        """CautareDosare by party name -> cases: numar, institutie, obiect, stadiuProcesual,
        categorieCaz, data, parti[{nume, calitateParte}], sedinte[...]."""
        raise NotImplementedError

    async def cases_modified_since(
        self, party_name: str, since: date
    ) -> Sourced[list[dict[str, Any]]]:
        """CautareDosare2 with the last-modified filter. Used by jobs/poll_new_cases.py."""
        raise NotImplementedError
