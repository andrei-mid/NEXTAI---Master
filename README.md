# verifirm

Agentic background checks for companies (Raiffeisen Bank Romania hackathon challenge). It continuously re-verifies the corporate portfolio and fact-checks new credit applications against official Romanian sources. The system produces a score, sourced signals and a memo. **The analyst decides, never the AI.**

## Run locally in fixture mode (no network, no API keys, no services)

Prerequisites: [uv](https://docs.astral.sh/uv/) and GNU make.
On Windows: `winget install astral-sh.uv ezwinports.make`.

```bash
make install            # Python 3.12 venv + dependencies
cp .env.example .env    # defaults = fixture mode, in-memory ports
make test               # everything passes or is skipped (TODO stubs)
make run-api            # http://localhost:8000/docs
```

Try it:

```bash
curl http://localhost:8000/companies
curl http://localhost:8000/companies/99000025/signals
curl -F cui=99000025 -F files=@some.pdf http://localhost:8000/applications   # -> run_id
curl -N http://localhost:8000/runs/<run_id>/events                           # live agent progress (SSE)
```

Optional services (Postgres 17 + Redis): `make up`, then set `REPOSITORY_BACKEND=postgres` in `.env` once role 1 ships the repository, and run `make db-upgrade`.

## Where to read next

| You are… | Read |
|---|---|
| a teammate using Claude Code | [CLAUDE.md](CLAUDE.md), then your folder's README / stub docstrings |
| working in Lovable / ChatGPT / another AI | [docs/SOLUTION.md](docs/SOLUTION.md) |
| curious about the design | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| preparing the demo | [docs/DEMO.md](docs/DEMO.md) |

Decisions: [docs/DECISIONS.md](docs/DECISIONS.md) · Rules: [docs/RULES.md](docs/RULES.md) · Sources: [docs/SOURCES.md](docs/SOURCES.md) · JSON Schemas: [docs/schema/](docs/schema/)
