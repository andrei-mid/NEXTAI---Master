"""STUB. Owner: @role-1-database. Company/person relationship graph (network agent + GET /companies/{cui}/graph).

Planned tables (write them as SQLAlchemy 2.0 typed models: `class X(Base)` with `Mapped[...]`,
then generate the migration `alembic revision --autogenerate -m "graph_create_tables"`):
- graph_nodes: node_id PK ('company:<cui>' | 'person:<normalized name>'), type, label, status, fictional
- graph_edges: (source, target, role) PK, since, until, run_id, evidence signal_id
- Rebuilt from onrc_representatives + mock shareholders + e-Factura flows. Query depth <= 2 with a recursive CTE.
"""

from __future__ import annotations

from verifirm.persistence.models.base import Base

__all__ = ["Base"]
