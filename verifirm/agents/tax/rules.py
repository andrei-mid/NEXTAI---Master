"""Tax rules. Severities and thresholds are PROPOSALS (docs/RULES.md)."""

from __future__ import annotations

from datetime import date
from typing import Any

from verifirm.agents.base import RuleSpec
from verifirm.schema.financials import FinancialYear
from verifirm.schema.signals import Component, Severity

C = Component.TAX

RULES: dict[str, RuleSpec] = {
    r.rule_id: r
    for r in [
        RuleSpec(
            "TAX-DECLARED-GAP-01",
            C,
            Severity.HIGH,
            "Submitted figures differ from ANAF by > 10% (turnover, profit sign/amount, employees)",
            "documents vs anaf_bilant",
        ),
        RuleSpec(
            "TAX-ARREARS-01",
            C,
            Severity.HIGH,
            "Company is on ANAF's tax-arrears list",
            "mock_restante",
        ),
        RuleSpec(
            "TAX-VAT-CANCELLED-01",
            C,
            Severity.MEDIUM,
            "VAT registration cancelled in the last 24 months (even if re-registered)",
            "anaf_v9",
        ),
        RuleSpec(
            "TAX-EFACTURA-GAP-01",
            C,
            Severity.MEDIUM,
            "D300 declared sales differ from e-Factura issued totals by > 10%",
            "mock_d300 vs mock_efactura",
        ),
        RuleSpec(
            "TAX-EFACTURA-REG-01",
            C,
            Severity.LOW,
            "Company not enrolled in RO e-Factura although required",
            "anaf_efactura_registry",
        ),
    ]
}


def check_declared_gap(
    submitted: FinancialYear, official: FinancialYear, tolerance_pct: float = 10.0
) -> dict[str, Any] | None:
    """TAX-DECLARED-GAP-01. One signal per year, listing every differing field with both values.
    Zephyria 2025: turnover 25.4M vs 18.6M, profit +1.2M vs -350k, employees 14 vs 2.
    Brunaldo 2025: profit +0.3M vs -2.6M."""
    raise NotImplementedError


def check_arrears(restante: dict[str, Any]) -> dict[str, Any] | None:
    """TAX-ARREARS-01. Brunaldo Q2 2026: 412,560 principal + 96,300 accessories."""
    raise NotImplementedError


def check_vat_cancelled(
    vat_periods: list[dict[str, Any]], today: date, window_days: int = 730
) -> dict[str, Any] | None:
    """TAX-VAT-CANCELLED-01. Input: anaf_v9 inregistrare_scop_Tva.perioade_TVA.
    Brunaldo: cancelled 2025-02-01, re-registered 2025-09-15."""
    raise NotImplementedError


def check_efactura_gap(
    d300_returns: list[dict[str, Any]], efactura: dict[str, Any], tolerance_pct: float = 10.0
) -> dict[str, Any] | None:
    """TAX-EFACTURA-GAP-01. Brunaldo: 18% gap."""
    raise NotImplementedError


def check_efactura_registration(registered: bool | None) -> dict[str, Any] | None:
    """TAX-EFACTURA-REG-01. None = unknown -> no signal (and not clean: note it)."""
    raise NotImplementedError
