"""Postgres persistence (D5): PostgreSQL 17 on AWS RDS, the same version in Docker locally.
SQLAlchemy 2.0 async + asyncpg, migrations with Alembic. Implements the Repository port.

Owner: @role-1-database. Rules:
- Every schema change is a NEW Alembic migration whose message starts with the area
  (e.g. `alembic revision -m "signals_add_rule_index"`). Never edit a merged migration.
- Only role 1 writes migrations.
- Bulk loads (ONRC, sanctions, SEAP, Kohesio) use Postgres COPY via asyncpg: engine.copy_records.
- No SQLite anywhere, not even in tests.
"""
