from pathlib import Path

import httpx

from apps.wiring import build_infra
from apps.worker.jobs import sync_portfolio
from apps.worker.sync import sync_company
from verifirm.core.config import Settings
from verifirm.core.ports.rate_limiter import RateLimit, RateLimiter
from verifirm.schema.identity import IdentitySheet


class _NoLimit(RateLimiter):
    async def acquire(self, key: str, limit: RateLimit) -> None:
        return None


def _bilant(request: httpx.Request) -> httpx.Response:
    year = int(request.url.params["an"])
    rows = [{"indicator": "I13", "val_indicator": 1, "val_den_indicator": "Cifra de afaceri neta"}]
    return httpx.Response(200, json={"an": year, "cui": 2816464, "i": rows})


def _infra(tmp_path: Path, *, fixture_mode: bool = False):  # type: ignore[no-untyped-def]
    infra = build_infra(
        Settings(
            fixture_mode=fixture_mode, object_store_path=tmp_path / "objects", llm_provider="fake"
        )
    )
    infra.http = httpx.AsyncClient(transport=httpx.MockTransport(_bilant))
    infra.rate_limiter = _NoLimit()
    return infra


async def test_sync_company_reports_every_adapter_and_never_raises(tmp_path: Path) -> None:
    infra = _infra(tmp_path)
    reports = {r.adapter: r for r in await sync_company("2816464", infra, skip={"web_search"})}
    await infra.aclose()
    assert reports["anaf_bilant"].downloaded == 6
    assert "web_search" not in reports
    # stubs that are not implemented yet are reported, not crashed
    assert all(r.skipped or r.failed or r.downloaded or r.reused for r in reports.values())


async def test_agents_then_read_locally(tmp_path: Path) -> None:
    infra = _infra(tmp_path)
    await sync_company("2816464", infra)
    history = await infra.adapters["anaf_bilant"].get_history("2816464", 2025, 5)  # type: ignore[attr-defined]
    await infra.aclose()
    assert len(history.filed) == 5 and history.failed == []


async def test_fixture_mode_never_syncs(tmp_path: Path) -> None:
    infra = _infra(tmp_path, fixture_mode=True)
    assert await sync_company("99000025", infra) == []
    await infra.aclose()


async def test_sync_portfolio_job(tmp_path: Path) -> None:
    infra = _infra(tmp_path)
    await infra.repository.save_identity_sheet(
        "r", IdentitySheet(cui="2816464", current_name="DEDEMAN SRL")
    )
    report = await sync_portfolio.run(infra)
    await infra.aclose()
    assert report["companies"] == 1 and report["downloaded"] >= 6
