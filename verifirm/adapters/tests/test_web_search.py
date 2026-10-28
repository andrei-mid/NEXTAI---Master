"""web_search: the presence footprint (website + job postings). Tavily search() is still TODO."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from verifirm.adapters.base import AdapterDeps, SourceUnavailable
from verifirm.adapters.web_search import TavilyWebSearch
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter
from verifirm.schema.signals import SourceType

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def adapter(
    tmp_path: Path, *, fixture_mode: bool = True, fixtures: Path = FIXTURES
) -> TavilyWebSearch:
    return TavilyWebSearch(
        AdapterDeps(
            settings=Settings(fixture_mode=fixture_mode, fixtures_dir=fixtures),
            cache=MemoryCache(),
            object_store=FilesystemObjectStore(tmp_path / "objects"),
            rate_limiter=MemoryRateLimiter(),
            clock=FixedClock(datetime(2026, 10, 28, tzinfo=UTC)),
        )
    )


def broken(tmp_path: Path, content: Any) -> Path:
    """A fixtures dir where company 99000999 has presence.json = `content`."""
    root = tmp_path / "fixtures"
    target = root / "companies" / "99000999_broken" / "presence.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(content), encoding="utf-8")
    return root


async def test_aurora_has_a_website_and_jobs(tmp_path: Path) -> None:
    result = await adapter(tmp_path).footprint("99000017", "AURORA SOFT LABS SRL")
    assert result.data["website"]["url"] == "https://aurora-soft-labs.example"
    assert len(result.data["jobs"]) == 2
    assert result.source.type is SourceType.WEB


async def test_zephyria_has_nothing(tmp_path: Path) -> None:
    result = await adapter(tmp_path).footprint("99000025", "ZEPHYRIA LOGISTIC NOVA SRL")
    assert result.data == {"website": None, "jobs": []}  # searched, nothing found


async def test_live_is_unavailable_never_empty(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailable, match="not in the local mirror"):
        await adapter(tmp_path, fixture_mode=False).footprint("2816464", "DEDEMAN SRL")


@pytest.mark.parametrize("content", [{"website": "yes", "jobs": []}, {"website": None}])
async def test_wrong_shape_is_unavailable(tmp_path: Path, content: Any) -> None:
    with pytest.raises(SourceUnavailable):
        await adapter(tmp_path, fixtures=broken(tmp_path, content)).footprint("99000999", "X")


# ---------------------------------------------------------------- live: simulated Tavily
import httpx  # noqa: E402

from verifirm.adapters.anaf_v9 import AnafV9Adapter, _single_body  # noqa: E402
from verifirm.adapters.web_search import (  # noqa: E402
    company_words,
    pick_jobs,
    pick_website,
    presence_queries,
)
from verifirm.core.ports.web_search import WebResult  # noqa: E402

DEDEMAN = "2816464"


class _Tavily:
    """Fake Tavily: answers per query, records every call (method, auth header, body)."""

    def __init__(self, answers: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.calls: list[httpx.Request] = []
        self.answers = answers or {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        query = json.loads(request.content)["query"]
        results = next((r for q, r in self.answers.items() if q in query), [])
        return httpx.Response(200, json={"query": query, "results": results})


DEDEMAN_ANSWERS = {
    "site oficial": [
        {"url": "https://www.listafirme.ro/dedeman-srl-2816464/", "title": "DEDEMAN SRL"},
        {"url": "https://www.dedeman.ro/ro/", "title": "Dedeman - magazin online"},
    ],
    "locuri de munca": [
        {
            "url": "https://www.ejobs.ro/locuri-de-munca/dedeman",
            "title": "Locuri de munca Dedeman",
            "content": "Angajari Dedeman: vanzator, casier",
            "published_date": "2026-10-20",
        },
        {
            "url": "https://www.ejobs.ro/locuri-de-munca/altceva",
            "title": "Locuri de munca",
            "content": "alta firma",
        },
        {"url": "https://www.facebook.com/dedeman", "title": "Dedeman jobs"},
    ],
}


def live(
    tmp_path: Path,
    tavily: _Tavily | None = None,
    *,
    network: bool = False,
    key: str | None = "tvly-test",
) -> TavilyWebSearch:
    return TavilyWebSearch(
        AdapterDeps(
            settings=Settings(fixture_mode=False, fixtures_dir=FIXTURES, tavily_api_key=key),
            cache=MemoryCache(),
            object_store=FilesystemObjectStore(tmp_path / "objects"),
            rate_limiter=MemoryRateLimiter(),
            clock=FixedClock(datetime(2026, 10, 28, tzinfo=UTC)),
            http=httpx.AsyncClient(transport=httpx.MockTransport(tavily)) if tavily else None,
            network=network,
        )
    )


async def seed_v9_name(tmp_path: Path, cui: str = DEDEMAN, name: str = "DEDEMAN SRL") -> None:
    """Put a v9 record (the company name) in the mirror, as the v9 fetch would."""
    v9 = AnafV9Adapter(live(tmp_path).deps)
    record = {"date_generale": {"cui": int(cui), "denumire": name}}
    await v9.store_in_mirror(cui, _single_body(cui, record), None)


def test_presence_queries_use_the_distinctive_words() -> None:
    assert presence_queries("DEDEMAN SRL") == {
        "website": "dedeman site oficial",
        "jobs": "dedeman locuri de munca angajari",
    }
    assert company_words("AUTOMOBILE-DACIA SA") == ["dacia"]
    assert "hidroelectrica" in company_words(
        'SOCIETATEA DE PRODUCERE A ENERGIEI ELECTRICE IN HIDROCENTRALE " HIDROELECTRICA" S.A.'
    )


def test_pick_website_skips_directories() -> None:
    results = [
        WebResult(url=r["url"], title=r["title"], snippet="", provider="t")
        for r in DEDEMAN_ANSWERS["site oficial"]
    ]
    assert pick_website(results, "DEDEMAN SRL") == {
        "url": "https://dedeman.ro",
        "address_on_site": None,
    }
    assert pick_website(results[:1], "DEDEMAN SRL") is None  # only a directory: no own website


def test_pick_jobs_needs_a_board_and_the_company() -> None:
    results = [
        WebResult(url=r["url"], title=r["title"], snippet=r.get("content", ""), provider="t")
        for r in DEDEMAN_ANSWERS["locuri de munca"]
    ]
    jobs = pick_jobs(results, "DEDEMAN SRL", "https://dedeman.ro")
    assert [j["url"] for j in jobs] == ["https://www.ejobs.ro/locuri-de-munca/dedeman"]


async def test_sync_downloads_the_two_searches_once(tmp_path: Path) -> None:
    await seed_v9_name(tmp_path)
    tavily = _Tavily(DEDEMAN_ANSWERS)
    first = await live(tmp_path, tavily, network=True).sync(DEDEMAN)
    second = await live(tmp_path, tavily, network=True).sync(DEDEMAN)
    assert (first.downloaded, first.failed) == (2, [])
    assert (second.downloaded, second.reused) == (0, 2)  # fresh in the mirror: no call
    assert len(tavily.calls) == 2
    assert tavily.calls[0].headers["Authorization"] == "Bearer tvly-test"
    assert json.loads(tavily.calls[0].content)["query"] == "dedeman site oficial"


async def test_agents_read_the_footprint_without_calls(tmp_path: Path) -> None:
    await seed_v9_name(tmp_path)
    await live(tmp_path, _Tavily(DEDEMAN_ANSWERS), network=True).sync(DEDEMAN)
    tavily = _Tavily()
    result = await live(tmp_path, tavily).footprint(DEDEMAN, "DEDEMAN SRL")
    assert result.data["website"] == {"url": "https://dedeman.ro", "address_on_site": None}
    assert len(result.data["jobs"]) == 1
    assert result.source.type is SourceType.WEB
    assert tavily.calls == []


async def test_no_key_is_unavailable_and_sends_nothing(tmp_path: Path) -> None:
    await seed_v9_name(tmp_path)
    tavily = _Tavily()
    report = await live(tmp_path, tavily, network=True, key=None).sync(DEDEMAN)
    assert len(report.failed) == 2 and tavily.calls == []


async def test_sync_without_the_company_name_never_calls_anaf(tmp_path: Path) -> None:
    calls = _Tavily()  # would also receive any ANAF request (same HTTP client)
    report = await live(tmp_path, calls, network=True).sync(DEDEMAN)
    assert report.failed == ["no company name: fetch anaf_v9 for this CUI first"]
    assert calls.calls == []  # not Tavily, and above all not ANAF


async def test_search_reads_the_mirror_for_agents(tmp_path: Path) -> None:
    await seed_v9_name(tmp_path)
    await live(tmp_path, _Tavily(DEDEMAN_ANSWERS), network=True).sync(DEDEMAN)
    results = await live(tmp_path).search("dedeman site oficial", max_results=8)
    assert [r.url for r in results][1] == "https://www.dedeman.ro/ro/"
    assert all(r.provider == "tavily" for r in results)


async def test_fixture_search_serves_media_json(tmp_path: Path) -> None:
    results = await adapter(tmp_path).search("Zephyria Logistic Nova")
    assert results and all(r.provider == "fixture" for r in results)


@pytest.mark.parametrize(
    ("label", "name", "own"),
    [
        ("dedeman", "DEDEMAN SRL", True),
        ("omvpetrom", "OMV PETROM SA", True),
        (
            "hidroelectrica",
            'SOCIETATEA DE PRODUCERE A ENERGIEI ELECTRICE IN HIDROCENTRALE " HIDROELECTRICA" S.A.',
            True,
        ),
        ("dacia", "AUTOMOBILE-DACIA SA", True),
        ("altex-romania", "ALTEX ROMANIA SRL", True),
        ("getdante", "DANTE INTERNATIONAL SA", False),  # real false match seen on live data
        ("dantelabs", "DANTE INTERNATIONAL SA", False),
        ("emag", "DANTE INTERNATIONAL SA", False),  # brand differs from the legal name: missed
        ("romania", "ALTEX ROMANIA SRL", False),  # only generic words, nothing distinctive
    ],
)
def test_domain_must_be_made_of_the_companys_name(label: str, name: str, own: bool) -> None:
    from verifirm.adapters.web_search import domain_matches

    assert domain_matches(label, name) is own
