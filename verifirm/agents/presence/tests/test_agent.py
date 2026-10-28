"""Presence agent with the REAL adapters in FIXTURE_MODE (no network), plus failure paths."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from verifirm.adapters.anaf_bilant import AnafBilantAdapter
from verifirm.adapters.base import AdapterDeps, BaseAdapter, Sourced, SourceUnavailable
from verifirm.adapters.kohesio import KohesioAdapter
from verifirm.adapters.seap import SeapAdapter
from verifirm.adapters.web_search import TavilyWebSearch
from verifirm.agents.base import AgentContext
from verifirm.agents.presence.agent import FOOTPRINT_SOURCE, PresenceAgent
from verifirm.agents.presence.rules import load_config
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter
from verifirm.schema.identity import Address, IdentitySheet
from verifirm.schema.signals import AgentResult, AgentStatus, Severity, SourceType

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures"
NOW = datetime(2026, 10, 28, 8, 0, tzinfo=UTC)
AURORA, ZEPHYRIA, BRUNALDO, DEDEMAN = "99000017", "99000025", "99000033", "2816464"

ADAPTERS: dict[str, type[BaseAdapter]] = {
    "web_search": TavilyWebSearch,
    "seap": SeapAdapter,
    "kohesio": KohesioAdapter,
    "anaf_bilant": AnafBilantAdapter,
}


def company_dir(cui: str) -> Path | None:
    matches = sorted((FIXTURES / "companies").glob(f"{cui}_*"))
    return matches[0] if matches else None


def identity(cui: str) -> IdentitySheet:
    directory = company_dir(cui)
    if directory is None or not (directory / "onrc.json").exists():
        return IdentitySheet(cui=cui, current_name="DEDEMAN SRL")
    onrc = json.loads((directory / "onrc.json").read_text(encoding="utf-8"))
    return IdentitySheet(
        cui=cui,
        fictional=True,
        current_name=onrc["denumire"],
        registered_office=Address(raw=onrc["adresa"]),
    )


def deps(tmp_path: Path, fixture_mode: bool = True) -> AdapterDeps:
    return AdapterDeps(
        settings=Settings(fixture_mode=fixture_mode, fixtures_dir=FIXTURES),
        cache=MemoryCache(),
        object_store=FilesystemObjectStore(tmp_path / "objects"),
        rate_limiter=MemoryRateLimiter(),
        clock=FixedClock(NOW),
    )


def ctx(
    cui: str,
    tmp_path: Path,
    *,
    overrides: Mapping[str, object] | None = None,
    sheet: IdentitySheet | None = None,
    fixture_mode: bool = True,
) -> AgentContext:
    d = deps(tmp_path, fixture_mode)
    adapters: dict[str, object] = {name: cls(d) for name, cls in ADAPTERS.items()}
    adapters.update(overrides or {})
    return AgentContext(
        run_id="test-run",
        cui=cui,
        identity=sheet or identity(cui),
        settings=d.settings,
        clock=FixedClock(NOW),
        adapters=cast(Mapping[str, BaseAdapter], adapters),
    )


async def run(context: AgentContext) -> AgentResult:
    return await PresenceAgent().run(context)


def by_rule(result: AgentResult) -> dict[str, Any]:
    return {s.rule_id: s for s in result.signals}


class _Down:
    def __getattr__(self, name: str) -> Any:
        async def call(*args: Any, **kwargs: Any) -> Any:
            raise SourceUnavailable(name, "down")

        return call


class _Footprint:
    """web_search stand-in with a chosen website / jobs."""

    def __init__(self, website: Any, jobs: list[Any]) -> None:
        self.website, self.jobs = website, jobs

    async def footprint(self, cui: str, name: str) -> Sourced[dict[str, Any]]:
        real = await TavilyWebSearch(_fixture_deps()).footprint(AURORA, name)
        return Sourced(data={"website": self.website, "jobs": self.jobs}, source=real.source)


class _Seap:
    def __init__(self, contracts: list[dict[str, Any]]) -> None:
        self.contracts = contracts

    async def contracts_for(self, cui: str) -> Sourced[list[dict[str, Any]]]:
        real = await SeapAdapter(_fixture_deps()).contracts_for(AURORA)
        return Sourced(data=self.contracts, source=real.source)


def _fixture_deps() -> AdapterDeps:
    return deps(Path("/nonexistent"))


# ------------------------------------------------------------------- demo companies
@pytest.mark.parametrize(
    ("cui", "expected", "status"),
    [
        (AURORA, set(), AgentStatus.OK),  # website + jobs: a normal footprint
        (ZEPHYRIA, {"PRE-NO-FOOTPRINT-01"}, AgentStatus.OK),
        (BRUNALDO, set(), AgentStatus.OK),  # has a website, same address as ONRC
        ("99000041", set(), AgentStatus.UNAVAILABLE),  # no presence data at all
        (DEDEMAN, set(), AgentStatus.UNAVAILABLE),
    ],
)
async def test_fixture_companies(
    tmp_path: Path, cui: str, expected: set[str], status: AgentStatus
) -> None:
    result = await run(ctx(cui, tmp_path))
    assert set(by_rule(result)) == expected
    assert result.status is status


async def test_zephyria_matches_api_fixture(tmp_path: Path) -> None:
    directory = company_dir(ZEPHYRIA)
    assert directory is not None
    api = json.loads((directory / "api" / "signals.json").read_text(encoding="utf-8"))
    want = next(s for s in api if s["agent"] == "presence")
    got = by_rule(await run(ctx(ZEPHYRIA, tmp_path)))["PRE-NO-FOOTPRINT-01"].model_dump(mode="json")
    for key in (
        "signal_id",
        "claim",
        "severity",
        "evidence_date",
        "confidence",
        "validated",
        "data",
    ):
        assert got[key] == want[key], key
    for key in ("name", "type", "raw_ref"):
        assert got["source"][key] == want["source"][key], key
    assert got["source"]["name"] == FOOTPRINT_SOURCE
    # api/signals.json was generated before presence.json last changed, so its content_hash is
    # stale. The agent's hash must be the file as it is now (fixtures belong to role 6).
    presence = directory / "presence.json"
    assert got["source"]["content_hash"] == hashlib.sha256(presence.read_bytes()).hexdigest()


# --------------------------------------------------------------- the other two rules
async def test_website_address_differs_from_onrc(tmp_path: Path) -> None:
    site = {
        "url": "https://aurora.example",
        "address_on_site": "Bd. Unirii nr. 3, Sector 3, București",
    }
    overrides = {"web_search": _Footprint(site, [])}
    signal = by_rule(await run(ctx(AURORA, tmp_path, overrides=overrides)))[
        "PRE-ADDRESS-MISMATCH-01"
    ]
    assert signal.validated is False  # website text is unvalidated web data
    assert signal.source.type is SourceType.WEB
    assert signal.severity is Severity.LOW
    assert signal.data["website"] == "https://aurora.example"


async def test_public_contracts_are_a_positive_info_signal(tmp_path: Path) -> None:
    contracts = [{"authority": "Primaria X", "date": "2026-03-01", "value_ron": 250_000}]
    result = await run(ctx(ZEPHYRIA, tmp_path, overrides={"seap": _Seap(contracts)}))
    signals = by_rule(result)
    assert set(signals) == {"PRE-PUBLIC-CONTRACTS-01"}  # a SEAP contract is a footprint
    info = signals["PRE-PUBLIC-CONTRACTS-01"]
    assert info.severity is Severity.INFO
    assert info.data["seap_value_ron"] == 250_000
    assert "250,000 RON" in info.claim


# --------------------------------------------------- failures: never clean (hard rule 2)
@pytest.mark.parametrize("source", ["web_search", "seap", "kohesio"])
async def test_one_footprint_part_down_means_no_conclusion(tmp_path: Path, source: str) -> None:
    result = await run(ctx(ZEPHYRIA, tmp_path, overrides={source: _Down()}))
    assert "PRE-NO-FOOTPRINT-01" not in by_rule(result)  # never "nothing" when we couldn't look
    assert result.status is AgentStatus.PARTIAL
    assert result.notes is not None and "not concluded" in result.notes


async def test_all_footprint_sources_down_is_unavailable(tmp_path: Path) -> None:
    downs = {name: _Down() for name in ("web_search", "seap", "kohesio")}
    result = await run(ctx(ZEPHYRIA, tmp_path, overrides=downs))
    assert result.status is AgentStatus.UNAVAILABLE
    assert result.sources_checked == []  # turnover alone is not a presence check


async def test_no_turnover_means_no_conclusion(tmp_path: Path) -> None:
    result = await run(ctx(ZEPHYRIA, tmp_path, overrides={"anaf_bilant": _Down()}))
    assert result.signals == []
    assert "anaf_bilant" in result.sources_failed


async def test_live_mode_is_unavailable_until_real_sources_exist(tmp_path: Path) -> None:
    """Real companies: no SEAP / Kohesio / web data yet, so presence never fakes a check."""
    result = await run(ctx(DEDEMAN, tmp_path, fixture_mode=False))
    assert result.status is AgentStatus.UNAVAILABLE
    assert set(result.sources_failed) == {"web_search", "seap", "kohesio"}


async def test_threshold_comes_from_config(tmp_path: Path) -> None:
    high = load_config().model_copy(update={"min_turnover_ron": 50_000_000})
    result = await PresenceAgent(high).run(ctx(ZEPHYRIA, tmp_path))
    assert result.signals == []


async def test_signal_data_is_plain_json(tmp_path: Path) -> None:
    for signal in (await run(ctx(ZEPHYRIA, tmp_path))).signals:
        assert json.loads(json.dumps(signal.data)) == signal.data
