"""STUB. Owner: @role-1-database. Monthly ONRC bulk ingest.

Implement `run(infra)`:
1. infra.adapters["onrc_bulk"].download(tmp_dir) (streaming, ~675 MB OD_FIRME.CSV).
2. Stream rows -> verifirm.persistence.engine.copy_records into STAGING tables
   (a new onrc_snapshots row). Normalize addresses + person names while streaming.
3. Swap staging -> current in one transaction. Keep the previous snapshot for the diff.
4. Diff vs the previous snapshot: changed name/address/status/representatives -> change records
   for change_detection.py. Idempotent: re-running for the same dataset date is a no-op.
Return {"snapshot_id", "rows", "changed_cuis"}.
"""

from __future__ import annotations

from typing import Any

from apps.wiring import Infra


async def run(infra: Infra) -> dict[str, Any]:
    raise NotImplementedError
