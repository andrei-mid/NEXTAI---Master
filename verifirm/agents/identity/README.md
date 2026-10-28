# identity agent

**Owner:** `@role-3-official-agents`

**Component:** `identity` (weight 15, PROPOSAL) · **Sources:** `anaf_v9`, `onrc_bulk` (OFFICIAL only, never the web)

Checks who the company is and whether its identity looks unstable: fiscally inactive, not
operating, recent administrator or office change, shared office, CAEN not authorized, natural
person, or the official sources not agreeing on who the company is.

## Status

| Part | State |
|---|---|
| `rules.py` (9 pure checks) | **done**, unit-tested (`tests/test_rules.py`) |
| `agent.py` (`run`) | **done**, tested on every fixture company and every failure path (`tests/test_agent.py`) |
| Real `anaf_v9.lookup`, `onrc_bulk.company` / `companies_at_address`, `identity_sheet` | **not implemented yet** (roles 3 / 1 / 5). Tests use stand-ins that read the same fixture files. Until they land, the agent reports those sources as failed with "adapter not implemented yet", never as clean |
| Thresholds | `config.yaml` in this folder (PROPOSAL), loaded by `rules.load_config()`. Change values there, not in code |

## Rules

**Data access (local-first, [docs/LOCAL_DATA.md](../../../docs/LOCAL_DATA.md)):** `anaf_v9` + `onrc_bulk` READ methods (mirror / local tables), `mock_shareholders`. Never call external APIs from the agent. "Not in the local mirror yet" is unavailable, never clean. Reference: `agents/financials/`.

| rule_id | Severity (PROPOSAL) | Condition |
|---|---|---|
| ID-INACTIVE-01 | critical, **auto-stop** | ANAF fiscally inactive |
| ID-REACTIVATED-01 | medium | reactivated in the last 12 months |
| ID-ADMIN-CHANGE-01 | medium | administrator changed in the last 12 months |
| ID-OFFICE-CHANGE-01 | low | registered office changed in the last 12 months |
| ID-SHARED-OFFICE-01 | medium | office shared by ≥ 20 companies |
| ID-CAEN-UNAUTH-01 | medium | main CAEN not authorized (Rev.2 ↔ Rev.3 mapped) |
| ID-STATUS-01 | high (critical for deregistered / bankruptcy, medium for suspended) | ONRC status not active; deregistration cross-checked with ANAF, worse value wins |
| ID-NATURAL-PERSON-01 | info | PFA / II / IF → separate flow (AI Act) |
| ID-SOURCE-MISMATCH-01 | high | ANAF and ONRC disagree on CUI, register no. or name (possible wrong entity) |

The same rows are in `docs/RULES.md`. `tests/contract/test_rules_documented.py` fails if they drift.

## Source authority (read this before touching status logic)

Each fact has one authoritative source. The agent always says which one it used.

| Fact | Authority | Why |
|---|---|---|
| Legal status (operating, insolvency, bankruptcy, dissolution) | ONRC | court decisions are recorded in the trade register |
| Fiscal inactivity | ANAF | only ANAF can declare it |
| VAT, e-Factura | ANAF | ANAF's own registries |
| Administrators | ONRC | that is where they are registered |
| Deregistration (radiere) | **both** | the one status both must show: a real cross-check |

- **ANAF "INREGISTRAT" next to ONRC "faliment" is NOT a conflict.** A company stays a
  registered taxpayer during insolvency and bankruptcy, until it is deregistered. Don't add a
  conflict signal for it (Kestrel in the fixtures is exactly this case).
- **A real disagreement on the same fact** (e.g. ANAF has `dataRadiere`, ONRC says
  `functiune`): the **worse value wins**, both values go in `data`, `sources_agree=false`, and
  the agent lowers confidence. The usual cause is lag: ONRC bulk is monthly, ANAF v9 is daily.
- **CUI / register number / name disagreeing** is not a status question: it may mean the wrong
  entity was matched. That is `ID-SOURCE-MISMATCH-01`. Register numbers are compared only when
  both use the old `Jxx/nnn/yyyy` format, because ONRC changed numbering in 2024 and ANAF may still
  show the old one. This is **not yet verified on live data**.
- The agent never settles a disagreement itself. The analyst resolves it, e.g. with an ONRC
  *certificat constatator*.

## Contract of `rules.py` (for whoever writes `agent.py`)

- Every `check_*` is pure: no I/O, no clock (pass `today` in), no config reads.
- Return value: **`None` = checked, nothing found.** A `dict` = the facts for the signal's
  `data` (dates are `date` objects).
- **`ValueError` = could not check** (missing `stare_inactiv`, empty administrator list, empty
  ONRC status, missing CAEN data...). The agent must catch it and treat the source as failed or
  partial. **Never** turn it into a clean result (CLAUDE.md hard rule 2).
- `ID-STATUS-01` severity varies by status: pass `severity=rules.status_severity(facts)` to
  `BaseAgent.signal(...)`. The table is `STATUS_SEVERITY`. Unknown ONRC status texts map to
  `unknown` with severity high, and are never treated as active.
- Dates accept `date`, ISO strings or `""` (ANAF uses `""` for "no date").
- Input shapes:
  - `check_admin_change`: `[{name, valid_from, valid_to}]`
  - `check_office_change`: `[{address, valid_from, valid_to}]`
  - `check_source_mismatch(v9_record, {cui, trade_register_no, name})`

