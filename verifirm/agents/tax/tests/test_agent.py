"""Tax agent with the REAL adapters in FIXTURE_MODE (no network), plus every failure path."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from verifirm.adapters.anaf_bilant import AnafBilantAdapter
from verifirm.adapters.anaf_efactura_registry import AnafEfacturaRegistryAdapter
from verifirm.adapters.anaf_v9 import AnafV9Adapter
from verifirm.adapters.base import AdapterDeps, BaseAdapter, Sourced, SourceUnavailable
from verifirm.adapters.mocks.d300 import MockD300Adapter
from verifirm.adapters.mocks.efactura import MockEfacturaAdapter
from verifirm.adapters.mocks.restante import MockRestanteAdapter
from verifirm.agents.base import AgentContext
from verifirm.agents.tax.agent import TaxAgent
from verifirm.agents.tax.rules import load_config
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter
from verifirm.schema.financials import FinancialYear, SubmittedFinancials
from verifirm.schema.identity import IdentitySheet
from verifirm.schema.signals import AgentResult, AgentStatus, Severity, SourceType

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures"
NOW = datetime(2026, 10, 28, 8, 0, tzinfo=UTC)

AURORA, ZEPHYRIA, BRUNALDO = "99000017", "99000025", "99000033"
ORVANTO, DEDEMAN = "99000058", "2816464"

ADAPTERS: dict[str, type[BaseAdapter]] = {
    "anaf_bilant": AnafBilantAdapter,
    "anaf_v9": AnafV9Adapter,
    "mock_restante": MockRestanteAdapter,
    "mock_d300": MockD300Adapter,
    "mock_efactura": MockEfacturaAdapter,
    "anaf_efactura_registry": AnafEfacturaRegistryAdapter,
}


def company_dir(cui: str) -> Path | None:
    matches = sorted((FIXTURES / "companies").glob(f"{cui}_*"))
    return matches[0] if matches else None


def submitted_for(cui: str) -> SubmittedFinancials | None:
    directory = company_dir(cui)
    path = directory / "submitted" / "financials.json" if directory else None
    if path is None or not path.exists():
        return None
    return SubmittedFinancials.model_validate_json(path.read_text(encoding="utf-8"))


def ctx(
    cui: str,
    tmp_path: Path,
    *,
    submitted: SubmittedFinancials | str | None = "fixture",
    overrides: Mapping[str, object] | None = None,
    disabled: frozenset[str] = frozenset(),
) -> AgentContext:
    deps = AdapterDeps(
        settings=Settings(fixture_mode=True, fixtures_dir=FIXTURES),
        cache=MemoryCache(),
        object_store=FilesystemObjectStore(tmp_path / "objects"),
        rate_limiter=MemoryRateLimiter(),
        clock=FixedClock(NOW),
    )
    adapters: dict[str, object] = {name: cls(deps) for name, cls in ADAPTERS.items()}
    adapters.update(overrides or {})
    return AgentContext(
        run_id="test-run",
        cui=cui,
        identity=IdentitySheet(cui=cui, current_name="X", fictional=cui.startswith("990")),
        settings=deps.settings,
        clock=FixedClock(NOW),
        adapters=cast(Mapping[str, BaseAdapter], adapters),
        submitted=submitted_for(cui) if submitted == "fixture" else cast(Any, submitted),
        disabled_sources=disabled,
    )


async def run(context: AgentContext) -> AgentResult:
    return await TaxAgent().run(context)


def by_rule(result: AgentResult) -> dict[str, Any]:
    return {s.rule_id: s for s in result.signals}


# ------------------------------------------------------------------- demo companies
@pytest.mark.parametrize(
    ("cui", "expected", "status"),
    [
        (AURORA, set(), AgentStatus.OK),
        (ZEPHYRIA, {"TAX-DECLARED-GAP-01"}, AgentStatus.OK),
        (
            BRUNALDO,
            {
                "TAX-ARREARS-01",
                "TAX-VAT-CANCELLED-01",
                "TAX-EFACTURA-GAP-01",
                "TAX-DECLARED-GAP-01",
            },
            AgentStatus.OK,
        ),
        # No arrears / D300 / e-Factura mock data for the affiliates: partial, never clean.
        ("99000041", set(), AgentStatus.PARTIAL),
        (ORVANTO, set(), AgentStatus.PARTIAL),  # e-Factura register rule is off by default
        (DEDEMAN, set(), AgentStatus.UNAVAILABLE),
    ],
)
async def test_fixture_companies(
    tmp_path: Path, cui: str, expected: set[str], status: AgentStatus
) -> None:
    result = await run(ctx(cui, tmp_path))
    assert set(by_rule(result)) == expected
    assert result.status is status


@pytest.mark.parametrize("cui", [ZEPHYRIA, BRUNALDO])
async def test_matches_api_fixture(tmp_path: Path, cui: str) -> None:
    """The signals the frontend / demo expects (fixtures/.../api/signals.json)."""
    directory = company_dir(cui)
    assert directory is not None
    api = json.loads((directory / "api" / "signals.json").read_text(encoding="utf-8"))
    expected = {s["rule_id"]: s for s in api if s["agent"] == "tax"}
    got = by_rule(await run(ctx(cui, tmp_path)))
    assert set(got) == set(expected)
    for rule_id, want in expected.items():
        signal = got[rule_id].model_dump(mode="json")
        for key in ("signal_id", "claim", "severity", "evidence_date", "confidence", "data"):
            assert signal[key] == want[key], (rule_id, key)
        assert signal["source"]["type"] == want["source"]["type"], rule_id
        assert signal["source"]["name"] == want["source"]["name"], rule_id


async def test_mock_signals_carry_the_mock_badge(tmp_path: Path) -> None:
    signals = by_rule(await run(ctx(BRUNALDO, tmp_path)))
    assert signals["TAX-ARREARS-01"].source.type is SourceType.MOCK
    assert signals["TAX-EFACTURA-GAP-01"].source.type is SourceType.MOCK
    assert signals["TAX-VAT-CANCELLED-01"].source.type is SourceType.OFFICIAL
    assert signals["TAX-DECLARED-GAP-01"].source.type is SourceType.OFFICIAL


async def test_aurora_notes_explain_the_clean_result(tmp_path: Path) -> None:
    result = await run(ctx(AURORA, tmp_path))
    assert result.notes is not None
    assert "not on the Q2 2026 arrears list" in result.notes
    assert "certificat de atestare fiscală" in result.notes


# --------------------------------------------------------------- documents vs ANAF
async def test_portfolio_recheck_has_no_documents(tmp_path: Path) -> None:
    result = await run(ctx(ZEPHYRIA, tmp_path, submitted=None))
    assert "TAX-DECLARED-GAP-01" not in by_rule(result)
    assert result.status is AgentStatus.OK  # not a failure: nothing was submitted
    assert result.notes is not None and "none submitted" in result.notes


async def test_documents_of_another_company_are_rejected(tmp_path: Path) -> None:
    other = submitted_for(ZEPHYRIA)
    result = await run(ctx(BRUNALDO, tmp_path, submitted=other))
    assert "documents" in result.sources_failed
    assert "TAX-DECLARED-GAP-01" not in by_rule(result)


async def test_year_not_filed_at_anaf_is_noted(tmp_path: Path) -> None:
    sub = submitted_for(ZEPHYRIA)
    assert sub is not None
    later = sub.model_copy(
        update={"years": [FinancialYear(year=2026, turnover=1, source=sub.years[0].source)]}
    )
    result = await run(ctx(ZEPHYRIA, tmp_path, submitted=later))
    assert "TAX-DECLARED-GAP-01" not in by_rule(result)
    assert result.notes is not None and "2026" in result.notes


# --------------------------------------------------- failures: never clean (hard rule 2)
async def test_switched_off_source_keeps_the_others(tmp_path: Path) -> None:
    result = await run(ctx(BRUNALDO, tmp_path, disabled=frozenset({"mock_restante"})))
    assert result.status is AgentStatus.PARTIAL
    assert result.sources_failed == ["mock_restante"]
    assert set(by_rule(result)) == {
        "TAX-VAT-CANCELLED-01",
        "TAX-EFACTURA-GAP-01",
        "TAX-DECLARED-GAP-01",
    }


class _Down:
    """Any adapter method raises SourceUnavailable."""

    def __getattr__(self, name: str) -> Any:
        async def call(*args: Any, **kwargs: Any) -> Any:
            raise SourceUnavailable(name, "down")

        return call


class _NotImplemented:
    def __getattr__(self, name: str) -> Any:
        async def call(*args: Any, **kwargs: Any) -> Any:
            raise NotImplementedError

        return call


# anaf_efactura_registry is not read while TAX-EFACTURA-REG-01 is off (see the tests below).
@pytest.mark.parametrize("source", sorted(set(ADAPTERS) - {"anaf_efactura_registry"}))
async def test_any_source_down_is_partial(tmp_path: Path, source: str) -> None:
    result = await run(ctx(BRUNALDO, tmp_path, overrides={source: _Down()}))
    assert result.status is AgentStatus.PARTIAL
    assert source in result.sources_failed


async def test_not_implemented_is_a_failed_source(tmp_path: Path) -> None:
    result = await run(ctx(BRUNALDO, tmp_path, overrides={"mock_d300": _NotImplemented()}))
    assert "mock_d300" in result.sources_failed
    assert "TAX-EFACTURA-GAP-01" not in by_rule(result)


async def test_everything_down_is_unavailable(tmp_path: Path) -> None:
    downs = {name: _Down() for name in ADAPTERS}
    result = await run(ctx(BRUNALDO, tmp_path, overrides=downs, submitted=None))
    assert result.status is AgentStatus.UNAVAILABLE
    assert result.signals == []


class _Restante:
    def __init__(self, data: Any, stale: bool = False) -> None:
        self.data, self.stale = data, stale

    async def arrears(self, cui: str) -> Sourced[Any]:
        real = await MockRestanteAdapter(_deps_for_source()).arrears(BRUNALDO)
        return Sourced(data=self.data, source=real.source, stale=self.stale)


def _deps_for_source() -> AdapterDeps:
    return AdapterDeps(
        settings=Settings(fixture_mode=True, fixtures_dir=FIXTURES),
        cache=MemoryCache(),
        object_store=FilesystemObjectStore(Path("/nonexistent")),
        rate_limiter=MemoryRateLimiter(),
        clock=FixedClock(NOW),
    )


async def test_malformed_arrears_entry_is_never_clean(tmp_path: Path) -> None:
    bad = {"list_period": "2026-Q2", "obligations": [{"type": "amenzi", "amount_ron": 5}]}
    result = await run(ctx(AURORA, tmp_path, overrides={"mock_restante": _Restante(bad)}))
    assert result.sources_failed == ["mock_restante"]
    assert result.status is AgentStatus.PARTIAL


async def test_stale_data_lowers_confidence(tmp_path: Path) -> None:
    entry = {"list_period": "2026-Q2", "obligations": [{"type": "principal", "amount_ron": 9}]}
    fake = _Restante(entry, stale=True)
    signal = by_rule(await run(ctx(AURORA, tmp_path, overrides={"mock_restante": fake})))
    assert signal["TAX-ARREARS-01"].confidence == 0.8


# --------------------------------------------------------------------------- config
async def test_thresholds_come_from_config(tmp_path: Path) -> None:
    lenient = load_config().model_copy(update={"efactura_gap_tolerance_pct": 25})
    result = await TaxAgent(lenient).run(ctx(BRUNALDO, tmp_path))
    assert "TAX-EFACTURA-GAP-01" not in by_rule(result)


async def test_severity_of_d300_above_efactura_is_low(tmp_path: Path) -> None:
    class _HighD300:
        async def returns(self, cui: str) -> Sourced[list[dict[str, Any]]]:
            real = await MockD300Adapter(_deps_for_source()).returns(BRUNALDO)
            high = [r | {"taxable_base_ron": 5_000_000} for r in real.data]
            return Sourced(data=high, source=real.source)

    signal = by_rule(await run(ctx(BRUNALDO, tmp_path, overrides={"mock_d300": _HighD300()})))
    gap = signal["TAX-EFACTURA-GAP-01"]
    assert gap.severity is Severity.LOW
    assert "above" in gap.claim


async def test_signal_data_is_plain_json(tmp_path: Path) -> None:
    """Signal.data goes to Postgres JSONB and the API: no date objects inside."""
    for signal in (await run(ctx(BRUNALDO, tmp_path))).signals:
        assert json.loads(json.dumps(signal.data)) == signal.data


class _V9:
    def __init__(self, record: dict[str, Any] | None) -> None:
        self.record = record

    async def lookup(self, cui: str, on_date: date) -> Sourced[dict[str, Any] | None]:
        real = await AnafV9Adapter(_deps_for_source()).lookup(AURORA, on_date)
        return Sourced(data=self.record, source=real.source)


@pytest.mark.parametrize(
    "record",
    [
        {"inregistrare_scop_Tva": {"scpTVA": True}},  # VAT history missing
        {"inregistrare_scop_Tva": {"perioade_TVA": "none"}},
        {"date_generale": {}},
        None,  # notFound
    ],
)
async def test_unreadable_vat_history_is_never_clean(
    tmp_path: Path, record: dict[str, Any] | None
) -> None:
    result = await run(ctx(AURORA, tmp_path, overrides={"anaf_v9": _V9(record)}))
    assert "anaf_v9" in result.sources_failed
    assert result.status is AgentStatus.PARTIAL


async def test_efactura_register_rule_is_off_by_default(tmp_path: Path) -> None:
    result = await run(ctx(ORVANTO, tmp_path))
    assert "TAX-EFACTURA-REG-01" not in by_rule(result)
    assert "anaf_efactura_registry" not in result.sources_failed  # skipped on purpose, not failed


async def test_efactura_register_rule_can_be_switched_on(tmp_path: Path) -> None:
    on = load_config().model_copy(update={"efactura_registration_check": True})
    result = await TaxAgent(on).run(ctx(ORVANTO, tmp_path))
    assert by_rule(result)["TAX-EFACTURA-REG-01"].severity is Severity.LOW
