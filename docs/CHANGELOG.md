# CHANGELOG: what changed, for the other Claude Code instances

**Read this at the start of every session** (newest first). Every change that affects other folders, contracts, conventions or how to work gets an entry here: what changed, why, and what you must do differently. Keep entries short and link the files.

---

## 2026-10-29: Presence agent implemented (role 4's files, built by role 3 with the human's approval)

**What:** `verifirm/agents/presence/` is done: 3 rules, `config.yaml`, tests with the real adapters in FIXTURE_MODE, and a full-pipeline check (Zephyria gets PRE-NO-FOOTPRINT-01, Aurora nothing). Adapters: `seap.contracts_for`, `kohesio.projects_for` and the new `web_search.footprint` (website + job postings) read `presence.json` in FIXTURE_MODE through `adapters/presence_fixture.py`. **Live they report unavailable**, never empty. PRE-NO-FOOTPRINT-01 needs all four parts checked. With no footprint source at all, the agent is `unavailable` (turnover alone is not a presence check).

**What you must do:**
- **Role 4:** presence is done. `TavilyWebSearch.search()` (media) is still yours. For live presence data: run the website / job queries in `web_search.sync()`, plus ingest jobs for SEAP and Kohesio.
- **Role 6:** `fixtures/companies/99000025_*/api/signals.json` has a stale `content_hash` for the presence signal (presence.json changed after it was generated). Regenerate with `make fixtures` when convenient.

---

## 2026-10-28: AI analyst opinion: dossier + LLM opinion + citation checks (role 1, steps 0-3) · CONTRACT ADDITION

**What:** an LLM reads a company dossier built by code and returns its educated opinion: flags with evidence, an `opinion_score` 0-100 and an explanation. DECIDED in `docs/DECISIONS.md` ("AI analyst opinion"). Code: `verifirm/consolidation/analyst/` (README there).

