from datetime import UTC, datetime

import pytest

from verifirm.agents.financials import rules
from verifirm.schema.financials import FinancialYear
from verifirm.schema.signals import SourceRef, SourceType

SRC = SourceRef(name="t", type=SourceType.OFFICIAL, retrieved_at=datetime(2026, 1, 1, tzinfo=UTC))
CFG = rules.load_config()


def fy(year: int, **kw: int | None) -> FinancialYear:
    return FinancialYear(year=year, source=SRC, **kw)


# ---------------------------------------------------------------- net assets
def test_net_assets_below_half() -> None:
    f = rules.check_net_assets(fy(2025, equity=-111_000, share_capital=200), CFG.net_assets)
    assert f == {"year": 2025, "equity": -111_000, "share_capital": 200, "threshold": 100.0}


@pytest.mark.parametrize(
    "equity,capital", [(100, 200), (5_000, 200), (None, 200), (-5, None), (-5, 0)]
)
def test_net_assets_no_signal(equity: int | None, capital: int | None) -> None:
    assert (
        rules.check_net_assets(fy(2025, equity=equity, share_capital=capital), CFG.net_assets)
        is None
    )


# ---------------------------------------------------------------- revenue jump
def test_revenue_jump_reports_largest() -> None:
    years = [fy(2022, turnover=410_000), fy(2023, turnover=1_900_000), fy(2024, turnover=9_800_000)]
    f = rules.check_revenue_jump(years, CFG.revenue_jump)
    assert f is not None and (f["from_year"], f["to_year"], f["growth_pct"]) == (2023, 2024, 415.8)
    assert len(f["all_jumps"]) == 2


def test_revenue_jump_exactly_300_is_not_flagged() -> None:
    assert (
        rules.check_revenue_jump(
            [fy(2024, turnover=1_000_000), fy(2025, turnover=4_000_000)], CFG.revenue_jump
        )
        is None
    )


def test_revenue_jump_ignores_tiny_base_and_gaps() -> None:
    tiny = [fy(2024, turnover=10_000), fy(2025, turnover=900_000)]
    gap = [fy(2022, turnover=200_000), fy(2025, turnover=5_000_000)]  # 2023-2024 not filed
    assert rules.check_revenue_jump(tiny, CFG.revenue_jump) is None
    assert rules.check_revenue_jump(gap, CFG.revenue_jump) is None


# ---------------------------------------------------------------- headcount
def test_headcount_against_caen_average() -> None:
    f = rules.check_headcount(fy(2025, turnover=18_600_000, employees=2), "4941", CFG.headcount)
    assert f is not None and f["turnover_per_employee"] == 9_300_000 and f["caen_division"] == "49"


def test_headcount_uses_fallback_and_skips_zero_employees() -> None:
    assert (
        rules.check_headcount(fy(2025, turnover=18_600_000, employees=0), "4941", CFG.headcount)
        is None
    )
    # Unlisted division: no benchmark, no comparison (real data: Hidroelectrica, Petrom, Dacia).
    assert (
        rules.check_headcount(fy(2025, turnover=30_000_000, employees=1), "9999", CFG.headcount)
        is None
    )
    with_fallback = CFG.headcount.model_copy(update={"fallback_avg_ron": 500_000})
    f = rules.check_headcount(fy(2025, turnover=30_000_000, employees=1), "9999", with_fallback)
    assert f is not None and f["caen_avg_turnover_per_employee"] == 500_000


def test_headcount_pads_caen_codes_anaf_sends_without_leading_zero() -> None:
    """ANAF v9 sends Petrom's 0610 (oil extraction) as "610": that is division 06, not 61."""
    table = {"06": 10_000_000}
    cfg = CFG.headcount.model_copy(update={"caen_avg_turnover_per_employee_ron": table})
    f = rules.check_headcount(fy(2025, turnover=600_000_000, employees=1), "610", cfg)
    assert f is not None and f["caen_division"] == "06"


def test_headcount_normal_company() -> None:
    assert (
        rules.check_headcount(fy(2025, turnover=4_600_000, employees=36), "6201", CFG.headcount)
        is None
    )


# ---------------------------------------------------------------- loss trend
def test_loss_trend_most_recent_run() -> None:
    years = [
        fy(2021, net_profit=-1),
        fy(2022, net_profit=-1),
        fy(2023, net_profit=5),
        fy(2024, net_profit=-400_000),
        fy(2025, net_profit=-2_600_000),
    ]
    f = rules.check_loss_trend(years, CFG.loss_trend)
    assert f is not None and (f["from_year"], f["to_year"]) == (2024, 2025)


def test_single_loss_or_gap_is_not_a_trend() -> None:
    assert (
        rules.check_loss_trend(
            [fy(2024, net_profit=5), fy(2025, net_profit=-350_000)], CFG.loss_trend
        )
        is None
    )
    assert (
        rules.check_loss_trend([fy(2023, net_profit=-1), fy(2025, net_profit=-1)], CFG.loss_trend)
        is None
    )


# ---------------------------------------------------------------- debt rise
def test_debt_rise_with_stagnant_revenue() -> None:
    years = [
        fy(2023, total_debts=1_000_000, turnover=5_000_000),
        fy(2024, total_debts=1_200_000, turnover=5_100_000),
        fy(2025, total_debts=1_600_000, turnover=5_400_000),
    ]  # debts +60%, turnover +8%
    f = rules.check_debt_rise(years, CFG.debt_rise)
    assert f is not None and f["debt_growth_pct"] == 60.0 and f["turnover_growth_pct"] == 8.0


def test_debt_rise_with_falling_revenue_counts() -> None:
    years = [
        fy(2023, total_debts=1_000_000, turnover=5_000_000),
        fy(2025, total_debts=2_000_000, turnover=3_000_000),
    ]
    assert rules.check_debt_rise(years, CFG.debt_rise) is not None


def test_debt_rise_not_flagged_when_revenue_grows() -> None:  # Zephyria
    years = [
        fy(2023, total_debts=1_100_000, turnover=1_900_000),
        fy(2025, total_debts=14_200_000, turnover=18_600_000),
    ]
    assert rules.check_debt_rise(years, CFG.debt_rise) is None


def test_debt_rise_window_is_three_years() -> None:  # Brunaldo: 2023 -> 2025 only +36.6%
    years = [
        fy(2021, total_debts=9_800_000, turnover=32_000_000),
        fy(2023, total_debts=14_200_000, turnover=29_100_000),
        fy(2025, total_debts=19_400_000, turnover=15_200_000),
    ]
    assert rules.check_debt_rise(years, CFG.debt_rise) is None


# ---------------------------------------------------------------- revenue decline / no filing
def test_revenue_decline() -> None:
    years = [
        fy(2023, turnover=29_100_000),
        fy(2024, turnover=21_700_000),
        fy(2025, turnover=15_200_000),
    ]
    f = rules.check_revenue_decline(years, CFG.revenue_decline)
    assert f is not None and f["change_pct"] == -47.8


def test_no_filing_only_when_source_answered() -> None:
    assert rules.check_no_filing({2025: None}, 2025) == {"year": 2025}
    assert rules.check_no_filing({2024: None}, 2025) is None  # 2025 unreadable = unknown


@pytest.mark.parametrize("month,expected", [(6, 2024), (7, 2025), (12, 2025)])
def test_expected_last_year(month: int, expected: int) -> None:
    assert rules.expected_last_year(2026, month, 7) == expected
