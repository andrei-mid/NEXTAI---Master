import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from verifirm.adapters.anaf_bilant import AnafBilantAdapter, normalize_label, parse_bilant
from verifirm.adapters.base import AdapterDeps
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter
from verifirm.core.ports.rate_limiter import RateLimit, RateLimiter
from verifirm.schema.signals import SourceRef, SourceType

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
SRC = SourceRef(name="t", type=SourceType.OFFICIAL, retrieved_at=datetime(2026, 1, 1, tzinfo=UTC))
NOW = datetime(2026, 10, 28, tzinfo=UTC)


class _NoLimit(RateLimiter):
    async def acquire(self, key: str, limit: RateLimit) -> None:
        return None


def _adapter(
    tmp_path: Path,
    *,
    fixture_mode: bool,
    fixtures_dir: Path = FIXTURES,
    transport: httpx.MockTransport | None = None,
    network: bool = False,
    now: datetime = NOW,
) -> AnafBilantAdapter:
    return AnafBilantAdapter(
        AdapterDeps(
            settings=Settings(
                fixture_mode=fixture_mode, fixtures_dir=fixtures_dir, http_max_retries=0
            ),
            cache=MemoryCache(),
            object_store=FilesystemObjectStore(tmp_path / "objects"),
            rate_limiter=_NoLimit() if transport else MemoryRateLimiter(),
            clock=FixedClock(now),
            http=httpx.AsyncClient(transport=transport) if transport else None,
            network=network,
        )
    )


class _Anaf:
    """Fake /bilant: statements filed for 2021..filed_until. Counts calls per year."""

    def __init__(self, filed_until: int = 2025) -> None:
        self.calls: list[int] = []
        self.filed_until = filed_until

    def __call__(self, request: httpx.Request) -> httpx.Response:
        year = int(request.url.params["an"])
        self.calls.append(year)
        rows = (
            [
                {
                    "indicator": "I13",
                    "val_indicator": year,
                    "val_den_indicator": "Cifra de afaceri neta",
                }
            ]
            if 2021 <= year <= self.filed_until
            else []
        )
        return httpx.Response(200, json={"an": year, "cui": 2816464, "i": rows})


async def test_sync_downloads_once_and_never_again_for_filed_years(tmp_path: Path) -> None:
    anaf = _Anaf(filed_until=2024)  # the 2025 statement is not filed yet
    syncer = _adapter(
        tmp_path, fixture_mode=False, transport=httpx.MockTransport(anaf), network=True
    )
    first = await syncer.sync("2816464")
    assert (first.downloaded, first.reused, first.failed) == (6, 0, [])
    assert sorted(anaf.calls) == [2020, 2021, 2022, 2023, 2024, 2025]

    second = await syncer.sync("2816464")  # same day: everything reused, zero calls
    assert (second.downloaded, second.reused) == (0, 6) and len(anaf.calls) == 6

    anaf.filed_until = 2025  # meanwhile the company filed 2025
    a_year_later = _adapter(
        tmp_path,
        fixture_mode=False,
        transport=httpx.MockTransport(anaf),
        network=True,
        now=NOW + timedelta(days=365),
    )
    third = await a_year_later.sync("2816464")  # window is now 2021-2026
    # 2021-2024 were filed -> never asked again. 2025 ("not filed" answer expired) and 2026 are.
    assert sorted(anaf.calls[6:]) == [2025, 2026] and third.reused == 4


async def test_agents_read_the_synced_mirror_without_calls(tmp_path: Path) -> None:
    anaf = _Anaf()
    await _adapter(
        tmp_path, fixture_mode=False, transport=httpx.MockTransport(anaf), network=True
    ).sync("2816464")
    reader = _adapter(tmp_path, fixture_mode=False, network=False)
    history = await reader.get_history("2816464", 2025, 5)
    assert [y.turnover for y in history.filed] == [2021, 2022, 2023, 2024, 2025]
    assert history.failed == [] and not any(s.stale for s in history.years.values())
    assert len(anaf.calls) == 6


