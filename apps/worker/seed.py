"""Fill YOUR local database with real companies, straight from ANAF (`make seed-real`).

Owner: @role-2-core. Real-company figures are never committed to git (CLAUDE.md rule 11), so
instead of sharing a database dump, everyone runs this: the same CUIs go through the real
pipeline (sync from ANAF into the local mirror -> agents -> scoring -> Postgres). ~7 ANAF calls
per company at 1 request/second. Re-running only refreshes stale data.

    make seed-real                      # the companies below
    uv run python -m apps.worker.seed 2816464 160796   # or any CUIs

Needs: Postgres reachable at DATABASE_URL with migrations applied (`make db-upgrade`).
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import UTC, datetime

from apps.wiring import build_infra
from apps.worker.orchestrator import run_pipeline
from verifirm.core.config import Settings
from verifirm.core.cui import InvalidCUIError, validate_cui
from verifirm.schema.runs import RunRequest, RunTrigger

# Real, well-known companies. Names are checked against what ANAF returns at seed time.
REAL_COMPANIES: dict[str, str] = {
    "2816464": "DEDEMAN SRL",
    "160796": "AUTOMOBILE-DACIA SA",
    "1590082": "OMV PETROM SA",
    "14399840": "DANTE INTERNATIONAL SA",
    "2864518": "ALTEX ROMANIA SRL",
    "13267213": "HIDROELECTRICA",
}


async def seed(cuis: list[str]) -> int:
    settings = Settings(fixture_mode=False, repository_backend="postgres")
    infra = build_infra(settings)
    failures = 0
    try:
        for cui in cuis:
            try:
                cui = validate_cui(cui, fixture_mode=False)
            except InvalidCUIError as exc:
                print(f"  SKIP {cui}: {exc}")
                failures += 1
                continue
            run_id = f"seed_{cui}_{uuid.uuid4().hex[:8]}"
            status = await run_pipeline(
                RunRequest(
                    run_id=run_id,
                    cui=cui,
                    trigger=RunTrigger.RECHECK,
                    requested_at=datetime.now(UTC),
                ),
                infra,
            )
            sheet = await infra.repository.get_identity_sheet(cui)
            name = sheet.current_name if sheet else "?"
            expected = REAL_COMPANIES.get(cui)
            warn = "" if expected is None or expected in name else f"  (expected {expected}!)"
            band = status.band.value if status.band else "-"
            note = f" | {status.error[:60]}" if status.error else ""
            print(f"  {cui:>9}  {status.state.value:<9} band={band:<6} {name}{warn}{note}")
            if status.state.value != "completed":
                failures += 1
    finally:
        await infra.aclose()
    return failures


def main() -> None:
    cuis = sys.argv[1:] or list(REAL_COMPANIES)
    print(f"Seeding {len(cuis)} real companies from ANAF into DATABASE_URL ...")
    failures = asyncio.run(seed(cuis))
    print("done" if not failures else f"done with {failures} problem(s)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
