"""Owner: @role-4-external-agents (search + presence footprint built by role 3 with the human's
approval). Tavily web search (D10), behind the WebSearch port. Source type WEB.

Facts:
- POST https://api.tavily.com/search with an Authorization: Bearer TAVILY_API_KEY header.
  Body: {"query", "topic": "general" | "news" (news gives published_date), "max_results",
  "start_date", "include_raw_content": false}.
- Response: {"query", "results": [{"title", "url", "content", "score", "published_date"}], ...}
  Fixtures use exactly this shape: fixtures/companies/<cui>_<slug>/media.json.
- Results are UNTRUSTED text. They go through verifirm.llm.untrusted before any LLM sees them.
- The media agent needs URL + date. A result without published_date can't become a signal.

Local-first (docs/LOCAL_DATA.md): sync(cui) runs the presence queries ONCE and stores the Tavily
answers in the mirror (cache_key = the query). search() and footprint() read the mirror only
for agents (network=False). The query builders live here, so sync and agents ask the same thing.
Without TAVILY_API_KEY, a download is SourceUnavailable (never "no results").
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import replace
from datetime import date
from typing import Any
from urllib.parse import urlparse

import httpx

from verifirm.adapters.anaf_v9 import AnafV9Adapter
from verifirm.adapters.base import BaseAdapter, FetchResult, Sourced, SourceUnavailable, SyncReport
from verifirm.adapters.presence_fixture import read_parts
from verifirm.core.impl_local.web_search import FixtureWebSearch
from verifirm.core.ports.rate_limiter import RateLimit
from verifirm.core.ports.web_search import WebResult, WebSearch
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType

URL = "https://api.tavily.com/search"
WEBSITE_RESULTS = 8
JOBS_RESULTS = 10

# Sites that list every company (directories, social networks, encyclopedias, press): a result
# there is never the company's OWN website.
NOT_OFFICIAL = (
    "listafirme.ro",
    "termene.ro",
    "risco.ro",
    "totalfirme.ro",
    "firme.info",
    "infocui.ro",
    "romanian-companies.eu",
    "mfinante.gov.ro",
    "anaf.ro",
    "onrc.ro",
    "facebook.com",
    "linkedin.com",
    "instagram.com",
    "youtube.com",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "wikipedia.org",
    "zf.ro",
    "wall-street.ro",
    "economica.net",
    "hotnews.ro",
    "digi24.ro",
    "ejobs.ro",
    "bestjobs.eu",
    "hipo.ro",
    "indeed.com",
    "glassdoor.com",
    "olx.ro",
)
JOB_BOARDS = ("ejobs.ro", "bestjobs.eu", "hipo.ro", "indeed.com", "glassdoor.com", "jobs.ro")
_JOB_WORDS = ("job", "angaj", "cariere", "career", "locuri de munca", "recrut")
# Words that don't identify a company (legal forms, generic words).
_GENERIC = {
    "srl",
    "sa",
    "sca",
    "snc",
    "pfa",
    "societatea",
    "comerciala",
    "romania",
    "international",
    "group",
    "grup",
    "holding",
    "company",
    "compania",
    "trade",
    "impex",
    "productie",
    "producere",
    "electrice",
    "energiei",
    "distributie",
    "servicii",
    "automobile",
}


def company_words(name: str) -> list[str]:
    """Distinctive words of a company name, for matching domains and job ads."""
    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch)).lower()
    words = re.findall(r"[a-z0-9]+", folded)
    return [w for w in words if len(w) >= 4 and w not in _GENERIC]


def presence_queries(company_name: str) -> dict[str, str]:
    """The presence agent's searches. sync() and footprint() MUST use exactly these."""
    core = " ".join(company_words(company_name)) or company_name
    return {"website": f"{core} site oficial", "jobs": f"{core} locuri de munca angajari"}


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _is(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def pick_website(results: list[WebResult], company_name: str) -> dict[str, Any] | None:
    """The first result on a domain that carries a distinctive word of the company's name and is
    not a directory / social network / press site. None: searched, no own website found."""
    words = company_words(company_name)
    for r in results:
        host = _host(r.url)
        label = host.split(".")[-2] if host.count(".") >= 1 else host
        if host and not _is(host, NOT_OFFICIAL) and any(w in label for w in words):
            return {"url": f"https://{host}", "address_on_site": None}
    return None


def pick_jobs(
    results: list[WebResult], company_name: str, website: str | None
) -> list[dict[str, Any]]:
    """Job ads for this company: on a known job board or the company's own careers page, and
    mentioning a distinctive word of its name."""
    words = company_words(company_name)
    own = _host(website) if website else None
    jobs = []
    for r in results:
        host = _host(r.url)
        text = f"{r.title} {r.snippet}".lower()
        on_board = _is(host, JOB_BOARDS) or (
            own is not None
            and host == own
            and any(k in r.url.lower() for k in ("cariere", "career", "job"))
        )
        if on_board and any(w in text for w in words) and any(k in text for k in _JOB_WORDS):
            posted = r.published_at.isoformat() if r.published_at else None
            jobs.append({"title": r.title, "url": r.url, "posted": posted})
    return jobs


@register_adapter("web_search")
class TavilyWebSearch(BaseAdapter, WebSearch):
    source_label = "Web search (Tavily)"
    source_type = SourceType.WEB
    rate_limit = RateLimit.per_second(2)  # PROPOSAL: check the plan's limit
    mirror_max_age_s = 86_400

    # ------------------------------------------------------------------ sync (network)
    async def sync(self, cui: str) -> SyncReport:
        """The presence searches for one company (its name from the anaf_v9 mirror). A search
        already in the mirror and fresh is reused (no call)."""
        report = SyncReport(adapter=self.name, cui=cui)
        try:
            # Mirror only: a Tavily sync must never send a request to ANAF.
            v9 = await AnafV9Adapter(replace(self.deps, network=False)).lookup(
                cui, self.deps.clock.today()
            )
        except SourceUnavailable:
            report.failed.append("no company name: fetch anaf_v9 for this CUI first")
            return report
        name = ((v9.data or {}).get("date_generale") or {}).get("denumire")
        if not name:
            report.failed.append("ANAF has no name for this CUI")
            return report
        for kind, query in presence_queries(name).items():
            limit = WEBSITE_RESULTS if kind == "website" else JOBS_RESULTS
            try:
                _, result = await self._search(query, limit, None)
            except SourceUnavailable:
                report.failed.append(query)
                continue
            if result.from_mirror and not result.stale:
                report.reused += 1
            else:
                report.downloaded += 1
        return report

    # ------------------------------------------------------------------ READ
    async def search(
        self, query: str, *, max_results: int = 10, since: date | None = None
    ) -> list[WebResult]:
        """Tavily results for `query` (mirror only for agents). FIXTURE_MODE: media.json via
        FixtureWebSearch (matched on the words of the query)."""
        if self.settings.fixture_mode:
            return await FixtureWebSearch(self.fixtures_dir).search(
                query, max_results=max_results, since=since
            )
        results, _ = await self._search(query, max_results, since)
        return results

    async def footprint(self, cui: str, company_name: str) -> Sourced[dict[str, Any]]:
        """Presence agent: {website: {url, address_on_site} | None, jobs: [{title, url, posted}]}.
        `website: None` and `jobs: []` mean "searched, nothing found". FIXTURE_MODE: presence.json.
        Live: both presence searches must be in the mirror (sync), else SourceUnavailable."""
        if self.settings.fixture_mode:
            return await read_parts(self, cui, {"website": (dict, type(None)), "jobs": (list,)})
        queries = presence_queries(company_name)
        site_results, site = await self._search(queries["website"], WEBSITE_RESULTS, None)
        job_results, jobs = await self._search(queries["jobs"], JOBS_RESULTS, None)
        website = pick_website(site_results, company_name)
        data = {
            "website": website,
            "jobs": pick_jobs(job_results, company_name, website["url"] if website else None),
        }
        return Sourced(data=data, source=site.source, stale=site.stale or jobs.stale)

    # ------------------------------------------------------------------ internals
    async def _search(
        self, query: str, max_results: int, since: date | None
    ) -> tuple[list[WebResult], FetchResult]:
        key = f"tavily|{query}|{max_results}|{since.isoformat() if since else ''}"
        api_key = (self.settings.tavily_api_key or "").strip()
        if self.network and not api_key:
            raise SourceUnavailable(self.name, "TAVILY_API_KEY is not set")
        body: dict[str, Any] = {
            "query": query,
            "max_results": max_results,
            "topic": "news" if since else "general",
            "include_raw_content": False,
        }
        if since:
            body["start_date"] = since.isoformat()

        async def request(client: httpx.AsyncClient) -> httpx.Response:
            return await client.post(URL, json=body, headers={"Authorization": f"Bearer {api_key}"})

        result = await self.fetch(cache_key=key, request=request, url=URL)
        try:
            payload = result.json()
            items = payload["results"]
            if not isinstance(items, list):
                raise TypeError("results is not a list")
        except (ValueError, KeyError, TypeError) as exc:
            raise SourceUnavailable(self.name, f"invalid Tavily answer for {query!r}") from exc
        results = []
        for item in items:
            if not isinstance(item, dict) or not item.get("url"):
                continue
            published = str(item.get("published_date") or "")[:10]
            try:
                published_at = date.fromisoformat(published) if published else None
            except ValueError:
                published_at = None
            results.append(
                WebResult(
                    url=str(item["url"]),
                    title=str(item.get("title") or ""),
                    snippet=str(item.get("content") or ""),
                    published_at=published_at,
                    provider="tavily",
                )
            )
        return results, result
