# sanctions agent

**Owner:** `@role-4-external-agents`

**Component:** `sanctions` (weight 10, PROPOSAL) · **Sources:** EU FSF, UN, OFAC (bulk, OFFICIAL), **MOCK** PEP

**Data access (local-first, [docs/LOCAL_DATA.md](../../../docs/LOCAL_DATA.md)):** locally ingested EU/UN/OFAC entries (ingest_sanctions job), `mock_pep`. Never call external APIs from the agent. "Not in the local mirror yet" is unavailable, never clean. Reference: `agents/financials/`.

| rule_id | Severity (PROPOSAL) | Condition |
|---|---|---|
| SAN-MATCH-CONFIRMED-01 | critical, **auto-stop** | score ≥ 0.95 + a second identifier agrees |
| SAN-MATCH-POSSIBLE-01 | medium | 0.85 ≤ score < 0.95, or no second identifier |
| SAN-PEP-01 | medium | PEP match (MOCK) |

Fuzzy matching is deterministic (`matching.py`, stdlib `difflib`), with no LLM.
GREEN requires both `identity` and `sanctions` to be available.
