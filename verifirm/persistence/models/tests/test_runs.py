"""models/runs.py: table names, primary keys and the indexes the queries rely on."""

from verifirm.persistence.models import Base


def test_tables() -> None:
    tables = Base.metadata.tables
    assert [c.name for c in tables["runs_runs"].primary_key] == ["run_id"]
    assert tables["runs_runs"].c.cui.index
    assert [c.name for c in tables["runs_agent_results"].primary_key] == ["run_id", "agent"]
