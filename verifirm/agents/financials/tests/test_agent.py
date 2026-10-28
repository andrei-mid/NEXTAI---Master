import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from verifirm.adapters.anaf_bilant import AnafBilantAdapter
from verifirm.adapters.base import AdapterDeps
from verifirm.agents.base import AgentContext
from verifirm.agents.financials.agent import FinancialsAgent
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter
from verifirm.schema.identity import IdentitySheet
from verifirm.schema.signals import AgentStatus, Severity

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures"
NOW = datetime(2026, 10, 28, 8, 0, tzinfo=UTC)


def _identity(cui: str, fixtures: Path = FIXTURES) -> IdentitySheet:
    folder = next((fixtures / "companies").glob(f"{cui}_*"))
    return IdentitySheet.model_validate(
        json.loads((folder / "api" / "company.json").read_text(encoding="utf-8"))["identity_sheet"]
    )


def _ctx(
    cui: str, tmp_path: Path, *, fixtures: Path = FIXTURES, disabled: frozenset[str] = frozenset()
) -> AgentContext:
    settings = Settings(fixture_mode=True, fixtures_dir=fixtures)
    deps = AdapterDeps(
        settings=settings,
        cache=MemoryCache(),
        object_store=FilesystemObjectStore(tmp_path / "o"),
        rate_limiter=MemoryRateLimiter(),
        clock=FixedClock(NOW),
    )
    return AgentContext(
        run_id="r1",
        cui=cui,
        identity=_identity(cui),
        settings=settings,
        clock=FixedClock(NOW),
        adapters={"anaf_bilant": AnafBilantAdapter(deps)},
        disabled_sources=disabled,
    )


@pytest.mark.parametrize(
    "cui,expected",
    [
        ("99000025", {"FIN-NET-ASSETS-01", "FIN-REVENUE-JUMP-01", "FIN-HEADCOUNT-01"}),
        ("99000033", {"FIN-REVENUE-DECLINE-01", "FIN-LOSS-TREND-01"}),
        ("99000017", set()),
    ],
)
async def test_demo_companies(tmp_path: Path, cui: str, expected: set[str]) -> None:
    result = await FinancialsAgent().run(_ctx(cui, tmp_path))
    assert result.status == AgentStatus.OK and result.sources_checked == ["anaf_bilant"]
    assert {s.rule_id for s in result.signals} == expected


async def test_matches_the_demo_fixture_signals(tmp_path: Path) -> None:
    """The API fixtures must show what this agent really produces."""
    for cui in ("99000017", "99000025", "99000033"):
        folder = next((FIXTURES / "companies").glob(f"{cui}_*"))
        fixture = {
            s["rule_id"]
            for s in json.loads((folder / "api" / "signals.json").read_text(encoding="utf-8"))
            if s["agent"] == "financials"
        }
        result = await FinancialsAgent().run(_ctx(cui, tmp_path))
        assert {s.rule_id for s in result.signals} == fixture, cui


async def test_zephyria_signal_content(tmp_path: Path) -> None:
    result = await FinancialsAgent().run(_ctx("99000025", tmp_path))
    by_rule = {s.rule_id: s for s in result.signals}
    net = by_rule["FIN-NET-ASSETS-01"]
    assert net.severity == Severity.HIGH and net.data["equity"] == -111_000
    assert (
        net.source.raw_ref == "fixture:companies/99000025_zephyria_logistic_nova/bilant_2025.json"
    )
    assert by_rule["FIN-REVENUE-JUMP-01"].data["growth_pct"] == 415.8
    assert by_rule["FIN-HEADCOUNT-01"].confidence == 0.8
    assert "18,600,000 RON" in by_rule["FIN-HEADCOUNT-01"].claim


async def test_rerun_gives_same_signal_ids(tmp_path: Path) -> None:
    a = await FinancialsAgent().run(_ctx("99000025", tmp_path))
    b = await FinancialsAgent().run(_ctx("99000025", tmp_path))
    assert [s.signal_id for s in a.signals] == [s.signal_id for s in b.signals]


async def test_source_switched_off_is_unavailable(tmp_path: Path) -> None:
    result = await FinancialsAgent().run(
        _ctx("99000025", tmp_path, disabled=frozenset({"anaf_bilant"}))
    )
    assert result.status == AgentStatus.UNAVAILABLE and result.sources_failed == ["anaf_bilant"]
    assert result.signals == []


async def test_missing_years_make_it_partial(tmp_path: Path) -> None:
    fx = tmp_path / "fx"
    src = next((FIXTURES / "companies").glob("99000025_*"))
    dst = fx / "companies" / src.name
    shutil.copytree(src / "api", dst / "api")
    for year in (2024, 2025):
        shutil.copy(src / f"bilant_{year}.json", dst / f"bilant_{year}.json")
    result = await FinancialsAgent().run(_ctx("99000025", tmp_path, fixtures=fx))
    assert result.status == AgentStatus.PARTIAL and "2021" in (result.notes or "")
    assert "FIN-NET-ASSETS-01" in {s.rule_id for s in result.signals}


async def test_nothing_filed_for_expected_year(tmp_path: Path) -> None:
    fx = tmp_path / "fx"
    src = next((FIXTURES / "companies").glob("99000017_*"))
    dst = fx / "companies" / src.name
    shutil.copytree(src, dst)
    (dst / "bilant_2025.json").write_text(
        json.dumps({"an": 2025, "cui": 99000017, "deni": "", "i": [], "fictional": True})
    )
    result = await FinancialsAgent().run(_ctx("99000017", tmp_path, fixtures=fx))
    assert result.status == AgentStatus.OK
    assert [s.rule_id for s in result.signals] == ["FIN-NO-FILING-01"]
