# presence agent

**Owner:** `@role-4-external-agents` (built by role 3 with the human's approval, 2026-10-29)

**Component:** `presence` (weight 5, PROPOSAL) · **Sources:** website + job postings (`web_search`, WEB), `seap` and `kohesio` (OFFICIAL), turnover from `anaf_bilant`

**Data access (local-first, [docs/LOCAL_DATA.md](../../../docs/LOCAL_DATA.md)):** READ methods only, no network. "Not in the local mirror yet" is unavailable, never clean.

Does the company leave the public trace a business of its size normally leaves?

## Status

| Part | State |
|---|---|
| `rules.py` (3 checks) + `config.yaml` | **done**, unit-tested |
| `agent.py` | **done**, tested with the real adapters in `FIXTURE_MODE` and in the full pipeline. Zephyria's signal matches `api/signals.json` |
| `web_search.footprint`, `seap.contracts_for`, `kohesio.projects_for` | **fixture mode only** (`presence.json`). Live they report **unavailable**: SEAP and Kohesio need an ingest job, website / jobs need the Tavily sync + `TAVILY_API_KEY` |

## Rules

| rule_id | Severity (PROPOSAL) | Condition |
|---|---|---|
| PRE-NO-FOOTPRINT-01 | medium (confidence 0.8) | turnover > 5M RON and **all four** parts checked and empty: no website, no jobs, no SEAP contracts, no EU funds |
| PRE-ADDRESS-MISMATCH-01 | low, **validated=false** (website text) | the website's address shares < 60% of its words with the ONRC registered office (after normalizing diacritics and abbreviations) |
| PRE-PUBLIC-CONTRACTS-01 | info (positive) | SEAP contracts or EU-funded projects found |

## Decisions

1. **"We couldn't look" is never "there is nothing".** PRE-NO-FOOTPRINT-01 needs all four parts checked. One unknown part means no conclusion, a note, and status `partial`.
2. **No footprint source at all means `unavailable`**, even if the turnover was read. Turnover alone is not a presence check, so real companies never get presence coverage they didn't earn.
3. **Absence of evidence is weaker than evidence**, so PRE-NO-FOOTPRINT-01 has confidence 0.8: searches can miss a site.
4. Website text is unvalidated web data: the address check is `validated=false` (capped at medium, never STOP).

## Demo expectations (fixtures)

| Company | Result |
|---|---|
| **Zephyria** | PRE-NO-FOOTPRINT-01: no website, jobs, SEAP or EU funds despite 18,600,000 RON 2025 turnover |
| Aurora | none: website + 2 job postings, same address as ONRC |
| Brunaldo | none: has a website, same address as ONRC |
| Other fictional companies, real companies | `unavailable`: no footprint data |

## How to check it

```bash
uv run pytest verifirm/agents/presence verifirm/adapters/tests/test_seap.py verifirm/adapters/tests/test_kohesio.py verifirm/adapters/tests/test_web_search.py -q
```

## Next (to get real data)

- **Website + jobs:** implement the Tavily presence queries in `web_search.sync()` (Tavily's free tier is enough for a demo; needs `TAVILY_API_KEY`).
- **SEAP:** an ingest job for the procurement exports on data.gov.ro, then `contracts_for` reads the local table.
- **Kohesio:** an ingest job for the Romanian beneficiaries export.

## Files

`config.yaml`, `rules.py`, `agent.py`, `tests/`. Adapters: `adapters/presence_fixture.py` (shared fixture reader), `seap.py`, `kohesio.py`, `web_search.py` (`footprint`).
