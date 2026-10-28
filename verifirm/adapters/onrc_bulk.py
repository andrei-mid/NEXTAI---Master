"""Owner: @role-1-database. ONRC trade-register open data (OFFICIAL, bulk).

Facts:
- data.gov.ro, licence CC BY 4.0 (attribute "ONRC"), refreshed roughly monthly.
- Files: OD_FIRME.CSV (~675 MB: name, CUI, reg. no., address, ...), OD_STARE_FIRMA.CSV
  (status codes), OD_CAEN_AUTORIZAT.CSV (authorized CAEN per company, Rev.2 and/or Rev.3),
  OD_REPREZENTANTI_LEGALI.CSV (administrators / legal representatives),
  OD_SUCURSALE_ALTE_STATE_MEMBRE.CSV (branches of EU companies).
- Has administrators, NO shareholders (shareholders are mocked: mocks/shareholders.py).
- BULK-LOAD it, NEVER call per company. Discover the current file URLs from the data.gov.ro
  dataset page / CKAN API at ingest time. Don't hard-code monthly URLs.
- Check the delimiter and encoding per file on download (historically `^`-separated).
  Stream line by line. The 675 MB file must never be read into memory.
- CAEN Rev.2 -> Rev.3 migration: keep both codes. The "CAEN not authorized" rule needs a
  Rev.2<->Rev.3 mapping table (put it in fixtures/sources/caen_rev2_rev3.csv).
- The bulk files are a snapshot: no name / office history. History comes from diffing
  snapshots (ingest_onrc), so records built from the CSVs have empty `istoric_*` lists.

Per-company record (`company(cui)`), the `fixtures/companies/*/onrc.json` shape:
  cui, denumire, cod_inmatriculare, data_inmatriculare, forma_juridica, stare, adresa, judet,
  caen_principal ({cod, revizie, denumire} | None), caen_autorizate [{cod, revizie}],
  istoric_denumiri [{denumire, de_la, pana_la}], istoric_sedii [{adresa, de_la, pana_la}],
  reprezentanti [{nume, calitate, de_la, pana_la}], fictional.
  `None` = the CUI is not in ONRC.

Where the READ methods get their data:
- FIXTURE_MODE=1: fixtures/companies/<cui>_<slug>/onrc.json when it exists, otherwise a record
  built from fixtures/sources/onrc/*_sample.csv (same columns as the real files, fictional
  rows). A company folder with neither -> None. A CUI with no fixture data at all ->
  SourceUnavailable (the fixtures are not the whole register). Address and person lookups use
  the sample CSVs.
- Otherwise: the Postgres onrc_* tables loaded by apps/worker/jobs/ingest_onrc.py. Adapters may
  not import persistence (tests/architecture/test_imports.py), so this needs the bulk-lookup
  port (PENDING in docs/DECISIONS.md). Until then the READ methods raise SourceUnavailable,
  which agents report as unavailable, never as clean.

Local-first (docs/LOCAL_DATA.md): bulk: the ingest_onrc job downloads and COPYs into Postgres. sync() stays the default no-op. READ methods query the local tables only.
"""

from __future__ import annotations

import asyncio
import csv
import io
import re
import unicodedata
from collections import defaultdict
from collections.abc import AsyncIterator, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

import httpx

from verifirm.adapters.base import BaseAdapter, Sourced, SourceUnavailable
from verifirm.core.logging import get_logger
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceRef, SourceType

log = get_logger(__name__)

DATASET_PAGE = (
    "https://data.gov.ro/dataset/firme-inregistrate-la-registrul-comertului-pana-la-data-de"
)
FILES = (
    "OD_FIRME.CSV",
    "OD_STARE_FIRMA.CSV",
    "OD_CAEN_AUTORIZAT.CSV",
    "OD_REPREZENTANTI_LEGALI.CSV",
    "OD_SUCURSALE_ALTE_STATE_MEMBRE.CSV",
)
SAMPLE_DIR = "onrc"  # fixtures/sources/onrc/<FILE stem>_sample.csv

