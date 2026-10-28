# adapters/

One file per external source, all on top of [`base.py`](base.py). **Local-first:** read [docs/LOCAL_DATA.md](../../docs/LOCAL_DATA.md) before writing or changing an adapter.

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
| `anaf_v9` | batch per company | **implemented** | READ `lookup` / `lookup_batch` (mirror, key = CUI). `sync()`: 1 request per applicant. `lookup_batch` on a network adapter: 100 CUIs per request → `store_in_mirror` per CUI (for the `sweep_anaf_v9` job, still a stub). Never retries a 429 |
| `anaf_efactura_registry` | per company | **implemented** | derived from the v9 mirror entry (`statusRO_e_Factura`). No call, no sync of its own |
| `onrc_bulk` | bulk | stub | `ingest_onrc` job → Postgres (COPY). `sync()` no-op |
| `portal_just` | per company | stub | `sync()` per company name. `poll_new_cases` job keeps it fresh |
| `scj` | per company, time window | stub | nightly batch 03:30–06:30 → mirror. `sync()` no-op outside the window |
| `sanctions_eu/un/ofac` | bulk | stub | `ingest_sanctions` job. `sync()` no-op |
| `seap`, `kohesio` | bulk | stub | ingest jobs (to add). `sync()` no-op |
| `web_search` (Tavily) | per company | stub | `sync()` runs the media/presence queries once per application. Results go to the mirror |
| `documents` | uploaded files | stub | files are already local (ObjectStore). No sync |
| `mocks/*` | fixtures only | **implemented** (all 6) | always read `fixtures/` through `mocks.MockAdapter` (shape-checked; wrong shape or no file → unavailable). No sync. Production route: `docs/SOURCES.md` |

Update this table when you change an adapter's status.
