"""The ANAF fetch tool: dry run by default, ONE request per run, spacing across runs.
Every network test uses a simulated ANAF (httpx.MockTransport). Nothing reaches the real ANAF."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest

from apps.worker.jobs import sweep_anaf_v9 as tool
from verifirm.adapters.anaf_bilant import AnafBilantAdapter
from verifirm.adapters.anaf_v9 import AnafV9Adapter
from verifirm.adapters.base import AdapterDeps
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter

NOW = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)
DEDEMAN, DACIA = "2816464", "160796"


class _Anaf:
    """Fake ANAF for both services. Records every request."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "POST":  # v9
            sent = json.loads(request.content)
            found = [
                {"date_generale": {"cui": e["cui"], "data": e["data"], "denumire": "FIRMA SRL"}}
                for e in sent
            ]
            return httpx.Response(200, json={"found": found, "notFound": []})
        year = int(request.url.params["an"])  # /bilant
        rows = [
            {"indicator": "I1", "val_indicator": 1, "val_den_indicator": "Cifra de afaceri neta"}
        ]
        return httpx.Response(200, json={"an": year, "cui": 1, "i": rows})


def _infra(tmp_path: Path, anaf: _Anaf) -> Any:
    deps = AdapterDeps(
        settings=Settings(fixture_mode=False, http_max_retries=0),
        cache=MemoryCache(),
        object_store=FilesystemObjectStore(tmp_path / "objects"),
        rate_limiter=MemoryRateLimiter(),
        clock=FixedClock(NOW),
        http=httpx.AsyncClient(transport=httpx.MockTransport(anaf)),
        network=True,
    )
    adapters = {"anaf_v9": AnafV9Adapter(deps), "anaf_bilant": AnafBilantAdapter(deps)}
    return SimpleNamespace(sync_adapters=adapters, clock=FixedClock(NOW))


# --------------------------------------------------------------------- the spacing guard
async def test_slot_waits_for_the_previous_request(tmp_path: Path) -> None:
    stamp = tmp_path / "stamp"
    stamp.write_text("1000.000")
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    async def send() -> str:
        return "sent"

    result = await tool.anaf_slot(stamp, send, now=lambda: 1000.4, sleep=sleep)
    assert result == "sent"
    assert slept == [pytest.approx(0.7)]  # 1.1 s after the previous one
    assert float(stamp.read_text()) == pytest.approx(1000.4)


async def test_slot_does_not_wait_after_a_long_pause(tmp_path: Path) -> None:
    stamp = tmp_path / "stamp"
    stamp.write_text("1000.000")
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    async def send() -> None:
        return None

    await tool.anaf_slot(stamp, send, now=lambda: 2000.0, sleep=sleep)
    assert slept == []


async def test_slot_on_a_fresh_machine(tmp_path: Path) -> None:
    async def send() -> int:
        return 1

    assert await tool.anaf_slot(tmp_path / "new" / "stamp", send) == 1


# ------------------------------------------------------------------------- the CUI gate
def test_only_real_cuis() -> None:
    assert tool.real_cuis([DEDEMAN, "RO160796", DEDEMAN]) == [DEDEMAN, DACIA]
    with pytest.raises(SystemExit, match="fictional"):
        tool.real_cuis(["99000025"])
    with pytest.raises(SystemExit, match="checksum"):
        tool.real_cuis(["2816465"])


# --------------------------------------------------------------------------------- v9
async def test_v9_dry_run_sends_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    anaf = _Anaf()
    await tool.cmd_v9(_infra(tmp_path, anaf), [DEDEMAN, DACIA], False, tmp_path / "stamp")
    assert anaf.requests == []
    out = capsys.readouterr().out
    assert "ONE request, 10 entries" in out and "dry run" in out


async def test_v9_send_is_exactly_one_request(tmp_path: Path) -> None:
    anaf = _Anaf()
    infra = _infra(tmp_path, anaf)
    await tool.cmd_v9(infra, [DEDEMAN, DACIA], True, tmp_path / "stamp")
    assert len(anaf.requests) == 1
    body = json.loads(anaf.requests[0].content)
    assert len(body) == 10  # 2 companies x (today + 4 quarter-ends)
    assert {e["data"] for e in body} == {
        "2026-10-28",
        "2026-09-30",
        "2026-06-30",
        "2026-03-31",
        "2025-12-31",
    }
    await tool.cmd_v9(infra, [DEDEMAN, DACIA], True, tmp_path / "stamp")  # nothing missing now
    assert len(anaf.requests) == 1


async def test_v9_more_than_100_entries_is_refused(tmp_path: Path) -> None:
    anaf = _Anaf()
    v9 = cast(AnafV9Adapter, _infra(tmp_path, anaf).sync_adapters["anaf_v9"])
    with pytest.raises(SystemExit, match="100 per request"):
        await tool.plan_v9(v9, [str(1000 + i) for i in range(21)])  # 21 x 5 = 105
    assert anaf.requests == []


# ----------------------------------------------------------------------------- bilant
async def test_bilant_one_year_per_run_newest_first(tmp_path: Path) -> None:
    anaf = _Anaf()
    infra = _infra(tmp_path, anaf)
    await tool.cmd_bilant(infra, DEDEMAN, False, tmp_path / "stamp")
    assert anaf.requests == []  # dry run

    await tool.cmd_bilant(infra, DEDEMAN, True, tmp_path / "stamp")
    await tool.cmd_bilant(infra, DEDEMAN, True, tmp_path / "stamp")
    assert [r.url.params["an"] for r in anaf.requests] == ["2025", "2024"]  # one per run


def test_bilant_years_follow_the_financials_agent() -> None:
    assert tool.bilant_years(NOW.date()) == [2025, 2024, 2023, 2022, 2021]


def test_bilant_takes_one_cui_per_run() -> None:
    with pytest.raises(SystemExit, match="one CUI per run"):
        tool.main(["bilant", DEDEMAN, DACIA])


# --------------------------------------------------------------------------- not automated
async def test_scheduled_sweep_never_calls_anaf_on_its_own() -> None:
    with pytest.raises(NotImplementedError, match="human"):
        await tool.run(cast(Any, None))
