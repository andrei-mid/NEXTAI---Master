"""End to end in FIXTURE_MODE: each demo company must land in its expected band.

Skips automatically while any pipeline step is still a stub. Once everything is implemented
it becomes the demo's safety net (`make demo-check`).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apps.wiring import build_infra
from apps.worker.orchestrator import run_pipeline
from verifirm.core.config import Settings
from verifirm.schema.runs import RunRequest, RunState, RunTrigger
from verifirm.schema.scoring import Band

EXPECTED = {"99000017": Band.GREEN, "99000025": Band.RED, "99000033": Band.RED}


@pytest.mark.parametrize("cui", sorted(EXPECTED))
async def test_demo_company_band(cui: str) -> None:
    infra = build_infra(
        Settings(
            fixture_mode=True,
            llm_provider="fake",
            repository_backend="memory",
            queue_backend="memory",
        )
    )
    try:
        status = await run_pipeline(
            RunRequest(
                run_id=f"e2e-{cui}",
                cui=cui,
                trigger=RunTrigger.RECHECK,
                requested_at=datetime.now(UTC),
            ),
            infra,
        )
    finally:
        await infra.aclose()
    if status.state == RunState.FAILED and "not implemented" in (status.error or ""):
        pytest.skip("TODO: e2e becomes active once every pipeline step is implemented")
    assert status.state == RunState.COMPLETED
    assert status.band == EXPECTED[cui]
    assert status.band != Band.STOP  # Brunaldo: insolvency only requested, not opened
