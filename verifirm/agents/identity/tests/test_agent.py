"""Identity agent on the fixture companies, plus every failure path.

anaf_v9 / onrc_bulk / identity_sheet are not implemented yet, so the stand-ins below read the
same fixture files the real adapters serve in FIXTURE_MODE. No network.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from verifirm.adapters.base import BaseAdapter, Sourced, SourceUnavailable
from verifirm.agents.base import AgentContext
from verifirm.agents.identity.agent import IdentityAgent
from verifirm.agents.identity.rules import load_config
from verifirm.core.config import Settings
from verifirm.core.impl_local.clock import FixedClock
from verifirm.schema.identity import (
    Address,
    CompanyStatus,
    IdentitySheet,
    Person,
    PersonRole,
)
from verifirm.schema.signals import AgentResult, AgentStatus, Severity, SourceRef, SourceType

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures"
NOW = datetime(2026, 10, 28, 8, 0, tzinfo=UTC)

ZEPHYRIA = "99000025"
AURORA = "99000017"
KESTREL = "99000041"
VANTIRO = "99000074"
DEDEMAN = "2816464"


def company_dir(cui: str) -> Path | None:
    matches = sorted((FIXTURES / "companies").glob(f"{cui}_*"))
    return matches[0] if matches else None


def load(cui: str, filename: str) -> Any:
    directory = company_dir(cui)
    if directory is None or not (directory / filename).exists():
        raise SourceUnavailable(filename, f"no fixture for {cui}")
    return json.loads((directory / filename).read_text(encoding="utf-8"))


def ref(name: str, raw: str) -> SourceRef:
    return SourceRef(name=name, type=SourceType.OFFICIAL, retrieved_at=NOW, raw_ref=raw)


V9_REF = ref("ANAF VAT registry v9", "fixture:anaf_v9.json")
ONRC_REF = ref("ONRC open data (data.gov.ro)", "fixture:onrc.json")


# ------------------------------------------------------------------------- stand-ins
class FakeV9:
    """anaf_v9 stand-in. `record` overrides the fixture; `error` makes every call fail."""

    def __init__(
        self,
        record: dict[str, Any] | str | None = "fixture",
        error: Exception | None = None,
        stale: bool = False,
    ) -> None:
        self.record, self.error, self.stale = record, error, stale
        self.calls = 0

    async def lookup(self, cui: str, on_date: date) -> Sourced[dict[str, Any] | None]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        if self.record == "fixture":
            found = load(cui, "anaf_v9.json")["found"]
            return Sourced(found[0] if found else None, V9_REF, stale=self.stale)
        return Sourced(cast(dict[str, Any] | None, self.record), V9_REF, stale=self.stale)


class FakeOnrc:
    """onrc_bulk stand-in: onrc.json per company + OD_FIRME sample for the address count."""

    def __init__(self, record: dict[str, Any] | None = None, error: Exception | None = None):
        self.record, self.error = record, error

    async def company(self, cui: str) -> Sourced[dict[str, Any] | None]:
        if self.error is not None:
            raise self.error
        return Sourced(self.record or load(cui, "onrc.json"), ONRC_REF)

    async def companies_at_address(self, normalized_address: str) -> Sourced[list[str]]:
        path = FIXTURES / "sources" / "onrc" / "OD_FIRME_sample.csv"
        with path.open(encoding="utf-8", newline="") as f:
            rows = csv.DictReader(f, delimiter="^")
            cuis = [r["CUI"] for r in rows if r["ADRESA_COMPLETA"] == normalized_address]
        return Sourced(cuis, ONRC_REF)


def sheet(cui: str, **over: Any) -> IdentitySheet:
    """What consolidation/identity_sheet builds from onrc.json (role 5's code is a stub)."""
    try:
        onrc = load(cui, "onrc.json")
    except SourceUnavailable:
        return IdentitySheet(cui=cui, current_name="UNKNOWN", **over)
    office = Address(raw=onrc["adresa"], county=onrc["judet"])
    fields: dict[str, Any] = {
        "cui": cui,
        "fictional": True,
        "trade_register_no": onrc["cod_inmatriculare"],
        "current_name": onrc["denumire"],
        "legal_form": onrc["forma_juridica"],
        "status": CompanyStatus.UNKNOWN,
        "registered_office": office,
        "office_history": [
            Address(
                raw=o["adresa"],
                valid_from=o["de_la"],
                valid_to=o["pana_la"],
            )
            for o in onrc["istoric_sedii"]
        ],
        "caen_code": onrc["caen_principal"]["cod"],
        "caen_revision": onrc["caen_principal"]["revizie"],
        "authorized_caen_codes": [c["cod"] for c in onrc["caen_autorizate"]],
        "administrators": [
            Person(
                name=r["nume"],
                role=PersonRole.ADMINISTRATOR,
                valid_from=r["de_la"],
                valid_to=r["pana_la"],
                source=ONRC_REF,
            )
            for r in onrc["reprezentanti"]
        ],
    }
    return IdentitySheet(**(fields | over))


def ctx(
    cui: str,
    v9: FakeV9 | None = None,
    onrc: FakeOnrc | None = None,
    identity: IdentitySheet | None = None,
    adapters: Mapping[str, object] | None = None,
    disabled: frozenset[str] = frozenset(),
) -> AgentContext:
    if adapters is None:
        adapters = {"anaf_v9": v9 or FakeV9(), "onrc_bulk": onrc or FakeOnrc()}
    return AgentContext(
        run_id="test-run",
        cui=cui,
        identity=identity or sheet(cui),
        settings=Settings(fixture_mode=True),
        clock=FixedClock(NOW),
        adapters=cast(Mapping[str, BaseAdapter], adapters),
        disabled_sources=disabled,
    )


async def run(context: AgentContext) -> AgentResult:
    return await IdentityAgent().run(context)


def by_rule(result: AgentResult) -> dict[str, Any]:
    return {s.rule_id: s for s in result.signals}


# ------------------------------------------------------------------- demo companies
@pytest.mark.parametrize(
    ("cui", "expected"),
    [
        (AURORA, set()),
        (ZEPHYRIA, {"ID-ADMIN-CHANGE-01", "ID-SHARED-OFFICE-01"}),
        ("99000033", set()),
        (KESTREL, {"ID-STATUS-01"}),
        ("99000058", {"ID-STATUS-01"}),
        ("99000066", {"ID-STATUS-01"}),
        (VANTIRO, {"ID-INACTIVE-01"}),
        ("99000082", set()),
        ("99000090", {"ID-INACTIVE-01"}),
    ],
)
async def test_fixture_companies(cui: str, expected: set[str]) -> None:
    result = await run(ctx(cui))
    assert result.status is AgentStatus.OK
    assert result.sources_checked == ["anaf_v9", "onrc_bulk"]
    assert result.sources_failed == []
    assert set(by_rule(result)) == expected


async def test_zephyria_matches_api_fixture() -> None:
    """The signals the frontend/demo expects (fixtures/.../api/signals.json)."""
    expected = {
        s["rule_id"]: s for s in load(ZEPHYRIA, "api/signals.json") if s["agent"] == "identity"
    }
    got = by_rule(await run(ctx(ZEPHYRIA)))
    assert set(got) == set(expected)
    for rule_id, want in expected.items():
        signal = got[rule_id].model_dump(mode="json")
        for key in ("signal_id", "claim", "severity", "evidence_date", "confidence", "data"):
            assert signal[key] == want[key], (rule_id, key)
        assert signal["entity_match"] == want["entity_match"]


async def test_kestrel_bankruptcy_is_critical_and_not_a_conflict() -> None:
    status = by_rule(await run(ctx(KESTREL)))["ID-STATUS-01"]
    assert status.severity is Severity.CRITICAL
    assert status.confidence == 1.0
    assert status.data["status"] == "bankruptcy"
    assert status.data["sources_agree"] is True
    assert status.source == ONRC_REF


async def test_inactive_is_an_auto_stop_candidate() -> None:
    inactive = by_rule(await run(ctx(VANTIRO)))["ID-INACTIVE-01"]
    assert inactive.auto_stop_candidate is True
    assert inactive.severity is Severity.CRITICAL
    assert inactive.evidence_date == date(2024, 6, 1)
    assert inactive.source == V9_REF


async def test_one_anaf_call_per_run() -> None:
    v9 = FakeV9()
    await run(ctx(ZEPHYRIA, v9=v9))
    assert v9.calls == 1


async def test_signal_ids_are_deterministic() -> None:
    first = [s.signal_id for s in (await run(ctx(ZEPHYRIA))).signals]
    second = [s.signal_id for s in (await run(ctx(ZEPHYRIA))).signals]
    assert first == second and len(set(first)) == len(first)


# ------------------------------------------------------------ cross-source conflicts
async def test_anaf_deregistered_but_onrc_active_takes_worse_value() -> None:
    record = load(AURORA, "anaf_v9.json")["found"][0]
    record["stare_inactiv"]["dataRadiere"] = "2026-09-01"
    status = by_rule(await run(ctx(AURORA, v9=FakeV9(record))))["ID-STATUS-01"]
    assert status.data["status"] == "deregistered"
    assert status.data["sources_agree"] is False
    assert status.severity is Severity.CRITICAL
    assert status.confidence == 0.6
    assert status.source == V9_REF  # the source that says "deregistered"


async def test_source_mismatch_on_name() -> None:
    record = load(AURORA, "anaf_v9.json")["found"][0]
    record["date_generale"]["denumire"] = "ALTA FIRMA SRL"
    mismatch = by_rule(await run(ctx(AURORA, v9=FakeV9(record))))["ID-SOURCE-MISMATCH-01"]
    assert set(mismatch.data["mismatches"]) == {"name"}
    assert mismatch.severity is Severity.HIGH


# ------------------------------------------------------------ rules without fixtures
async def test_office_change_from_sheet_history() -> None:
    history = [
        Address(raw="Str. Veche nr. 1", valid_from=date(2019, 1, 1), valid_to=date(2026, 2, 1)),
        Address(raw="Str. Noua nr. 2", valid_from=date(2026, 2, 1)),
    ]
    identity = sheet(AURORA, office_history=history)
    moved = by_rule(await run(ctx(AURORA, identity=identity)))["ID-OFFICE-CHANGE-01"]
    assert moved.data["previous"] == "Str. Veche nr. 1"
    assert moved.data["changed_on"] == "2026-02-01"
    assert moved.severity is Severity.LOW


async def test_caen_not_authorized() -> None:
    identity = sheet(AURORA, caen_code="4120", authorized_caen_codes=["6201"])
    caen = by_rule(await run(ctx(AURORA, identity=identity)))["ID-CAEN-UNAUTH-01"]
    assert caen.data["main_caen"] == "4120"


async def test_natural_person_from_anaf_wording() -> None:
    record = load(AURORA, "anaf_v9.json")["found"][0]
    record["date_generale"]["forma_juridica"] = "PERSOANĂ FIZICĂ AUTORIZATĂ"
    person = by_rule(await run(ctx(AURORA, v9=FakeV9(record))))["ID-NATURAL-PERSON-01"]
    assert person.data["legal_form"] == "PFA"
    assert person.severity is Severity.INFO


async def test_reactivated_recently() -> None:
    record = load(AURORA, "anaf_v9.json")["found"][0]
    record["stare_inactiv"] |= {"dataInactivare": "2025-02-01", "dataReactivare": "2026-04-15"}
    signal = by_rule(await run(ctx(AURORA, v9=FakeV9(record))))["ID-REACTIVATED-01"]
    assert signal.evidence_date == date(2026, 4, 15)


# --------------------------------------------------- failures: never clean (hard rule 2)
async def test_anaf_down_is_partial_and_onrc_still_runs() -> None:
    v9 = FakeV9(error=SourceUnavailable("anaf_v9", "timeout"))
    result = await run(ctx(ZEPHYRIA, v9=v9))
    assert result.status is AgentStatus.PARTIAL
    assert result.sources_failed == ["anaf_v9"]
    assert result.sources_checked == ["onrc_bulk"]
    assert set(by_rule(result)) == {"ID-ADMIN-CHANGE-01", "ID-SHARED-OFFICE-01"}
    assert result.notes is not None and "timeout" in result.notes


async def test_anaf_down_status_is_not_a_conflict() -> None:
    v9 = FakeV9(error=SourceUnavailable("anaf_v9", "timeout"))
    status = by_rule(await run(ctx(KESTREL, v9=v9)))["ID-STATUS-01"]
    assert status.data["sources_agree"] is None
    assert status.confidence == 1.0


async def test_onrc_down_is_partial() -> None:
    onrc = FakeOnrc(error=SourceUnavailable("onrc_bulk", "tables not loaded"))
    result = await run(ctx(VANTIRO, onrc=onrc))
    assert result.status is AgentStatus.PARTIAL
    assert result.sources_failed == ["onrc_bulk"]
    assert set(by_rule(result)) == {"ID-INACTIVE-01"}


async def test_both_down_is_unavailable() -> None:
    result = await run(
        ctx(
            AURORA,
            v9=FakeV9(error=SourceUnavailable("anaf_v9", "down")),
            onrc=FakeOnrc(error=SourceUnavailable("onrc_bulk", "down")),
        )
    )
    assert result.status is AgentStatus.UNAVAILABLE
    assert result.signals == []


async def test_dedeman_without_fixtures_is_never_clean() -> None:
    result = await run(ctx(DEDEMAN))
    assert result.status is AgentStatus.UNAVAILABLE
    assert set(result.sources_failed) == {"anaf_v9", "onrc_bulk"}


async def test_not_implemented_adapter_is_a_failed_source() -> None:
    v9 = FakeV9(error=NotImplementedError())
    result = await run(ctx(AURORA, v9=v9))
    assert result.status is AgentStatus.PARTIAL
    assert result.notes is not None and "not implemented" in result.notes


async def test_switched_off_source() -> None:
    result = await run(ctx(AURORA, disabled=frozenset({"anaf_v9"})))
    assert result.sources_failed == ["anaf_v9"]
    assert result.status is AgentStatus.PARTIAL


async def test_missing_adapter() -> None:
    result = await run(ctx(AURORA, adapters={"onrc_bulk": FakeOnrc()}))
    assert result.sources_failed == ["anaf_v9"]


async def test_cui_not_found_at_anaf() -> None:
    result = await run(ctx(AURORA, v9=FakeV9(record=None)))
    assert result.sources_failed == ["anaf_v9"]
    assert result.notes is not None and "notFound" in result.notes


@pytest.mark.parametrize(
    "record",
    [
        {"date_generale": {}},
        {"stare_inactiv": {"statusInactivi": False}},
        {},
    ],
)
async def test_malformed_anaf_record_is_never_clean(record: dict[str, Any]) -> None:
    result = await run(ctx(AURORA, v9=FakeV9(record=record)))
    assert result.status is AgentStatus.PARTIAL
    assert result.sources_failed == ["anaf_v9"]
    assert result.signals == []


async def test_no_administrators_is_partial() -> None:
    result = await run(ctx(AURORA, identity=sheet(AURORA, administrators=[])))
    assert result.status is AgentStatus.PARTIAL
    assert result.sources_failed == ["onrc_bulk"]


async def test_stale_data_lowers_confidence() -> None:
    result = await run(ctx(VANTIRO, v9=FakeV9(stale=True)))
    assert by_rule(result)["ID-INACTIVE-01"].confidence == 0.8
    assert result.notes is not None and "stale" in result.notes


# ------------------------------------------------------------------------------ config
def test_config_yaml_loads() -> None:
    cfg = load_config()
    assert cfg.window_days == 365
    assert cfg.shared_office_min_companies == 20


async def test_thresholds_come_from_config() -> None:
    strict = load_config().model_copy(update={"shared_office_min_companies": 100})
    result = await IdentityAgent(strict).run(ctx(ZEPHYRIA))
    assert set(by_rule(result)) == {"ID-ADMIN-CHANGE-01"}
