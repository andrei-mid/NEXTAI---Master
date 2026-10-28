"""Download one company's data into the local mirror (docs/LOCAL_DATA.md). Owner: @role-2-core.

This is the ONLY place in the pipeline that triggers external calls. It runs:
- once at the start of a run for a new application / manual recheck (orchestrator step 1b),
- for the whole portfolio from apps/worker/jobs/sync_portfolio.py.
Every adapter's sync() runs in parallel under SYNC_TIMEOUT_S. Rate limits stay global
because all adapters share the RateLimiter port. A failed sync never fails the run: the
agents then find nothing in the mirror and report the source as unavailable.
"""

from __future__ import annotations

import asyncio
from collections.abc import Collection

from apps.wiring import Infra
from verifirm.adapters.base import BaseAdapter, SyncReport
from verifirm.core.logging import get_logger, log_context

log = get_logger(__name__)


async def _sync_one(adapter: BaseAdapter, cui: str, timeout_s: float) -> SyncReport:
    try:
        return await asyncio.wait_for(adapter.sync(cui), timeout=timeout_s)
    except TimeoutError:
        return SyncReport(adapter=adapter.name, cui=cui, failed=[f"timeout after {timeout_s}s"])
    except NotImplementedError:
        return SyncReport(adapter=adapter.name, cui=cui, skipped="sync not implemented yet")
    except Exception as exc:  # one source must never break the others
        log.exception("sync failed", extra={"adapter": adapter.name})
        return SyncReport(adapter=adapter.name, cui=cui, failed=[f"{type(exc).__name__}: {exc}"])


async def sync_company(cui: str, infra: Infra, *, skip: Collection[str] = ()) -> list[SyncReport]:
    """Run every adapter's sync() for `cui` (except `skip`). No-op in FIXTURE_MODE."""
    if infra.settings.fixture_mode:
        return []
    with log_context(cui=cui):
        adapters = [a for name, a in infra.sync_adapters.items() if name not in skip]
        reports = await asyncio.gather(
            *(_sync_one(a, cui, infra.settings.sync_timeout_s) for a in adapters)
        )
        log.info(
            "company synced",
            extra={
                "downloaded": sum(r.downloaded for r in reports),
                "reused": sum(r.reused for r in reports),
                "failed": [r.adapter for r in reports if r.failed],
            },
        )
        return list(reports)
