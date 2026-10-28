# tax agent

**Owner:** `@role-3-official-agents`

**Component:** `tax` (weight 15, PROPOSAL) · **Sources:** submitted documents vs `anaf_bilant` / `anaf_v9`; **MOCK:** arrears list, D300, e-Factura (SAF-T later)

**Data access (local-first, [docs/LOCAL_DATA.md](../../../docs/LOCAL_DATA.md)):** `anaf_bilant`, `anaf_v9`, `anaf_efactura_registry` READ methods (mirror), mocks, and `ctx.submitted`. Never call external APIs from the agent. "Not in the local mirror yet" is unavailable, never clean. Reference: `agents/financials/`.

Does the company owe the state, and do its declarations add up? It covers three areas:
**arrears to the state budget** (ANAF's debtors list), **differences in the credit file**
(the applicant's figures vs ANAF), and **tax reconciliation** (VAT history, D300 vs e-Factura).

## Status

| Part | State |
|---|---|
| `rules.py` (5 pure checks) + `config.yaml` | **done**, unit-tested (`tests/test_rules.py`) |
| `agent.py` | **done**, tested with the **real adapters** in `FIXTURE_MODE` (`tests/test_agent.py`). Zephyria's and Brunaldo's output matches `api/signals.json` field by field |
| Adapters it reads | all implemented: `anaf_bilant`, `anaf_v9`, `anaf_efactura_registry`, `mock_restante`, `mock_d300`, `mock_efactura` |
| `ctx.submitted` (`adapters/documents.py`, role 5) | stub. Until it lands, applications have no submitted figures and DECLARED-GAP is skipped with a note (not a failure) |

## Rules

| rule_id | Severity (PROPOSAL) | Condition | Source |
|---|---|---|---|
| TAX-DECLARED-GAP-01 | high | submitted vs ANAF differ > 10% (sign flip / ANAF 0 always a gap), one signal per year | documents vs `anaf_bilant` (OFFICIAL source on the signal) |
| TAX-ARREARS-01 | high | on ANAF's arrears list | `mock_restante` (**MOCK**) |
| TAX-VAT-CANCELLED-01 | medium | VAT cancelled within 24 months, even if re-registered | `anaf_v9` |
| TAX-EFACTURA-GAP-01 | medium if D300 **below** e-Factura, low if above | D300 sales vs e-Factura issued > 10% over the same period | `mock_d300` + `mock_efactura` (**MOCK**) |
| TAX-EFACTURA-REG-01 | low | not enrolled in RO e-Factura | `anaf_efactura_registry` (from v9) |

Thresholds live in [`config.yaml`](config.yaml). Change values there, not in code.

## Decisions (and why)

1. **Profit vs loss is always a gap.** "+1.2M declared, −350k at ANAF" can't be judged with a
   percentage. The same applies when ANAF shows 0. Otherwise the gap must exceed 10% of ANAF's value.
2. **Only fields present on both sides are compared.** Brunaldo submitted only net profit, so
   only that is compared. A submitted year ANAF doesn't have yet gets a note, not a signal.
3. **The direction of the e-Factura gap matters.** D300 below e-Factura means sales were
   under-declared: medium. D300 above e-Factura can be legitimate (exports, B2C): low, and the
   claim says "above". D300 must cover **every month** of the e-Factura period, otherwise the
   check is reported as failed (never a false clean).
4. **Not on the arrears list is clean only for that list.** ANAF publishes only debts above
   its thresholds, quarterly. The note names the quarter and points to the definitive proof:
   a *certificat de atestare fiscală*. The mock accepts an optional `on_white_list` (ANAF's
   no-arrears list). If it contradicts the arrears, the arrears still flag.
5. **No VAT registration and no cancellation date** (Orvanto, Vantiro): a note, no signal.
   Identity already flags those companies as deregistered or inactive.
6. **No submitted documents** (portfolio re-check): DECLARED-GAP is skipped with a note. That
   is not a failed source, because there was nothing to check.

## Demo expectations (fixture data, `today = 2026-10-28`)

| Company | Signals |
|---|---|
| **Zephyria** | DECLARED-GAP 2025: turnover 25.4M vs 18.6M, net result +1.2M vs −350k, employees 14 vs 2 |
| **Brunaldo** | ARREARS (Q2 2026: 412,560 principal + 96,300 accessories) · VAT-CANCELLED (2025-02-01, re-registered 2025-09-15) · EFACTURA-GAP (12.46M vs 15.2M, 18% below) · DECLARED-GAP (net result +300k vs −2.6M) |
| Aurora | none (control). The note says "not on the Q2 2026 arrears list" |
| Kestrel, Pelinor, Vantiro, Mirelda, Calbrona | `partial`: no arrears / D300 / e-Factura mock data |
| Orvanto | EFACTURA-REG (ANAF lists it as not enrolled; it is deregistered), `partial` |
| Dedeman (real) | `unavailable`: no fixtures, never clean |

## How to check it works

```bash
uv run pytest verifirm/agents/tax -q    # rules + agent with the real adapters
make check                              # everything CI runs
```

## Failure handling

Every source is read on its own. A failing one never hides the others' signals. A source goes
to `sources_failed` with a note (status `partial`, or `unavailable` if all fail) when it is
down, switched off, missing, not implemented, `notFound`, or returns data the rules can't check
(unknown arrears type, VAT history missing, D300 not covering the period, documents for another
CUI). Confidence: 1.0, e-Factura gap 0.95, stale mirror data 0.8.

## Where MOCK data will come from

The MOCK sources (arrears, D300, e-Factura) have no API we can legally call. The production
route for each (the applicant's documents, or a paid provider) is in
[docs/SOURCES.md](../../../docs/SOURCES.md). Going live changes only the adapter.

## Files

- `config.yaml`: thresholds and confidences (PROPOSAL).
- `rules.py`: RuleSpecs, `TaxConfig` / `load_config`, the 5 pure checks.
- `agent.py`: reads the sources, runs the checks, writes the claims.
- `tests/test_rules.py`, `tests/test_agent.py`.
