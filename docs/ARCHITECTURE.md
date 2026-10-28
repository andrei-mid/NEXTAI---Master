# ARCHITECTURE

## Pipeline

```
            POST /applications (CUI + PDFs)      POST /recheck      scheduler: change_detection
                         \                            |                    /
                          v                           v                   v
                     +-------------------- Queue (topic "runs") --------------------+
                                                   |
                                          apps/worker/main.py   (N stateless workers)
                                                   |
  1. CUI gate ............ core/cui.py               invalid -> REJECTED
  2. Identity sheet ...... consolidation/identity_sheet.py   (anaf_v9 + onrc_bulk + mock shareholders; never web)
  3. Submitted docs ...... adapters/documents.py     PDF -> SubmittedFinancials (untrusted text stays inside)
  4. 8 agents in parallel, each under a time budget (core/timebudget.py)
        identity  financials  tax  litigation  network  sanctions  media  presence
        timeout -> TIMEOUT, crash -> UNAVAILABLE, failed source -> PARTIAL  (never clean)
        each finished agent -> Repository + progress event (topic "run-events:<run_id>") -> SSE
  5. Entity resolution ... consolidation/entity_resolution.py  (dedupe, CUI/county/name checks, lower ambiguous confidence)
  6. Scoring ............. scoring/engine.py  (deterministic, weights.yaml, no LLM)
  7. Memo ................ consolidation/memo   (LLM, ONLY from ConsolidatedReport JSON)
  8. Critic .............. consolidation/critic (numbers check + LLM check; removes unsourced sentences)
                                                   |
                                    Repository (Postgres 17) -> API -> Lovable UI -> analyst decision -> audit log
```

The flow lives in `apps/worker/orchestrator.py`. Agents are **discovered** through the registry, so adding one never edits the orchestrator.

## Package dependencies (enforced by `tests/architecture/test_imports.py`)

```
schema  <-  core  <-  adapters  <-  agents/<each>       (agents never import each other)
                 ^        ^   \
                 |        |    -> llm                    (only llm/ imports LLM SDKs)
                 |   consolidation -> llm
                 +-- scoring          (pure: no llm, no network, no adapters, no DB)
                 +-- persistence      (only place with sqlalchemy/asyncpg/alembic)
apps (api, worker, wiring)  ->  everything above;   nothing in verifirm imports apps
```

## Ports and adapters

All infrastructure sits behind a port in `verifirm/core/ports`. `apps/wiring.py` is the only place that picks implementations, driven by `.env`.

| Port | Local (zero services) | Real / cloud |
|---|---|---|
| Queue | MemoryQueue | RedisQueue (compose), SqsQueue (AWS) |
| Cache | MemoryCache | RedisCache |
| ObjectStore | FilesystemObjectStore (`.data/objects`) | S3ObjectStore |
| RateLimiter | MemoryRateLimiter | RedisRateLimiter (global across workers) |
| Repository | MemoryRepository (pure Python) | SqlRepository (Postgres 17, `verifirm/persistence`) |
| LLMClient | FakeLLMClient | anthropic (default), bedrock, openai, openai_compatible (`verifirm/llm`) |
| WebSearch | FixtureWebSearch | TavilyWebSearch (`adapters/web_search.py`) |
| Clock | SystemClock / FixedClock | n/a |

## Scaling principles (and where each lives)

1. **One shared contract.** `verifirm/schema` is the only thing every package depends on. Import rules are tested.
2. **Plug-in registration.** `@register_agent` / `@register_adapter` + `core/registry.discover_*`. No central lists.
3. **Ports and adapters.** See the table above. Infra changes = a new implementation.
4. **Stateless API and workers.** State lives in Repository / Cache / Queue only, so you can run N replicas.
5. **Shared rate limits.** Declared on each adapter class and enforced via the RateLimiter port (Redis in multi-worker setups).
6. **Bulk-first data.** ONRC, sanctions, ICCJ, SEAP and Kohesio are ingested on a schedule (`apps/worker/jobs/ingest_*`, Postgres COPY). Agents read local tables.
7. **Cache everything external.** `BaseAdapter.fetch()`: TTL cache (default 24h, per adapter), raw archive in ObjectStore with a sha256 (audit + replay), last-known-good fallback.
8. **Change detection instead of brute force.** Cheap global sweeps (v9 batches of 100, sanctions re-screen, new cases, ONRC diff) → `change_detection` enqueues full runs only where needed.
9. **Fixture mode.** `FIXTURE_MODE=1` makes adapters read `fixtures/`. Every team member can work offline and independently.
10. **Contract-first API.** Routes serve schema-valid fixtures from day one (`tests/contract/test_api.py`).
11. **Configuration over code.** `weights.yaml`, `.env` (time budgets, TTLs, pool sizes, model names).
12. **Idempotent jobs.** `run_id` everywhere, deterministic `signal_id`s, upserts, queue dedupe keys.

## Deployment

- **Now (D7-D):** one VM running `docker compose` (Postgres 17, Redis), plus API and worker processes. Details in `infra/local/README.md`.
- **Later (D7-A):** Fargate services for the API and workers, SQS, RDS PostgreSQL 17, ElastiCache Redis, S3 (eu-central-1). Details in `infra/aws/README.md`.
