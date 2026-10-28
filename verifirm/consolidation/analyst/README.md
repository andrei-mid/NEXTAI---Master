# consolidation/analyst: AI analyst opinion

Decision: `docs/DECISIONS.md`, "AI analyst opinion". Contract: `verifirm/schema/analyst.py`.

An LLM reads a **company dossier built by code** and gives its educated opinion to the human
analyst. The opinion **never changes the official score or band** (hard rule 8) and never decides.

| File | What it does |
|---|---|
| `dossier.py` | `collect_inputs` (mirror only: ANAF v9 + its quarterly snapshots, ONRC, /bilant) and `build_dossier` (pure): ANAF vs ONRC `cross_checks` with `match`, `anaf_changes` between snapshots, `financials` + `indicators` computed here, source states, the agents' signals, the official score. People are replaced by aliases ("Administrator A") everywhere |
| `agent.py` | `write_opinion(dossier, llm, model)`: prompt `prompts/analyst.md`, dossier wrapped as untrusted data, output `AnalystDraft` validated, then checked |
| `citations.py` | deterministic checks: every evidence path exists and holds the cited value, every number/date in a flag is in its own evidence, no decision wording, severity capped at `high`. Failing flags go to `rejected` with the reason |
| `config.yaml` | years of /bilant, filing month, max dossier size |

Model: `LLM_MODEL_ANALYST` (falls back to `LLM_MODEL_DEFAULT`). A large model is recommended
(tested: `Qwen/Qwen2.5-72B-Instruct` via Featherless, 4/4 flags backed on Zephyria).

**Pipeline:** `analyse()` runs in `apps/worker/orchestrator.py` after scoring, independent of
the memo (`ANALYST_ENABLED=0` switches it off). A failure (LLM down, invalid output, no key)
completes the run without an opinion and keeps the official score. Stored in `analyst_opinions`
(with the dossier the model saw), served by `GET /companies/{cui}/analyst-opinion`.
