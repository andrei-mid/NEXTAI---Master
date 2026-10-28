# LOCAL_DATA: local-first data access (DECIDED)

**Rule:** data from ANAF, the courts, the sanctions lists and every other external source is **downloaded onto our server first**. **Agents only process the local copy.** They never call an external API. We can't afford many API calls (ANAF allows 1 req/s, ICCJ is only reachable 03:30–06:30, Tavily costs money), and an agent run must not depend on a source being up at that moment.

Applies to every adapter and every agent. If your change doesn't fit this model, add a PENDING entry to `docs/DECISIONS.md` and ask before you build around it.

## The three ways data reaches the server

| Kind of source | Examples | How it is downloaded | Where it lands |
|---|---|---|---|
| **Bulk** (whole dataset) | ONRC CSVs, EU/UN/OFAC sanctions, SEAP, Kohesio | scheduled `apps/worker/jobs/ingest_*` jobs, Postgres COPY | Postgres bulk tables (role 1) |
| **Per company** | ANAF `/bilant`, ANAF v9, Portal Just, web search | each adapter's `sync(cui)` | the **mirror** (below) |
| **Batch per company** | ANAF v9 (100 CUIs per call) | a sweep job (`sweep_anaf_v9.py`) that calls `store_in_mirror()` once per CUI | the mirror |

**When per-company sync runs:**
1. **New application / manual recheck:** the orchestrator runs `apps/worker/sync.py:sync_company(cui)` **once**, before the identity sheet and the agents (step 1b). That's the only network moment in a pipeline run.
2. **Portfolio:** `apps/worker/jobs/sync_portfolio.py`, daily. Repeat runs are cheap, because fresh or immutable data is reused, not downloaded again.
3. **Never** inside an agent.

## The mirror

`verifirm/adapters/base.py` gives every adapter one local copy per request (`cache_key`):
- raw bytes archived content-addressed in the ObjectStore (`raw/<adapter>/<sha256>`): audit + replay,
- a mirror entry `mirror/<adapter>/<hash(cache_key)>` with `retrieved_at`, `content_hash` and `url`.

Locally that is `.data/objects/` (`OBJECT_STORE_BACKEND=filesystem`). On AWS it's S3, which every worker shares. A Postgres index of the mirror is planned in `verifirm/persistence/models/source_cache.py` (role 1).

Adapter instances come in two flavours (built in `apps/wiring.py`):

| | `infra.adapters` | `infra.sync_adapters` |
|---|---|---|
| used by | agents, identity sheet | `sync_company`, sync/ingest jobs |
| `network` | **False** | True |
| `fetch()` on a fresh mirror entry | served | served (no call) |
| `fetch()` on an old entry | served, `stale=True` | re-downloaded (falls back to the old copy if the source is down) |
| `fetch()` with no entry | `SourceUnavailable("not in the local mirror yet (run sync)")` | downloaded |

Freshness: `mirror_max_age_s` on the adapter class (default `MIRROR_MAX_AGE_S`, 24h; per-adapter overrides via `MIRROR_MAX_AGE_OVERRIDES_S`). Data that cannot change, such as a balance sheet already filed, is **never** re-downloaded (see `AnafBilantAdapter._load`).

`FIXTURE_MODE=1` still bypasses everything: fixtures only, no sync.

## How to write an adapter (checklist)

1. **READ methods** (`get_year`, `search_cases`, …) call `self.fetch(cache_key=..., request=..., url=..., fixture=...)` and parse. They must work with `network=False`: they read the mirror only.
2. **`sync(cui)`** downloads everything your READ methods will need for that company and returns a `SyncReport(downloaded, reused, failed)`. Use the **same `cache_key`s** as the READ methods. That's what connects them.
3. **Reuse before download.** If a mirror entry can't have changed (a filed statement, a closed case), return it without a call.
4. **Bulk sources:** leave `sync()` as the default no-op and load data in an `ingest_*` job instead.
5. **Batch APIs:** download in batches in a job, then `store_in_mirror(cache_key, body_for_one_company, url)` once per company, so READ methods find per-company entries.
6. Tests: `network=True` + `httpx.MockTransport` to test `sync`, then `network=False` to prove the READ path makes **zero** calls (see `verifirm/adapters/tests/test_anaf_bilant.py`).

Reference implementation: **`verifirm/adapters/anaf_bilant.py`**.

## How to write an agent (checklist)

- Use `ctx.adapter("<name>")` READ methods only. They are network-free by construction.
- `SourceUnavailable` (including "not in the local mirror yet") → put the adapter in `sources_failed` → PARTIAL / UNAVAILABLE. **Never clean.**
- Copy `Sourced.source` into your signals: it carries `retrieved_at`, so the UI shows how old the data is. If `Sourced.stale` is True, say so in `notes`.
- Never import `httpx` or call a URL from an agent. `tests/architecture/test_imports.py` enforces it.

Reference implementation: **`verifirm/agents/financials/`**.
