# DEDEMAN SRL (CUI 2816464): REAL company, clean case

No figures are committed for this company. At demo time the adapters fetch live data from ANAF
(and the other official sources). Each adapter archives the raw response through the ObjectStore
and keeps a last-known-good copy (`lastgood/<adapter>/...`) that is served as a fallback if a
source is down during the demo.

`api/list_item.json` and `api/company.json` contain only public identity facts (name, CUI) and
`band: null` (never checked), so the portfolio view can list it before the live run.
