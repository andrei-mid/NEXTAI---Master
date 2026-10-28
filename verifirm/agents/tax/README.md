# tax agent

**Owner:** `@role-3-official-agents`

**Component:** `tax` (weight 15, PROPOSAL) · **Sources:** submitted documents vs `anaf_bilant` / `anaf_v9`; **MOCK:** arrears list, D300, e-Factura (SAF-T later)

| rule_id | Severity (PROPOSAL) | Condition |
|---|---|---|
| TAX-DECLARED-GAP-01 | high | submitted vs ANAF differ > 10% |
| TAX-ARREARS-01 | high | on ANAF arrears list (MOCK) |
| TAX-VAT-CANCELLED-01 | medium | VAT cancelled within 24 months |
| TAX-EFACTURA-GAP-01 | medium | D300 vs e-Factura gap > 10% (MOCK) |
| TAX-EFACTURA-REG-01 | low | not enrolled in RO e-Factura |

The "unexplained differences" demo moment (DEMO step 5) is driven by TAX-DECLARED-GAP-01: show submitted and ANAF figures side by side from `signal.data`.
