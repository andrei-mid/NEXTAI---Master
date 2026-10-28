# anaf_v9: ANAF VAT registry adapter

**Owner:** role 3 · **Code:** [`anaf_v9.py`](anaf_v9.py) · **Tests:** [`tests/test_anaf_v9.py`](tests/test_anaf_v9.py) (36, no network)

Reads ANAF's v9 web service: VAT registration, VAT on collection (TVA la încasare), inactive /
reactivated status, split VAT, the RO e-Factura register, plus name, address, CAEN code and legal
form. Used by the identity sheet, the identity and tax agents, `anaf_efactura_registry` and the
future `sweep_anaf_v9` job.

## 1. ANAF's rules, and how this adapter follows them

From ANAF's documentation (*"Folosirea serviciului este supusa urmatoarelor reguli"*):

> a) A request may contain at most 100 CUIs. A client may make at most 1 request per second.
> b) Any attempt to overload the server will be punished under the regulations in force.

These are **not negotiable**. The adapter guarantees:

| Guarantee | How | Test |
|---|---|---|
| **One call = at most one request** | The only line that sends a request runs once per call. No method sends requests in a loop | `test_every_network_method_makes_at_most_one_request` |
| **Max 100 per request** | More than 100 *entries* (an entry = one CUI + one date) raises `ValueError` **before anything is sent**. Counting entries satisfies both readings of "100 CUIs" | `test_more_than_100_cuis_is_refused_before_sending` |
| **Max 1 request / second** | Every request first waits for the global `RateLimiter` (key `anaf_webservicesp`, shared with `/bilant`) | `test_batch_is_one_request_for_at_most_100_cuis` |
| **No retries** | On a 429, any 5xx, or a timeout: **one attempt**, the failure is reported, and the old stored copy is served as `stale` | `test_no_error_is_ever_retried`, `test_timeout_is_not_retried` |
| **Agents never call ANAF** | READ methods (`lookup`, `history`) read the local mirror only | `test_read_path_never_calls_anaf` |
| **Nothing is downloaded twice** | A past date never changes, so it is downloaded once, ever. Today's record is re-asked only after 24h | `test_second_sync_same_day_makes_no_request` |

Anything that needs several requests (the daily sweep over the portfolio) must **schedule** them
(one batch of 100 per run). It must never loop inside a single run.

## 2. The API call

`POST https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva`, with a list of `{cui, data}`
entries. `data` is **the date the answer is for**, so one request can ask the same company for
several dates:

```json
[
  {"cui": 99000025, "data": "2026-10-28"},
  {"cui": 99000025, "data": "2026-09-30"},
  {"cui": 99000025, "data": "2026-08-31"}
]
```

The answer is `{"found": [...], "notFound": [cui, ...]}`. Each found record carries
`date_generale.cui` **and** `date_generale.data`, which is how answers are matched back to their
entries (`split_entries`). ANAF's documentation shows a `{"cod", "message"}` wrapper. Live answers
come without it. Both are accepted.

## 3. What is stored per company

Each entry in the local mirror is shaped like a v9 answer for one company:

| Mirror key | Content | Downloaded |
|---|---|---|
| `99000025` | the **latest** record (what agents read with `lookup`) | again when older than 24h |
| `99000025:2026-10-28` | ANAF's answer **for today** | daily |
| `99000025:2026-09-30`, `…-06-30`, `…-03-31`, `99000025:2025-12-31` | ANAF's answer **for each of the last 4 quarter-ends** | **once, ever** |

So for every company we keep a year of official snapshots (5 data points): name, address, CAEN,
legal form, VAT and inactive status as ANAF saw them at each quarter-end. Live ONRC data has no office history, so
these snapshots are the official way to detect "the registered office changed".

## 4. How many requests over time (one company)

| When | Entries in the request | Requests |
|---|---|---|
| First sync | today + 4 quarter-ends = **5** | **1** |
| Same day again | nothing missing | **0** |
| Next day | today | **1** (1 entry) |
| First sync of a new quarter | today + the new quarter-end | **1** (2 entries) |
| ANAF down / 429 / timeout | none: no retry | **1**, then serve the old copy |

## 5. Methods

