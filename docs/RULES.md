# RULES

Every `rule_id` an agent can emit. The source of truth is each agent's `rules.py` (`RuleSpec`). Severities and thresholds are a **PROPOSAL** until DECISIONS.md marks them DECIDED. `tests/contract/test_rules_documented.py` fails if a rule is missing here, or if the auto-stop list in `verifirm/scoring/config/weights.yaml` drifts.

**Naming:** `<AREA>-<WHAT>-<NN>`, e.g. `NET-SERIAL-ADMIN-01`. A new rule needs: a `RuleSpec` in the agent's `rules.py`, a row here, and a unit test in the agent's `tests/`.

**Hard rules that apply to every row:**
- Media (`MED-*`) signals are always `validated=false`, max severity medium, and **never** STOP (enforced by the `Signal` model AND by the scoring engine).
- Only these rules can force **STOP**: `SAN-MATCH-CONFIRMED-01`, `LIT-INSOLVENCY-OPENED-01`, `LIT-CRIMINAL-01`, `ID-INACTIVE-01`.
- A source that fails produces no signal. It shows up as `sources_failed` / agent status `unavailable` / `timeout`, which lowers coverage. Never "clean".

**Penalties (PROPOSAL):** info 0 · low 5 · medium 15 · high 35 · critical 60. Component score = `max(0, 100 − Σ penalty × confidence × match_score)`.


### identity

| rule_id | Severity (PROPOSAL) | Auto-stop | Condition | Source |
|---|---|---|---|---|
| `ID-INACTIVE-01` | critical | **yes** | ANAF declares the company fiscally inactive (stare_inactiv.statusInactivi = true) | anaf_v9 |
| `ID-REACTIVATED-01` | medium |  | Company reactivated by ANAF in the last 12 months (dataReactivare) | anaf_v9 |
| `ID-ADMIN-CHANGE-01` | medium |  | Administrator changed in the last 12 months | onrc_bulk |
| `ID-OFFICE-CHANGE-01` | low |  | Registered office changed in the last 12 months | onrc_bulk, anaf_v9 |
| `ID-SHARED-OFFICE-01` | medium |  | Registered office shared by >= 20 companies (threshold configurable) | onrc_bulk |
| `ID-CAEN-UNAUTH-01` | medium |  | Main CAEN activity not among authorized CAEN codes (Rev.2<->Rev.3 mapped) | onrc_bulk |
| `ID-STATUS-01` | high (per status: deregistered/bankruptcy critical, insolvency/dissolution high, suspended medium, unknown high) |  | ONRC status is not active (dissolution, suspension, deregistered...). Deregistration cross-checked with ANAF `dataRadiere`: on disagreement the worse value wins, `sources_agree=false` | onrc_bulk, anaf_v9 |
| `ID-NATURAL-PERSON-01` | info |  | Legal form PFA/II/IF: route to the natural-person flow (AI Act) | onrc_bulk, anaf_v9 |
| `ID-SOURCE-MISMATCH-01` | high |  | ANAF and ONRC disagree on CUI, register number (old Jxx/nnn/yyyy format only) or name: possible wrong entity | anaf_v9, onrc_bulk |

### financials

| rule_id | Severity (PROPOSAL) | Auto-stop | Condition | Source |
|---|---|---|---|---|
| `FIN-NET-ASSETS-01` | high |  | Equity < 1/2 of share capital in the latest filed year (Law 31/1990 art. 153^24) | anaf_bilant |
| `FIN-REVENUE-JUMP-01` | medium |  | Turnover grew > 300% from one year to the next (base >= 100k RON) | anaf_bilant |
| `FIN-HEADCOUNT-01` | medium |  | Turnover per employee > 5x the average of the CAEN division (averages: config, PROPOSAL) | anaf_bilant |
| `FIN-LOSS-TREND-01` | medium |  | Net loss in >= 2 consecutive years | anaf_bilant |
| `FIN-DEBT-RISE-01` | medium |  | Debts grew > 50% over the last 3 filed years while turnover grew <= 10% (or fell) | anaf_bilant |
| `FIN-REVENUE-DECLINE-01` | medium |  | Turnover fell > 25% over the last 3 filed years | anaf_bilant |
| `FIN-NO-FILING-01` | medium |  | No financial statement for the latest expected year (source reachable, nothing filed) | anaf_bilant |

### tax

