# HANDOFF: the frontend as it is in the code

**For the next person or Claude session on `frontend/`.** This file describes what is actually built
(branch `raisa`, merged into `main`). The team lead's original RiskLens brief is kept unchanged in
[`design/SPEC.md`](design/SPEC.md); the table at the end says which parts of it were built, built
differently, or not built. Also read `CLAUDE.md` and `docs/SOLUTION.md`.

## Status (2026-10-28)

- The React frontend in this folder is the one in use. It was **not** replaced by RiskLens, and the
  old files were **not** deleted.
- `design/RiskLens-design-reference.html` was removed (role 6's decision). It is in git history
  (added in `bc6e2f9`) if anyone needs it.
- Works in three data modes (below), including live against the backend.

## Stack (what `package.json` installs)

| | In the code |
|---|---|
| Build / dev server | Vite 5.4.21 + `@vitejs/plugin-react` 4.3.4 |
| UI | React 18.3.1 + React DOM |
| Language | JavaScript (JSX), no TypeScript |
| Styles | One plain CSS file, `src/styles.css`, colour tokens on `:root` |
| Routing | None: one page, the top menu switches views in React state |
| Data fetching | `fetch` in `src/api.js`, no query library |
| Charts | Hand-written SVG (dashboard donut), no chart library |
| Animation, icons, fonts | None added (system font, text symbols) |
| Tests / lint | None set up yet |
| Runtime | Node.js 24 + npm (on Windows: `npm.cmd`) |

Nothing else is installed. Adding a dependency needs the owner's approval (CLAUDE.md §1).

## Data: three modes, one file

`src/api.js` is the only place that loads data. Shapes are the API's Pydantic models
(`verifirm/schema/api.py`, JSON Schemas in `docs/schema/`). The mode is chosen in this order:

1. **Snapshot** (default when it exists): `snapshot/data.json`, made with `npm run snapshot` from
   `VITE_API_URL` while the API is reachable; read offline, no server calls. **Git-ignored: it can
   hold real-company figures (rule 11).** Top bar: "Snapshot · date".
2. **Live API**: no snapshot, or `VITE_DATA_SOURCE=live` in `.env.local` (git-ignored). Calls
   `GET /companies`, `/companies/{cui}`, `/companies/{cui}/signals`, `/companies/{cui}/history` at
   `VITE_API_URL`. Top bar: "Live API".
3. **Mock**: neither. Reads the team's fixtures `fixtures/companies/*/api/*.json` (read-only,
   through `import.meta.glob`). Top bar: "MOCK DATA".

In every mode, 10 invented companies from `src/mock/` (CUIs 99001001–99001091, invalid checksum,
`.example` URLs, labelled **FICTIV**) are added and always answered locally, never sent to the API.

## Screens (top menu)

- **Dashboard**: three cards (Urgent = STOP + red, Can be postponed = yellow, Inconclusive = grey or
  not checked), each with "Review in Alerts"; a donut of companies by band with counts in the legend.
- **Alerts**: left list sorted by criticality (name, band dot, top claim, FICTIV/REAL); centre company
  page; right review panel.
  - Company page: identity sheet, "Inconclusive" box for the grey band with the checked / not checked
    components and cited sources, data sources with links; Components (dropdown, closed); Claims and
    sources (collapsed rows, sort by importance or date found, every claim shows its source or a
    "no source link" warning); Check history (from `/history`, live and snapshot only); Flag history
    (dropdown: reviews that raised a flag + messages about the company); Relationship with the bank
    (FICTIV companies only).
  - Review panel: No risk / Status differs between registries / Escalate / Unreliable data, required
    comment, recorded as the signed-in analyst.
- **Messages**: chats between analysts. Clicking a person's name anywhere opens a chat with the
  current company attached as an alert; the recipient opens it with "Open alert". Unread counter in
  the menu.

## Mock parts (not in the API contract yet)

All shown only with FICTIV companies or clearly marked:

- **Accounts** (`src/mock/analysts.js`): 6 analysts with a login (switch with "Signed in as", marked
  MOCK) and 3 relationship managers (contact only). E-mails use `bank.example`.
- **Flag history, bank relationship and contracts** (`src/mock/frontendExtras.js`): invented, only
  for fictional companies. A real company shows "Not shown".
- **Reviews and messages** are kept in this browser's `localStorage`. Nothing is sent to the API.

## Rules kept

- No scoring in the frontend: band, score, coverage and components are shown exactly as received.
  "Inconclusive" is only the display label for the API's `grey` band.
- An unavailable source is never shown as clean.
- No invented figures for a real company (Dedeman, CUI 2816464).
- No "approve / reject" wording; the AI never decides.

## Open points for the backend

- `GET /companies/{cui}` cites only "ANAF VAT registry v9" in `sources`, although the financials
  agent also used ANAF balance sheets. Add that source and the site shows it automatically.
- No `GET` route for past decisions, so reviews stay in the browser (already PENDING in
  `docs/DECISIONS.md`).
- `POST /companies/{cui}/decision` takes `approve / reject / escalate / request_info` and `analyst`;
  the review panel's options do not map to it yet.
- STOP reasons (`band_reasons`) are not in the API response.
- No messaging or accounts endpoints.

## Run

```
npm install
npm run dev          # http://localhost:5173
npm run build
npm run snapshot     # save the live API's data for offline use
```

## design/SPEC.md compared with the code

| SPEC item | In the code |
|---|---|
| Replace the frontend, delete old files (Step 0) | Not done: the existing frontend was kept and extended |
| TypeScript, Tailwind, React Router, TanStack Query, Framer Motion, lucide-react, Google fonts | Not used: plain JS + CSS, no extra libraries (stack above) |
| `VITE_API_BASE_URL`, `VITE_USE_MOCKS=1`, `src/api/client.ts` | `VITE_API_URL` (unset = offline), one `src/api.js` |
| Types generated from `docs/schema/*.json` | Not done (JavaScript) |
| Design tokens (#0B0D10, #FACC15, orange for yellow band, …) | Own dark theme: `--bg #1f2023`, accent `#ffe600`, band colours in `styles.css` |
| UI language: Romanian | English |
| Sidebar nav: Dashboard, Portfolio, Queue, New application, Data sources, Audit | Top menu: Dashboard, Alerts, Messages |
| Dashboard: 4 KPIs, stacked bar, risk "cloud" bubble map, leaderboard, hazard cards | 3 summary cards + band donut |
| Portfolio table, verification queue | Alerts list (sorted, opens the company) |
| Report: identity, 8 component bars, signals with MOCK / unvalidated / auto-stop badges | Built (components and claims as dropdowns) |
| Report: big verdict banner (FAVORABIL / NEFAVORABIL) | Not built; band chip + "Inconclusive" box. The verdict wording was already rejected in the old HANDOFF |
| Report: 5-year financials, declared vs official, litigation, network, memo + client questions | Not built (not in the API responses yet) |
| Analyst decision form (approve / request info / escalate / reject, AI agreement, checklist, re-check interval) | Different: review panel with 4 assessments + required comment, attributed to the signed-in analyst |
| New application page (CUI check, PDF upload, SSE progress) | Not built |
| Data sources page, resilience test | Not built (sources are cited per company instead) |
| Audit log page | Not built |
| Mock data: Dedeman with demo figures and exposure, 20 companies from the architecture report | Not used: team fixtures + 10 own FICTIV companies; no invented Dedeman figures |
| Vitest tests, lint | Not set up |
| Not in SPEC | Built: Messages, analyst accounts, e-mail links, contract owners, check history, offline snapshot |