## Demo expectations (fixture data, `today = 2026-10-28`)

| Company | Signals from this agent |
|---|---|
| Aurora | none (control) |
| **Zephyria** | ADMIN-CHANGE (2025-11-02, Marcela Inventatu → Ionel Fictivescu), SHARED-OFFICE (63) |
| Brunaldo | none (its problems are tax and financial) |
| Kestrel | STATUS: bankruptcy, critical |
| Orvanto | STATUS: deregistered 2023-07-20, critical, ANAF and ONRC agree |
| Pelinor | STATUS: insolvency, high |
| Vantiro | INACTIVE since 2024-06-01 (auto-stop) |
| Calbrona | INACTIVE since 2023-09-01 (auto-stop) |
| Mirelda | none |
| Dedeman (real) | no fixtures, so both sources are `unavailable`, **never clean** |

No fixture triggers REACTIVATED, OFFICE-CHANGE, CAEN-UNAUTH, NATURAL-PERSON or SOURCE-MISMATCH.
Those are covered by inline test data in `tests/test_rules.py`.

## How to check it works

```bash
export PATH="$HOME/.local/bin:$PATH"     # if `uv` is not found
make install                             # once: Python 3.12 + deps via uv
uv run pytest verifirm/agents/identity -q              # this agent's tests
uv run pytest tests/contract/test_rules_documented.py  # RULES.md in sync
make check                               # everything CI runs. Must be green before a PR
```

To see the rules on the demo companies (fixtures only, no network):

```bash
uv run python -c '
import json; from datetime import date; from pathlib import Path
from verifirm.agents.identity import rules
for d in sorted(Path("fixtures/companies").glob("990*")):
    v9 = json.loads((d / "anaf_v9.json").read_text())["found"][0]
    onrc = json.loads((d / "onrc.json").read_text())
    print(d.name, rules.check_inactive(v9), rules.check_status(onrc["stare"], v9["stare_inactiv"]["dataRadiere"]))
'
```

`tests/test_agent.py` runs the whole agent per fixture company and checks Zephyria's output
field by field against `fixtures/companies/99000025_*/api/signals.json` (what the frontend
shows). End to end (`make demo-check`) works once the pipeline's other steps exist.

## ANAF limits are non-negotiable

ANAF's terms: **max 100 CUIs per request, max 1 request per second; any attempt to overload the
server is punished under the law.**

- Develop and test only with `FIXTURE_MODE=1`. Never run live ANAF calls in a loop, from a test, or on a schedule you start yourself.
- Every ANAF call goes through `BaseAdapter.fetch()`: rate limiter (`rate_limit_key =
  "anaf_webservicesp"`, shared by v9 and bilanț), cache, archive.
- Batch with `lookup_batch` (100 per request). Never call per company in a loop.
- A live ANAF request needs explicit human approval. Claude instances: give the command, don't
  run it.

## Dependencies on other roles

| Needed | From | Used for |
|---|---|---|
| `onrc_bulk.company(cui)`, `companies_at_address(addr)` | role 1 | administrators, office history, status, CAEN, shared-office count |
| `consolidation/identity_sheet` builds `ctx.identity` | role 5 | the agent's main input |
| `fixtures/sources/caen_rev2_rev3.csv` (header only today) | role 3 | ID-CAEN-UNAUTH-01 across revisions. Until filled, codes compare within one revision |

**Not verified on live data yet:** whether `OD_REPREZENTANTI_LEGALI` has end dates for
administrators (needed for ADMIN-CHANGE), and whether any office history exists outside our
fixtures (ANAF v9 and the ONRC files are current snapshots, so OFFICE-CHANGE may need snapshot diffs).

## How `agent.py` runs (one run, one company)

1. `anaf_v9.lookup(cui, today)`: **one** ANAF call (cached, rate limited). Gives INACTIVE, REACTIVATED and the
   deregistration date.
2. `onrc_bulk.company(cui)`: gives STATUS (cross-checked with ANAF), plus ADMIN-CHANGE, OFFICE-CHANGE and CAEN-UNAUTH
   from `ctx.identity`. Then `companies_at_address(address)` gives SHARED-OFFICE.
3. Both sources available: SOURCE-MISMATCH (CUI, register number, name).
4. NATURAL-PERSON from the ONRC legal form, with ANAF's wording as backup.

Failure handling: a source that is down, switched off, missing, not implemented, returns `notFound`, or
returns a record the rules can't check goes into `sources_failed` with a note. The result is `partial`
(one source failed) or `unavailable` (both failed). A malformed record is never reused later in the
run. Confidence is 1.0, 0.6 when ANAF and ONRC disagree on the same fact, and 0.8 for stale
(last-known-good) data.

## Files

- `config.yaml`: thresholds and confidences (PROPOSAL).
- `rules.py`: RuleSpecs, `IdentityConfig` / `load_config`, plus the pure checks. Unit-test these first.
- `agent.py`: orchestrates the checks (described above).
- `tests/test_rules.py`: edge cases plus the fixture companies.
- `tests/test_agent.py`: the agent on every fixture company, the API-fixture match, and the failure paths.
