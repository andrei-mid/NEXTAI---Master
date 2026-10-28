# HANDOFF: RiskLens dashboard v2 (branch `feat/dashboard-v2`)

**For the next Claude Code session.** Read this, then [`design/SPEC.md`](design/SPEC.md) (the team lead's brief, verbatim) and [`design/RiskLens-design-reference.html`](design/RiskLens-design-reference.html) (visual reference + all mock data). Also `CLAUDE.md` and `docs/SOLUTION.md`.

## Status (2026-10-28)

- Step 0 is done: branch created and the existing frontend inventoried. **No code written and nothing deleted yet.**
- The old frontend (Raisa, role 6) is still in `frontend/`: React + Vite, 29 tracked files.

## Decided with the team lead (don't ask again)

| Topic | Decision |
|---|---|
| Location | The new app goes in **`frontend/`** (not `apps/web/`). CODEOWNERS / CLAUDE.md stay valid. The final README is `frontend/README.md`. |
| Mock data source | **`design/RiskLens-design-reference.html`** is the source of truth for mock mode: companies, component scores, signals, financials, cases, network, memos, questions, sources, audit seed. |
| Dedeman (real, 2816464) | "Demo figures, clearly marked": component scores and exposure (250) are demo values → visible **"DATE DEMO"** badge, and record the exception to CLAUDE.md rule 11 in `docs/DECISIONS.md`. |
| Verdict banner | **Risk profile, not a decision** (SOLUTION.md: never make AI output look like a decision): VERDE → "RISC SCĂZUT", ATENȚIE → "DE VERIFICAT", ROȘU and STOP → "RISC RIDICAT", GRI → "DATE INSUFICIENTE". Keep the icons, score ring and "AI-ul recomandă, nu decide". **Not** FAVORABIL/NEFAVORABIL as in the HTML. |
| 10 extra fictional CUIs | 99000104, 112, 120, 139, 147, 155, 163, 171, 180, 198: **verified to FAIL the real checksum** (as required). |

## Proposed defaults: SENT to the team lead, NOT yet confirmed

Confirm these before relying on them, unless the team lead already said "ok":

1. **Rule ids**: the HTML uses ids that don't exist in the backend (`TAX-SUBMIT-GAP-02`, `FIN-NETASSETS-01`, `MEDIA-ADVERSE-01`, `LIT-INSOLV-PETITION-01`, `ID-SHARED-ADDR-01`, …). Map them to the real ids in `docs/RULES.md` (`TAX-DECLARED-GAP-01`, `FIN-NET-ASSETS-01`, `MED-ADVERSE-01`, `LIT-INSOLVENCY-REQUEST-01`, `ID-SHARED-OFFICE-01`, …).
2. **Scoring logic from the HTML** (`computeCo`: weighted mean, GRI below 60% coverage, Portal-Just-down → VERDE becomes ATENȚIE) lives **only in `src/mocks/`**. Components only display.
3. **Dedeman figures**: the HTML's financials (turnover 13,157,835,535 / 12,294,042,595 RON, net profit 1,635,337,205 / 1,636,814,708, capital 2,570,500,000, employees 12,313 / 12,702) **match the real ANAF data** the backend downloaded. Keep them, with source "ANAF /bilant". **The register no. "J1992002621040" could NOT be confirmed** (ANAF returns an empty `nrRegCom`), so show "—".
4. **"Surse de date" texts**: align with `docs/SOURCES.md`. The HTML mentions `rapidfuzz` and ICCJ zip archives, which the backend doesn't use.
5. **Decision "Solicită informații"** → API value `request_info`.
6. **Not in the API contract yet**: exposure, decision queue/status, audit-log read, source status, sweep, 5-year financials, litigation list, declared-vs-official. Full in mock mode. With the real API, those sections show "încă neconectat la API", and each missing endpoint becomes a PENDING entry in `docs/DECISIONS.md` (role 5 API, role 2 schema).
7. **Decision form extras** (AI agreement, checklist, re-check interval) aren't in `DecisionRequest` (`decision`, `comment`, `analyst`): prepend them to `comment` as structured text until the schema is extended (PENDING).
8. **Analyst** = `analist.demo` (no auth yet).
9. **Fixture mode for 99000xxx CUIs**: read `fixture_mode` from `GET /health`. In mock mode, treat it as on.
10. **CI**: add a frontend job (npm ci, lint, test, build) to `.github/workflows/ci.yml`.

## Waiting for "ok" from the team lead

- [ ] **Deletion**: `git rm` the 27 old files in `frontend/` (keep `.gitignore`, `README.md`, and the new `HANDOFF.md` + `design/`) in a separate commit `chore(web): remove old frontend`. Raisa (role 6) owns `frontend/`, so tell her.
- [ ] **npm dependencies**: `vite`, `react@18`, `typescript`, `tailwindcss@3.4`, `react-router-dom@6`, `@tanstack/react-query@5`, `framer-motion`, `lucide-react`, `vitest`, `eslint` + `typescript-eslint`, `json-schema-to-typescript` (TS types from `docs/schema/*.json`).

## Useful facts from the repo

- API contract: `docs/SOLUTION.md`. JSON Schemas: `docs/schema/*.json` (`make schema` regenerates them).
- Backend locally: `make run-api` (fixture mode: fictional companies). Live mode with real companies: `infra/local/README.md` + `make seed-real` (Dedeman, Dacia, Petrom, eMAG, Altex, Hidroelectrica).
- In live mode the backend currently gives GREY bands (coverage 50%: only identity, financials and tax agents exist). That's expected.
