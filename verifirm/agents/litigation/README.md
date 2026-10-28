# litigation agent

**Owner:** `@role-4-external-agents`

**Component:** `litigation` (weight 15, PROPOSAL) · **Sources:** `portal_just` (SOAP), `scj` (ICCJ, nightly 03:30–06:30 only), **MOCK** `mock_bpi`

| rule_id | Severity (PROPOSAL) | Condition |
|---|---|---|
| LIT-INSOLVENCY-OPENED-01 | critical, **auto-stop** | insolvency opened |
| LIT-INSOLVENCY-REQUEST-01 | high | pending insolvency request (NOT stop) |
| LIT-CRIMINAL-01 | critical, **auto-stop** | criminal case, company is the defendant |
| LIT-MATERIAL-CLAIM-01 | high | claim > 10% of turnover |
| LIT-MINOR-01 | low | other pending cases |

The LLM classifies each case (`prompts/classify_case.md` → `CaseClassification`). The rules are deterministic.
Parties have no CUI, so matching is by name only and entity resolution lowers confidence on ambiguous names.

**Demo:** Brunaldo is RED, not STOP. Case 9101/99/2026 is only a *request* (first instance, hearing 2026-11-20). The memo explains it becomes STOP once insolvency is opened.
