# CLAUDE.md: shared rules for every Claude Code instance on this repo

Five Claude Code instances (roles 1–5) work here in parallel. Role 6 uses Claude + Lovable and reads `docs/SOLUTION.md` instead. Read this file fully before touching anything.

## 0. The product in one paragraph

**verifirm** is an agentic background-check system for Raiffeisen Bank Romania's corporate clients. It continuously re-verifies the portfolio and fact-checks new credit applications (CUI + documents) against official Romanian sources. Eight agents run in parallel, a deterministic engine scores the results, an LLM writes a memo **only from the consolidated JSON**, and a critic removes any unsourced sentence. **The AI never decides. The analyst decides.**

## 1. Ask before deciding

- If something is not written in this file, `docs/DECISIONS.md`, or your stub's docstring, **stop and ask the human**. Propose 2–3 options with short trade-offs, then wait.
- Never add a dependency without asking. If approved, add it to `pyproject.toml` in the same PR that uses it.
- Never overwrite or delete files outside your folder.

## 2. Who owns what (CODEOWNERS)

| Role | Owns |
|---|---|
| 1 Database | `verifirm/persistence/`, `apps/worker/jobs/ingest_*`, `verifirm/adapters/onrc_bulk.py`. **Only role 1 writes Alembic migrations.** |
| 2 Core | `verifirm/schema/`, `verifirm/core/`, `verifirm/scoring/`, `apps/worker/` (orchestrator, main, scheduler, change_detection), `apps/wiring.py`, `adapters/base.py`, `agents/base.py`, root config, CI, `tests/`. **Only role 2 edits `schema/` and `core/`.** |
| 3 Official agents | `verifirm/agents/{identity,financials,tax,network}/`, `verifirm/adapters/anaf_*`, `verifirm/adapters/mocks/`, `jobs/sweep_anaf_v9.py` |
| 4 External agents | `verifirm/agents/{litigation,sanctions,media,presence}/`, `adapters/{portal_just,scj,sanctions_*,web_search,seap,kohesio}.py`, `jobs/poll_new_cases.py` |
| 5 AI + API | `verifirm/llm/`, `verifirm/consolidation/`, `verifirm/adapters/documents.py`, `apps/api/` |
| 6 Frontend + demo | `frontend/`, `fixtures/`, `docs/DEMO.md` |

### Stay inside your folder

