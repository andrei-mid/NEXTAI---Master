"""STUB. Owner: @role-4-external-agents. New court cases for portfolio companies.

Implement `run(infra)`:
- Portal Just CautareDosare2 with the last-modified filter since the previous poll, per company
  name (current + former). Respect the 1,000-result cap.
- Inside 03:30-06:30 only: scj.nightly_refresh(all portfolio names) (ICCJ is offline otherwise).
- New/changed cases -> change records for change_detection.py.
Return {"companies_polled": n, "new_cases": n, "scj_refreshed": n}.
"""

from __future__ import annotations

from typing import Any

from apps.wiring import Infra


async def run(infra: Infra) -> dict[str, Any]:
    raise NotImplementedError
