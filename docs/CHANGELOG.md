# CHANGELOG: what changed, for the other Claude Code instances

**Read this at the start of every session** (newest first). Every change that affects other folders, contracts, conventions or how to work gets an entry here: what changed, why, and what you must do differently. Keep entries short and link the files.

---

## 2026-10-28: `.claude/settings.local.json` removed from git (role 2) · ACTION NEEDED

**What:** a personal `.claude/settings.local.json` (`VERIFIRM_ROLE=@andrei-mid`) was committed to `main` by mistake. Anyone who pulled it was treated as role 2 by the ownership guard, so their Claude could edit any file. It's now untracked and git-ignored.

**What you must do:** after pulling, git deletes your copy of that file. Recreate it with **your own** handle, `{"env": {"VERIFIRM_ROLE": "@your-handle"}}`, and restart Claude Code. Never commit it (`.gitignore` already covers it).

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

## 2026-10-28: File ownership is enforced (role 2) · ACTION NEEDED

**What:** a Claude Code hook (`.claude/settings.json` → `.claude/hooks/ownership_guard.py`) refuses Edit/Write on files CODEOWNERS doesn't give you. CODEOWNERS now names `@andrei-mid` for role 2. `agents/financials/` + `adapters/anaf_bilant.py` are co-owned by `@andrei-mid` and role 3. On GitHub, `main` requires review from Code Owners.

**What you must do (everyone):**
1. Create `.claude/settings.local.json` with `{"env": {"VERIFIRM_ROLE": "@your-handle"}}` and restart Claude Code. Until you do, the hook refuses all edits.
2. Send your GitHub handle to role 2 so the `@role-N-…` placeholder in CODEOWNERS is replaced.
3. If your Claude gets "owned by …": don't work around it. Add a PENDING entry in `docs/DECISIONS.md` (editable by everyone) and tell the owner.

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
