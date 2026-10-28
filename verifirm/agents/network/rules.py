"""Network rules. Severities and thresholds are PROPOSALS (docs/RULES.md)."""

from __future__ import annotations

from typing import Any

from verifirm.agents.base import RuleSpec
from verifirm.schema.signals import Component, Severity

C = Component.NETWORK

RULES: dict[str, RuleSpec] = {
    r.rule_id: r
    for r in [
        RuleSpec(
            "NET-SERIAL-ADMIN-01",
            C,
            Severity.HIGH,
            "An administrator is/was administrator of >= 2 companies that failed in the last 5 years (bankrupt, insolvent, deregistered, ANAF inactive)",
            "onrc_bulk, anaf_v9, mock_bpi",
        ),
        RuleSpec(
            "NET-CIRCULAR-INVOICE-01",
            C,
            Severity.HIGH,
            "Invoice cycle A->B->...->A among related companies (total >= 500k RON)",
            "mock_efactura",
        ),
        RuleSpec(
            "NET-PARTNER-INACTIVE-01",
            C,
            Severity.MEDIUM,
            "Main shareholder/partner company is ANAF inactive or deregistered",
            "mock_shareholders, anaf_v9",
        ),
    ]
}


def check_serial_admin(
    affiliates: list[dict[str, Any]], min_failed: int = 2, years: int = 5
) -> dict[str, Any] | None:
    """NET-SERIAL-ADMIN-01. `affiliates`: [{cui, name, status, failed_on, via_person}].
    Zephyria: Ionel Fictivescu -> Kestrel (bankruptcy 2024), Orvanto (deregistered 2023),
    Pelinor (insolvency 2025), Vantiro (ANAF inactive since 2024-06-01); Mirelda is active."""
    raise NotImplementedError


def find_invoice_cycles(
    flows: list[dict[str, Any]], min_total_ron: int = 500_000
) -> list[dict[str, Any]]:
    """NET-CIRCULAR-INVOICE-01. Simple cycle detection (DFS) on from_cui -> to_cui edges.
    Zephyria -> Mirelda -> Kestrel -> Zephyria, 2.1M RON."""
    raise NotImplementedError


def check_partner_inactive(shareholders: list[dict[str, Any]]) -> dict[str, Any] | None:
    """NET-PARTNER-INACTIVE-01. Calbrona Holding Fictiv (99000090) is inactive."""
    raise NotImplementedError
