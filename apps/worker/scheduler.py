"""Scheduled job DEFINITIONS only. Running them (APScheduler, cron, EventBridge in AWS)
is not decided yet (PENDING in DECISIONS.md). All times are Europe/Bucharest.
Owner: @role-2-core (ingest_* jobs: @role-1-database).

Principle: cheap global checks first (change detection). Only companies with changes or a
stale score get a full re-check enqueued.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobSpec:
    name: str
    cron: str  # minute hour day month weekday
    entrypoint: str  # "module:function", an async def run(infra) -> dict
    description: str


JOBS: tuple[JobSpec, ...] = (
    JobSpec(
        "ingest_onrc",
        "0 2 3 * *",
        "apps.worker.jobs.ingest_onrc:run",
        "Monthly ONRC open-data snapshot -> COPY into onrc_* tables, then diff vs the previous snapshot",
    ),
    JobSpec(
        "ingest_sanctions",
        "30 1 * * *",
        "apps.worker.jobs.ingest_sanctions:run",
        "Daily EU FSF / UN / OFAC download. Re-screen the portfolio if a list changed",
    ),
    JobSpec(
        "sweep_anaf_v9",
        "0 4 * * *",
        "apps.worker.jobs.sweep_anaf_v9:run",
        "Daily v9 batches of 100 CUIs (1 req/s) over the whole portfolio: inactive / VAT / name / address changes",
    ),
    JobSpec(
        "poll_new_cases",
        "0 * * * *",
        "apps.worker.jobs.poll_new_cases:run",
        "Hourly Portal Just CautareDosare2 (last-modified) + nightly ICCJ refresh inside 03:30-06:30",
    ),
    JobSpec(
        "change_detection",
        "0 7 * * *",
        "apps.worker.jobs.change_detection:run",
        "Collect changes from the jobs above + stale scores -> enqueue full re-checks (idempotent)",
    ),
)
