"""SQLAlchemy models, one file per area. Importing this package registers every table on
Base.metadata (migrations/env.py relies on that for autogenerate).

Conventions for @role-1-database:
- Store full pydantic payloads as JSONB (`model_dump(mode="json")`) next to the indexed
  columns you query. verifirm.schema stays the source of truth.
- Every table has created_at (timestamptz, server default now()).
- Table names are prefixed with the area: companies_*, runs_*, signals_*, ...
"""

from verifirm.persistence.models import (  # noqa: F401  (register tables)
    analyst,
    audit,
    companies,
    graph,
    memos,
    onrc,
    runs,
    sanctions,
    scores,
    signals,
    source_cache,
)
from verifirm.persistence.models.base import Base

__all__ = ["Base"]
