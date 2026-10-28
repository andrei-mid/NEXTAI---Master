# CHANGELOG: what changed, for the other Claude Code instances

**Read this at the start of every session** (newest first). Every change that affects other folders, contracts, conventions or how to work gets an entry here: what changed, why, and what you must do differently. Keep entries short and link the files.

---

## 2026-10-28: anaf_v9 keeps several dated snapshots per company (role 3)

**What:** ANAF v9 answers "as of a date" (`data` in the request), and one request can ask the same CUI for several dates. `adapters/anaf_v9.py` now stores, per company:
- `CUI`: the latest record (unchanged: `lookup` reads it).
- `CUI:date`: what ANAF answered for that date. `sync()` asks for **today plus the previous 12 month-ends in ONE request** (13 entries), only the ones missing. A past date never changes, so it is downloaded once, ever. After the first sync, a company costs at most one entry per request.
- New READ method **`history(cui, dates=None) -> Sourced[{ISO date: record | None}]`**: mirror only, never the network. In FIXTURE_MODE it has today's fixture only.
- ANAF's limit counts **entries (cui+date)**: max 100 per request. The batch code chunks by entries.
- `split_entries()` matches answers on `date_generale.cui` **and** `date_generale.data`, so two dates of one CUI never overwrite each other.
- Fixed: a network `lookup` could make two requests (once through `fetch()`, once through the batch path). It's always one now (tested).
- `tax/rules.check_vat_cancelled` accepts `perioade_TVA` as a single object too, as ANAF's documentation shows it.

**What you can do with it:** name, address, CAEN and legal form **as of each month-end**, from an official source. Role 3 will use it for `ID-OFFICE-CHANGE-01` (live ONRC has no office history). Role 5 / identity sheet: `history()` can fill `names` and `office_history`.

---

## 2026-10-28: Tax agent, anaf_v9, e-Factura registry and all 6 mocks implemented (role 3)

