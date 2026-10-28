# DEDEMAN SRL (CUI 2816464): REAL company, clean case

No figures are committed for this company. Its real data is downloaded onto our server by
`apps/worker/sync.py:sync_company("2816464")` (local-first, docs/LOCAL_DATA.md). The raw
responses are archived in the ObjectStore and the agents read that local mirror only, so the
demo does not depend on ANAF being up. Sync it before the demo.

`api/list_item.json` and `api/company.json` contain only public identity facts (name, CUI) and
`band: null` (never checked), so the portfolio view can list it before the live run.
