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

## Why three sources are MOCK (and where the real data will come from)

Three of the agent's sources are simulated: the arrears list, D300 and e-Factura. Our mentor
approved this. It isn't laziness: for each one, **we have no legal, reliable way to get the
data ourselves**. Every MOCK signal carries `source.type = "mock"`, so the UI shows a badge and
nobody mistakes simulated data for verified data.

### 1. ANAF arrears list (`mock_restante`): public, but behind a captcha

The list is **public by law** (art. 162 of the Fiscal Procedure Code, Law 207/2015): ANAF
publishes it every quarter. But it only exists as a **search page protected by a captcha**,
with no API and no download we could find. We deliberately don't bypass that captcha:

- **A captcha is ANAF saying "humans only, no automated access."** Bypassing it, with a
  captcha-solving service, browser automation or anything else, means doing on purpose
  exactly what the site owner forbids. That is not a technical detail we can work around.
- **ANAF's own terms:** "any attempt to overload the server is punished under the law". For
  this project that rule is non-negotiable. A scraper that defeats a captcha is the
  textbook case of unwanted automated traffic.
- **Legal and compliance risk for a bank:** getting around a system's access protection can
  count as unauthorized access to a computer system under Romanian law. Whether it applies
  to a public page is a lawyer's question, but no bank compliance team would sign off on a
  product built on it, and Raiffeisen is our client.
- **It would be fragile.** Captchas change, scrapers break, and a check that silently stops
  working is worse than no check. Our rule is "a source failure is never clean".
- **There is a better source anyway.** Absence from the list proves little: ANAF lists only
  debts above legal thresholds, once a quarter. The definitive proof is a **certificat de
  atestare fiscală** (certificate of tax status), which the applicant gets from ANAF and
  submits with the credit file. That is how banks already work.

ANAF also publishes a **list of companies with NO arrears** (OPANAF 1923/2022). The mock
accepts an optional `on_white_list`, so the real list can be plugged in the same way.

### 2. D300 VAT returns (`mock_d300`): the company's confidential data

D300 returns (and the SAF-T D406 file) are the company's own tax filings. ANAF keeps them
private under **fiscal secrecy** (art. 11 of the Fiscal Procedure Code). They are reachable only
through ANAF's private portal (SPV) with **the company's own qualified digital certificate**.
A bank has no right to them without the client's consent.

### 3. e-Factura invoices (`mock_efactura`): the same reason

ANAF's e-Factura API exists, but it uses OAuth tied to **the company's certificate**. It shows
a company's invoices only to that company, or to an app the company has authorized.

### Production route: going live changes only the adapter

| Mock | Real source in production |
|---|---|
| `mock_restante` | The applicant's **certificat de atestare fiscală** (through `adapters/documents.py`), or a licensed data provider |
| `mock_d300` | D300 copies / SAF-T submitted in the credit file, or the client authorizing our app with their certificate |
| `mock_efactura` | The client's consent (OAuth with their certificate), or exports submitted in the credit file |

Each mock sits behind the same READ method the real source will have (`arrears(cui)`,
`returns(cui)`, `invoice_flows(cui)`). So switching to the real source replaces the adapter,
and **this agent doesn't change**. The production route for every mock in the project
(including BPI, shareholders and PEP) is in [docs/SOURCES.md](../../../docs/SOURCES.md).

## Files

- `config.yaml`: thresholds and confidences (PROPOSAL).
- `rules.py`: RuleSpecs, `TaxConfig` / `load_config`, the 5 pure checks.
- `agent.py`: reads the sources, runs the checks, writes the claims.
- `tests/test_rules.py`, `tests/test_agent.py`.
