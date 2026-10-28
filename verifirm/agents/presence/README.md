# presence agent

**Owner:** `@role-4-external-agents`

**Component:** `presence` (weight 5, PROPOSAL) · **Sources:** website + job postings (web), `seap`, `kohesio`, address vs ONRC

**Data access (local-first, [docs/LOCAL_DATA.md](../../../docs/LOCAL_DATA.md)):** web-search mirror + `seap` / `kohesio` local data + `anaf_bilant` mirror. Never call external APIs from the agent. "Not in the local mirror yet" is unavailable, never clean. Reference: `agents/financials/`.

| rule_id | Severity (PROPOSAL) | Condition |
|---|---|---|
| PRE-NO-FOOTPRINT-01 | medium | turnover > 5M RON but no public footprint |
| PRE-ADDRESS-MISMATCH-01 | low | website address ≠ ONRC office |
| PRE-PUBLIC-CONTRACTS-01 | info | SEAP contracts / EU funds found |

**Demo:** Zephyria has 18.6M RON turnover with no website, no jobs and no SEAP contracts, so it triggers PRE-NO-FOOTPRINT-01.