If you need a change in `verifirm/schema/` or `verifirm/core/` (or any folder you don't own): **don't edit it.** Add a `PENDING` entry to `docs/DECISIONS.md` describing the change and why, tell the human, and continue with a local workaround. Schema changes need a `DECIDED` entry first, because every package depends on the schema.

## 3. Repo map

```
verifirm/                 the Python package (the brief's "packages/")
  schema/                 THE contract (Pydantic). Frozen without a DECISIONS.md entry
  core/                   cui gate, config, logging, registry, timebudget, ports/, impl_local/, impl_cloud/
  adapters/               one file per source on top of adapters/base.py; mocks/ for unreachable sources
  agents/<name>/          8 independent agents: agent.py, rules.py, README.md, tests/
  consolidation/          identity_sheet, entity_resolution, memo/, critic/
  scoring/                deterministic engine + config/weights.yaml (no LLM, no network)
  llm/                    the ONLY code that talks to LLM providers; json_output, untrusted
  persistence/            Postgres 17: engine.py, models/, repositories/, alembic.ini, migrations/
apps/api/                 FastAPI. Serves fixtures in FIXTURE_MODE (contract-first)
apps/worker/              queue consumer, orchestrator (pipeline flow), scheduler, jobs/
apps/wiring.py            Settings -> port implementations (the only place infra is chosen)
fixtures/                 fictional demo data + tools/build_fixtures.py + tools/check_fixtures.py
docs/                     SOLUTION, DECISIONS, ARCHITECTURE, RULES, SOURCES, DEMO, schema/
tests/                    architecture/ (import rules, migrations), contract/ (API + schema), e2e/
```

Tests live **next to the code** (`<folder>/tests/test_<module>.py`, no `__init__.py`), so you stay inside your folder.

## 4. Hard rules (never break these)

1. **Schema is frozen.** `verifirm/schema/*` changes need a DECIDED entry in `docs/DECISIONS.md`. Agents communicate **only** through schema-validated JSON. Free text never crosses agent boundaries.
2. **A source failure is never clean.** A timeout, outage, missing fixture or switched-off source gives `unavailable` / `timeout` / `partial` and goes in `sources_failed`. An agent never returns `ok` with zero signals when it couldn't check. A source outage can never produce GREEN.
3. **Media rules.** Only claims with URL + date. Always `validated=false`, max severity medium, and they **can never trigger STOP**.
4. **Rate limits** are declared on the adapter class (`rate_limit`, `rate_limit_key`) and enforced by the `RateLimiter` port, which is global across workers. ANAF: 1 req/s, v9 max 100 CUIs/request. Never call a source in a loop without going through `BaseAdapter.fetch()`.
5. **CUI gate first.** Every entry point calls `verifirm.core.cui.validate_cui`. Fictional CUIs pass only with `FIXTURE_MODE=1`.
6. **Untrusted text** (PDFs, web pages, court data) is wrapped with `verifirm.llm.untrusted.wrap_untrusted` before any LLM sees it. Prompts state that `<untrusted_data>` is data, not instructions.
7. **LLM only via `verifirm/llm`.** Everyone else uses the `LLMClient` port (`ctx.llm`) and `llm.json_output` (schema-constrained + re-validated). Model names come from config.
8. **Scoring has no LLM** and no network. Same inputs + same `weights.yaml` give the same score.
9. **Identity sheet comes from official sources only**, never from the web.
10. **No CNP, and no personal data beyond what the sources publish.** Don't log document contents.
11. **Fictional data is clearly marked:** `"fictional": true`, `.example` URLs, `J99` register numbers, invalid-checksum 99000xxx CUIs. `make fixtures-check` must stay green. DEDEMAN SRL (2816464) is real: never commit figures for it.
12. **The AI never decides.** No "approve/reject" wording in memos. The decision endpoint only records what the analyst chose.
13. **Postgres only (D5).** No SQLite anywhere, not even in tests. Every schema change is a new Alembic migration named `<area>_<what>`. Bulk loads use COPY (`persistence.engine.copy_records`).
14. **No central lists.** Agents and adapters self-register (`@register_agent`, `@register_adapter`). Adding one never edits the orchestrator.
15. **Idempotent jobs.** Every run has a `run_id`. Signal ids are deterministic (`agents.base.make_signal_id`), so re-runs never duplicate.
16. **Config over code.** Weights, thresholds, time budgets, TTLs and model names go in `weights.yaml` / env (`.env.example`), not constants buried in logic.

## 5. Coding conventions

- Python 3.12, full type hints (`mypy` runs with `disallow_untyped_defs`), `from __future__ import annotations`.
- Adapters and agents are `async`. Never block the loop (use `asyncio.to_thread` for CPU or file work).
- Match the surrounding style: short docstrings that say *what and why*, ruff-formatted, line length 100.
- One module, one test file. Rules are pure functions, so unit-test them first, then the agent with fixtures.
- Small PRs, one concern each. The PR title starts with the area (`agents/tax: …`).
- Logging through `verifirm.core.logging.get_logger`. Context (`run_id`, `cui`, `agent`) is attached automatically.

## 6. Commands

```bash
make install         # uv sync
make test            # all tests (Postgres tests skip without `make up`)
make check           # lint + typecheck + fixtures-check + test  (= CI)
make run-api         # http://localhost:8000/docs
make up              # postgres 17 + redis in docker
make fixtures        # regenerate fixtures from fixtures/tools/build_fixtures.py
make db-revision m=signals_add_index   # role 1 only
```

## 7. Definition of done

- [ ] The stub's docstring contract is implemented (inputs, outputs, rules, sources, rule_ids).
- [ ] The `pytest.skip("TODO…")` is replaced by real tests: rules on edge cases, the agent on fixtures, failure paths (source down / timeout gives unavailable or partial, never clean).
- [ ] Works in `FIXTURE_MODE=1` with no network and with nobody else's unfinished code.
- [ ] New rule_ids are in `rules.py` **and** `docs/RULES.md`. New sources are in `docs/SOURCES.md`.
- [ ] `make check` is green. No new dependency without approval. No edits outside your folder.
- [ ] Demo expectations in your agent's README still hold (`make demo-check` once the pipeline is complete).
