"""STUB. Owner: @role-2-core. Decide which companies get a full re-check.

Implement `run(infra)`:
- Inputs: change records from ingest_onrc / ingest_sanctions / sweep_anaf_v9 / poll_new_cases,
  plus companies whose latest score is older than the staleness limit (config, e.g. 30 days).
- Enqueue one RunRequest(trigger=SWEEP) per company with dedupe_key=f"sweep:{cui}:{date}",
  so re-running this job the same day never duplicates runs (idempotent).
Return {"enqueued": n, "reasons": {cui: [...]}}.
"""

from __future__ import annotations

from typing import Any

from apps.wiring import Infra


async def run(infra: Infra) -> dict[str, Any]:
    raise NotImplementedError