async def test_agents_without_sync_get_unavailable_not_clean(tmp_path: Path) -> None:
    history = await _adapter(tmp_path, fixture_mode=False, network=False).get_history(
        "2816464", 2025, 5
    )
    assert history.years == {} and history.failed == [2021, 2022, 2023, 2024, 2025]


def test_normalize_label() -> None:
    assert normalize_label("Capitaluri - total, din care:") == "capitaluri total din care"
    assert normalize_label("Număr mediu de salariaţi") == "numar mediu de salariati"


def test_parse_small_company_format() -> None:
    payload = json.loads(
        (FIXTURES / "companies/99000025_zephyria_logistic_nova/bilant_2025.json").read_text(
            encoding="utf-8"
        )
    )
    y = parse_bilant(payload, SRC)
    assert y is not None
    assert (
        y.year,
        y.turnover,
        y.net_profit,
        y.total_debts,
        y.equity,
        y.share_capital,
        y.employees,
    ) == (2025, 18_600_000, -350_000, 14_200_000, -111_000, 200, 2)


def test_parse_large_company_format_sums_split_debts_and_reads_diacritics() -> None:
    payload = {
        "an": 2025,
        "i": [
            {
                "indicator": "I1",
                "val_indicator": 100.0,
                "val_den_indicator": "Cifra de afaceri netă",
            },
            {
                "indicator": "I2",
                "val_indicator": 30,
                "val_den_indicator": "DATORII CE TREBUIE PLATITE INTR-O PERIOADA DE PANA LA UN AN",
            },
            {
                "indicator": "I3",
                "val_indicator": 20,
                "val_den_indicator": "DATORII CE TREBUIE PLATITE INTR-O PERIOADA MAI MARE DE UN AN",
            },
            {
                "indicator": "I4",
                "val_indicator": 70,
                "val_den_indicator": "CAPITALURI PROPRII - TOTAL",
            },
            {"indicator": "I5", "val_indicator": 7, "val_den_indicator": "Profit net"},
        ],
    }
    y = parse_bilant(payload, SRC)
    assert y is not None and (y.turnover, y.total_debts, y.equity, y.net_profit) == (100, 50, 70, 7)


def test_empty_statement_means_not_filed() -> None:
    assert parse_bilant({"an": 2025, "cui": 1, "deni": "", "i": []}, SRC) is None


async def test_fixture_history(tmp_path: Path) -> None:
    history = await _adapter(tmp_path, fixture_mode=True).get_history("99000033", 2025, 5)
    assert history.failed == [] and [y.year for y in history.filed] == [
        2021,
        2022,
        2023,
        2024,
        2025,
    ]
    assert (
        history.years[2025].source.raw_ref
        == "fixture:companies/99000033_brunaldo_trade_impex/bilant_2025.json"
    )


async def test_missing_years_are_failed_not_clean(tmp_path: Path) -> None:
    history = await _adapter(tmp_path, fixture_mode=True).get_history(
        "99000025", 2025, 7
    )  # 2019-2020 absent
    assert history.failed == [2019, 2020] and len(history.filed) == 5


async def test_live_call_shape(tmp_path: Path) -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(
            200,
            json={
                "an": 2025,
                "cui": 2816464,
                "i": [
                    {
                        "indicator": "I13",
                        "val_indicator": 5,
                        "val_den_indicator": "Cifra de afaceri neta",
                    }
                ],
            },
        )

    adapter = _adapter(
        tmp_path, fixture_mode=False, transport=httpx.MockTransport(handler), network=True
    )
    result = await adapter.get_year("2816464", 2025)
    assert result.data is not None and result.data.turnover == 5
    assert seen[0].params["an"] == "2025" and seen[0].params["cui"] == "2816464"
    assert result.source.content_hash and str(result.source.url).startswith(
        "https://webservicesp.anaf.ro/bilant"
    )
