from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from verifirm.agents.identity import rules
from verifirm.schema.signals import Severity

COMPANIES = Path(__file__).resolve().parents[4] / "fixtures" / "companies"
TODAY = date(2026, 10, 28)


def v9(cui_dir: str) -> dict[str, Any]:
    found: list[dict[str, Any]] = json.loads(
        (COMPANIES / cui_dir / "anaf_v9.json").read_text(encoding="utf-8")
    )["found"]
    return found[0]


def onrc(cui_dir: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (COMPANIES / cui_dir / "onrc.json").read_text(encoding="utf-8")
    )
    return data


def inactive_block(**over: Any) -> dict[str, Any]:
    block = {
        "dataInactivare": "",
        "dataReactivare": "",
        "dataPublicare": "",
        "dataRadiere": "",
        "statusInactivi": False,
    }
    return {"stare_inactiv": block | over}


ZEPHYRIA = "99000025_zephyria_logistic_nova"
AURORA = "99000017_aurora_soft_labs"
VANTIRO = "99000074_vantiro_agro_fictiv"
KESTREL = "99000041_kestrel_fictiv_transport"


# ------------------------------------------------------------------ ID-INACTIVE-01
def test_inactive_fixture_vantiro() -> None:
    assert rules.check_inactive(v9(VANTIRO)) == {
        "inactive_since": date(2024, 6, 1),
        "published_on": date(2024, 6, 1),
    }


def test_active_company_is_not_inactive() -> None:
    assert rules.check_inactive(v9(AURORA)) is None


def test_inactive_without_date_still_fires() -> None:
    facts = rules.check_inactive(inactive_block(statusInactivi=True))
    assert facts is not None and facts["inactive_since"] is None