| Method | Network? | What it does |
|---|---|---|
| `sync(cui)` | yes (sync code only) | ONE request with today + the missing quarter-ends, capped at 100 entries. The rest waits for the next sync |
| `lookup(cui, date)` | no for agents | The latest record, or `None` if ANAF lists the CUI in `notFound`. Unreadable means `SourceUnavailable`, never "clean" |
| `history(cui, dates=None)` | **never** | `{ISO date: record or None}` for the stored snapshots. Missing dates are left out (unknown). In fixture mode: today only |
| `lookup_batch(cuis, date)` | sync adapters only | ONE request for at most 100 CUIs (for the sweep job). Without network: reads the mirror |
| `split_entries(payload, entries)` | (pure) | Matches answers on CUI **and** date, so two dates of one company never overwrite each other |
| `missing(cui)` | **never** | The dates `sync` would ask for (used by the fetch tool's plan) |
| `download(entries)` | sync adapters only | EXACTLY one request for given entries (max 100) |
| `history_dates(today, quarters)` | (pure) | The quarter-ends to keep, newest first |

## 6. Failure handling

Hard rule 2: **a source failure is never clean.**
- ANAF down, 429, 5xx or a timeout: the failure is reported (`SyncReport.failed`, or `SourceUnavailable`). The old copy is served with `stale=True`. No retry.
- An invalid answer, or one that doesn't mention the CUI: nothing is stored. The agents see the source as unavailable.
- A corrupt stored entry: downloaded again on the next sync (in the same single request), instead of being reused for 24h.
- A CUI in `notFound`: stored as `None`. That is a fact ("ANAF doesn't know this CUI"), not an error.

## 7. Fetching real data (a human, one request per run)

The ONE place a human triggers ANAF requests is the fetch tool
[`apps/worker/jobs/sweep_anaf_v9.py`](../../apps/worker/jobs/sweep_anaf_v9.py). **Dry run by
default**: it prints the exact request. Only `--send` sends it. One request per run, at least
1.1 s apart even across runs (lock file), no retries, real CUIs only.

```bash
uv run python -m apps.worker.jobs.sweep_anaf_v9 status 2816464 160796        # no request
uv run python -m apps.worker.jobs.sweep_anaf_v9 v9 2816464 160796            # dry run
uv run python -m apps.worker.jobs.sweep_anaf_v9 v9 2816464 160796 --send     # 1 request, 10 entries
uv run python -m apps.worker.jobs.sweep_anaf_v9 bilant 2816464 --send        # 1 request: newest missing year
uv run python -m apps.worker.jobs.sweep_anaf_v9 web 2816464 --send         # Tavily (not ANAF): 2 searches
SYNC_ON_APPLICATION=0 uv run python -m apps.worker.seed 2816464 160796       # 0 requests: mirror -> Postgres
```

A shared server must run with **`SYNC_ON_APPLICATION=0`**: otherwise every "recheck" click in
the frontend syncs, which means ANAF requests nobody approved.

## 8. How to check it (no network)

```bash
uv run pytest verifirm/adapters/tests/test_anaf_v9.py -q
```

Every test uses a **simulated ANAF** (`httpx.MockTransport`) that counts every request. Nothing in
the tests ever reaches the real ANAF.

**Live runs** are a human decision: no Claude instance runs one on its own. A live run needs a
single process (`EMBEDDED_WORKER=1`) or `RATE_LIMITER_BACKEND=redis`, because the default rate
limiter only counts within one process. See [infra/local/README.md](../../infra/local/README.md).

## 9. Still open

| Item | Owner | Status |
|---|---|---|
| Use `history()` in `ID-OFFICE-CHANGE-01` (official office-change detection) | role 3 | next |
| Scheduled `sweep_anaf_v9.run` | role 3 | **not automated on purpose**: only a human triggers ANAF requests (fetch tool above) |
| The same rule for `anaf_bilant` (today 6 requests in a loop per sync, with retries) | role 2 + role 3 | PENDING in `docs/DECISIONS.md` |
| Rate limiter counts per process by default | role 2 | PENDING in `docs/DECISIONS.md` |
| Fixtures with past-date snapshots (demo of office change) | role 6 | optional |
