from datetime import UTC, datetime
from pathlib import Path

import pytest

from verifirm.adapters.anaf_v9 import AnafV9Adapter
from verifirm.adapters.base import AdapterDeps, BaseAdapter, SourceUnavailable
from verifirm.adapters.onrc_bulk import OnrcBulkAdapter
from verifirm.consolidation.identity_sheet import build_identity_sheet, short_legal_form
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter
from verifirm.schema.identity import CompanyStatus, PersonRole

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
CLOCK = FixedClock(datetime(2026, 10, 28, tzinfo=UTC))


def _adapters(tmp_path: Path, *, fixture_mode: bool = True) -> dict[str, BaseAdapter]:
    deps = AdapterDeps(
        settings=Settings(fixture_mode=fixture_mode, fixtures_dir=FIXTURES),
        cache=MemoryCache(),
        object_store=FilesystemObjectStore(tmp_path / "objects"),
        rate_limiter=MemoryRateLimiter(),
        clock=CLOCK,
    )
    return {"anaf_v9": AnafV9Adapter(deps), "onrc_bulk": OnrcBulkAdapter(deps)}


async def test_zephyria_from_anaf_and_onrc(tmp_path: Path) -> None:
    sheet = await build_identity_sheet("99000025", _adapters(tmp_path), CLOCK)
    assert sheet.current_name == "ZEPHYRIA LOGISTIC NOVA SRL" and sheet.fictional
    assert sheet.trade_register_no == "J99/1234/2021" and sheet.legal_form == "SRL"
    assert sheet.caen_code == "4941" and sheet.status == CompanyStatus.ACTIVE
    assert sheet.registered_office and sheet.registered_office.raw.startswith(
        "Str. Exemplului nr. 1"
    )
    admins = {p.name: p for p in sheet.administrators}
    assert admins["IONEL FICTIVESCU"].valid_to is None
    assert admins["MARCELA INVENTATU"].valid_to is not None
    assert all(p.role == PersonRole.ADMINISTRATOR for p in sheet.administrators)
    assert len(sheet.sources) == 2 and sheet.vat_registered is True


@pytest.mark.parametrize(
    "cui,status",
    [("99000074", CompanyStatus.INACTIVE_ANAF), ("99000058", CompanyStatus.DEREGISTERED)],
)
async def test_status_from_anaf(tmp_path: Path, cui: str, status: CompanyStatus) -> None:
    sheet = await build_identity_sheet(cui, _adapters(tmp_path), CLOCK)
    assert sheet.status == status


async def test_anaf_alone_is_enough(tmp_path: Path) -> None:
    adapters = _adapters(tmp_path)
    del adapters["onrc_bulk"]  # live ONRC isn't ingested yet
    sheet = await build_identity_sheet("99000033", adapters, CLOCK)
    assert sheet.current_name == "BRUNALDO TRADE IMPEX SRL"
    assert sheet.administrators == [] and len(sheet.sources) == 1


async def test_no_identity_source_stops_the_run(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailable):
        await build_identity_sheet("2816464", _adapters(tmp_path, fixture_mode=False), CLOCK)


@pytest.mark.parametrize(
    "anaf,short",
    [
        ("SOCIETATE COMERCIALĂ CU RĂSPUNDERE LIMITATĂ", "SRL"),
        ("SOCIETATE COMERCIALA PE ACTIUNI", "SA"),
        ("PERSOANĂ FIZICĂ AUTORIZATĂ", "PFA"),
        ("ÎNTREPRINDERE INDIVIDUALĂ", "II"),
        (None, None),
    ],
)
def test_short_legal_form(anaf: str | None, short: str | None) -> None:
    assert short_legal_form(anaf) == short
