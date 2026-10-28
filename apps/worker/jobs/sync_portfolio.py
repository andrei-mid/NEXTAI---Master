"""Owner: @role-2-core. Keep the local mirror fresh for the whole portfolio (docs/LOCAL_DATA.md).

Runs every adapter's per-company sync() for each portfolio company. Cheap on repeat runs:
data that cannot change (e.g. a filed balance sheet) is never downloaded twice, and fresh
mirror entries are reused. Batch-friendly sources (ANAF v9: 100 CUIs per call) are refreshed
by their own sweep job (sweep_anaf_v9.py), which writes one mirror entry per CUI.
"""

from __future__ import annotations

from typing import Any

from apps.wiring import Infra
from apps.worker.sync import sync_company

PAGE_SIZE = 200


async def run(infra: Infra) -> dict[str, Any]:
    page, synced, downloaded, failed = 1, 0, 0, {}
    while True:
        cuis, total = await infra.repository.list_portfolio(
            band=None, q=None, page=page, page_size=PAGE_SIZE
        )
        for cui in cuis:
            reports = await sync_company(cui, infra)
            synced += 1
            downloaded += sum(r.downloaded for r in reports)
            bad = [r.adapter for r in reports if r.failed]
            if bad:
                failed[cui] = bad
        if page * PAGE_SIZE >= total or not cuis:
            break
        page += 1
    return {"companies": synced, "downloaded": downloaded, "failed": failed}
