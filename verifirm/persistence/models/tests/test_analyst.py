"""models/analyst.py: table name, primary key and the index the latest-opinion query uses."""

from verifirm.persistence.models import Base


def test_tables() -> None:
    t = Base.metadata.tables["analyst_opinions"]
    assert [c.name for c in t.primary_key] == ["run_id"]
    assert ("cui", "generated_at") in {tuple(c.name for c in ix.columns) for ix in t.indexes}
    assert {"payload", "dossier", "created_at"} <= set(t.c.keys())
