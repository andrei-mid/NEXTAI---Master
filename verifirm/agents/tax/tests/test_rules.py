from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from verifirm.agents.tax import rules
from verifirm.schema.financials import FinancialYear
from verifirm.schema.signals import Severity, SourceRef, SourceType

COMPANIES = Path(__file__).resolve().parents[4] / "fixtures" / "companies"
TODAY = date(2026, 10, 28)
SRC = SourceRef(name="t", type=SourceType.OFFICIAL, retrieved_at=datetime(2026, 1, 1, tzinfo=UTC))
BRUNALDO = "99000033_brunaldo_trade_impex"
AURORA = "99000017_aurora_soft_labs"


def load(company: str, filename: str) -> Any:
    return json.loads((COMPANIES / company / filename).read_text(encoding="utf-8"))


def year(y: int = 2025, **figures: int | None) -> FinancialYear:
    return FinancialYear(year=y, source=SRC, **figures)


# -------------------------------------------------------------- TAX-DECLARED-GAP-01
def test_declared_gap_zephyria() -> None:
    submitted = year(turnover=25_400_000, net_profit=1_200_000, employees=14)
    official = year(turnover=18_600_000, net_profit=-350_000, employees=2, total_debts=14_200_000)
    assert rules.check_declared_gap(submitted, official) == {
        "year": 2025,
        "submitted": {"turnover": 25_400_000, "net_profit": 1_200_000, "employees": 14},
        "official": {"turnover": 18_600_000, "net_profit": -350_000, "employees": 2},
    }


def test_only_differing_fields_are_listed() -> None:
    facts = rules.check_declared_gap(
        year(turnover=1_000_000, net_profit=300_000),
        year(turnover=1_050_000, net_profit=-2_600_000),
    )
    assert facts is not None
    assert facts["submitted"] == {"net_profit": 300_000}


@pytest.mark.parametrize(
    ("submitted", "official", "gap"),
    [
        (1_100_000, 1_000_000, False),  # exactly 10%: inside the tolerance
        (1_100_001, 1_000_000, True),
        (100, -100, True),  # profit vs loss: always a gap
        (-100, 100, True),
        (-1_000, -1_050, False),  # two losses, 4.8% apart
        (5, 0, True),  # ANAF shows 0
        (0, 0, False),
        (0, 50_000, True),
    ],
)
def test_tolerance_and_sign(submitted: int, official: int, gap: bool) -> None:
    facts = rules.check_declared_gap(year(net_profit=submitted), year(net_profit=official))
    assert (facts is not None) is gap


def test_tolerance_comes_from_the_caller() -> None:
    assert rules.check_declared_gap(year(turnover=130), year(turnover=100), 50.0) is None


def test_nothing_comparable_is_never_clean() -> None:
    with pytest.raises(ValueError):
        rules.check_declared_gap(year(turnover=1), year(employees=3))


def test_different_years_are_never_compared() -> None:
    with pytest.raises(ValueError):
        rules.check_declared_gap(year(2025, turnover=1), year(2024, turnover=1))


# -------------------------------------------------------------------- TAX-ARREARS-01
def test_arrears_brunaldo() -> None:
    assert rules.check_arrears(load(BRUNALDO, "restante.json")) == {
        "list_period": "2026-Q2",
        "principal_ron": 412_560,
        "accessories_ron": 96_300,
    }


def test_not_on_the_list() -> None:
    assert rules.check_arrears(load(AURORA, "restante.json")) is None


def test_white_list_contradiction_still_flags() -> None:
    entry = {
        "list_period": "2026-Q2",
        "obligations": [{"type": "principal", "amount_ron": 10}],
        "on_white_list": True,
    }
    facts = rules.check_arrears(entry)
    assert facts is not None and facts["on_white_list"] is True


