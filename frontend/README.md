# frontend/

**Owner:** `@role-6-frontend-demo`. React 18 + Vite 5, plain JavaScript and CSS.
What is built, the stack and the open points: **[HANDOFF.md](HANDOFF.md)**.

- The API contract, band colours, UI rules and the "never" list are in **[../docs/SOLUTION.md](../docs/SOLUTION.md)**.
- JSON Schemas for every response: [../docs/schema/](../docs/schema/).
- Demo script: [../docs/DEMO.md](../docs/DEMO.md).

No scoring logic in the frontend: display what the API returns.

## Run locally

Requires Node.js LTS. In this folder:

```
npm install
npm run dev
```

Open http://localhost:5173. On Windows PowerShell, if `npm` is blocked by the execution policy, use `npm.cmd` instead.

- `src/App.jsx`: top menu and the three views (Dashboard, Alerts, Messages)
- `src/api.js`: the only file that loads data
- `src/styles.css`: colours (top of the file) and styles

## Data: live API, snapshot or mock

Shapes follow the API's Pydantic models (`verifirm/schema/api.py`, JSON Schemas in `docs/schema/`).

Copy `.env.example` to `.env.local` and set `VITE_API_URL` (e.g. `http://localhost:8000`, or the
tunnel URL from the backend team). Then:

- **Snapshot (the default once you have one):** while the API is reachable, run `npm run snapshot`.
  It saves the API's answers to `snapshot/data.json` (git-ignored: it can hold real-company figures).
  From then on the site reads that local copy and makes no server calls. The top bar shows
  "Snapshot · date". Run `npm run snapshot` again to refresh it.
- **Live API:** no snapshot yet, or `VITE_DATA_SOURCE=live` in `.env.local`. Restart `npm run dev`.
  The top bar shows "Live API".
- **Mock:** no snapshot and no `VITE_API_URL`. Shows the team's fixtures
  (`fixtures/companies/*/api/*.json`, read-only). The top bar shows "MOCK DATA".

In every mode, 10 invented companies from `src/mock/` are added, labelled FICTIV.

Accounts, bank relationship, flag history and messages are not in the API contract yet: they are mock,
and reviews and messages are kept in this browser only.
