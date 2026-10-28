"""models/audit.py: table names, primary keys and the indexes the queries rely on."""

from verifirm.persistence.models import Base


def test_tables() -> None:
    tables = Base.metadata.tables
    t = tables["audit_decisions"]
    assert [c.name for c in t.primary_key] == ["decision_id"]
    assert t.c.cui.index
