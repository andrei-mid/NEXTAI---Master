# media agent

**Owner:** `@role-4-external-agents`

**Component:** `media` (weight 5, PROPOSAL) · **Source:** web search (Tavily, D10), type `WEB`

**Data access (local-first, [docs/LOCAL_DATA.md](../../../docs/LOCAL_DATA.md)):** `ctx.web_search` = the Tavily mirror written by `web_search.sync()`. Same query strings. Never call external APIs from the agent. "Not in the local mirror yet" is unavailable, never clean. Reference: `agents/financials/`.

| rule_id | Severity (PROPOSAL) | Condition |
|---|---|---|
| MED-ADVERSE-01 | medium (max) | adverse article with URL + date |
| MED-NEGATIVE-01 | low | other negative article with URL + date |

Hard rules: only claims with **URL + date**, always `validated=false`, max severity **medium**, **can never trigger STOP**.
The `Signal` model validator enforces the cap even if this agent gets it wrong.
