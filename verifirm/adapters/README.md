# adapters/

One file per external source, all on top of [`base.py`](base.py). **Local-first:** read [docs/LOCAL_DATA.md](../../docs/LOCAL_DATA.md) before writing or changing an adapter.

**ANAF v9 (dated snapshots, one request per call, no retries):** see [`anaf_v9.md`](anaf_v9.md).

**Reference implementation:** [`anaf_bilant.py`](anaf_bilant.py) (READ methods + `sync()` + immutable-data reuse + tests in `tests/test_anaf_bilant.py`).

## Every adapter has two halves

| Half | Who calls it | Network |
|---|---|---|
| **READ methods** (`get_year`, `lookup`, `search_cases`, …) built on `self.fetch()` | agents, identity sheet (`ctx.adapter(...)`) | **never**: mirror only (`network=False`) |
| **`sync(cui)`** | `apps/worker/sync.py`, sync jobs | yes, rate-limited globally |

Both halves use the **same `cache_key`s**. That's how sync fills exactly what READ needs.

## Status

| Adapter | Kind | Status | How data gets to the server |
|---|---|---|---|
| `anaf_bilant` | per company | **implemented** | `sync()`: 6 years, filed years downloaded once ever |
| `anaf_v9` | batch per company + dated snapshots | **implemented** | Mirror: `CUI` = latest record, `CUI:date` = what ANAF answered for that date (past dates downloaded once, ever). **One call = at most one request** to ANAF: no chunking loop, no retries, more than 100 entries (cui+date) refused before sending. `sync()`: one request with today + the missing quarter-ends (4). Human-triggered fetch tool: `apps/worker/jobs/sweep_anaf_v9.py` (dry run by default). `lookup_batch` on a network adapter: one request for at most 100 CUIs (the `sweep_anaf_v9` job, still a stub, schedules the batches). READ: `lookup`, `history` |
| `anaf_efactura_registry` | per company | **implemented** | derived from the v9 mirror entry (`statusRO_e_Factura`). No call, no sync of its own |
| `onrc_bulk` | bulk | **fixture reads only** (`company`, `companies_at_address`, `companies_of_person`, streaming `iter_rows`). Live: reports unavailable until `ingest_onrc` (role 1) loads the tables and the bulk-lookup port (PENDING) lets the adapter read them. `download()` stub | `ingest_onrc` job → Postgres (COPY). `sync()` no-op |
| `portal_just` | per company | stub | `sync()` per company name. `poll_new_cases` job keeps it fresh |
| `scj` | per company, time window | stub | nightly batch 03:30–06:30 → mirror. `sync()` no-op outside the window |
| `sanctions_eu/un/ofac` | bulk | stub | `ingest_sanctions` job. `sync()` no-op |
| `seap` | bulk | **fixture mode only** | `contracts_for()` reads `presence.json` in FIXTURE_MODE. Live: unavailable until a procurement ingest job (data.gov.ro) exists. `sync()` no-op |
| `kohesio` | bulk | **fixture mode only** | `projects_for()` reads `presence.json` in FIXTURE_MODE. Live: unavailable until a Kohesio ingest job exists. `sync()` no-op |
| `web_search` (Tavily) | per company | partly | `footprint()` (website + jobs, presence agent) reads `presence.json` in FIXTURE_MODE, live unavailable. `search()` (Tavily, media agent) still a stub. `sync()` should run the media/presence queries once per application |
| `documents` | uploaded files | stub | files are already local (ObjectStore). No sync |
| `mocks/*` | fixtures only | **implemented** (all 6) | always read `fixtures/` through `mocks.MockAdapter` (shape-checked; wrong shape or no file → unavailable). No sync. Production route: `docs/SOURCES.md` |

Update this table when you change an adapter's status.
