"""Tax rules. Severities and thresholds are PROPOSALS (docs/RULES.md, config.yaml).

Each check is a pure function: facts in -> Signal-ready facts out (or None). No I/O here.
`None` means "checked and nothing found". Input that can't be checked (wrong shape, periods
that don't cover each other, nothing comparable) raises ValueError, so the agent reports it
instead of calling the company clean.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from verifirm.agents.base import RuleSpec
from verifirm.schema.financials import FinancialYear
from verifirm.schema.signals import Component, Severity

C = Component.TAX
CONFIG_PATH = Path(__file__).with_name("config.yaml")

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
            "D300 declared sales differ from e-Factura issued totals by > 10% "
            "(medium when D300 is below e-Factura, low when above)",
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


class TaxConfig(BaseModel):
    """Thresholds from config.yaml (PROPOSAL)."""

    declared_gap_tolerance_pct: float = Field(ge=0)
    vat_cancelled_window_days: int = Field(gt=0)
    efactura_gap_tolerance_pct: float = Field(ge=0)
    efactura_gap_confidence: float = Field(ge=0, le=1)
    stale_confidence: float = Field(ge=0, le=1)


def load_config(path: Path = CONFIG_PATH) -> TaxConfig:
    return TaxConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


# Fields compared between the applicant's documents and ANAF, in claim order.
DECLARED_FIELDS: tuple[str, ...] = ("turnover", "net_profit", "employees", "total_debts", "equity")

_QUARTER = re.compile(r"^(\d{4})-Q([1-4])$")
_MONTH = re.compile(r"^(\d{4})-(\d{2})$")


# ---------------------------------------------------------------------------- helpers
def _as_date(value: Any) -> date | None:
    """date, ISO string or "" -> date | None. ANAF uses "" for "no date"."""
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _differs(submitted: int, official: int, tolerance_pct: float) -> bool:
    if submitted == official:
        return False
    sign_flip = submitted != 0 and (submitted > 0) != (official > 0)
    if official == 0 or sign_flip:
        return True  # ANAF shows 0, or profit vs loss: a percentage means nothing here
    return abs(submitted - official) / abs(official) * 100 > tolerance_pct


def _months(period: str) -> list[tuple[int, int]]:
    """'2025-Q2' -> [(2025, 4), (2025, 5), (2025, 6)]; '2025-03' -> [(2025, 3)]."""
    if m := _QUARTER.match(period):
        year, quarter = int(m[1]), int(m[2])
        return [(year, month) for month in range(quarter * 3 - 2, quarter * 3 + 1)]
    if (m := _MONTH.match(period)) and 1 <= int(m[2]) <= 12:
        return [(int(m[1]), int(m[2]))]
    raise ValueError(f"unknown D300 period {period!r}")


def _months_between(start: date, end: date) -> list[tuple[int, int]]:
    out, year, month = [], start.year, start.month
    while (year, month) <= (end.year, end.month):
        out.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


def quarter_end(list_period: str) -> date | None:
    """'2026-Q2' -> 2026-06-30. None for any other format."""
    if not (m := _QUARTER.match(list_period)):
        return None
    year, quarter = int(m[1]), int(m[2])
    if quarter == 4:
        return date(year, 12, 31)
    return date(year, quarter * 3 + 1, 1) - timedelta(days=1)


# ------------------------------------------------------------------------------ rules
def check_declared_gap(
    submitted: FinancialYear, official: FinancialYear, tolerance_pct: float = 10.0
) -> dict[str, Any] | None:
    """TAX-DECLARED-GAP-01. One signal per year, listing every differing field with both values.
    Zephyria 2025: turnover 25.4M vs 18.6M, profit +1.2M vs -350k, employees 14 vs 2.
    Brunaldo 2025: profit +0.3M vs -2.6M.

    Only fields present on BOTH sides are compared. Nothing comparable -> ValueError."""
    if submitted.year != official.year:
        raise ValueError(f"comparing {submitted.year} with {official.year}")
    pairs = {
        f: (getattr(submitted, f), getattr(official, f))
        for f in DECLARED_FIELDS
        if getattr(submitted, f) is not None and getattr(official, f) is not None
    }
    if not pairs:
        raise ValueError(f"no {submitted.year} figure is both submitted and published by ANAF")
    gaps = {f: v for f, v in pairs.items() if _differs(v[0], v[1], tolerance_pct)}
    if not gaps:
        return None
    return {
        "year": submitted.year,
        "submitted": {f: s for f, (s, _) in gaps.items()},
        "official": {f: o for f, (_, o) in gaps.items()},
    }


def check_arrears(restante: dict[str, Any]) -> dict[str, Any] | None:
    """TAX-ARREARS-01. Brunaldo Q2 2026: 412,560 principal + 96,300 accessories.

    Empty `obligations` = checked, not on the list. Optional `on_white_list` (ANAF's list of
    companies WITHOUT arrears) is copied into the facts; a contradiction still flags."""
    obligations = restante.get("obligations")
    if not isinstance(obligations, list) or not isinstance(restante.get("list_period"), str):
        raise ValueError("restante needs list_period and an obligations list")
    totals = {"principal": 0, "accesorii": 0}
    for item in obligations:
        kind, amount = item.get("type"), item.get("amount_ron")
        if kind not in totals or not isinstance(amount, int):
            raise ValueError(f"unknown arrears entry {item!r}")
        totals[kind] += amount
    if totals["principal"] + totals["accesorii"] <= 0:
        return None
    facts: dict[str, Any] = {
        "list_period": restante["list_period"],
        "principal_ron": totals["principal"],
        "accessories_ron": totals["accesorii"],
    }
    if "on_white_list" in restante:
        facts["on_white_list"] = restante["on_white_list"]
    return facts


def check_vat_cancelled(
    vat_periods: list[dict[str, Any]] | dict[str, Any], today: date, window_days: int = 730
) -> dict[str, Any] | None:
    """TAX-VAT-CANCELLED-01. Input: anaf_v9 inregistrare_scop_Tva.perioade_TVA.
    Brunaldo: cancelled 2025-02-01, re-registered 2025-09-15.

    A period's end date (data_sfarsit_ScpTVA) is a cancellation. The latest one inside the
    window wins; re-registration = the first period starting on or after it."""
    if isinstance(vat_periods, dict):
        vat_periods = [vat_periods]  # ANAF's documentation shows a single object, live is a list
    if not isinstance(vat_periods, list) or not all(isinstance(p, dict) for p in vat_periods):
        raise ValueError("perioade_TVA must be a list of periods")
    starts = [d for d in (_as_date(p.get("data_inceput_ScpTVA")) for p in vat_periods) if d]
    ends = [d for d in (_as_date(p.get("data_sfarsit_ScpTVA")) for p in vat_periods) if d]
    recent = [d for d in ends if 0 <= (today - d).days <= window_days]
    if not recent:
        return None
    cancelled_on = max(recent)
    later = [d for d in starts if d >= cancelled_on]
    return {"cancelled_on": cancelled_on, "reregistered_on": min(later) if later else None}


def check_efactura_gap(
    d300_returns: list[dict[str, Any]], efactura: dict[str, Any], tolerance_pct: float = 10.0
) -> dict[str, Any] | None:
    """TAX-EFACTURA-GAP-01. Brunaldo: 18% gap.

    Sums the D300 taxable base over exactly the e-Factura period. D300 must cover every month
    of it, otherwise the two can't be compared (ValueError). gap_pct > 0 = D300 BELOW
    e-Factura (sales under-declared), < 0 = above (can be legitimate: exports, B2C)."""
    period = efactura.get("period") or {}
    start, end = _as_date(period.get("from")), _as_date(period.get("to"))
    issued = efactura.get("issued_total_ron")
    if start is None or end is None or not isinstance(issued, int):
        raise ValueError("e-Factura data needs period.from, period.to and issued_total_ron")
    wanted = set(_months_between(start, end))
    covered: set[tuple[int, int]] = set()
    declared = 0
    for ret in d300_returns:
        months = _months(str(ret.get("period", "")))
        if not set(months) <= wanted:
            continue  # a return outside the e-Factura period
        if covered & set(months):
            raise ValueError(f"D300 period {ret['period']} declared twice")
        covered |= set(months)
        declared += int(ret["taxable_base_ron"])
    if covered != wanted:
        raise ValueError("D300 returns don't cover the whole e-Factura period")
    if issued == declared:
        return None
    gap_pct = -100.0 if issued == 0 else round((issued - declared) / issued * 100, 1)
    if abs(gap_pct) <= tolerance_pct:
        return None
    return {"d300_ron": declared, "efactura_ron": issued, "gap_pct": gap_pct}


def efactura_gap_severity(facts: dict[str, Any]) -> Severity:
    """D300 below e-Factura (under-declared sales) -> medium; above -> low."""
    return Severity.MEDIUM if facts["gap_pct"] > 0 else Severity.LOW


def check_efactura_registration(registered: bool | None) -> dict[str, Any] | None:
    """TAX-EFACTURA-REG-01. None = unknown -> no signal (and not clean: note it)."""
    return {"registered": False} if registered is False else None
