# infra/local: single box (D7 option D, used now)

## Live run on one machine (tested 2026-10-28)

Real data from ANAF, stored in Postgres, shown in the frontend. No Docker needed.

1. **PostgreSQL 17** (same major as RDS). Either `make up` (Docker), or the portable EDB binaries
   (no admin rights, no Windows service):
   ```bash
   # once: download postgresql-17.x-windows-x64-binaries.zip from get.enterprisedb.com, unzip to %LOCALAPPDATA%/verifirm-postgres
   initdb -D <data> -U verifirm -A scram-sha-256 -E UTF8 --locale=C --pwprompt   # password: verifirm (local only)
   pg_ctl -D <data> -o "-p 5433" -l <data>\..\postgres.log start                # 5433 if 5432 is taken
   createdb -h localhost -p 5433 -U verifirm verifirm
   createdb -h localhost -p 5433 -U verifirm verifirm_test                        # tests write here, never into dev
   ```
2. **`.env`** (git-ignored):
   ```
   DATABASE_URL=postgresql+asyncpg://verifirm:verifirm@localhost:5433/verifirm
   TEST_DATABASE_URL=postgresql+asyncpg://verifirm:verifirm@localhost:5433/verifirm_test
   ```
3. `make db-upgrade` (Alembic migrations).
4. **API + embedded worker** (the API also processes the queue, so no Redis or separate worker is needed):
   ```bash
   FIXTURE_MODE=0 REPOSITORY_BACKEND=postgres EMBEDDED_WORKER=1 LLM_PROVIDER=fake make run-api
   ```
   Use `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` to get memos. With `fake`, runs complete without a memo.
5. Trigger a check: `curl -X POST http://localhost:8000/companies/2816464/recheck`. Follow it live with
   `curl -N http://localhost:8000/runs/<run_id>/events`. Then `GET /companies` lists it from Postgres.
6. Frontend: `cd frontend && VITE_API_URL=http://localhost:8000 npm run dev`.

Notes: FIXTURE_MODE=0 rejects the fictional demo CUIs (99000xxx), so in live mode the portfolio only
holds real companies you checked. Downloaded data lands in the local mirror `.data/objects/`.

## Several workers (later)

`.env`: `QUEUE_BACKEND=redis`, `CACHE_BACKEND=redis`, `RATE_LIMITER_BACKEND=redis`, `REPOSITORY_BACKEND=postgres`,
`EMBEDDED_WORKER=0`, then `make run-api` + N x `make run-worker`. Needs the Redis stubs in
`verifirm/core/impl_cloud/` implemented (role 2).
