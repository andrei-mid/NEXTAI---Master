# infra/local: single box (D7 option D, used now)

One VM (or a laptop) runs:

```bash
make up            # docker compose: postgres:17 + redis:7
make db-upgrade    # alembic migrations (once role 1 has written them)
make run-api       # FastAPI :8000
make run-worker    # one or more workers (stateless, so start N)
```

`.env` for the single box: `QUEUE_BACKEND=redis`, `CACHE_BACKEND=redis`, `RATE_LIMITER_BACKEND=redis`, `REPOSITORY_BACKEND=postgres`, `OBJECT_STORE_BACKEND=filesystem`. Each backend switches on once its owner has implemented it (see the stubs in `verifirm/core/impl_cloud/` and `verifirm/persistence/`).
