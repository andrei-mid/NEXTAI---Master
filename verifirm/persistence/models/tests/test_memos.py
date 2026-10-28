"""models/memos.py: table names, primary keys and the indexes the queries rely on."""

from verifirm.persistence.models import Base


def test_tables() -> None:
    tables = Base.metadata.tables
    t = tables["memos_memos"]
    assert [c.name for c in t.primary_key] == ["run_id"]
    assert ("cui", "generated_at") in {tuple(c.name for c in ix.columns) for ix in t.indexes}
