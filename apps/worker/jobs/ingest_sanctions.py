"""STUB. Owner: @role-1-database. Daily sanctions-list ingest (EU FSF via RSS, UN, OFAC).

Implement `run(infra)`:
1. For each of sanctions_eu / sanctions_un / sanctions_ofac: download_entries().
2. Same content_hash as the stored list -> skip. Otherwise COPY into sanctions_entries (staging + swap).
3. A list changed -> record "re-screen portfolio" for change_detection.py (screening is cheap, so
   re-screen everyone).
Return {"lists_changed": [...], "entries": n}.
"""

from __future__ import annotations

from typing import Any

from apps.wiring import Infra


async def run(infra: Infra) -> dict[str, Any]:
    raise NotImplementedError