| rule_id | Severity (PROPOSAL) | Auto-stop | Condition | Source |
|---|---|---|---|---|
| `TAX-DECLARED-GAP-01` | high |  | Submitted figures differ from ANAF by > 10% (turnover, net result, employees, debts, equity; only fields on both sides). A profit/loss sign flip or ANAF showing 0 is always a gap. One signal per year | documents vs anaf_bilant |
| `TAX-ARREARS-01` | high |  | Company is on ANAF's tax-arrears list. Not being on it is clean for that list only (ANAF lists debts above thresholds); the note names the quarter checked | mock_restante |
| `TAX-VAT-CANCELLED-01` | medium |  | VAT registration cancelled in the last 24 months (even if re-registered) | anaf_v9 |
| `TAX-EFACTURA-GAP-01` | medium (D300 below e-Factura) · low (D300 above: can be legitimate, e.g. exports, B2C) |  | D300 declared sales differ from e-Factura issued totals by > 10% over the same period (D300 must cover every month) | mock_d300 vs mock_efactura |
| `TAX-EFACTURA-REG-01` | low |  | Company not enrolled in RO e-Factura although required | anaf_efactura_registry |

### litigation

| rule_id | Severity (PROPOSAL) | Auto-stop | Condition | Source |
|---|---|---|---|---|
| `LIT-INSOLVENCY-OPENED-01` | critical | **yes** | Insolvency/bankruptcy proceedings OPENED against the company | mock_bpi, portal_just |
| `LIT-INSOLVENCY-REQUEST-01` | high |  | Pending request to open insolvency against the company (not yet opened) | portal_just |
| `LIT-CRIMINAL-01` | critical | **yes** | Criminal case with the company as defendant | portal_just, scj |
| `LIT-MATERIAL-CLAIM-01` | high |  | Claim against the company > 10% of last turnover, pending | portal_just, scj |
| `LIT-MINOR-01` | low |  | Other pending case against the company (labour, small claims...) | portal_just, scj |

### network

| rule_id | Severity (PROPOSAL) | Auto-stop | Condition | Source |
|---|---|---|---|---|
| `NET-SERIAL-ADMIN-01` | high |  | An administrator is/was administrator of >= 2 companies that failed in the last 5 years (bankrupt, insolvent, deregistered, ANAF inactive) | onrc_bulk, anaf_v9, mock_bpi |
| `NET-CIRCULAR-INVOICE-01` | high |  | Invoice cycle A->B->...->A among related companies (total >= 500k RON) | mock_efactura |
| `NET-PARTNER-INACTIVE-01` | medium |  | Main shareholder/partner company is ANAF inactive or deregistered | mock_shareholders, anaf_v9 |

### sanctions

| rule_id | Severity (PROPOSAL) | Auto-stop | Condition | Source |
|---|---|---|---|---|
| `SAN-MATCH-CONFIRMED-01` | critical | **yes** | Company or administrator matches a sanctions entry (score >= 0.95 AND a second identifier agrees: country, birth date, registration no.) | sanctions_eu, sanctions_un, sanctions_ofac |
| `SAN-MATCH-POSSIBLE-01` | medium |  | Possible fuzzy match (0.85 <= score < 0.95, or no second identifier): human review | sanctions_eu, sanctions_un, sanctions_ofac |
| `SAN-PEP-01` | medium |  | Administrator/shareholder matches a PEP entry | mock_pep |

### media

| rule_id | Severity (PROPOSAL) | Auto-stop | Condition | Source |
|---|---|---|---|---|
| `MED-ADVERSE-01` | medium |  | Article with URL + date reports fraud, tax evasion, investigation or searches involving the company or its administrators (unvalidated) | web_search |
| `MED-NEGATIVE-01` | low |  | Article with URL + date reports other negative news (unpaid suppliers, disputes) (unvalidated) | web_search |

### presence

| rule_id | Severity (PROPOSAL) | Auto-stop | Condition | Source |
|---|---|---|---|---|
| `PRE-NO-FOOTPRINT-01` | medium |  | Turnover > 5M RON but no website, no job postings, no SEAP contracts and no EU funds | presence sources |
| `PRE-ADDRESS-MISMATCH-01` | low |  | Address on the company website differs from the ONRC registered office | website vs onrc_bulk |
| `PRE-PUBLIC-CONTRACTS-01` | info |  | Company has SEAP contracts or EU-funded projects (positive footprint) | seap, kohesio |
