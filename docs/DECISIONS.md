# DECISIONS

Decision log. **DECIDED** entries are binding. **PENDING** entries are open: if your work depends on one, ask the human before choosing. To propose a change to `verifirm/schema` or `verifirm/core`, add a PENDING entry here (who, what, why) and tell the team.

## Team decisions (D1–D12)

| # | Decision | Status | Value |
|---|---|---|---|
| D1 | Project / package name | DECIDED | `verifirm`. The brief's `packages/` folder is the importable package `verifirm/` (so mypy, ruff and VS Code work without import hooks) |
| D2 | Backend language | DECIDED | Python 3.12 |
| D3 | LLM providers | DECIDED | Claude or OpenAI. **Default: Claude via the direct Anthropic API.** Bedrock (Claude, EU region), OpenAI and OpenAI-compatible are switchable with `LLM_PROVIDER`. `fake` is used for tests |
| D4 | API framework | DECIDED | FastAPI (+ uvicorn, python-multipart). SSE via StreamingResponse, no extra library |
| D5 | Database | DECIDED | **PostgreSQL 17 on AWS RDS**, the same version in Docker locally. SQLAlchemy 2.0 async + asyncpg. Alembic migrations, names prefixed by area. Bulk loads via COPY (asyncpg). Pool size from env. **No SQLite anywhere, not even in tests.** The in-memory Repository (pure Python) stays for fixture mode and unit tests. Persistence tests run against real Postgres (skipped locally if it's down, always run in CI) |
| D6 | Queue | DECIDED | Redis locally (docker-compose), SQS in AWS. In-memory for zero-service mode |
| D7 | Deployment | DECIDED | **D now** (single box: docker-compose on one VM/EC2), **A later** (Fargate + SQS) |
| D8 | Lovable role | DECIDED | L1: frontend only, against our API contract |
| D9 | Agent framework | DECIDED | Plain asyncio + Pydantic |
| D10 | Web search provider | DECIDED | Tavily |
| D11 | Team split | DECIDED | 6 people. Roles 1–5 use Claude Code, role 6 uses Claude + Lovable. Owners in `CODEOWNERS` (placeholders `@role-N-…` until real handles are known). Only Core edits `schema/` + `core/`. Only Database writes migrations. Unowned paths → Core. `onrc_bulk.py` → Database. `documents.py` → AI+API |
| D12 | Dependency tool | DECIDED | uv, single project (one `pyproject.toml`, one lockfile) |

## Other decided items

| Item | Value |
|---|---|
| Dependencies approved | pydantic, pydantic-settings, httpx, PyYAML, fastapi, uvicorn, python-multipart, sqlalchemy[asyncio], alembic, asyncpg. Dev: pytest, pytest-asyncio, ruff, mypy, types-PyYAML. Implementing PRs may add: `anthropic`, `openai`, `redis`, `boto3`/`aioboto3` (approved "as needed", listed in the PR) |
| Postgres version | 17 (RDS and docker-compose must match) |
| Local-first data | DECIDED (2026-10-28): external data is downloaded onto our server (ingest jobs + per-company `sync()`). Agents only read the local mirror and never call external APIs. See `docs/LOCAL_DATA.md` |
| Tests layout | Next to the code (`<folder>/tests/`), pytest `--import-mode=importlib` |
| Tooling on Windows | `winget install astral-sh.uv ezwinports.make` |
| Time-travel reads | DECIDED (2026-10-28, role 1, asked by role 6; touches role 2's port + schema and role 5's routes at the team's request): two time axes, never mixed. *Known-at* (`Score.computed_at`, `DecisionRecord.recorded_at`): `as_of` = what the bank knew at the end of that day (UTC). *Happened-at* (`Signal.evidence_date`): events of the company. `Repository` port: `get_score_as_of`, `list_score_history`, `list_signals_as_of`, `list_events`, `list_portfolio_as_of`, `list_decisions_between` (Memory + SQL). `schema.api`: new `ScorePoint`, `CompanyHistory`. API: `?as_of=` on `GET /companies`, `/companies/{cui}`, `/companies/{cui}/signals`; new `GET /companies/{cui}/history?from=&to=`. The identity sheet is not versioned by date (detail `as_of` shows the current sheet). Open: a replay job for monthly demo checkpoints |
| `onrc_bulk` per-company contract | DECIDED (2026-10-28, role 1 + role 3): `company(cui)` returns the `fixtures/companies/*/onrc.json` shape, `None` = not in ONRC. Records built from the bulk CSVs have `caen_principal: None` and empty `istoric_*` lists (the files are a snapshot). `companies_at_address()` takes the raw address and normalizes inside the adapter (`onrc_bulk.normalize_address`); the count includes the company itself. `companies_of_person()` items: `cui, denumire, cod_inmatriculare, judet, stare, nume, calitate, de_la, pana_la, match {method: "person_name", score, ambiguous}` (score 1.0 same name, 0.9 same words in another order) |

## PENDING

| Item | Owner | Notes |
|---|---|---|
| Scoring weights, penalties, thresholds, rule severities | role 2 + team | Proposal in `verifirm/scoring/config/weights.yaml` and `docs/RULES.md`. Engine implemented with these values |
| Financials: CAEN averages for FIN-HEADCOUNT-01 | role 3 | Approximate per-division values in `verifirm/agents/financials/config.yaml` (PROPOSAL, signal confidence 0.8). Replace with INS data |
| Financials: interpretations of the brief | role 3 | DECIDED with the team lead: "debts +50% at constant revenue" = first vs last filed year within the last 3 years, turnover ≤ +10% (falling counts too). FIN-REVENUE-DECLINE-01 and FIN-NO-FILING-01 kept as additions to the brief. Thresholds stay PROPOSAL |
| GREEN when a low-weight source is down | role 2 + team | The brief has "GREEN needs coverage ≥ 80%" AND "an outage can never produce GREEN". Implemented strictly: `green_requires_all_ok: true` (any unavailable/timeout/partial component → at most YELLOW, matching demo step 7). Set it to `false` to allow GREEN at ≥ 80% coverage with identity + sanctions available |
| Second real company for the demo (besides Dedeman) | role 6 | Must be clean and public. Live data only, no committed figures |
| Retention period for the GDPR audit log and submitted documents | role 1 + team | Affects `audit_*` tables and S3 lifecycle |
| Auth for the demo (analyst identity on decisions) | role 5 | `DecisionRequest.analyst` is free text for now |
| Dedeman live run while `FIXTURE_MODE=1` | role 2 | Fixture mode serves fixtures, falling back to the local mirror. Options: (a) run the demo with `FIXTURE_MODE=0` + the fictional companies served from fixtures some other way, (b) a per-CUI "real CUI → mirror" switch, (c) sync Dedeman before the demo (`sync_company`), so the mirror serves it even in fixture mode. (c) already works today |
| Scheduler runtime | role 2 | APScheduler in the worker vs cron vs EventBridge (Fargate). Job definitions are in `apps/worker/scheduler.py` |
| PDF parsing library for `documents.py` | role 5 | Not chosen |
| Read API for the audit log (`GET /companies/{cui}/decisions`) | role 5 + 6 | DEMO step 8 shows the audit log, but the contract has no read route yet. Schema change → needs DECIDED |
| Port for bulk tables (ONRC / sanctions / SEAP / Kohesio lookups) | role 1 + 2 | Adapters may not import `persistence` (test_imports), so `onrc_bulk` can't read the `onrc_*` tables today: outside FIXTURE_MODE its READ methods raise `SourceUnavailable("... bulk-lookup port PENDING")`. **Role 1 proposal:** (1) role 2 adds `verifirm/core/ports/bulk_lookup.py` with an ABC `BulkLookup` (`onrc_company(cui) -> dict \| None`, `onrc_companies_at_address(normalized) -> list[str]`, `onrc_companies_of_person(normalized_name) -> list[dict]`, later sanctions / SEAP / Kohesio methods); (2) `AdapterDeps.bulk: BulkLookup \| None = None` in `adapters/base.py`; (3) `apps/wiring.py` passes role 1's `persistence.repositories.bulk_lookup.SqlBulkLookup` when `REPOSITORY_BACKEND=postgres`. Role 1 writes the implementation and switches `onrc_bulk` to it. Alternative rejected: one mirror entry per company written by ingest (1M+ objects, plus an address index) |
| SQS dedupe strategy | role 2 | FIFO queue + MessageDeduplicationId vs standard queue + Repository idempotency |
| Real handles for CODEOWNERS | team | Replace the `@role-N-…` placeholders |
| LLM timeout setting (`LLM_TIMEOUT_S`) in `core/config.py` | role 5 -> role 2 | `llm/providers/_http.py` uses `max(HTTP_TIMEOUT_S, 90)` until it exists |
| Entity-resolution tunables (ambiguous factor, name thresholds) in `scoring/config/weights.yaml` | role 5 -> role 2 | Today a `ResolutionConfig` dataclass with defaults in `consolidation/entity_resolution.py` |
| `LLM_MODEL_DEFAULT` default is a Claude id | role 5 -> role 2 | With `LLM_PROVIDER=openai` / `openai_compatible` the model names must be set in `.env`. The providers raise a clear error otherwise |
| Anthropic / OpenAI providers use httpx, not the vendor SDKs | role 5 | No new dependency needed. Bedrock stays a stub (needs SigV4: boto3 or the anthropic SDK). Say if you want it |
| Graph depth > 1 in the live read model | role 5 + role 1 | `GET /companies/{cui}/graph` returns one hop from the identity sheet until graph tables exist |
| Identity thresholds | role 3 | `verifirm/agents/identity/config.yaml` (PROPOSAL): `window_days` 365, `shared_office_min_companies` 20, `conflict_confidence` 0.6, `stale_confidence` 0.8. Same pattern as `agents/financials/config.yaml` |
| Tax thresholds | role 3 | `verifirm/agents/tax/config.yaml` (PROPOSAL): declared-gap tolerance 10%, VAT-cancelled window 730 days, e-Factura gap tolerance 10%, e-Factura gap confidence 0.95 (D300 base and e-Factura totals are not the same measure), stale confidence 0.8 |
| anaf_v9 mirror key | role 3 | DECIDED by role 3 (its own adapter): one mirror entry per company, `cache_key = CUI` (latest record), freshness by `mirror_max_age_s`. Not `cui:date`, because a run before the daily sweep would find nothing for "today" and report every company unavailable. The request still sends the reference date to ANAF |
