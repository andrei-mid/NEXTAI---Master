"""STUB. Owner: @role-1-database. ONRC open-data bulk tables (loaded with COPY, swapped atomically per monthly snapshot).

Planned tables (write them as SQLAlchemy 2.0 typed models: `class X(Base)` with `Mapped[...]`,
then generate the migration `alembic revision --autogenerate -m "onrc_create_tables"`):
- onrc_snapshots: snapshot_id PK, dataset_date, files manifest JSONB, loaded_at
- onrc_companies: (snapshot_id, cui) PK, name, reg_no, address_raw, address_normalized (indexed, for ID-SHARED-OFFICE-01), county, legal_form, registration_date, status_code
- onrc_status, onrc_caen_authorized (cui, caen_code, revision), onrc_representatives (cui, person_name, person_name_normalized (indexed), role, valid_from, valid_to)
- onrc_caen_rev2_rev3: rev2_code, rev3_code (mapping for ID-CAEN-UNAUTH-01)
"""

from __future__ import annotations

from verifirm.persistence.models.base import Base

__all__ = ["Base"]