@pytest.mark.parametrize("record", [{}, {"stare_inactiv": {}}, {"stare_inactiv": None}])
def test_missing_inactive_block_is_never_clean(record: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        rules.check_inactive(record)


def test_inactive_rule_is_the_only_auto_stop() -> None:
    assert [r for r, spec in rules.RULES.items() if spec.auto_stop] == ["ID-INACTIVE-01"]


# --------------------------------------------------------------- ID-REACTIVATED-01
def test_reactivated_within_window() -> None:
    record = inactive_block(dataInactivare="2025-01-10", dataReactivare="2026-03-01")
    assert rules.check_reactivated(record, TODAY) == {
        "reactivated_on": date(2026, 3, 1),
        "inactive_since": date(2025, 1, 10),
        "window_days": 365,
    }


def test_reactivated_outside_window() -> None:
    assert rules.check_reactivated(inactive_block(dataReactivare="2025-10-27"), TODAY) is None


def test_reactivated_window_boundary_and_future_date() -> None:
    assert rules.check_reactivated(inactive_block(dataReactivare="2025-10-28"), TODAY)
    assert rules.check_reactivated(inactive_block(dataReactivare="2026-11-01"), TODAY) is None


def test_never_reactivated() -> None:
    assert rules.check_reactivated(v9(ZEPHYRIA), TODAY) is None


# -------------------------------------------------------------- ID-ADMIN-CHANGE-01
def admins_from_onrc(cui_dir: str) -> list[dict[str, Any]]:
    return [
        {"name": r["nume"], "valid_from": r["de_la"], "valid_to": r["pana_la"]}
        for r in onrc(cui_dir)["reprezentanti"]
    ]


def test_admin_change_zephyria() -> None:
    assert rules.check_admin_change(admins_from_onrc(ZEPHYRIA), TODAY) == {
        "previous": ["MARCELA INVENTATU"],
        "current": ["IONEL FICTIVESCU"],
        "changed_on": date(2025, 11, 2),
        "window_days": 365,
    }


def test_no_admin_change_aurora() -> None:
    assert rules.check_admin_change(admins_from_onrc(AURORA), TODAY) is None


def test_initial_appointment_of_new_company_is_not_a_change() -> None:
    admins = [{"name": "A", "valid_from": date(2026, 9, 1), "valid_to": None}]
    assert rules.check_admin_change(admins, TODAY) is None


def test_resignation_without_replacement_is_a_change() -> None:
    admins = [
        {"name": "A", "valid_from": "2015-01-01", "valid_to": None},
        {"name": "B", "valid_from": "2015-01-01", "valid_to": "2026-05-05"},
    ]
    facts = rules.check_admin_change(admins, TODAY)
    assert facts is not None
    assert facts["previous"] == ["B"] and facts["current"] == ["A"]


def test_old_admin_change_outside_window() -> None:
    admins = [
        {"name": "A", "valid_from": "2015-01-01", "valid_to": "2020-01-01"},
        {"name": "B", "valid_from": "2020-01-01", "valid_to": None},
    ]
    assert rules.check_admin_change(admins, TODAY) is None


def test_no_administrators_is_never_clean() -> None:
    with pytest.raises(ValueError):
        rules.check_admin_change([], TODAY)


# ------------------------------------------------------------- ID-OFFICE-CHANGE-01
def test_office_change_within_window() -> None:
    history = [
        {"address": "Str. Veche nr. 1", "valid_from": "2019-01-01", "valid_to": "2026-02-01"},
        {"address": "Str. Noua nr. 2", "valid_from": "2026-02-01", "valid_to": None},
    ]
    assert rules.check_office_change(history, TODAY) == {
        "previous": "Str. Veche nr. 1",
        "current": "Str. Noua nr. 2",
        "changed_on": date(2026, 2, 1),
        "window_days": 365,
    }


def test_no_office_change_zephyria() -> None:
    history = [
        {"address": o["adresa"], "valid_from": o["de_la"], "valid_to": o["pana_la"]}
        for o in onrc(ZEPHYRIA)["istoric_sedii"]
    ]
    assert rules.check_office_change(history, TODAY) is None


def test_no_office_history_is_never_clean() -> None:
    with pytest.raises(ValueError):
        rules.check_office_change([], TODAY)


# ------------------------------------------------------------ ID-SHARED-OFFICE-01
def test_shared_office_zephyria() -> None:
    assert rules.check_shared_office(63) == {"n_companies": 63, "threshold": 20}


@pytest.mark.parametrize(("n", "hit"), [(19, False), (20, True), (1, False)])
def test_shared_office_threshold(n: int, hit: bool) -> None:
    assert (rules.check_shared_office(n) is not None) is hit


# --------------------------------------------------------------- ID-CAEN-UNAUTH-01
MAPPING = {"4941": ["4941"], "6201": ["6210"], "4639": ["4639", "4631"]}


def test_caen_authorized_same_revision() -> None:
    assert rules.check_caen_authorized("4941", ["4941"], MAPPING) is None


def test_caen_rev2_main_authorized_via_rev3() -> None:
    assert rules.check_caen_authorized("6201", ["6210"], MAPPING) is None


def test_caen_rev3_main_authorized_via_rev2() -> None:
    assert rules.check_caen_authorized("6210", ["6201"], MAPPING) is None


def test_caen_not_authorized() -> None:
    assert rules.check_caen_authorized("4639", ["6201"], MAPPING) == {
        "main_caen": "4639",
        "authorized": ["6201"],
        "mapped_equivalents": ["4631", "4639"],
    }


def test_caen_formats_are_normalized() -> None:
    assert rules.check_caen_authorized("01.11", ["111"], {}) is None


@pytest.mark.parametrize(("main", "authorized"), [("", ["4941"]), ("4941", [])])
def test_caen_missing_data_is_never_clean(main: str, authorized: list[str]) -> None:
    with pytest.raises(ValueError):
        rules.check_caen_authorized(main, authorized, MAPPING)


# ------------------------------------------------------------------- ID-STATUS-01
def test_active_status() -> None:
    assert rules.check_status("functiune") is None
    assert rules.check_status("În funcțiune") is None


@pytest.mark.parametrize(
    ("onrc_status", "status", "severity"),
    [
        ("faliment", "bankruptcy", Severity.CRITICAL),
        ("radiata", "deregistered", Severity.CRITICAL),
        ("intrare în insolvență", "insolvency", Severity.HIGH),
        ("reorganizare judiciară", "insolvency", Severity.HIGH),
        ("dizolvare", "in_dissolution", Severity.HIGH),
        ("suspendare activitate", "suspended", Severity.MEDIUM),
        ("ceva nou de la ONRC", "unknown", Severity.HIGH),
    ],
)
def test_status_and_severity(onrc_status: str, status: str, severity: Severity) -> None:
    facts = rules.check_status(onrc_status)
    assert facts is not None
    assert facts["status"] == status
    assert rules.status_severity(facts) is severity


def test_kestrel_bankruptcy_with_anaf_registered_is_not_a_conflict() -> None:
    record = v9(KESTREL)
    facts = rules.check_status(onrc(KESTREL)["stare"], record["stare_inactiv"]["dataRadiere"])
    assert facts is not None
    assert facts["status"] == "bankruptcy"
    assert facts["sources_agree"] is True


def test_anaf_deregistered_but_onrc_active_takes_worse_value() -> None:
    facts = rules.check_status("functiune", "2026-01-15")
    assert facts == {
        "status": "deregistered",
        "onrc_status": "functiune",
        "anaf_deregistered_on": date(2026, 1, 15),
        "sources_agree": False,
    }


def test_onrc_deregistered_but_anaf_not_yet() -> None:
    facts = rules.check_status("radiata", "")
    assert facts is not None
    assert facts["status"] == "deregistered" and facts["sources_agree"] is False


def test_both_deregistered_agree() -> None:
    facts = rules.check_status("radiata", "2023-07-20")
    assert facts is not None and facts["sources_agree"] is True


def test_empty_status_is_never_clean() -> None:
    with pytest.raises(ValueError):
        rules.check_status("  ")


# ----------------------------------------------------------- ID-NATURAL-PERSON-01
@pytest.mark.parametrize(
    ("legal_form", "expected"),
    [
        ("PFA", "PFA"),
        ("p.f.a.", "PFA"),
        ("II", "II"),
        ("PERSOANĂ FIZICĂ AUTORIZATĂ", "PFA"),
        ("ÎNTREPRINDERE INDIVIDUALĂ", "II"),
        ("INTREPRINDERE FAMILIALA", "IF"),
    ],
)
def test_natural_person_forms(legal_form: str, expected: str) -> None:
    facts = rules.check_natural_person(legal_form)
    assert facts is not None and facts["legal_form"] == expected


@pytest.mark.parametrize(
    "legal_form", ["SRL", "SA", "SOCIETATE COMERCIALĂ CU RĂSPUNDERE LIMITATĂ", None, ""]
)
def test_companies_are_not_natural_persons(legal_form: str | None) -> None:
    assert rules.check_natural_person(legal_form) is None


# ---------------------------------------------------------- ID-SOURCE-MISMATCH-01
def onrc_keys(cui_dir: str) -> dict[str, Any]:
    data = onrc(cui_dir)
    return {
        "cui": data["cui"],
        "trade_register_no": data["cod_inmatriculare"],
        "name": data["denumire"],
    }


@pytest.mark.parametrize("cui_dir", sorted(p.name for p in COMPANIES.glob("990*")))
def test_fixture_sources_agree(cui_dir: str) -> None:
    assert rules.check_source_mismatch(v9(cui_dir), onrc_keys(cui_dir)) is None


def test_name_compares_without_dots_case_and_diacritics() -> None:
    record = {"date_generale": {"cui": 1, "denumire": "ȘTEFAN COM S.R.L.", "nrRegCom": ""}}
    assert rules.check_source_mismatch(record, {"cui": "1", "name": "Stefan Com SRL"}) is None


def test_all_identity_keys_mismatch() -> None:
    record = {
        "date_generale": {"cui": 99000025, "denumire": "ALTA FIRMA SRL", "nrRegCom": "J99/1/2020"}
    }
    facts = rules.check_source_mismatch(record, onrc_keys(ZEPHYRIA))
    assert facts is not None
    assert set(facts["mismatches"]) == {"trade_register_no", "name"}

    record["date_generale"]["cui"] = 99000033
    facts = rules.check_source_mismatch(record, onrc_keys(ZEPHYRIA))
    assert facts is not None and "cui" in facts["mismatches"]


def test_new_register_number_format_is_not_a_mismatch() -> None:
    record = {"date_generale": {"cui": 1, "denumire": "X SRL", "nrRegCom": "J2021001234409"}}
    assert (
        rules.check_source_mismatch(
            record, {"cui": "1", "trade_register_no": "J99/1234/2021", "name": "X SRL"}
        )
        is None
    )


def test_missing_date_generale_is_never_clean() -> None:
    with pytest.raises(ValueError):
        rules.check_source_mismatch({}, onrc_keys(ZEPHYRIA))
