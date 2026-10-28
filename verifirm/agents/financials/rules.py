"""Financials rules. Severities and thresholds are PROPOSALS (docs/RULES.md).

Pure functions over list[FinancialYear] (oldest first). A year that was not filed is
missing data, not zero.
"""

from __future__ import annotations

from typing import Any

from verifirm.agents.base import RuleSpec
from verifirm.schema.financials import FinancialYear
from verifirm.schema.signals import Component, Severity

C = Component.FINANCIALS

RULES: dict[str, RuleSpec] = {
    r.rule_id: r
    for r in [
        RuleSpec(
            "FIN-REVENUE-DECLINE-01",
            C,
            Severity.MEDIUM,
            "Turnover fell > 25% over the last 3 filed years",
            "anaf_bilant",
        ),
        RuleSpec(
            "FIN-LOSS-TREND-01",
            C,
            Severity.MEDIUM,
            "Net loss in >= 2 consecutive recent years",
            "anaf_bilant",
        ),
        RuleSpec(
            "FIN-NET-ASSETS-01",
            C,
            Severity.HIGH,
            "Equity < 1/2 of share capital (Law 31/1990 art. 153^24)",
            "anaf_bilant",
        ),
        RuleSpec(
            "FIN-DEBT-RISE-01",
            C,
            Severity.MEDIUM,
            "Debts grow faster than turnover, or debts > 70% of turnover",
            "anaf_bilant",
        ),
        RuleSpec(
            "FIN-HEADCOUNT-01",
            C,
            Severity.MEDIUM,
            "Turnover per employee > 3M RON (implausible for the activity)",
            "anaf_bilant",
        ),
        RuleSpec(
            "FIN-REVENUE-JUMP-01",
            C,
            Severity.MEDIUM,
            "Turnover grew > 200% year over year",
            "anaf_bilant",
        ),
        RuleSpec(
            "FIN-NO-FILING-01",
            C,
            Severity.MEDIUM,
            "No financial statement for the latest expected year",
            "anaf_bilant",
        ),
    ]
}


def check_revenue_decline(
    years: list[FinancialYear], drop_pct: float = 25.0
) -> dict[str, Any] | None:
    """FIN-REVENUE-DECLINE-01. Brunaldo: 32.0M -> 15.2M."""
    raise NotImplementedError


def check_loss_trend(years: list[FinancialYear], consecutive: int = 2) -> dict[str, Any] | None:
    """FIN-LOSS-TREND-01. Brunaldo: losses 2023-2025."""
    raise NotImplementedError


def check_net_assets(latest: FinancialYear) -> dict[str, Any] | None:
    """FIN-NET-ASSETS-01. Zephyria 2025: equity -111,000 < 100 (= 1/2 of 200 share capital)."""
    raise NotImplementedError


def check_debt_rise(
    years: list[FinancialYear], debt_to_turnover: float = 0.7
) -> dict[str, Any] | None:
    """FIN-DEBT-RISE-01. Zephyria: debts 40k -> 14.2M. Brunaldo: 9.8M -> 19.4M on falling turnover."""
    raise NotImplementedError


def check_headcount(
    latest: FinancialYear, max_turnover_per_employee: int = 3_000_000
) -> dict[str, Any] | None:
    """FIN-HEADCOUNT-01. Zephyria 2025: 18.6M RON with 2 employees."""
    raise NotImplementedError


def check_revenue_jump(
    years: list[FinancialYear], jump_pct: float = 200.0
) -> dict[str, Any] | None:
    """FIN-REVENUE-JUMP-01. Zephyria: 410k -> 1.9M -> 9.8M."""
    raise NotImplementedError


def check_no_filing(years: list[FinancialYear], expected_last_year: int) -> dict[str, Any] | None:
    """FIN-NO-FILING-01."""
    raise NotImplementedError
