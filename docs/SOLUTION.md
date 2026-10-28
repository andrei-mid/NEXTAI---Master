# verifirm: solution reference (for Lovable, ChatGPT, Featherless and anyone without Claude Code)

Paste this whole file into your AI tool as context. It is self-contained.

## The product

verifirm runs automated background checks on Romanian companies for Raiffeisen Bank Romania. Existing corporate clients are re-verified continuously in the background. New credit applicants submit their CUI (Romanian tax ID) and documents, and everything is fact-checked against official sources. Eight agents (identity, financials, tax, litigation, network, sanctions, media, presence) produce **sourced signals**. A deterministic engine turns them into a **trust score** (0–100), a **band** and a **coverage** figure, and an LLM writes a memo that a critic fact-checks. **The AI never decides: the analyst does.** The UI shows evidence and records the analyst's decision. Nothing else.

## API contract

Base URL: `http://localhost:8000` locally (OpenAPI at `/docs`). JSON Schemas for every model are in `docs/schema/`. From day one the API serves **fixture data**, so you can build the whole UI now.

| Method & path | Returns |
|---|---|
| `GET /health` | `{status, fixture_mode, version}` |
| `GET /companies?band=&q=&page=&page_size=&as_of=` | `{items: [{cui, name, band, score, coverage, last_checked, top_signal, fictional}], page, page_size, total}` |
| `GET /companies/{cui}?as_of=` | `{identity_sheet, score, band, components[], coverage, sources[], last_checked}` |
| `GET /companies/{cui}/signals?as_of=` | `Signal[]` (see below) |
| `GET /companies/{cui}/history?from=&to=` | `{cui, date_from, date_to, scores[{run_id, computed_at, band, score, coverage}], events: Signal[], decisions: DecisionRecord[]}`. All oldest first. See "Time travel" below |
| `GET /companies/{cui}/memo` | `{markdown, questions[{question, reason_signal_ids}], generated_at, verifier_report}` |
| `GET /companies/{cui}/graph?depth=2` | `{nodes[{id, type: company\|person, label, status, fictional}], edges[{source, target, role}]}`. `role` is administrator, former_administrator, shareholder or invoices |
| `POST /applications` (multipart: `cui`, `files[]`) | `202 {run_id}` |
| `GET /runs/{run_id}/events` | **SSE** stream of `{run_id, agent, status, n_signals, elapsed_ms, done}`. Stop when `done: true` |
| `POST /companies/{cui}/recheck` | `202 {run_id}` |
| `POST /companies/{cui}/decision` | body `{decision: approve\|reject\|escalate\|request_info, comment, analyst}` → `201` audit record |

Invalid CUI → `422`. Unknown company → `404`.

**Time travel** (dates `YYYY-MM-DD`, bounds inclusive, all optional):
- `as_of=2026-09-15` on the list, the company and its signals: what the bank knew **at the end of that day**. A company not checked yet by then is left out of the list, and its detail / signals return `404`.
- `/history?from=2026-01-01&to=2026-11-30`: `scores` = the checks made in the period (the band over time), `decisions` = analyst decisions recorded in the period, `events` = what **happened** to the company in the period (signals by `evidence_date`). `from` after `to` → `422`.
- Fixture mode: each demo company has one check (`last_checked`), so `scores` has at most one point; `events` are the fixture signals by date.

**Signal:** `{signal_id, cui, agent, component, rule_id, claim, source{name, type, url, retrieved_at, raw_ref, content_hash}, evidence_date, confidence (0–1), severity (info|low|medium|high|critical), validated, auto_stop_candidate, entity_match{method, score, ambiguous}, data{}}`.
`source.type` is one of `official | aggregator | web | mock | submitted`.

## Band colours

| Band | Meaning | Colour |
|---|---|---|
| GREEN | ≥ 75, no high/critical signals, **all 8 sources checked OK** (any outage → at most YELLOW) | green |
| YELLOW | 50–74, or 1 high signal, or coverage < 80% | amber |
| RED | < 50, or ≥ 2 high signals in different components | red |
| STOP | an auto-stop fact: confirmed sanctions, insolvency opened, criminal case against the company, ANAF inactive | dark red / black |
| GREY | coverage < 60%: not enough data to say anything | grey |
| `null` | never checked yet | neutral outline |

## UI rules

- **Always show coverage** next to the score, as "7/8 sources" plus the percentage. A missing source is never shown as clean.
- Badges: **MOCK** when `source.type == "mock"`, **FICTIV** when `fictional == true` (company or record), **unvalidated** when `validated == false` (media).
- Every signal shows its source and links to `source.url` when present. Also show the data date `source.retrieved_at` ("data as of …"): the backend works on a local copy of the official sources, so freshness must be visible.
- The decision buttons only **record the analyst's decision** (with a mandatory comment). Never pre-select, suggest or highlight a decision.
- **No scoring logic in the frontend.** Display the API's score, band and components as they are.
- Show the memo's `verifier_report`: how many sentences were checked and which were removed, and why.
- Live progress during an application: one row per agent from the SSE stream (running → ok / partial / unavailable / timeout, with n_signals and elapsed time).

## The "never" list

- Never show a source outage as a clean result, and never show GREEN when coverage < 80%.
- Never let a media signal look validated, and never let it trigger STOP.
- Never make the AI's output look like a decision ("approved", "rejected").
- Never compute, round or re-score anything in the frontend.
- Never show a CNP or personal data beyond what the API returns.
- Never hide the MOCK / FICTIV / unvalidated badges.
- Never call external sources (ANAF, courts, web) from the frontend. Everything goes through the API.
