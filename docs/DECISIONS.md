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
| Tests layout | Next to the code (`<folder>/tests/`), pytest `--import-mode=importlib` |
| Tooling on Windows | `winget install astral-sh.uv ezwinports.make` |

## PENDING

| Item | Owner | Notes |
|---|---|---|
| Scoring weights, penalties, thresholds, rule severities | role 2 + team | Proposal in `verifirm/scoring/config/weights.yaml` and `docs/RULES.md` |
| Second real company for the demo (besides Dedeman) | role 6 | Must be clean and public. Live data only, no committed figures |
| Retention period for the GDPR audit log and submitted documents | role 1 + team | Affects `audit_*` tables and S3 lifecycle |
| Auth for the demo (analyst identity on decisions) | role 5 | `DecisionRequest.analyst` is free text for now |
| Dedeman live run while `FIXTURE_MODE=1` | role 2 | Today fixture mode serves only fixtures + last-known-good copies. Options: (a) run the demo with `FIXTURE_MODE=0` and pre-warmed caches for fictional companies, (b) add a per-CUI "live if real" switch, (c) pre-fetch Dedeman before the demo so the last-known-good copy serves it |
| Scheduler runtime | role 2 | APScheduler in the worker vs cron vs EventBridge (Fargate). Job definitions are in `apps/worker/scheduler.py` |
| PDF parsing library for `documents.py` | role 5 | Not chosen |
| Read API for the audit log (`GET /companies/{cui}/decisions`) | role 5 + 6 | DEMO step 8 shows the audit log, but the contract has no read route yet. Schema change → needs DECIDED |
| Port for bulk tables (ONRC / sanctions / SEAP / Kohesio lookups) | role 1 + 2 | Adapters need local lookup tables. Today that is implicit in `persistence`. Decide whether it becomes a port |
| SQS dedupe strategy | role 2 | FIFO queue + MessageDeduplicationId vs standard queue + Repository idempotency |
| Real handles for CODEOWNERS | team | Replace the `@role-N-…` placeholders |
| Identity thresholds | role 3 | `verifirm/agents/identity/config.yaml` (PROPOSAL): `window_days` 365, `shared_office_min_companies` 20, `conflict_confidence` 0.6, `stale_confidence` 0.8. Same pattern as `agents/financials/config.yaml` |
| `onrc_bulk` per-company contract | role 1 + role 3 | The identity agent reads `onrc_bulk.company(cui)` in the **`fixtures/companies/*/onrc.json` shape** (`cui`, `denumire`, `cod_inmatriculare`, `stare`, ...) and `None` for not found. It passes the **raw** ONRC address to `companies_at_address()`, so normalization should happen inside the adapter. Confirm or propose another shape |
