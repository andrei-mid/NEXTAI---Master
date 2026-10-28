import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from verifirm.adapters.anaf_v9 import AnafV9Adapter, split_response
from verifirm.adapters.base import AdapterDeps, SourceUnavailable
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.ports.rate_limiter import RateLimit, RateLimiter

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
TODAY = date(2026, 10, 28)


class _NoLimit(RateLimiter):
    async def acquire(self, key: str, limit: RateLimit) -> None:
        return None


class _Anaf:
    """Fake v9: every CUI ending in 0 is notFound, the rest are found."""

    def __init__(self) -> None:
        self.bodies: list[list[dict[str, object]]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.bodies.append(body)
        found = [
            {
                "date_generale": {"cui": item["cui"], "denumire": f"FIRMA {item['cui']}"},
                "stare_inactiv": {"statusInactivi": False},
            }
            for item in body
            if str(item["cui"])[-1] != "0"
        ]
        not_found = [item["cui"] for item in body if str(item["cui"])[-1] == "0"]
        return httpx.Response(
            200, json={"cod": 200, "message": "SUCCESS", "found": found, "notFound": not_found}
        )


def _adapter(
    tmp_path: Path, *, network: bool, fixture_mode: bool = False, anaf: _Anaf | None = None
) -> AnafV9Adapter:
    return AnafV9Adapter(
        AdapterDeps(
            settings=Settings(fixture_mode=fixture_mode, fixtures_dir=FIXTURES, http_max_retries=0),
            cache=MemoryCache(),
            object_store=FilesystemObjectStore(tmp_path / "objects"),
            rate_limiter=_NoLimit(),
            clock=FixedClock(datetime(2026, 10, 28, tzinfo=UTC)),
            http=httpx.AsyncClient(transport=httpx.MockTransport(anaf)) if anaf else None,
            network=network,
        )
    )


def test_split_response_never_invents_a_clean_answer() -> None:
    payload = {"found": [{"date_generale": {"cui": 2816464}}], "notFound": [123]}
    out = split_response(payload, ["2816464", "123", "999"])
    assert out["2816464"] is not None and out["123"] is None and "999" not in out


async def test_fixture_lookup(tmp_path: Path) -> None:
    result = await _adapter(tmp_path, network=False, fixture_mode=True).lookup("99000025", TODAY)
    assert result.data is not None
    assert result.data["date_generale"]["denumire"] == "ZEPHYRIA LOGISTIC NOVA SRL"


async def test_sync_then_agents_read_the_mirror_without_calls(tmp_path: Path) -> None:
    anaf = _Anaf()
    report = await _adapter(tmp_path, network=True, anaf=anaf).sync("2816464")
    assert report.downloaded == 1 and anaf.bodies == [[{"cui": 2816464, "data": "2026-10-28"}]]

    reader = _adapter(tmp_path, network=False)
    record = await reader.lookup("2816464", TODAY)
    assert record.data is not None and record.data["date_generale"]["denumire"] == "FIRMA 2816464"
    assert len(anaf.bodies) == 1  # the agent made no call


async def test_not_found_is_none_and_unsynced_is_unavailable(tmp_path: Path) -> None:
    await _adapter(tmp_path, network=True, anaf=_Anaf()).sync("1230")
    assert (await _adapter(tmp_path, network=False).lookup("1230", TODAY)).data is None
    with pytest.raises(SourceUnavailable, match="local mirror"):
        await _adapter(tmp_path, network=False).lookup("2816464", TODAY)


async def test_batch_100_per_call_and_one_mirror_entry_per_cui(tmp_path: Path) -> None:
    anaf = _Anaf()
    cuis = [str(1000001 + i) for i in range(150)]
    batch = await _adapter(tmp_path, network=True, anaf=anaf).lookup_batch(cuis, TODAY)
    assert [len(b) for b in anaf.bodies] == [100, 50]
    assert len(batch.data) == 150
    reader = _adapter(tmp_path, network=False)
    one = await reader.lookup(cuis[42], TODAY)
    assert one.data is not None and len(anaf.bodies) == 2
