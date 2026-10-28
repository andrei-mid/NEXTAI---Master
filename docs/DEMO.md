# DEMO

**Owner:** `@role-6-frontend-demo`. Demo facts live in `fixtures/tools/build_fixtures.py` (regenerate with `make fixtures`, check with `make fixtures-check`, then `make demo-check`).

## Companies

| CUI | Company | Role in the demo | Expected band |
|---|---|---|---|
| 2816464 | **DEDEMAN SRL** (REAL) | clean case. Real ANAF data, **synced to our server** before the demo (local mirror) | GREEN, 8/8 |
| 99000017 | AURORA SOFT LABS SRL | fictional clean control: steady growth, no signals | GREEN |
| 99000025 | **ZEPHYRIA LOGISTIC NOVA SRL** | serial administrator, declared-vs-ANAF gap, circular invoicing | RED (no STOP) |
| 99000033 | **BRUNALDO TRADE IMPEX SRL** | tax problems + litigation | RED (not STOP) |
| 99000041 | Kestrel Fictiv Transport SRL | affiliate, bankruptcy 2024 (case 9001/99/2024) | n/a |
| 99000058 | Orvanto Distributie SRL | affiliate, deregistered 2023 | n/a |
| 99000066 | Pelinor Construct Grup SRL | affiliate, insolvency 2025 (case 9002/99/2025) | n/a |
| 99000074 | Vantiro Agro Fictiv SRL | affiliate, ANAF inactive since 2024-06-01 | n/a |
| 99000082 | Mirelda Servicii Imaginare SRL | affiliate, active, in the circular-invoicing loop | n/a |
| 99000090 | Calbrona Holding Fictiv SRL | inactive main partner (of Zephyria and Brunaldo) | n/a |

**Zephyria:** founded 2021-03-15, CAEN 4941, office "Str. Exemplului nr. 1, Sector 9, București", shared by 63 companies. Administrator changed 2025-11-02 from Marcela Inventatu to Ionel Fictivescu. Turnover 180k → 410k → 1.9M → 9.8M → 18.6M RON (2021–2025), 2025 net −350k, equity −111k vs 200 RON share capital, 2 employees. Submitted documents declare 25.4M turnover, +1.2M profit, 14 employees. Circular invoicing 2.1M RON Zephyria → Mirelda → Kestrel → Zephyria. No website, jobs or SEAP. Unvalidated media: stiri-fictive.example, 2026-04-12.

**Brunaldo:** founded 2012, CAEN 4690, administrator Sorin Imaginescu. Turnover 32.0M → 15.2M, losses 2023–2025, debts 9.8M → 19.4M, employees 85 → 41. Arrears Q2 2026: 412,560 + 96,300 RON (MOCK). VAT cancelled 2025-02-01, re-registered 2025-09-15. D300 vs e-Factura gap 18%. Cases: 9101/99/2026 (ANAF insolvency **request**, first instance, hearing 2026-11-20), 9102/99/2025 (1.8M claim, appeal), 9103/99/2025 (labour). Submitted 2025 profit +0.3M vs ANAF −2.6M. Unvalidated media: ziar-inventat.example, 2026-03-03.

## Script

1. **Portfolio view.** Every company with its band, score and coverage. FICTIV badges on the fictional ones.
2. **Dedeman.** GREEN, live data, "8/8 sources". Click through to the sources (official ANAF links).
3. **New application for Zephyria.** Upload the PDF and watch per-agent live progress (SSE): network and tax light up.
4. **Network graph.** Ionel Fictivescu → Kestrel (bankrupt), Orvanto (deregistered), Pelinor (insolvency), Vantiro (inactive), Mirelda + the invoice cycle.
5. **Declared vs ANAF.** 25.4M vs 18.6M, +1.2M vs −350k, 14 vs 2 employees. Then the **critic report**: the sentence "The company is very likely a missing-trader fraud vehicle." was removed as unsupported.
6. **Brunaldo: why RED and not STOP.** Insolvency is only *requested* (9101/99/2026, hearing 2026-11-20). The memo says it becomes STOP if opened, and asks for a tax compliance certificate.
7. **Switch a source off.** Re-check Dedeman with one source disabled (`RunRequest.disabled_sources`). It drops to YELLOW, "7/8 sources". An outage is never shown as clean.
8. **Audit log + analyst decision.** The analyst records "escalate" with a comment, and it shows in the audit log. AI Act note: the system supports a human decision, PFA/II/IF go to a separate flow, and every claim is traceable to a source.

## Before the demo

- [ ] `make demo-check` is green (fixtures-check + e2e bands).
- [ ] Dedeman synced to the local mirror that day (`sync_company("2816464")`). See PENDING "Dedeman live run while FIXTURE_MODE=1" in DECISIONS.md.
- [ ] Lovable app points at the demo API URL. CORS restricted to it.
