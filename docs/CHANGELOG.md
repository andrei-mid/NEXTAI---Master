# CHANGELOG: what changed, for the other Claude Code instances

**Read this at the start of every session** (newest first). Every change that affects other folders, contracts, conventions or how to work gets an entry here: what changed, why, and what you must do differently. Keep entries short and link the files.

---

## 2026-10-28: Tax agent, anaf_v9, e-Factura registry and all 6 mocks implemented (role 3)

**What:**
- **`verifirm/agents/tax/`** is done: 5 rules, `config.yaml`, tests with the **real adapters** in `FIXTURE_MODE`. Zephyria's and Brunaldo's output matches `api/signals.json` field by field. Decisions are in its README.
- **`adapters/anaf_v9.py`** is implemented. READ `lookup` / `lookup_batch` reads the mirror only. `sync()` makes 1 request per applicant. `lookup_batch` on a network adapter sends 100 CUIs per request and stores one mirror entry per CUI. It **never retries an HTTP 429**. The mirror key is the **CUI** (latest record), not `cui:date`; the reason is in DECISIONS.md.
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
