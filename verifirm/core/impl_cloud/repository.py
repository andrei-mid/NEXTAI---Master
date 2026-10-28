"""Pointer only. The Postgres Repository (D5: RDS PostgreSQL 17, SQLAlchemy 2.0 async + asyncpg,
Alembic) lives in verifirm/persistence/repositories/sql_repository.py (`SqlRepository`),
because core must not depend on an ORM. apps/wiring.py picks it when REPOSITORY_BACKEND=postgres.
"""
