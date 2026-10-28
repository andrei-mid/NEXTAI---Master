from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from verifirm.adapters.anaf_bilant import AnafBilantAdapter, BilantHistory
from verifirm.adapters.anaf_v9 import AnafV9Adapter
from verifirm.adapters.base import AdapterDeps, BaseAdapter, Sourced
from verifirm.adapters.onrc_bulk import OnrcBulkAdapter
from verifirm.consolidation.analyst.agent import last_expected_year, load_config
from verifirm.consolidation.analyst.dossier import (
    DossierInputs,
    addresses_match,
    aliases,
    build_dossier,
    collect_inputs,
    compact_name,
    cross_checks,
    indicators,
    redact,
    snapshot,
    snapshot_changes,
)
from verifirm.consolidation.identity_sheet import build_identity_sheet
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter
from verifirm.schema.analyst import DossierYear
from verifirm.schema.identity import Person, PersonRole
from verifirm.schema.memo import ConsolidatedReport
from verifirm.schema.scoring import Band, Coverage, Score
from verifirm.schema.signals import (
    Component,
    EntityMatch,
    Severity,
    Signal,
    SourceRef,
    SourceType,
)

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures"
CLOCK = FixedClock(datetime(2026, 10, 28, tzinfo=UTC))
ZEPHYRIA = "99000025"
SRC = SourceRef(name="ONRC", type=SourceType.OFFICIAL, retrieved_at=CLOCK.now())


def adapters(tmp_path: Path) -> dict[str, BaseAdapter]:
    deps = AdapterDeps(
        settings=Settings(fixture_mode=True, fixtures_dir=FIXTURES),
        cache=MemoryCache(),
        object_store=FilesystemObjectStore(tmp_path / "objects"),
        rate_limiter=MemoryRateLimiter(),
        clock=CLOCK,
    )
    return {
        "anaf_v9": AnafV9Adapter(deps),
        "onrc_bulk": OnrcBulkAdapter(deps),
        "anaf_bilant": AnafBilantAdapter(deps),
    }


def score(cui: str) -> Score:
    return Score(
        cui=cui,
        run_id="run_1",
        trust_score=55.0,
        band=Band.YELLOW,
        components=[],
        coverage=Coverage(weight_pct=100, available=8, total=8),
        config_version="t",
        computed_at=CLOCK.now(),
    )


async def zephyria(tmp_path: Path, signals: list[Signal] | None = None) -> Any:
    ad = adapters(tmp_path)
    cfg = load_config()
    inputs = await collect_inputs(
        ZEPHYRIA,
        ad,
        CLOCK.today(),
        last_year=last_expected_year(CLOCK.today(), cfg),
        years=cfg.years_of_history,
    )
    report = ConsolidatedReport(
        cui=ZEPHYRIA,
        run_id="run_1",
        identity=await build_identity_sheet(ZEPHYRIA, ad, CLOCK),
        results=[],
        signals=signals or [],
        score=score(ZEPHYRIA),
        generated_at=CLOCK.now(),
    )
    return build_dossier(report, inputs)


# ---------------------------------------------------------------------- the real fixture
async def test_zephyria_dossier_from_the_fixtures(tmp_path: Path) -> None:
    d = await zephyria(tmp_path)
    assert d.cross_checks["name"].match is True and d.cross_checks["address"].match is True
    assert d.cross_checks["status"].match is None  # different vocabularies, never a mismatch
    assert list(d.financials) == ["2021", "2022", "2023", "2024", "2025"]
    assert d.financials["2025"].equity == -111000
    assert d.indicators["2025"].turnover_per_employee == 9300000
    assert d.indicators["2023"].turnover_growth_pct == 363.4
    assert {s: v.status for s, v in d.sources.items()} == {
        "anaf_v9": "ok",
        "onrc_bulk": "ok",
        "anaf_bilant": "ok",
    }
    assert d.official_score.band == Band.YELLOW and d.official_score.coverage == "8/8 sources"


async def test_no_person_name_reaches_the_dossier(tmp_path: Path) -> None:
    leak = Signal(
        signal_id="ID-ADMIN-CHANGE-01:x",
        cui=ZEPHYRIA,
        agent="identity",
        component=Component.IDENTITY,
        rule_id="ID-ADMIN-CHANGE-01",
        claim="Ionel Fictivescu replaced MARCELA INVENTATU on 2025-11-02.",
        source=SRC,
        evidence_date=date(2025, 11, 2),
        confidence=0.9,
        severity=Severity.MEDIUM,
        entity_match=EntityMatch(method="cui_exact", score=1),
        data={"new": "IONEL FICTIVESCU", "old": ["MARCELA INVENTATU"]},
    )
    d = await zephyria(tmp_path, [leak])
    text = d.model_dump_json().lower()
    assert "fictivescu" not in text and "inventatu" not in text
    assert [p.alias for p in d.administrators] == ["Administrator A", "Administrator B"]
    assert d.signals["ID-ADMIN-CHANGE-01:x"].claim == (
        "Administrator B replaced Administrator A on 2025-11-02."
    )