@pytest.mark.parametrize(
    "entry",
    [
        {"list_period": "2026-Q2"},
        {"obligations": []},
        {"list_period": "2026-Q2", "obligations": [{"type": "amenzi", "amount_ron": 5}]},
        {"list_period": "2026-Q2", "obligations": [{"type": "principal", "amount_ron": "5"}]},
    ],
)
def test_malformed_arrears_are_never_clean(entry: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        rules.check_arrears(entry)


@pytest.mark.parametrize(
    ("period", "end"),
    [
        ("2026-Q1", date(2026, 3, 31)),
        ("2026-Q2", date(2026, 6, 30)),
        ("2026-Q3", date(2026, 9, 30)),
        ("2026-Q4", date(2026, 12, 31)),
        ("2026", None),
    ],
)
def test_quarter_end(period: str, end: date | None) -> None:
    assert rules.quarter_end(period) == end


# -------------------------------------------------------------- TAX-VAT-CANCELLED-01
def vat_periods(company: str) -> list[dict[str, Any]]:
    periods: list[dict[str, Any]] = load(company, "anaf_v9.json")["found"][0][
        "inregistrare_scop_Tva"
    ]["perioade_TVA"]
    return periods


def test_vat_cancelled_brunaldo() -> None:
    assert rules.check_vat_cancelled(vat_periods(BRUNALDO), TODAY) == {
        "cancelled_on": date(2025, 2, 1),
        "reregistered_on": date(2025, 9, 15),
    }


def test_vat_never_cancelled() -> None:
    assert rules.check_vat_cancelled(vat_periods(AURORA), TODAY) is None


def test_vat_cancelled_long_ago() -> None:
    periods = [{"data_inceput_ScpTVA": "2010-01-01", "data_sfarsit_ScpTVA": "2020-01-01"}]
    assert rules.check_vat_cancelled(periods, TODAY) is None


def test_vat_cancelled_and_not_reregistered() -> None:
    periods = [{"data_inceput_ScpTVA": "2010-01-01", "data_sfarsit_ScpTVA": "2026-05-01"}]
    assert rules.check_vat_cancelled(periods, TODAY) == {
        "cancelled_on": date(2026, 5, 1),
        "reregistered_on": None,
    }


def test_vat_window_is_configurable() -> None:
    assert rules.check_vat_cancelled(vat_periods(BRUNALDO), TODAY, window_days=365) is None


def test_vat_malformed_is_never_clean() -> None:
    with pytest.raises(ValueError):
        rules.check_vat_cancelled("none", TODAY)  # type: ignore[arg-type]


# --------------------------------------------------------------- TAX-EFACTURA-GAP-01
def test_efactura_gap_brunaldo() -> None:
    facts = rules.check_efactura_gap(
        load(BRUNALDO, "d300.json")["returns"], load(BRUNALDO, "efactura.json")
    )
    assert facts == {"d300_ron": 12_464_000, "efactura_ron": 15_200_000, "gap_pct": 18.0}
    assert rules.efactura_gap_severity(facts) is Severity.MEDIUM


def test_efactura_matches_aurora() -> None:
    assert (
        rules.check_efactura_gap(
            load(AURORA, "d300.json")["returns"], load(AURORA, "efactura.json")
        )
        is None
    )


EF_2025 = {
    "period": {"from": "2025-01-01", "to": "2025-12-31"},
    "issued_total_ron": 1_000,
    "received_total_ron": 0,
    "flows": [],
}


def quarters(*bases: int) -> list[dict[str, Any]]:
    return [{"period": f"2025-Q{i + 1}", "taxable_base_ron": b} for i, b in enumerate(bases)]


def test_d300_above_efactura_is_low() -> None:
    facts = rules.check_efactura_gap(quarters(300, 300, 300, 300), EF_2025)
    assert facts is not None and facts["gap_pct"] == -20.0
    assert rules.efactura_gap_severity(facts) is Severity.LOW


def test_monthly_returns_and_returns_outside_the_period() -> None:
    monthly = [{"period": f"2025-{m:02d}", "taxable_base_ron": 70} for m in range(1, 13)]
    outside = [{"period": "2024-Q4", "taxable_base_ron": 999_999}]  # ignored: not in 2025
    facts = rules.check_efactura_gap(monthly + outside, EF_2025)
    assert facts == {"d300_ron": 840, "efactura_ron": 1_000, "gap_pct": 16.0}


def test_gap_within_tolerance() -> None:
    assert rules.check_efactura_gap(quarters(240, 240, 240, 240), EF_2025) is None


def test_missing_quarter_is_never_clean() -> None:
    with pytest.raises(ValueError, match="cover"):
        rules.check_efactura_gap(quarters(250, 250, 250), EF_2025)


def test_overlapping_returns_are_never_clean() -> None:
    returns = [*quarters(250, 250, 250, 250), {"period": "2025-03", "taxable_base_ron": 1}]
    with pytest.raises(ValueError, match="twice"):
        rules.check_efactura_gap(returns, EF_2025)


def test_unknown_period_format() -> None:
    with pytest.raises(ValueError):
        rules.check_efactura_gap([{"period": "anul 2025", "taxable_base_ron": 1}], EF_2025)


def test_no_invoices_but_declared_sales() -> None:
    facts = rules.check_efactura_gap(quarters(1, 1, 1, 1), EF_2025 | {"issued_total_ron": 0})
    assert facts is not None and facts["gap_pct"] == -100.0


# --------------------------------------------------------------- TAX-EFACTURA-REG-01
@pytest.mark.parametrize(("flag", "hit"), [(False, True), (True, False), (None, False)])
def test_efactura_registration(flag: bool | None, hit: bool) -> None:
    assert (rules.check_efactura_registration(flag) is not None) is hit


# ------------------------------------------------------------------------- config
def test_config_yaml_loads() -> None:
    cfg = rules.load_config()
    assert cfg.declared_gap_tolerance_pct == 10
    assert cfg.vat_cancelled_window_days == 730


def test_vat_periods_as_a_single_object() -> None:
    """ANAF's v9 documentation shows perioade_TVA as one object, not a list."""
    period = {"data_inceput_ScpTVA": "2010-01-01", "data_sfarsit_ScpTVA": "2026-05-01"}
    assert rules.check_vat_cancelled(period, TODAY) == {
        "cancelled_on": date(2026, 5, 1),
        "reregistered_on": None,
    }
