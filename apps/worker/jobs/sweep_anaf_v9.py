"""STUB. Owner: @role-3-official-agents. Daily ANAF v9 sweep over the whole portfolio (change detection).

Implement `run(infra)`:
- Portfolio CUIs from the Repository -> chunks of 100 -> anaf_v9.lookup_batch (1 req/s globally,
  so 10,000 companies take ~100 s).
- Compare with the last stored record: inactive status, VAT registration, name, address, CAEN.
- Changes -> change records for change_detection.py. Never enqueue full runs from here.
Return {"checked": n, "changed_cuis": [...], "not_found": [...]}.
"""

from __future__ import annotations

from typing import Any

from apps.wiring import Infra


async def run(infra: Infra) -> dict[str, Any]:
    raise NotImplementedError
