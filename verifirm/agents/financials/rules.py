"""Financials rules. Severities and thresholds are PROPOSALS (docs/RULES.md, config.yaml).

Pure functions over list[FinancialYear], oldest first, containing ONLY filed years. A year
that was not filed is missing data, never zero. Each check returns the facts behind the
signal (they become Signal.data, so the memo and critic can quote them) or None.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from verifirm.agents.base import RuleSpec
from verifirm.schema.financials import FinancialYear
from verifirm.schema.signals import Component, Severity

C = Component.FINANCIALS
CONFIG_PATH = Path(__file__).with_name("config.yaml")

RULES: dict[str, RuleSpec] = {
    r.rule_id: r
    for r in [
        RuleSpec(
            "FIN-NET-ASSETS-01",
            C,
            Severity.HIGH,
            "Equity < 1/2 of share capital in the latest filed year (Law 31/1990 art. 153^24)",
            "anaf_bilant",
        ),
        RuleSpec(
            "FIN-REVENUE-JUMP-01",
            C,
            Severity.MEDIUM,
            "Turnover grew > 300% from one year to the next (base >= 100k RON)",
            "anaf_bilant",
        ),
        RuleSpec(
            "FIN-HEADCOUNT-01",
            C,
            Severity.MEDIUM,
            "Turnover per employee > 5x the average of the CAEN division (averages: config, PROPOSAL)",
            "anaf_bilant",
        ),
        RuleSpec(
            "FIN-LOSS-TREND-01",
            C,
            Severity.MEDIUM,
            "Net loss in >= 2 consecutive years",
            "anaf_bilant",
        ),
        RuleSpec(
            "FIN-DEBT-RISE-01",
            C,
            Severity.MEDIUM,
            "Debts grew > 50% over the last 3 filed years while turnover grew <= 10% (or fell)",
            "anaf_bilant",
        ),
        RuleSpec(
            "FIN-REVENUE-DECLINE-01",
            C,
            Severity.MEDIUM,
            "Turnover fell > 25% over the last 3 filed years",
            "anaf_bilant",
        ),
        RuleSpec(
            "FIN-NO-FILING-01",
            C,
            Severity.MEDIUM,
            "No financial statement for the latest expected year (source reachable, nothing filed)",
            "anaf_bilant",
        ),
    ]
}


# --------------------------------------------------------------------------- config
class RevenueJump(BaseModel):
    min_growth_pct: float
    min_base_turnover_ron: int


class NetAssets(BaseModel):
    max_equity_to_share_capital: float


class LossTrend(BaseModel):
    min_consecutive_years: int


class DebtRise(BaseModel):
    window_years: int
    min_debt_growth_pct: float
    max_turnover_growth_pct: float


class RevenueDecline(BaseModel):
    window_years: int
    min_drop_pct: float


class Headcount(BaseModel):
    multiplier: float
    confidence: float
    caen_avg_turnover_per_employee_ron: dict[str, int]
    fallback_avg_ron: int | None = None  # None: no comparison for unlisted divisions


class FinancialsConfig(BaseModel):
    years_of_history: int
    filing_available_from_month: int
    revenue_jump: RevenueJump
    net_assets: NetAssets
    loss_trend: LossTrend
    debt_rise: DebtRise
    revenue_decline: RevenueDecline
    headcount: Headcount


def load_config(path: Path = CONFIG_PATH) -> FinancialsConfig:
    return FinancialsConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- helpers
def _pct(old: int, new: int) -> float:
    return round((new - old) / abs(old) * 100, 1)


def _window(years: list[FinancialYear], window_years: int) -> list[FinancialYear]:
    """Filed years inside the most recent `window_years` calendar years."""
    if not years:
        return []
    last = years[-1].year
    return [y for y in years if y.year > last - window_years]


# --------------------------------------------------------------------------- checks
def check_net_assets(latest: FinancialYear, cfg: NetAssets) -> dict[str, Any] | None:
    """FIN-NET-ASSETS-01. Zephyria 2025: equity -111,000 < 100 (= 1/2 of 200 share capital)."""
    if latest.equity is None or not latest.share_capital:
        return None
    threshold = latest.share_capital * cfg.max_equity_to_share_capital
    if latest.equity >= threshold:
        return None
    return {
        "year": latest.year,
        "equity": latest.equity,
        "share_capital": latest.share_capital,
        "threshold": threshold,
    }


def check_revenue_jump(years: list[FinancialYear], cfg: RevenueJump) -> dict[str, Any] | None:
    """FIN-REVENUE-JUMP-01. Consecutive years only. Reports the largest jump plus all jumps.
    Zephyria: 410k -> 1.9M (+363.4%), 1.9M -> 9.8M (+415.8%)."""
    jumps = []
    for prev, cur in pairwise(years):
        if cur.year != prev.year + 1 or prev.turnover is None or cur.turnover is None:
            continue
        if prev.turnover < cfg.min_base_turnover_ron:
            continue
        growth = _pct(prev.turnover, cur.turnover)
        if growth > cfg.min_growth_pct:
            jumps.append(
                {
                    "from_year": prev.year,
                    "to_year": cur.year,
                    "from_turnover": prev.turnover,
                    "to_turnover": cur.turnover,
                    "growth_pct": growth,
                }
            )
    if not jumps:
        return None
    largest = max(jumps, key=lambda j: j["growth_pct"])
    return {**largest, "all_jumps": jumps}


def check_headcount(
    latest: FinancialYear, caen: str | None, cfg: Headcount
) -> dict[str, Any] | None:
    """FIN-HEADCOUNT-01. Zephyria 2025 (CAEN 49): 18.6M RON / 2 employees = 9.3M per employee."""
    if not latest.turnover or not latest.employees or latest.employees <= 0:
        return None
    digits = "".join(ch for ch in (caen or "") if ch.isdigit())
    # ANAF v9 drops leading zeros ("610" is 0610, oil extraction): pad before taking the division.
    division = digits.zfill(4)[:2] if digits else ""
    average = cfg.caen_avg_turnover_per_employee_ron.get(division, cfg.fallback_avg_ron)
    if average is None:
        return None  # no benchmark for this sector: a generic average would only make noise
    per_employee = latest.turnover // latest.employees
    if per_employee <= average * cfg.multiplier:
        return None
    return {
        "year": latest.year,
        "turnover": latest.turnover,
        "employees": latest.employees,
        "turnover_per_employee": per_employee,
        "caen_division": division or None,
        "caen_avg_turnover_per_employee": average,
        "ratio_to_avg": round(per_employee / average, 1),
        "average_is_proposal": True,
    }


def check_loss_trend(years: list[FinancialYear], cfg: LossTrend) -> dict[str, Any] | None:
    """FIN-LOSS-TREND-01. The most recent run of consecutive loss years. Brunaldo: 2023-2025."""
    runs: list[list[FinancialYear]] = []
    for y in years:
        if y.net_profit is not None and y.net_profit < 0:
            if runs and runs[-1][-1].year == y.year - 1:
                runs[-1].append(y)
            else:
                runs.append([y])
    qualifying = [r for r in runs if len(r) >= cfg.min_consecutive_years]
    if not qualifying:
        return None
    run = qualifying[-1]
    return {
        "from_year": run[0].year,
        "to_year": run[-1].year,
        "years": len(run),
        "net_profit": {str(y.year): y.net_profit for y in run},
    }


def check_debt_rise(years: list[FinancialYear], cfg: DebtRise) -> dict[str, Any] | None:
    """FIN-DEBT-RISE-01. First vs last filed year in the window. Needs both debts and turnover."""
    window = [
        y
        for y in _window(years, cfg.window_years)
        if y.total_debts is not None and y.turnover is not None
    ]
    if len(window) < 2:
        return None
    first, last = window[0], window[-1]
    if not first.total_debts or not first.turnover:
        return None
    debt_growth = _pct(first.total_debts, last.total_debts or 0)
    turnover_growth = _pct(first.turnover, last.turnover or 0)
    if debt_growth <= cfg.min_debt_growth_pct or turnover_growth > cfg.max_turnover_growth_pct:
        return None
    return {
        "from_year": first.year,
        "to_year": last.year,
        "debts": {str(first.year): first.total_debts, str(last.year): last.total_debts},
        "turnover": {str(first.year): first.turnover, str(last.year): last.turnover},
        "debt_growth_pct": debt_growth,
        "turnover_growth_pct": turnover_growth,
    }


def check_revenue_decline(years: list[FinancialYear], cfg: RevenueDecline) -> dict[str, Any] | None:
    """FIN-REVENUE-DECLINE-01. Brunaldo: 29.1M (2023) -> 15.2M (2025), -47.8%."""
    window = [y for y in _window(years, cfg.window_years) if y.turnover is not None]
    if len(window) < 2 or not window[0].turnover:
        return None
    first, last = window[0], window[-1]
    change = _pct(first.turnover or 0, last.turnover or 0)
    if -change <= cfg.min_drop_pct:
        return None
    return {
        "from_year": first.year,
        "to_year": last.year,
        "turnover": {str(first.year): first.turnover, str(last.year): last.turnover},
        "change_pct": change,
    }


def check_no_filing(
    fetched: dict[int, FinancialYear | None], expected_last_year: int
) -> dict[str, Any] | None:
    """FIN-NO-FILING-01. Only when the source ANSWERED for that year and nothing was filed.
    A year the source could not be read for is unknown, not a missing filing."""
    if expected_last_year in fetched and fetched[expected_last_year] is None:
        return {"year": expected_last_year}
    return None


def expected_last_year(today_year: int, today_month: int, available_from_month: int) -> int:
    return today_year - 1 if today_month >= available_from_month else today_year - 2
