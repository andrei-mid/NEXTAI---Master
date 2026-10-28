from __future__ import annotations

from typing import Any

import pytest

from verifirm.agents.presence import rules

NOTHING: dict[str, Any] = {"website": None, "jobs": [], "seap": [], "kohesio": []}


# ------------------------------------------------------------- PRE-NO-FOOTPRINT-01
def test_no_footprint_zephyria() -> None:
    assert rules.check_no_footprint(18_600_000, NOTHING) == {
        "turnover": 18_600_000,
        "website": False,
        "jobs": 0,
        "seap": 0,
        "kohesio": 0,
    }


@pytest.mark.parametrize(
    "part",
    [
        {"website": {"url": "https://x.example", "address_on_site": None}},
        {"jobs": [{"title": "Sofer"}]},
        {"seap": [{"value_ron": 10}]},
        {"kohesio": [{"title": "Proiect"}]},
    ],
)
def test_any_trace_is_a_footprint(part: dict[str, Any]) -> None:
    assert rules.check_no_footprint(18_600_000, NOTHING | part) is None


@pytest.mark.parametrize("turnover", [None, 0, 5_000_000, 4_999_999])
def test_small_or_unknown_turnover_is_not_suspicious(turnover: int | None) -> None:
    assert rules.check_no_footprint(turnover, NOTHING) is None


def test_threshold_is_configurable() -> None:
    assert rules.check_no_footprint(18_600_000, NOTHING, min_turnover=20_000_000) is None


@pytest.mark.parametrize("missing", ["website", "jobs", "seap", "kohesio"])
def test_an_unchecked_part_is_never_absence(missing: str) -> None:
    partial = {k: v for k, v in NOTHING.items() if k != missing}
    with pytest.raises(ValueError, match=missing):
        rules.check_no_footprint(18_600_000, partial)


# --------------------------------------------------------- PRE-ADDRESS-MISMATCH-01
def test_same_address_written_differently() -> None:
    site = "Strada Algoritmului numar 7, Localitatea Fictiva, Judetul Fictiv"
    onrc = "Str. Algoritmului nr. 7, Localitatea Fictivă, Județul Fictiv"
    assert rules.check_address_mismatch(site, onrc) is None


def test_different_address() -> None:
    facts = rules.check_address_mismatch(
        "Bd. Unirii nr. 3, București", "Str. Algoritmului nr. 7, Localitatea Fictivă"
    )
    assert facts is not None
    assert facts["similarity"] < 0.6
    assert facts["website_address"] == "Bd. Unirii nr. 3, București"


@pytest.mark.parametrize(
    ("site", "onrc"), [(None, "Str. X nr. 1"), ("Str. X nr. 1", None), ("", "")]
)
def test_missing_address_is_no_conclusion(site: str | None, onrc: str | None) -> None:
    assert rules.check_address_mismatch(site, onrc) is None


def test_address_words_are_normalized() -> None:
    assert rules.address_words("Str. Ştefan cel Mare nr. 5, Jud. Iaşi") == {
        "strada",
        "stefan",
        "cel",
        "mare",
        "numar",
        "5",
        "judetul",
        "iasi",
    }


# --------------------------------------------------------- PRE-PUBLIC-CONTRACTS-01
def test_public_contracts_and_eu_funds() -> None:
    facts = rules.check_public_contracts(
        [{"value_ron": 120_000}, {"value_ron": 80_000}],
        [{"eu_contribution_eur": 50_000}],
    )
    assert facts == {
        "seap_contracts": 2,
        "seap_value_ron": 200_000,
        "kohesio_projects": 1,
        "eu_contribution_eur": 50_000,
    }


@pytest.mark.parametrize(("seap", "kohesio"), [([], []), (None, None), (None, [])])
def test_no_public_contracts(seap: Any, kohesio: Any) -> None:
    assert rules.check_public_contracts(seap, kohesio) is None


def test_config_yaml_loads() -> None:
    cfg = rules.load_config()
    assert cfg.min_turnover_ron == 5_000_000
    assert cfg.no_footprint_confidence == 0.8
