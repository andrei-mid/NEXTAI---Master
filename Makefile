# verifirm: every recipe is a plain `uv run ...` call, so it works with GNU make on Windows,
# macOS and Linux. Windows: `winget install astral-sh.uv ezwinports.make`.

.DEFAULT_GOAL := help
ALEMBIC := uv run alembic -c verifirm/persistence/alembic.ini

.PHONY: help install test test-pg lint format typecheck schema fixtures fixtures-check \
        run-api run-worker demo-check up down db-upgrade db-revision check

help:
	@echo "install         uv sync (Python 3.12 + all deps)"
	@echo "test            all tests (Postgres tests skip if 'make up' is not running)"
	@echo "test-pg         only the Postgres integration tests (needs 'make up')"
	@echo "lint / format   ruff check / ruff format"
	@echo "typecheck       mypy verifirm apps"
	@echo "schema          export JSON Schemas to docs/schema/"
	@echo "fixtures        regenerate fixtures/ from fixtures/tools/build_fixtures.py"
	@echo "fixtures-check  enforce the fictional-data rules"
	@echo "run-api         FastAPI on http://localhost:8000 (docs at /docs)"
	@echo "run-worker      queue consumer"
	@echo "demo-check      fixtures-check + e2e demo bands"
	@echo "up / down       docker compose: postgres 17 + redis"
	@echo "db-upgrade      alembic upgrade head"
	@echo "db-revision     alembic autogenerate; usage: make db-revision m=signals_add_index"
	@echo "check           lint + typecheck + fixtures-check + test (what CI runs)"

install:
	uv sync

test:
	uv run pytest

test-pg:
	uv run pytest verifirm/persistence -v

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy verifirm apps

schema:
	uv run python -m verifirm.schema.export docs/schema

fixtures:
	uv run python fixtures/tools/build_fixtures.py

fixtures-check:
	uv run python fixtures/tools/check_fixtures.py

run-api:
	uv run uvicorn apps.api.main:app --reload --port 8000

run-worker:
	uv run python -m apps.worker.main

demo-check: fixtures-check
	uv run pytest tests/e2e -v

up:
	docker compose up -d

down:
	docker compose down

db-upgrade:
	$(ALEMBIC) upgrade head

db-revision:
	$(ALEMBIC) revision --autogenerate -m "$(m)"

check: lint typecheck fixtures-check test
