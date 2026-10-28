# SOURCES

Every external source: endpoint, access, limits, real vs mock. Adapter docstrings hold the details. Keep this table in sync when you add or confirm a source.

**Local-first ([LOCAL_DATA.md](LOCAL_DATA.md)):** none of these endpoints is ever called by an agent. Bulk sources are ingested by jobs. Per-company sources are downloaded by the adapter's `sync(cui)` into the local mirror, and agents read only that. How each source gets onto our server: [verifirm/adapters/README.md](../verifirm/adapters/README.md).

| Adapter | Source | Endpoint | Auth | Limits / access | Real / Mock | Fixture |
|---|---|---|---|---|---|---|
| `anaf_v9` | ANAF VAT registry v9 | `POST https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva`, body `[{"cui": 123, "data": "YYYY-MM-DD"}]` | none | **max 100 CUIs/request, 1 req/s** (shared with /bilant). The response is `{found[], notFound[]}` with no cod/message wrapper on live 200s | REAL | `companies/*/anaf_v9.json` |
| `anaf_bilant` | ANAF financial statements | `GET https://webservicesp.anaf.ro/bilant?an={year}&cui={cui}` | none | one CUI-year per call, 1 req/s. **Map by `val_den_indicator` label**, not code | REAL | `companies/*/bilant_<year>.json` |
| `anaf_efactura_registry` | RO e-Factura registry | prefer `date_generale.statusRO_e_Factura` from v9; separate listing TBD | none | to confirm | REAL | via v9 |
| `onrc_bulk` | ONRC open data (data.gov.ro, **CC BY 4.0**) | `OD_FIRME.CSV` (~675 MB), `OD_STARE_FIRMA.CSV`, `OD_CAEN_AUTORIZAT.CSV`, `OD_REPREZENTANTI_LEGALI.CSV`, `OD_SUCURSALE_ALTE_STATE_MEMBRE.CSV` | none | ~monthly. **Bulk only, never per company.** Administrators yes, **shareholders no** | REAL | `sources/onrc/*`, `companies/*/onrc.json` |
| `portal_just` | Romanian courts portal | SOAP `http://portalquery.just.ro/query.asmx`: `CautareDosare`, `CautareDosare2` (last-modified), `CautareSedinte` | none | **max 1,000 results/query**. Parties have **no CUI**, so match by name only | REAL | `companies/*/portal_just.xml` |
| `scj` | ICCJ (High Court) | `http://api.scj.ro:97/api/CautareDosare` (JSON) | none | **only 03:30–06:30**, so nightly batch + cache | REAL | `companies/*/scj.json` (none yet) |
| `sanctions_eu` | EU Financial Sanctions Files | file URL discovered from RSS `https://webgate.ec.europa.eu/fsd/fsf/public/rss` | none (token in the link) | bulk, daily | REAL | `sources/sanctions/eu_fsf_sample.xml` |
| `sanctions_un` | UN SC consolidated list | `https://scsanctions.un.org/resources/xml/en/consolidated.xml` | none | bulk, daily | REAL | `sources/sanctions/un_sample.xml` |
| `sanctions_ofac` | OFAC SDN | `https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV` | none | bulk, daily | REAL | `sources/sanctions/ofac_sdn_sample.csv` |
| `seap` | Public procurement (SEAP) | data.gov.ro procurement exports (URL to confirm) | none | bulk | REAL | `companies/*/presence.json` |
| `kohesio` | EU funds (Kohesio) | `https://kohesio.ec.europa.eu` (API/export to confirm) | none | bulk preferred | REAL | `companies/*/presence.json` |
| `web_search` | Tavily (D10) | `POST https://api.tavily.com/search` | `TAVILY_API_KEY` | plan limits | REAL (WEB, unvalidated) | `companies/*/media.json` |
| `documents` | Applicant's PDFs | upload via `POST /applications` | n/a | untrusted text | SUBMITTED | `companies/*/submitted/financials.json` |
| `mock_bpi` | Insolvency bulletin (BPI) | paid | n/a | n/a | **MOCK** | `companies/*/bpi.json` |
| `mock_restante` | ANAF arrears list | captcha | n/a | n/a | **MOCK** | `companies/*/restante.json` |
| `mock_efactura` | e-Factura invoices | company certificate needed | n/a | n/a | **MOCK** | `companies/*/efactura.json` |
| `mock_d300` | D300 VAT returns (+ SAF-T) | company certificate needed | n/a | n/a | **MOCK** | `companies/*/d300.json` |
| `mock_shareholders` | Shareholders | paid ONRC extract | n/a | n/a | **MOCK** | `companies/*/shareholders.json` |
| `mock_pep` | PEP list | commercial | n/a | n/a | **MOCK** | `sources/pep_sample.json` |

**Mocks: where the real data will come from.** Every mock sits behind the same READ method the real source will have, so going live changes only the adapter, never the agents. Checked on 2026-10-28; contracts and prices are TO VERIFY.

| Mock | Why there is no API for us | Production route |
|---|---|---|
| `mock_restante` | Public by law (art. 162 Fiscal Procedure Code, quarterly), but only as a search page with a captcha. Automating it would break ANAF's terms | (1) the applicant's **certificat de atestare fiscală** (definitive) via `documents`, (2) a licensed data provider. ANAF also publishes a **no-arrears list** (OPANAF 1923/2022): the mock accepts an optional `on_white_list` |
| `mock_d300` | The company's confidential tax data: only via SPV with **its own** qualified certificate | The applicant submits D300 copies / SAF-T (D406) in the credit file (`documents`), or authorizes our app with their certificate |
| `mock_efactura` | Same: OAuth tied to the company's certificate | Applicant consent (OAuth with their certificate) or exports submitted in the credit file |
| `mock_bpi` | Free per-name lookup on bpi.ro, full bulletin paid, no API found | Paid ONRC subscription or a commercial provider. Insolvency is also seen for free via ONRC status (identity) and court cases (litigation) |
| `mock_shareholders` | ONRC open data has no shareholders | Paid ONRC extract or a commercial provider |
| `mock_pep` | Commercial lists only | The bank's existing compliance vendor |

**CAEN Rev.2 → Rev.3:** the "CAEN not authorized" rule (`ID-CAEN-UNAUTH-01`) must map both revisions. Import the official INS correspondence table into `fixtures/sources/caen_rev2_rev3.csv` (role 3) and the `onrc_caen_rev2_rev3` table (role 1).