**What:**
- **`verifirm/agents/tax/`** is done: 5 rules, `config.yaml`, tests with the **real adapters** in `FIXTURE_MODE`. Zephyria's and Brunaldo's output matches `api/signals.json` field by field. Decisions are in its README.
- **`adapters/anaf_v9.py`** is implemented. READ `lookup` / `lookup_batch` reads the mirror only. `sync()` makes 1 request per applicant. `lookup_batch` on a network adapter sends 100 CUIs per request and stores one mirror entry per CUI. It **never retries an HTTP 429**. The mirror key is the **CUI** (latest record), not `cui:date`; the reason is in DECISIONS.md.
- **`anaf_v9` was written twice in parallel** (role 2 in "Live end to end" below, role 3 here). Merged into one file. The public API is unchanged (`lookup`, `lookup_batch`, `sync`, `split_response`), and both test suites are kept. Role 3 added: **no retry on HTTP 429**, a corrupt mirror entry is downloaded again instead of being reused for 24h, and duplicate CUIs are dropped from batches.
- **`adapters/anaf_efactura_registry.py`** is derived from the v9 mirror entry: no call, no sync.
- **All 6 mocks** (`restante`, `d300`, `efactura`, `bpi`, `shareholders`, `pep`) are implemented on a shared `mocks.MockAdapter`. A missing file or wrong shape gives `SourceUnavailable`, never "nothing found".
- `docs/SOURCES.md` now has the **production route** for every mock (the applicant's documents or a paid provider).
- New severity rule: `TAX-EFACTURA-GAP-01` is medium when D300 is below e-Factura and low when above (`docs/RULES.md`).

**What you must do:**
- **Role 4 (litigation, sanctions):** `mock_bpi.proceedings(cui)` and `mock_pep.entries()` work now. Both return `Sourced[list[dict]]`.
- **Role 2 (`sweep_anaf_v9`, change detection):** use `AnafV9Adapter.lookup_batch(cuis, date)` on a `sync_adapters` instance. It handles the 100-CUI chunks and the mirror. Never loop over `lookup` to call ANAF.
- **Role 5 (`identity_sheet`, `documents`):** read v9 through `anaf_v9.lookup(cui, today)`. When `documents.extract` lands, the tax agent picks up `ctx.submitted` with no change.
- **Role 6 (fixtures):** optional. Add `"on_white_list": true|false` to `restante.json` if you want the demo to show ANAF's no-arrears list.

---

## 2026-10-28: `make seed-real`: the same real companies in everyone's database (role 2)

**What:** `apps/worker/seed.py` runs DEDEMAN, AUTOMOBILE-DACIA, OMV PETROM, DANTE INTERNATIONAL (eMAG), ALTEX ROMANIA and HIDROELECTRICA through the real pipeline (ANAF → local mirror → agents → scoring → your Postgres). Real-company figures are never committed (CLAUDE.md rule 11), so we share this script, not a database dump. ~7 ANAF calls per company. Re-runs only refresh stale data.

Also: a missing/misconfigured LLM (e.g. `LLM_PROVIDER=anthropic` without `ANTHROPIC_API_KEY`) no longer fails the run. Agents get `llm=None`, and only the memo is missing (`apps/worker/orchestrator.py`).

**What you must do:** to see the real companies: Postgres up (see `infra/local/README.md`), `make db-upgrade`, then `make seed-real`. Add CUIs: `uv run python -m apps.worker.seed <cui> <cui>`.

---

## 2026-10-28: Live end to end: ANAF → mirror → agents → Postgres → API (role 2, with role 3/5 pieces)

**What works now (tested on DEDEMAN SRL with real ANAF data):** `POST /companies/{cui}/recheck` → sync downloads ANAF v9 + 6 balance sheets into the local mirror → identity sheet → 8 agents → scoring → saved in Postgres → `GET /companies` serves it. Guide: [infra/local/README.md](../infra/local/README.md).

- `verifirm/adapters/anaf_v9.py` (**role 3: done by role 2**): `lookup`, `sync`, `lookup_batch` (100/POST, one mirror entry per CUI). Tests: `adapters/tests/test_anaf_v9.py`. @role-3: the `sweep_anaf_v9` job can now call `lookup_batch`.
- `verifirm/consolidation/identity_sheet.py` (**role 5: done by role 2**): built from ANAF v9 (required) + ONRC (optional) + mock shareholders (optional). Tests: `consolidation/tests/test_identity_sheet.py`. @role-5: extend freely.
- `verifirm/adapters/onrc_bulk.py` (**role 1**): `company()` and `companies_at_address()` read fixtures in FIXTURE_MODE. Live they report unavailable until `ingest_onrc` exists. @role-1: replace the live branch with table reads.
- `EMBEDDED_WORKER=1`: the API runs the queue consumer in-process (single box, in-memory queue). `apps/api/main.py`.
- **Tests never touch your dev database any more:** `./conftest.py` swaps `DATABASE_URL` for `TEST_DATABASE_URL` (see `.env.example`). Persistence tests insert rows they never delete, and they used to fill the dev portfolio with test companies.
- `tests/e2e` now runs the whole pipeline and skips with the list of agents still missing: tax, network, litigation, sanctions, media, presence.

**What you must do:** local Postgres users: create `verifirm_test` and set `TEST_DATABASE_URL`. Agent authors: your agent is the only thing missing for its component. Copy `agents/financials/` + `adapters/anaf_bilant.py`.

---

## 2026-10-28: Pipeline never hangs on a memo/LLM failure (role 2)

**What:** `apps/worker/orchestrator.py`. If the memo or critic step raises (LLM down, invalid output, no API key), the run now ends **COMPLETED** with its deterministic score saved and `RunStatus.error = "memo not generated: …"`. Any other unexpected exception ends the run **FAILED** with the error. Before, both escaped `run_pipeline`: the worker retried, and the SSE stream never sent `done`.

**What you must do:** role 5 / frontend: a completed run can have no memo (`GET /companies/{cui}/memo` → 404). Show "memo unavailable" and keep showing the score. Tests: `apps/worker/tests/test_orchestrator.py`.

**Integration status (smoke test on the demo companies, fixture mode):** only `financials` produces signals end to end. `identity` is implemented but reports unavailable until the `anaf_v9` + `onrc_bulk` adapters exist (roles 3/1). `consolidation/identity_sheet.py` (role 5) is still a stub, so the full pipeline stops at step 2 and `tests/e2e` stays skipped.

---

## 2026-10-28: Ownership guard removed (role 2) · ACTION NEEDED

**What:** the Claude Code ownership hook (`.claude/settings.json` + `.claude/hooks/ownership_guard.py`) and everything tied to `VERIFIRM_ROLE` are gone. They blocked teammates' work. CODEOWNERS is back to the `@role-N-…` placeholders. The ownership *rules* in CLAUDE.md ("Stay inside your folder") still apply. They are just not enforced by a hook any more.

**What you must do:** delete your `.claude/settings.local.json` if it only contained `VERIFIRM_ROLE` (it's git-ignored, so it never blocks commits), then restart Claude Code.

---

## 2026-10-28: Identity agent implemented, new rule ID-SOURCE-MISMATCH-01 (role 3)

**What:** `verifirm/agents/identity/` is done: `rules.py` (9 pure checks), `agent.py`, `config.yaml` (thresholds, PROPOSAL), tests on every fixture company and every failure path. Zephyria's output matches `fixtures/companies/99000025_*/api/signals.json` field by field. The README has the full contract.

- **New rule `ID-SOURCE-MISMATCH-01`** (high): ANAF and ONRC disagree on CUI, register number or name, which means the wrong entity may have been matched. It is in `docs/RULES.md`.
- **`ID-STATUS-01` severity now varies by status** (PROPOSAL): deregistered and bankruptcy critical, insolvency and dissolution high, suspended medium, unknown high. Deregistration is cross-checked with ANAF `dataRadiere`: on disagreement the worse value wins, `data.sources_agree=false`, confidence 0.6.
- **Source authority:** legal status and administrators come from ONRC, fiscal inactivity from ANAF, deregistration from both. ANAF "INREGISTRAT" next to ONRC "faliment" is **not** a conflict (a company stays a taxpayer until it is deregistered).

**What you must do:**
- **Role 1:** `onrc_bulk.company(cui)` is read in the **`fixtures/companies/*/onrc.json` shape** (`cui`, `denumire`, `cod_inmatriculare`, `stare`, ...), with `None` meaning not found. `companies_at_address()` receives the **raw** ONRC address, so normalize inside the adapter. PENDING in `docs/DECISIONS.md`. Confirm it or propose another shape.
- **Role 5:** the agent reads `ctx.identity.administrators` (with `valid_from`/`valid_to`), `office_history`, `caen_code`, `authorized_caen_codes` and `legal_form`. Fill them from ONRC in `identity_sheet`.
- **Role 3:** ~~`anaf_v9.lookup` is still a stub~~ Done (see the tax entry above).

---

## 2026-10-28: Postgres repository for the core tables (role 1)

**What:** `SqlRepository` (`verifirm/persistence/repositories/sql_repository.py`) implements the whole `Repository` port. Migrations exist for `companies_*`, `runs_*`, `signals_*`, `scores_*`, `memos_*`, `audit_*`. `REPOSITORY_BACKEND=postgres` now works (`make up`, then `uv run alembic -c verifirm/persistence/alembic.ini upgrade head`).

- `audit_decisions` is append-only through a trigger: UPDATE / DELETE / TRUNCATE raise for every role.
- Signals live only in `signals_signals`. `save_agent_result` replaces the agent's signals for that run (stale ones are deleted), so re-runs never duplicate.
- `list_portfolio` reads `companies_companies.latest_band`, which only moves forward (an older score saved late doesn't overwrite it).

**What you must do:** nothing, unless your tests need Postgres: use the `migrated_db` / `repo` fixtures pattern from `verifirm/persistence/conftest.py` (skip when unreachable, never truncate).

---

## 2026-10-28: Local-first data access (role 2) · DECIDED

**What:** external data is downloaded onto our server first. Agents only read the local copy (the "mirror") and never call external APIs. Full guide: [docs/LOCAL_DATA.md](LOCAL_DATA.md).

- `verifirm/adapters/base.py`: the TTL cache and "last-known-good" are replaced by the mirror (`mirror/<adapter>/<key>` in the ObjectStore). New: `AdapterDeps.network`, `BaseAdapter.sync(cui) -> SyncReport`, `from_mirror()`, `store_in_mirror()`, `FetchResult.from_mirror` (was `from_cache`).
- `apps/wiring.py`: `infra.adapters` = read-only (agents). `infra.sync_adapters` = may download (sync code only).
- `apps/worker/sync.py` (new): `sync_company(cui)`. The orchestrator calls it once per application/recheck (step 1b) before any agent runs.
- `apps/worker/jobs/sync_portfolio.py` (new, daily in `scheduler.py`).
- Settings renamed: `CACHE_TTL_S` → `MIRROR_MAX_AGE_S`, `CACHE_TTL_OVERRIDES_S` → `MIRROR_MAX_AGE_OVERRIDES_S`, adapter attr `cache_ttl_s` → `mirror_max_age_s`. New: `SYNC_TIMEOUT_S`, `SYNC_ON_APPLICATION`.

**What you must do:**
- **Adapter authors (roles 1, 3, 4, 5):** implement READ methods on `fetch()` + `sync(cui)` with the same cache keys. Bulk sources use `ingest_*` jobs instead. See the checklist in LOCAL_DATA.md and copy `anaf_bilant.py`.
- **Agent authors (roles 3, 4):** use only `ctx.adapter(...)` READ methods. "Not in the local mirror yet" is a `SourceUnavailable`, so report it as unavailable, never as clean. Copy `agents/financials/`.
- **Role 1:** the mirror index table (`persistence/models/source_cache.py`) and bulk tables are where this goes long-term.

## 2026-10-28: Financials agent implemented (role 3 work, done by role 2)

- `verifirm/adapters/anaf_bilant.py`: label-based mapping, `sync()`, `get_year`, `get_history` → `BilantHistory(years, failed)`.
- `verifirm/agents/financials/`: rules (pure, thresholds in `config.yaml`), agent, tests. Interpretations of the brief are recorded in DECISIONS.md.
- `fixtures/tools/build_fixtures.py` now **runs the real financials agent** to produce the financials signals in `api/signals.json`. Other agents should follow: once yours works, replace its hand-written fixture signals with a call to your agent (see `financials_signals()` there).

## 2026-10-28: Scoring engine implemented (role 2)

- `verifirm/scoring/` engine, bands and coverage are implemented and tested. `green_requires_all_ok: true` in `weights.yaml`: **any** source outage means at most YELLOW (demo step 7).
- Scores in the demo fixtures equal the real engine's output (`verifirm/scoring/tests/test_engine.py`).

## 2026-10-28: Scaffold (role 2)

- Initial structure, contracts, stubs, fixtures, docs. Start with [CLAUDE.md](../CLAUDE.md).
