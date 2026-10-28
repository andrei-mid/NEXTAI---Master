"""models/signals.py: table names, primary keys and the indexes the queries rely on."""

from verifirm.persistence.models import Base


def test_tables() -> None:
    tables = Base.metadata.tables
    t = tables["signals_signals"]
    assert [c.name for c in t.primary_key] == ["run_id", "signal_id"]
    indexed = {tuple(c.name for c in ix.columns) for ix in t.indexes}
    assert {("cui", "run_id"), ("rule_id",), ("severity",)} <= indexed
