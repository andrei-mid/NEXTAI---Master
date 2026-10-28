# identity agent

**Owner:** `@role-3-official-agents`

**Component:** `identity` (weight 15, PROPOSAL) · **Sources:** `anaf_v9`, `onrc_bulk` (OFFICIAL only, never the web)

Checks who the company is and whether its identity looks unstable.

**Data access (local-first, [docs/LOCAL_DATA.md](../../../docs/LOCAL_DATA.md)):** `anaf_v9` + `onrc_bulk` READ methods (mirror / local tables), `mock_shareholders`. Never call external APIs from the agent. "Not in the local mirror yet" is unavailable, never clean. Reference: `agents/financials/`.

| rule_id | Severity (PROPOSAL) | Condition |
|---|---|---|
| ID-INACTIVE-01 | critical, **auto-stop** | ANAF fiscally inactive |
| ID-REACTIVATED-01 | medium | reactivated in the last 12 months |
| ID-ADMIN-CHANGE-01 | medium | administrator changed in the last 12 months |
| ID-OFFICE-CHANGE-01 | low | registered office changed in the last 12 months |
| ID-SHARED-OFFICE-01 | medium | office shared by ≥ 20 companies |
| ID-CAEN-UNAUTH-01 | medium | main CAEN not authorized (Rev.2 ↔ Rev.3 mapped) |
| ID-STATUS-01 | high | ONRC status not active |
| ID-NATURAL-PERSON-01 | info | PFA / II / IF → separate flow (AI Act) |

**Demo expectations:** Zephyria triggers ADMIN-CHANGE (2025-11-02, Marcela Inventatu → Ionel Fictivescu) and SHARED-OFFICE (63). Aurora triggers nothing.

**Files:** `agent.py` (orchestrates checks), `rules.py` (pure functions, unit-test these first), `tests/`.