- **`schema/analyst.py` (new, role 2's folder):** `CompanyDossier`, `AnalystDraft`, `AnalystOpinion`, `DISCLAIMER`. Exported to `docs/schema/`.
- **`core/config.py` (role 2's folder):** `LLM_MODEL_ANALYST`, `model_for("analyst")`. In `.env.example`.
- The dossier compares ANAF with ONRC field by field (`match` true / false / null), lists the changes between the quarterly ANAF v9 snapshots, and has /bilant years plus indicators **computed in code**. People are aliases, never real names.
- Every flag must cite dossier paths whose values check out, and every number in it must be in its evidence; otherwise it is rejected with the reason. Severity is capped at `high`, there is no decision wording, and the disclaimer is added by code.
- **The official score and band are unchanged** (hard rule 8). The opinion is shown next to them.

**What you must do:**
- **Role 5:** the pipeline step (after scoring, like the memo) and `GET /companies/{cui}/analyst-opinion`. `write_opinion` raises on invalid output, so catch it like the memo step.
- **Role 2:** review the two files in your folders.
- **Everyone running it:** set `LLM_MODEL_ANALYST` in `.env` to a large model.

---

## 2026-10-29: Live company list ~4x faster (role 3, in role 5's `apps/api/read_model.py`, approved by the human)

**What:** on a hosted Postgres (Neon, about 0.1 s per round trip from a laptop), `GET /companies` took about 14 s: every company's identity, score and signals were read one after another. `RepoReadModel.list_companies` now loads the companies concurrently (at most `LIST_CONCURRENCY = 8` at once), and each company's three reads in parallel. `detail()` reads identity, score and signals in parallel too. Measured on real data: list 14.2 s → 3.3 s, one company 3.1 s → 1.0 s. Same responses, same order. Test: `test_list_loads_companies_concurrently_and_keeps_the_page_order`.

**What you must do:** role 5: nothing, but keep it concurrent if you change the list. Role 1: going under 1 s needs batch reads in the repository (one query for all companies on a page) and no `pool_pre_ping` round trip before each query. Optional.

---

## 2026-10-29: TAX-EFACTURA-REG-01 is off by default (role 3) · found on real data

**What:** the first real-data run (6 real companies, ANAF v9 into Neon) flagged Dacia, Petrom, eMAG and Altex as "not enrolled in RO e-Factura". That's impossible, because e-Factura has been mandatory for B2B since 2024. ANAF v9's `statusRO_e_Factura` is the **old opt-in register**, not current e-Factura use. The rule is now **off by default** (`efactura_registration_check: false` in `verifirm/agents/tax/config.yaml`). The agent doesn't even read that source while the rule is off, so it is never a "failed source".

**What you must do:** nothing. Role 5 / memo: there is no `TAX-EFACTURA-REG-01` on real companies any more.

---

## 2026-10-28: Real data the safe way: the ANAF fetch tool (role 3) · ACTION NEEDED for a shared server

**What:** `apps/worker/jobs/sweep_anaf_v9.py` is now **the ONE place a human triggers ANAF requests**: dry run by default, `--send` sends exactly ONE request, at least 1.1 s between requests even across runs (lock file), no retries, real CUIs only. `v9`: one request for all given companies (today + 4 quarter-ends each, only what's missing, max 100 entries). `bilant`: one request per run (newest missing year of the 5 the financials agent reads). `status`: what's in the mirror, no request. The scheduled `run()` is **not automated on purpose**. Commands: `verifirm/adapters/anaf_v9.md` §7. `anaf_v9` keeps 4 quarter-ends now (5 data points per company), not 12 month-ends.

**What you must do:**
- **Whoever runs a shared server: set `SYNC_ON_APPLICATION=0`.** Otherwise every "recheck" click from the frontend runs a sync, which means ANAF requests nobody approved. Data then comes only from the fetch tool, and the pipeline reads the mirror.
- **Don't use `make seed-real` with sync on** (it sends about 7 requests per company in a loop). Fetch with the tool, then `SYNC_ON_APPLICATION=0 uv run python -m apps.worker.seed <CUIs>` (0 requests).
- **Role 2 / role 5:** real and fictional companies on one server need a per-CUI switch (PENDING in DECISIONS.md, "Dedeman live run while FIXTURE_MODE=1", option b).

---

## 2026-10-28: anaf_v9 keeps several dated snapshots per company (role 3)

**What:** ANAF v9 answers "as of a date" (`data` in the request), and one request can ask the same CUI for several dates. `adapters/anaf_v9.py` now stores, per company:
- `CUI`: the latest record (unchanged: `lookup` reads it).
- `CUI:date`: what ANAF answered for that date. `sync()` asks for **today plus the previous 4 quarter-ends in ONE request** (5 entries; first version had 12 month-ends), only the ones missing. A past date never changes, so it is downloaded once, ever. After the first sync, a company costs at most one entry per request.
- New READ method **`history(cui, dates=None) -> Sourced[{ISO date: record | None}]`**: mirror only, never the network. In FIXTURE_MODE it has today's fixture only.
- ANAF's limit counts **entries (cui+date)**: max 100 per request. The batch code chunks by entries.
- `split_entries()` matches answers on `date_generale.cui` **and** `date_generale.data`, so two dates of one CUI never overwrite each other.
- Fixed: a network `lookup` could make two requests (once through `fetch()`, once through the batch path). It's always one now (tested).
- `tax/rules.check_vat_cancelled` accepts `perioade_TVA` as a single object too, as ANAF's documentation shows it.
- **Safety (ANAF: max 100 CUIs per request, 1 request/second, overloading is punished): in `anaf_v9`, one call = at most one request.** No chunking loop, no retries (429, 5xx, timeout: reported, the old copy is served stale). More than 100 entries raises `ValueError` before anything is sent. `lookup_batch` takes at most 100 CUIs, so **role 2's `sweep_anaf_v9` must schedule batches**, never loop. PENDING in DECISIONS.md: the same rule for `anaf_bilant` (6 requests per sync, with retries) and the per-process rate limiter.

**What you can do with it:** name, address, CAEN and legal form **as of each quarter-end**, from an official source. Role 3 will use it for `ID-OFFICE-CHANGE-01` (live ONRC has no office history). Role 5 / identity sheet: `history()` can fill `names` and `office_history`.

---

## 2026-10-28: Time travel: `?as_of=` and `GET /companies/{cui}/history?from=&to=` (role 1, for role 6) · CONTRACT CHANGE

**What:** the frontend can show a company or the portfolio **as of a date** and **everything from date X to date Y**. DECIDED in `docs/DECISIONS.md` ("Time-travel reads"). Contract in `docs/SOLUTION.md` ("Time travel"). Done by role 1 across folders at the team's request:

- **`schema/api.py` (role 2):** new `ScorePoint`, `CompanyHistory`. `docs/schema/` regenerated.
- **`core/ports/repository.py` + `core/impl_local/repository.py` (role 2):** six new port methods: `get_score_as_of`, `list_score_history`, `list_signals_as_of`, `list_events`, `list_portfolio_as_of`, `list_decisions_between`. `MemoryRepository` now keeps every score per company, not only the latest.
- **`apps/api` (role 5):** `as_of` on `GET /companies`, `/companies/{cui}`, `/companies/{cui}/signals`; new `/history` route. Works in fixture mode too (one check per demo company, events from the fixture signals).
- **`persistence` (role 1):** the SQL implementation, tested on PostgreSQL 17.11 (all persistence tests pass on a real Postgres now).

Two time axes, never mixed: *known-at* (`computed_at`, `recorded_at`: what the bank knew) and *happened-at* (`Signal.evidence_date`: when the fact occurred).

**What you must do:**
- **Role 6:** use `?as_of=` and `/history` (see SOLUTION.md). In fixture mode `scores` has at most one point per company.
- **Role 2 / role 5:** review the changes in your folders. Any new `Repository` implementation must implement the six methods.

---

## 2026-10-28: `onrc_bulk` works in fixture mode (role 1)

**What:** `verifirm/adapters/onrc_bulk.py` READ methods are implemented for `FIXTURE_MODE=1` (this replaces role 2's first fixture version below, same behaviour plus more). The per-company contract is now DECIDED in `docs/DECISIONS.md`.

- `company(cui)`: `onrc.json` when the company has one, otherwise a record built from `fixtures/sources/onrc/*_sample.csv` (so the 63 shell companies and the affiliates resolve too). A fixture folder without either (Dedeman) → `None`. A CUI with no fixture data at all → `SourceUnavailable` (kept from role 2's version: in fixture mode we can't say it's not in ONRC).
- `companies_at_address(raw)`: normalizes inside (`normalize_address`: diacritics, case, `Strada`/`Str.`, `Bulevardul`/`B-dul`/`Bd.`, `nr.`). Zephyria's office → 63 CUIs.
- `companies_of_person(name)`: affiliations with `stare` and `match {method, score, ambiguous}`. Ionel Fictivescu → Zephyria + 5 affiliates.
- `iter_rows(path)`: streaming parser for the real files (delimiter + UTF-8/cp1250 sniffed, malformed lines counted). Used next by `ingest_onrc`.
- The identity agent run with the real adapter gives the same signals as with its `FakeOnrc` on all 9 fictional companies (only `source.raw_ref` is more precise).
- Outside fixture mode the READ methods raise `SourceUnavailable` (never empty) until the bulk-lookup port exists.

**What you must do:**
- **Role 3:** you can replace `FakeOnrc` in `agents/identity/tests/` with `OnrcBulkAdapter` (fixture mode). The network agent can use `companies_of_person`.
- **Role 5:** `identity_sheet` already reads `onrc_bulk.company(cui)`: nothing to change.
- **Role 2:** please review the bulk-lookup port proposal in `docs/DECISIONS.md` (PENDING, "Port for bulk tables"). It is what the live branch of `onrc_bulk` needs to read the tables.

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
