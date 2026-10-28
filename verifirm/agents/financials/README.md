# financials agent

**Owner:** `@role-3-official-agents`

**Component:** `financials` (weight 20, PROPOSAL) · **Source:** `anaf_bilant` (OFFICIAL, 5 years, 1 req/s)

| rule_id | Severity (PROPOSAL) | Condition |
|---|---|---|
| FIN-REVENUE-DECLINE-01 | medium | turnover −25% over 3 filed years |
| FIN-LOSS-TREND-01 | medium | loss in ≥ 2 consecutive years |
| FIN-NET-ASSETS-01 | high | equity < ½ share capital |
| FIN-DEBT-RISE-01 | medium | debts outpace turnover / debts > 70% of turnover |
| FIN-HEADCOUNT-01 | medium | turnover per employee > 3M RON |
| FIN-REVENUE-JUMP-01 | medium | turnover +200% YoY |
| FIN-NO-FILING-01 | medium | latest expected year not filed |

Map ANAF indicators **by label** (`val_den_indicator`), never by code. That happens in the adapter, and this agent only sees `FinancialYear`.

**Demo expectations:** see `agent.py` docstring and docs/DEMO.md.