DELIMITERS = ("^", ";", "|", ",", "\t")
SNIFF_BYTES = 64 * 1024
ROWS_PER_BATCH = 5_000  # rows parsed per worker-thread hop while streaming

# Address words that appear spelled out or abbreviated. Both sides are folded first.
_ADDRESS_WORDS = {
    "strada": "str",
    "bulevardul": "bd",
    "bulevard": "bd",
    "bdul": "bd",
    "blvd": "bd",
    "soseaua": "sos",
    "sosea": "sos",
    "numarul": "nr",
    "numar": "nr",
    "nr": "nr",
    "sectorul": "sector",
    "judetul": "jud",
    "judet": "jud",
    "municipiul": "mun",
    "localitatea": "loc",
    "aleea": "al",
    "piata": "pta",
    "blocul": "bl",
    "scara": "sc",
    "etajul": "et",
    "apartamentul": "ap",
}


# ---------------------------------------------------------------------- normalization (pure)
def fold(text: str) -> str:
    """Lowercase, no diacritics (ș/ş, ț/ţ, ă, â, î), punctuation -> spaces, single spaces."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", stripped).split())


def normalize_address(raw: str) -> str:
    """'Str. Exemplului nr. 1, Sector 9, București' -> 'str exemplului nr 1 sector 9 bucuresti'.

    Spelled-out and abbreviated street words compare equal ('Bulevardul' == 'Bd.', 'B-dul').
    """
    words = fold(raw.replace("B-dul", "Bd").replace("b-dul", "bd")).split()
    return " ".join(_ADDRESS_WORDS.get(w, w) for w in words)


def normalize_person_name(name: str) -> str:
    """'Ionel  Fictivescu' -> 'ionel fictivescu' (word order kept)."""
    return fold(name)


def person_match(query: str, candidate: str) -> float | None:
    """Score of a name-only match: 1.0 same words in the same order, 0.9 same words in another
    order ('POPESCU ION' vs 'ION POPESCU'), None otherwise."""
    q, c = normalize_person_name(query), normalize_person_name(candidate)
    if not q or not c:
        return None
    if q == c:
        return 1.0
    if sorted(q.split()) == sorted(c.split()):
        return 0.9
    return None


def caen_revision(version: str) -> str:
    """VERSIUNE_CAEN '2' / '3' (or 'rev2') -> 'rev2' / 'rev3'."""
    digits = re.sub(r"\D", "", version or "")
    return f"rev{digits}" if digits else "unknown"


def _empty_to_none(value: str | None) -> str | None:
    return value if value else None


def _is_true(value: str | None) -> bool:
    return (value or "").strip().lower() in {"true", "1", "da", "yes"}


# ---------------------------------------------------------------------- CSV parsing (pure)
@dataclass
class CsvFormat:
    delimiter: str
    encoding: str


def sniff_format(head: bytes) -> CsvFormat:
    """Delimiter and encoding from the first bytes of a file.

    Encoding: UTF-8 (BOM allowed) if the head decodes, otherwise cp1250 (Romanian legacy).
    A multi-byte character cut at the end of the head is ignored. Delimiter: the candidate
    that appears most often in the header line.
    """
    encoding = "utf-8-sig"
    try:
        head.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        if exc.reason != "unexpected end of data":  # not just a character cut by SNIFF_BYTES
            encoding = "cp1250"
    text = head.decode(encoding, errors="ignore")
    header = text.splitlines()[0] if text else ""
    delimiter = max(DELIMITERS, key=header.count)
    if header.count(delimiter) == 0:
        raise ValueError("no known delimiter in the header line")
    return CsvFormat(delimiter=delimiter, encoding=encoding)


@dataclass
class RowStats:
    rows: int = 0
    malformed: int = 0


def _reader(stream: TextIO, fmt: CsvFormat) -> Iterator[list[str]]:
    # `^` files are not quoted, and names contain stray quotes (SC "ABC" SRL): no quoting.
    if fmt.delimiter == "^":
        return csv.reader(stream, delimiter="^", quoting=csv.QUOTE_NONE)
    return csv.reader(stream, delimiter=fmt.delimiter)


def _dict_rows(
    rows: Iterable[list[str]], header: list[str], stats: RowStats
) -> Iterator[dict[str, str]]:
    for values in rows:
        if not values or (len(values) == 1 and not values[0].strip()):
            continue  # blank line
        if len(values) != len(header):
            stats.malformed += 1
            continue
        stats.rows += 1
        yield {key: value.strip() for key, value in zip(header, values, strict=True)}


def _header(values: list[str]) -> list[str]:
    return [h.strip().lstrip("﻿").upper() for h in values]


def parse_rows(body: bytes, stats: RowStats | None = None) -> list[dict[str, str]]:
    """Parse a whole (small) CSV body. Fixtures only: real files go through iter_rows."""
    stats = stats if stats is not None else RowStats()
    fmt = sniff_format(body[:SNIFF_BYTES])
    reader = _reader(io.StringIO(body.decode(fmt.encoding, errors="replace")), fmt)
    header = _header(next(reader, []))
    return list(_dict_rows(reader, header, stats))


# ---------------------------------------------------------------------- in-memory index
@dataclass
class OnrcIndex:
    """The four ONRC files joined in memory. Used for the fixture samples only (tiny)."""

    firms: dict[str, dict[str, str]] = field(default_factory=dict)  # cui -> OD_FIRME row
    cui_by_reg: dict[str, str] = field(default_factory=dict)
    status_by_reg: dict[str, str] = field(default_factory=dict)
    caen_by_reg: dict[str, list[dict[str, str]]] = field(default_factory=lambda: defaultdict(list))
    reps_by_reg: dict[str, list[dict[str, str]]] = field(default_factory=lambda: defaultdict(list))
    cuis_by_address: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    @classmethod
    def build(
        cls,
        firms: Iterable[dict[str, str]],
        status: Iterable[dict[str, str]],
        caen: Iterable[dict[str, str]],
        reps: Iterable[dict[str, str]],
    ) -> OnrcIndex:
        index = cls()
        for row in firms:
            cui = row.get("CUI", "")
            if not cui:
                continue
            index.firms[cui] = row
            index.cui_by_reg[row.get("COD_INMATRICULARE", "")] = cui
            address = normalize_address(row.get("ADRESA_COMPLETA", ""))
            if address:  # no address is not "the same address"
                index.cuis_by_address[address].append(cui)
        for row in status:
            index.status_by_reg[row.get("COD_INMATRICULARE", "")] = row.get("STARE", "")
        for row in caen:
            index.caen_by_reg[row.get("COD_INMATRICULARE", "")].append(row)
        for row in reps:
            index.reps_by_reg[row.get("COD_INMATRICULARE", "")].append(row)
        return index

    def record(self, cui: str) -> dict[str, Any] | None:
        firm = self.firms.get(cui)
        return (
            None
            if firm is None
            else record_from_rows(
                firm,
                self.status_by_reg.get(firm.get("COD_INMATRICULARE", "")),
                self.caen_by_reg.get(firm.get("COD_INMATRICULARE", ""), []),
                self.reps_by_reg.get(firm.get("COD_INMATRICULARE", ""), []),
            )
        )

    def at_address(self, raw_address: str) -> list[str]:
        address = normalize_address(raw_address)
        return list(self.cuis_by_address.get(address, [])) if address else []

    def of_person(self, person_name: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for reg_no, reps in self.reps_by_reg.items():
            for rep in reps:
                score = person_match(person_name, rep.get("PERSOANA_IMPUTERNICITA", ""))
                if score is None:
                    continue
                cui = self.cui_by_reg.get(reg_no)
                firm = self.firms.get(cui or "", {})
                found.append(affiliation(rep, firm, cui, self.status_by_reg.get(reg_no), score))
        return sorted(found, key=lambda a: (a["cod_inmatriculare"], a["de_la"] or ""))


def record_from_rows(
    firm: dict[str, str],
    status: str | None,
    caen: Iterable[dict[str, str]],
    reps: Iterable[dict[str, str]],
) -> dict[str, Any]:
    """One company in the onrc.json shape, from the bulk-file rows. No history in the bulk."""
    return {
        "fictional": _is_true(firm.get("FICTIONAL")),
        "cui": firm.get("CUI"),
        "denumire": firm.get("DENUMIRE"),
        "cod_inmatriculare": _empty_to_none(firm.get("COD_INMATRICULARE")),
        "data_inmatriculare": _empty_to_none(firm.get("DATA_INMATRICULARE")),
        "forma_juridica": _empty_to_none(firm.get("FORMA_JURIDICA")),
        "stare": _empty_to_none(status),
        "adresa": _empty_to_none(firm.get("ADRESA_COMPLETA")),
        "judet": _empty_to_none(firm.get("JUDET")),
        "caen_principal": None,  # not in the bulk files
        "caen_autorizate": [
            {
                "cod": c.get("COD_CAEN_AUTORIZAT"),
                "revizie": caen_revision(c.get("VERSIUNE_CAEN", "")),
            }
            for c in caen
        ],
        "istoric_denumiri": [],
        "istoric_sedii": [],
        "reprezentanti": [
            {
                "nume": r.get("PERSOANA_IMPUTERNICITA"),
                "calitate": _empty_to_none(r.get("CALITATE")),
                "de_la": _empty_to_none(r.get("DATA_NUMIRE")),
                "pana_la": _empty_to_none(r.get("DATA_INCETARE")),
            }
            for r in reps
        ],
    }


def affiliation(
    rep: dict[str, str],
    firm: dict[str, str],
    cui: str | None,
    status: str | None,
    score: float,
) -> dict[str, Any]:
    """One `companies_of_person` result: the company, the role, and how the name matched."""
    return {
        "cui": cui,
        "denumire": firm.get("DENUMIRE"),
        "cod_inmatriculare": rep.get("COD_INMATRICULARE"),
        "judet": _empty_to_none(firm.get("JUDET")),
        "stare": _empty_to_none(status),
        "nume": rep.get("PERSOANA_IMPUTERNICITA"),
        "calitate": _empty_to_none(rep.get("CALITATE")),
        "de_la": _empty_to_none(rep.get("DATA_NUMIRE")),
        "pana_la": _empty_to_none(rep.get("DATA_INCETARE")),
        "match": {"method": "person_name", "score": score, "ambiguous": score < 1.0},
    }


async def _no_live_call(client: httpx.AsyncClient) -> httpx.Response:
    raise SourceUnavailable("onrc_bulk", "bulk source: no per-company download (run ingest_onrc)")


@register_adapter("onrc_bulk")
class OnrcBulkAdapter(BaseAdapter):
    source_label = "ONRC open data (data.gov.ro)"
    source_type = SourceType.OFFICIAL
    mirror_max_age_s = 30 * 86_400

    _sample: tuple[OnrcIndex, SourceRef] | None = None

    async def download(self, dest_dir: Path) -> dict[str, Path]:
        """Stream every file in FILES to dest_dir (httpx streaming, chunked). Return name -> path.
        Archive a manifest (file names, sizes, sha256, source URLs) via the ObjectStore."""
        raise NotImplementedError

    async def iter_rows(
        self, path: Path, stats: RowStats | None = None
    ) -> AsyncIterator[dict[str, str]]:
        """Stream one CSV as dicts (header row = keys, upper-cased), skipping malformed lines and
        counting them in `stats`. Delimiter and encoding are sniffed per file. Parsing runs in a
        worker thread, ROWS_PER_BATCH rows at a time, so the event loop is never blocked and the
        file is never read whole."""
        stats = stats if stats is not None else RowStats()
        head = await asyncio.to_thread(_read_head, path)
        fmt = sniff_format(head)
        stream = await asyncio.to_thread(
            path.open, encoding=fmt.encoding, errors="replace", newline=""
        )
        try:
            reader = _reader(stream, fmt)
            header = _header(await asyncio.to_thread(next, reader, []))
            rows = _dict_rows(reader, header, stats)
            while batch := await asyncio.to_thread(_take, rows, ROWS_PER_BATCH):
                for row in batch:
                    yield row
        finally:
            await asyncio.to_thread(stream.close)
            if stats.malformed:
                log.warning(
                    "malformed ONRC rows skipped",
                    extra={"file": path.name, "malformed": stats.malformed, "rows": stats.rows},
                )

    async def company(self, cui: str) -> Sourced[dict[str, Any] | None]:
        """Per-company view: names (with history if available), reg. no., address, status,
        CAEN (main + authorized), legal representatives. None = CUI not in ONRC."""
        self._require_fixture_mode()
        fixture = self.company_fixture(cui, "onrc.json")
        if fixture is not None:
            result = await self.fetch(
                cache_key=f"company:{cui}", request=_no_live_call, fixture=fixture
            )
            return Sourced(result.json(), result.source, stale=result.stale)
        index, source = await self._sample_index()
        record = index.record(cui)
        if record is None and self.company_fixture_dir(cui) is None:
            # Fixtures are not the whole register: no data at all is unknown, not "not in ONRC".
            raise SourceUnavailable(self.name, f"no ONRC fixture for {cui}")
        return Sourced(record, source)

    async def companies_at_address(self, normalized_address: str) -> Sourced[list[str]]:
        """CUIs registered at the same address (rule ID-SHARED-OFFICE-01), the company itself
        included. Takes the raw ONRC address and normalizes it here (normalize_address)."""
        self._require_fixture_mode()
        index, source = await self._sample_index()
        return Sourced(index.at_address(normalized_address), source)

    async def companies_of_person(self, person_name: str) -> Sourced[list[dict[str, Any]]]:
        """Companies where this person is or was a legal representative (network agent).
        Matching is by name only: each item carries `match` {method, score, ambiguous} so the
        agent can lower confidence. Items: see `affiliation`."""
        self._require_fixture_mode()
        index, source = await self._sample_index()
        return Sourced(index.of_person(person_name), source)

    # ------------------------------------------------------------------ internals
    def _require_fixture_mode(self) -> None:
        if not self.settings.fixture_mode:
            raise SourceUnavailable(
                self.name,
                "ONRC tables are not wired to the adapter yet (bulk-lookup port PENDING)",
            )

    async def _sample_index(self) -> tuple[OnrcIndex, SourceRef]:
        """The fixture sample CSVs, parsed once per adapter instance. Source = OD_FIRME sample."""
        if self._sample is None:
            bodies: dict[str, bytes] = {}
            source: SourceRef | None = None
            for name in FILES[:4]:
                relative = f"{SAMPLE_DIR}/{Path(name).stem}_sample.csv"
                result = await self.fetch(
                    cache_key=f"sample:{relative}",
                    request=_no_live_call,
                    fixture=self.shared_fixture(relative),
                )
                bodies[name] = result.body
                source = source or result.source
            assert source is not None
            index = await asyncio.to_thread(
                OnrcIndex.build,
                parse_rows(bodies["OD_FIRME.CSV"]),
                parse_rows(bodies["OD_STARE_FIRMA.CSV"]),
                parse_rows(bodies["OD_CAEN_AUTORIZAT.CSV"]),
                parse_rows(bodies["OD_REPREZENTANTI_LEGALI.CSV"]),
            )
            self._sample = (index, source)
        return self._sample


def _read_head(path: Path) -> bytes:
    with path.open("rb") as f:
        return f.read(SNIFF_BYTES)


def _take(rows: Iterator[dict[str, str]], n: int) -> list[dict[str, str]]:
    batch: list[dict[str, str]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= n:
            break
    return batch
