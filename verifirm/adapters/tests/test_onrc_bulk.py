from datetime import UTC, datetime
from pathlib import Path

import pytest

from verifirm.adapters.base import AdapterDeps, SourceUnavailable
from verifirm.adapters.onrc_bulk import (
    OnrcBulkAdapter,
    OnrcIndex,
    RowStats,
    caen_revision,
    fold,
    normalize_address,
    parse_rows,
    person_match,
    sniff_format,
)
from verifirm.core.config import Settings
from verifirm.core.impl_local.cache import MemoryCache
from verifirm.core.impl_local.clock import FixedClock
from verifirm.core.impl_local.object_store import FilesystemObjectStore
from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
NOW = datetime(2026, 10, 28, tzinfo=UTC)
ZEPHYRIA, AURORA, KESTREL, CALBRONA = "99000025", "99000017", "99000041", "99000090"
ZEPHYRIA_OFFICE = "Str. Exemplului nr. 1, Sector 9, București"


def _adapter(tmp_path: Path, *, fixture_mode: bool = True) -> OnrcBulkAdapter:
    return OnrcBulkAdapter(
        AdapterDeps(
            settings=Settings(fixture_mode=fixture_mode, fixtures_dir=FIXTURES),
            cache=MemoryCache(),
            object_store=FilesystemObjectStore(tmp_path / "objects"),
            rate_limiter=MemoryRateLimiter(),
            clock=FixedClock(NOW),
        )
    )


# ---------------------------------------------------------------------- normalization
def test_fold_strips_diacritics_both_cedilla_and_comma() -> None:
    assert fold("Județul Fictiv, ŞTEFĂNEŞTI / Ștefănești") == "judetul fictiv stefanesti stefanesti"


@pytest.mark.parametrize(
    "variant",
    [
        "STR. EXEMPLULUI NR. 1, SECTOR 9, BUCURESTI",
        "Strada Exemplului, numărul 1, Sectorul 9, București",
        "  str exemplului   nr 1 sector 9 bucurești ",
    ],
)
def test_address_variants_normalize_equal(variant: str) -> None:
    assert normalize_address(variant) == normalize_address(ZEPHYRIA_OFFICE)


def test_boulevard_spellings_are_equal() -> None:
    assert normalize_address("B-dul Inventat 42") == normalize_address("Bulevardul Inventat 42")
    assert normalize_address("Bd. Inventat 42") == "bd inventat 42"


def test_person_match_scores() -> None:
    assert person_match("Ionel Fictivescu", "IONEL FICTIVESCU") == 1.0
    assert person_match("FICTIVESCU IONEL", "IONEL FICTIVESCU") == 0.9
    assert person_match("IONEL FICTIVESCU", "IONELA FICTIVESCU") is None
    assert person_match("", "IONEL FICTIVESCU") is None


def test_caen_revision() -> None:
    assert (caen_revision("2"), caen_revision("rev3"), caen_revision("")) == (
        "rev2",
        "rev3",
        "unknown",
    )


# ---------------------------------------------------------------------- CSV parsing
def test_sniff_caret_utf8_and_cp1250() -> None:
    assert sniff_format("A^B\n1^ț\n".encode()).delimiter == "^"
    assert sniff_format("A^B\n1^ț\n".encode()).encoding == "utf-8-sig"
    assert sniff_format("A;B\n1;ş\n".encode("cp1250")).encoding == "cp1250"
    assert sniff_format(b"A;B\n").delimiter == ";"


def test_sniff_ignores_multibyte_char_cut_at_the_end() -> None:
    head = "A^B\n1^ț".encode()[:-1]  # 'ț' is 2 bytes in UTF-8, cut in half
    assert sniff_format(head).encoding == "utf-8-sig"


def test_sniff_refuses_unknown_delimiter() -> None:
    with pytest.raises(ValueError):
        sniff_format(b"just one column\n")


def test_parse_rows_skips_and_counts_malformed() -> None:
    stats = RowStats()
    body = '﻿cui^denumire\n1^SC "ABC" SRL\n2^too^many\n\n3^OK SRL\n'.encode()
    rows = parse_rows(body, stats)
    assert rows == [{"CUI": "1", "DENUMIRE": 'SC "ABC" SRL'}, {"CUI": "3", "DENUMIRE": "OK SRL"}]
    assert (stats.rows, stats.malformed) == (2, 1)


async def test_iter_rows_streams_in_batches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import verifirm.adapters.onrc_bulk as onrc

    monkeypatch.setattr(onrc, "ROWS_PER_BATCH", 3)
    path = tmp_path / "OD_FIRME.CSV"
    lines = ["DENUMIRE^CUI"] + [f"FIRMA {i} SRL^{i}" for i in range(10)] + ["BROKEN"]
    path.write_text("\n".join(lines) + "\n", encoding="cp1250")
    stats = RowStats()
    rows = [r async for r in _adapter(tmp_path).iter_rows(path, stats)]
    assert [r["CUI"] for r in rows] == [str(i) for i in range(10)]
    assert (stats.rows, stats.malformed) == (10, 1)


async def test_iter_rows_reads_the_real_sample(tmp_path: Path) -> None:
    path = FIXTURES / "sources" / "onrc" / "OD_FIRME_sample.csv"
    rows = [r async for r in _adapter(tmp_path).iter_rows(path)]
    assert len(rows) == 71
    assert rows[1]["ADRESA_COMPLETA"] == ZEPHYRIA_OFFICE


