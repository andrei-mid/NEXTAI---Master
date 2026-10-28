from typing import Any

import pytest

from verifirm.consolidation.analyst.citations import (
    check_flag,
    check_flags,
    clean_explanation,
    resolve,
    value_matches,
)
from verifirm.schema.analyst import AnalystFlag, Citation, FlagCategory
from verifirm.schema.signals import Severity

DOSSIER: dict[str, Any] = {
    "financials": {
        "2024": {"turnover": 9800000, "equity": 239000, "employees": 2},
        "2025": {"net_profit": -350000},
    },
    "indicators": {"2024": {"turnover_per_employee": 4900000, "debts_to_turnover": 0.7}},
    "cross_checks": {"address": {"anaf": "Str. Exemplului nr. 1, București", "match": False}},
    "administrators": [{"alias": "Administrator A", "valid_to": None}],
    "signals": {"ID-ADMIN-CHANGE-01:ab": {"claim": "The administrator changed on 2025-11-02."}},
}


def flag(
    claim: str, *evidence: tuple[str, str], severity: Severity = Severity.MEDIUM
) -> AnalystFlag:
    return AnalystFlag(
        title="Observation",
        claim=claim,
        category=FlagCategory.FINANCIAL_INCONSISTENCY,
        severity=severity,
        evidence=[Citation(path=p, value=v) for p, v in evidence],
    )


def test_resolve_paths() -> None:
    assert resolve(DOSSIER, "financials.2024.equity") == 239000
    assert resolve(DOSSIER, "administrators[0].alias") == "Administrator A"
    assert resolve(DOSSIER, "administrators.0.valid_to") is None
    assert resolve(DOSSIER, "signals.ID-ADMIN-CHANGE-01:ab.claim").startswith("The administrator")


@pytest.mark.parametrize(
    ("cited", "actual", "ok"),
    [
        ("9800000", 9800000, True),
        ("9.800.000", 9800000, True),
        ("9,800,000", 9800000, True),
        ("9700000", 9800000, False),
        ("350000", -350000, False),  # a loss cited as a profit
        ("-350000", -350000, True),
        ("0.7", 0.7, True),
        ("true", False, False),
        ("false", False, True),
        ("null", None, True),
        ("str. exemplului nr. 1, bucuresti", "Str. Exemplului nr. 1, București", True),
        ("changed on 2025-11-02", "The administrator changed on 2025-11-02.", True),
    ],
)
def test_value_matches(cited: str, actual: Any, ok: bool) -> None:
    assert value_matches(cited, actual) is ok


def test_a_backed_flag_is_kept() -> None:
    good = flag(
        "Turnover per employee was 4900000 RON in 2024 with 2 employees.",
        ("indicators.2024.turnover_per_employee", "4900000"),
        ("financials.2024.employees", "2"),
    )
    assert check_flag(good, DOSSIER) is None


@pytest.mark.parametrize(
    ("bad", "reason"),
    [
        (flag("x", ("financials.2023.turnover", "1")), "does not exist"),
        (flag("x", ("financials.2024", "9800000")), "a section"),
        (flag("x", ("financials.2024.equity", "300000")), "not '300000'"),
        (flag("Equity fell to 120000 RON.", ("financials.2024.equity", "239000")), "120000"),
        (
            flag("We recommend to reject the file.", ("financials.2024.equity", "239000")),
            "decision",
        ),
        (flag("This looks like fraud.", ("financials.2024.equity", "239000")), "fraud"),
    ],
)
def test_unbacked_flags_are_rejected(bad: AnalystFlag, reason: str) -> None:
    accepted, rejected = check_flags([bad], DOSSIER)
    assert accepted == [] and reason in rejected[0].reason


def test_critical_is_capped_at_high() -> None:
    accepted, _ = check_flags(
        [
            flag(
                "Equity is 239000 RON.",
                ("financials.2024.equity", "239000"),
                severity=Severity.CRITICAL,
            )
        ],
        DOSSIER,
    )
    assert accepted[0].severity == Severity.HIGH


def test_explanation_drops_only_unsupported_sentences() -> None:
    text = "Turnover reached 9800000 RON. Debts are 12000000 RON. We approve it. Growth is fast."
    assert clean_explanation(text, DOSSIER) == "Turnover reached 9800000 RON. Growth is fast."