async def test_failing_sources_are_unavailable_never_empty(tmp_path: Path) -> None:
    ad = adapters(tmp_path)
    del ad["onrc_bulk"]
    inputs = await collect_inputs("99009999", ad, CLOCK.today(), last_year=2025, years=5)
    assert inputs.failures["onrc_bulk"] == "adapter not configured"
    assert "anaf_v9" in inputs.failures and "anaf_bilant" not in inputs.failures


# ---------------------------------------------------------------------- pure helpers
@pytest.mark.parametrize(
    ("anaf", "onrc", "match"),
    [
        (
            "JUD. BACĂU, MUN. BACĂU, STR. DIMITRIE COJOCARU NR. 2",
            "Str. Dimitrie Cojocaru 2, Bacău",
            True,
        ),
        (
            "Str. Exemplului nr. 1, Sector 9, București",
            "Str. Umbrei nr. 5, Sector 9, București",
            False,
        ),
        (None, "Str. Umbrei 5", None),
    ],
)
def test_address_match_ignores_order_and_abbreviations(
    anaf: str | None, onrc: str | None, match: bool | None
) -> None:
    assert addresses_match(anaf, onrc) is match


def test_name_ignores_legal_form_spelling() -> None:
    assert compact_name("Dedeman S.R.L.") == compact_name("DEDEMAN SRL") == "dedeman"


def test_cross_checks_mismatch_and_missing_side() -> None:
    v9 = {
        "date_generale": {"denumire": "ALFA SRL", "cod_CAEN": "4941", "nrRegCom": ""},
        "stare_inactiv": {"dataRadiere": "2025-01-10"},
    }
    onrc = {"denumire": "BETA SRL", "stare": "functiune", "cod_inmatriculare": "J99/1/2020"}
    checks = cross_checks(v9, onrc)
    assert checks["name"].match is False
    assert checks["caen_code"].match is None  # ONRC bulk has no main CAEN
    assert checks["trade_register_no"].anaf is None and checks["trade_register_no"].match is None
    assert checks["deregistered"].match is False  # a real disagreement on the same fact


def test_snapshot_changes_between_quarters() -> None:
    def record(address: str, inactive: bool) -> dict[str, Any]:
        return {
            "date_generale": {"denumire": "ALFA SRL", "adresa": address, "cod_CAEN": "4941"},
            "inregistrare_scop_Tva": {"scpTVA": True},
            "stare_inactiv": {"statusInactivi": inactive},
        }

    snaps = {
        "2026-03-31": snapshot(record("Str. A 1", False)),
        "2025-12-31": snapshot(record("Str. A 1", False)),
        "2026-06-30": snapshot(record("Str. B 2", True)),
        "2026-09-30": snapshot(None),
    }
    changes = [(c.field, c.date_from.isoformat(), c.old, c.new) for c in snapshot_changes(snaps)]
    assert ("address", "2026-03-31", "Str. A 1", "Str. B 2") in changes
    assert ("inactive", "2026-03-31", "False", "True") in changes
    assert ("found", "2026-06-30", "True", "False") in changes
    assert not any(c[1] == "2025-12-31" for c in changes)  # nothing changed in Q1


def test_indicators_skip_unfiled_years_and_zero_denominators() -> None:
    ind = indicators(
        {
            "2023": DossierYear(
                filed=True, turnover=1000, net_profit=-50, employees=0, equity=10, share_capital=200
            ),
            "2024": DossierYear(filed=False),
            "2025": DossierYear(filed=True, turnover=1500, total_debts=300),
        }
    )
    assert set(ind) == {"2023", "2025"}
    assert ind["2023"].turnover_per_employee is None  # 0 employees
    assert ind["2023"].net_margin_pct == -5.0 and ind["2023"].equity_to_share_capital == 0.05
    assert ind["2025"].turnover_growth_pct == 50.0 and ind["2025"].debts_to_turnover == 0.2


def test_aliases_people_not_companies() -> None:
    admins = [
        Person(
            name="B Two", role=PersonRole.ADMINISTRATOR, valid_from=date(2024, 1, 1), source=SRC
        ),
        Person(
            name="A One", role=PersonRole.ADMINISTRATOR, valid_from=date(2020, 1, 1), source=SRC
        ),
    ]
    holders = [
        Person(name="HOLDING SRL", role=PersonRole.SHAREHOLDER, is_company=True, source=SRC),
        Person(name="C Three", role=PersonRole.SHAREHOLDER, source=SRC),
    ]
    names = aliases(admins, holders)
    assert names == {
        "A One": "Administrator A",
        "B Two": "Administrator B",
        "C Three": "Shareholder A",
    }
    assert redact({"x": ["a one and HOLDING SRL"]}, names) == {
        "x": ["Administrator A and HOLDING SRL"]
    }


def test_bilant_partial_and_unreadable_years() -> None:
    from verifirm.consolidation.analyst.dossier import financial_years, source_states

    history = BilantHistory(years={2025: Sourced(None, SRC)}, failed=[2024])
    years = financial_years(history)
    assert years == {"2024": DossierYear(filed=None), "2025": DossierYear(filed=False)}
    states = source_states(DossierInputs(bilant=history))
    assert states["anaf_bilant"].status == "partial"
    assert states["anaf_v9"].status == "unavailable"
