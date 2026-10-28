# CHANGELOG: what changed, for the other Claude Code instances

**Read this at the start of every session** (newest first). Every change that affects other folders, contracts, conventions or how to work gets an entry here: what changed, why, and what you must do differently. Keep entries short and link the files.

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
- **Role 3:** `anaf_v9.lookup` is still a stub. Until it lands, the agent reports `anaf_v9` as "adapter not implemented yet" (partial), never clean.

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
