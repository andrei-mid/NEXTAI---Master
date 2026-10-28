# network agent

**Owner:** `@role-3-official-agents`

**Component:** `network` (weight 15, PROPOSAL) · **Sources:** `onrc_bulk` (administrators), `anaf_v9`, **MOCK** `mock_bpi`, `mock_efactura`, `mock_shareholders`

**Data access (local-first, [docs/LOCAL_DATA.md](../../../docs/LOCAL_DATA.md)):** `onrc_bulk` local tables, `anaf_v9` mirror, `mock_*`. Affiliates' data must already be local (bulk ONRC + the v9 sweep). Never fetch per affiliate. Never call external APIs from the agent. "Not in the local mirror yet" is unavailable, never clean. Reference: `agents/financials/`.

| rule_id | Severity (PROPOSAL) | Condition |
|---|---|---|
| NET-SERIAL-ADMIN-01 | high | administrator linked to ≥ 2 failed companies in 5 years |
| NET-CIRCULAR-INVOICE-01 | high | invoice cycle among related companies ≥ 500k RON |
| NET-PARTNER-INACTIVE-01 | medium | main partner inactive / deregistered |

**Demo (step 4):** the Zephyria graph shows Ionel Fictivescu → Kestrel (bankrupt 2024), Orvanto (deregistered 2023), Pelinor (insolvency 2025), Vantiro (inactive 2024-06-01), Mirelda (active, in the invoice cycle). Partner: Calbrona (inactive).
