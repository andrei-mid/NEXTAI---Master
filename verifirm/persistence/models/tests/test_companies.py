"""models/companies.py: table names, primary keys and the indexes the queries rely on."""

from verifirm.persistence.models import Base


def test_tables() -> None:
    tables = Base.metadata.tables
    assert [c.name for c in tables["companies_companies"].primary_key] == ["cui"]
    assert tables["companies_companies"].c.latest_band.index
    sheets = tables["companies_identity_sheets"]
    assert {fk.target_fullname for fk in sheets.foreign_keys} == {"companies_companies.cui"}
    assert "payload" in sheets.c and "payload" in tables["companies_submitted_financials"].c
    assert all("created_at" in t.c for n, t in tables.items() if n.startswith("companies_"))