# ---------------------------------------------------------------------- READ methods
async def test_company_serves_onrc_json_unchanged(tmp_path: Path) -> None:
    got = await _adapter(tmp_path).company(ZEPHYRIA)
    assert got.data is not None
    assert got.data["denumire"] == "ZEPHYRIA LOGISTIC NOVA SRL"
    assert got.data["cod_inmatriculare"] == "J99/1234/2021"
    assert got.source.raw_ref == "fixture:companies/99000025_zephyria_logistic_nova/onrc.json"
    assert got.source.type.value == "official"


async def test_company_from_sample_csvs_when_no_onrc_json(tmp_path: Path) -> None:
    got = await _adapter(tmp_path).company("99001570")  # a shell company, sample rows only
    assert got.data is not None
    assert got.data["denumire"] == "FIRMA PARAVAN FICTIVA 58 SRL"
    assert got.data["adresa"] == ZEPHYRIA_OFFICE
    assert got.data["fictional"] is True
    assert got.data["istoric_sedii"] == [] and got.data["caen_principal"] is None
    assert got.source.raw_ref == "fixture:sources/onrc/OD_FIRME_sample.csv"


async def test_sample_record_has_same_keys_as_onrc_json(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    curated = (await adapter.company(ZEPHYRIA)).data
    assert curated is not None
    adapter._sample = None
    index, _ = await adapter._sample_index()
    built = index.record(ZEPHYRIA)
    assert built is not None
    assert set(built) == set(curated)
    for key in (
        "cui",
        "denumire",
        "cod_inmatriculare",
        "stare",
        "adresa",
        "judet",
        "reprezentanti",
    ):
        assert built[key] == curated[key], key


async def test_company_not_in_onrc_is_none(tmp_path: Path) -> None:
    got = await _adapter(tmp_path).company("99009999")
    assert got.data is None


async def test_zephyria_office_is_shared_by_63(tmp_path: Path) -> None:
    got = await _adapter(tmp_path).companies_at_address(ZEPHYRIA_OFFICE)
    assert len(got.data) == 63 and ZEPHYRIA in got.data
    upper = await _adapter(tmp_path).companies_at_address(ZEPHYRIA_OFFICE.upper())
    assert upper.data == got.data


async def test_single_company_address(tmp_path: Path) -> None:
    got = await _adapter(tmp_path).companies_at_address(
        "Str. Algoritmului nr. 7, Localitatea Fictivă, Județul Fictiv"
    )
    assert got.data == [AURORA]
    assert (await _adapter(tmp_path).companies_at_address("Str. Nicăieri 0")).data == []


def test_empty_addresses_never_match_each_other() -> None:
    index = OnrcIndex.build(
        [{"CUI": "1", "ADRESA_COMPLETA": ""}, {"CUI": "2", "ADRESA_COMPLETA": " , "}], [], [], []
    )
    assert index.at_address("") == [] and index.at_address(" , ") == []


async def test_companies_of_person_finds_affiliates_with_status(tmp_path: Path) -> None:
    got = await _adapter(tmp_path).companies_of_person("Ionel Fictivescu")
    by_reg = {a["cod_inmatriculare"]: a for a in got.data}
    assert set(by_reg) == {
        f"J99/{n}"
        for n in ("1234/2021", "3001/2018", "3002/2017", "3003/2020", "3004/2019", "3005/2022")
    }
    assert by_reg["J99/1234/2021"]["cui"] == ZEPHYRIA
    assert by_reg["J99/3001/2018"]["stare"] == "faliment"
    assert by_reg["J99/3002/2017"]["pana_la"] == "2023-07-20"
    assert by_reg["J99/3001/2018"]["cui"] == KESTREL
    assert all(
        a["match"] == {"method": "person_name", "score": 1.0, "ambiguous": False} for a in got.data
    )


async def test_companies_of_person_reversed_name_is_ambiguous(tmp_path: Path) -> None:
    got = await _adapter(tmp_path).companies_of_person("INEXISTENTU GELU")
    assert [a["cui"] for a in got.data] == [CALBRONA]
    assert got.data[0]["match"] == {"method": "person_name", "score": 0.9, "ambiguous": True}
    assert (await _adapter(tmp_path).companies_of_person("NIMENI NICIODATA")).data == []


async def test_sample_is_parsed_once(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    await adapter.companies_at_address(ZEPHYRIA_OFFICE)
    first = adapter._sample
    await adapter.companies_of_person("Ana Exemplescu")
    assert adapter._sample is first


# ---------------------------------------------------------------------- failure paths
@pytest.mark.parametrize(
    "call",
    [
        lambda a: a.company(ZEPHYRIA),
        lambda a: a.companies_at_address(ZEPHYRIA_OFFICE),
        lambda a: a.companies_of_person("Ionel Fictivescu"),
    ],
)
async def test_without_fixture_mode_is_unavailable_never_empty(tmp_path: Path, call) -> None:
    with pytest.raises(SourceUnavailable, match="not wired"):
        await call(_adapter(tmp_path, fixture_mode=False))


async def test_missing_sample_files_are_unavailable(tmp_path: Path) -> None:
    empty = tmp_path / "fixtures"
    (empty / "companies").mkdir(parents=True)
    adapter = OnrcBulkAdapter(
        AdapterDeps(
            settings=Settings(fixture_mode=True, fixtures_dir=empty),
            cache=MemoryCache(),
            object_store=FilesystemObjectStore(tmp_path / "objects"),
            rate_limiter=MemoryRateLimiter(),
            clock=FixedClock(NOW),
        )
    )
    with pytest.raises(SourceUnavailable):
        await adapter.companies_at_address(ZEPHYRIA_OFFICE)


async def test_sync_is_a_noop(tmp_path: Path) -> None:
    report = await _adapter(tmp_path).sync(ZEPHYRIA)
    assert report.skipped and report.downloaded == 0
