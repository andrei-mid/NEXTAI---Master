# frontend/

**Owner:** `@role-6-frontend-demo`. Built in Lovable (D8 = L1: frontend only).

- The API contract, band colours, UI rules and the "never" list are in **[../docs/SOLUTION.md](../docs/SOLUTION.md)**. Paste it into Lovable as project knowledge.
- JSON Schemas for every response: [../docs/schema/](../docs/schema/).
- The API serves fixture data from day one: `make run-api`, then open http://localhost:8000/docs.
- Demo script: [../docs/DEMO.md](../docs/DEMO.md).

No scoring logic in the frontend: display what the API returns.

## Run locally (React + Vite)

Requires Node.js LTS. In this folder:

```
npm install
npm run dev
```

Open http://localhost:5173. On Windows PowerShell, if `npm` is blocked by the execution policy, use `npm.cmd` instead.

- `src/App.jsx`: the page
- `src/styles.css`: colours (top of the file) and styles

## Data: mock or real API

`src/api.js` is the only file that loads data. Shapes follow the API's Pydantic models
(`verifirm/schema/api.py`, JSON Schemas in `docs/schema/`).

- **Mock (default):** no `VITE_API_URL`. Shows the team's fixtures (`fixtures/companies/*/api/*.json`,
  read-only) plus invented UI companies from `src/mock/`.
- **Real API:** copy `.env.example` to `.env.local` (sets `VITE_API_URL=http://localhost:8000`),
  start the API with `make run-api`, then restart `npm run dev`. The top bar shows "Live API".

Bank relationship and flag history are not in the API contract yet: they are always mock and only
shown for fictional companies.
