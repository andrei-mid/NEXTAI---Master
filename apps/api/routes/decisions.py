"""POST /companies/{cui}/decision: records the ANALYST's decision in the append-only audit log.

The AI never decides. This route only stores what a human chose, with the band and run they saw.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from apps.api.deps import get_infra, valid_cui
from apps.wiring import Infra
from verifirm.schema.api import DecisionRecord, DecisionRequest

router = APIRouter(tags=["decisions"])


@router.post("/companies/{cui}/decision", response_model=DecisionRecord, status_code=201)
async def record_decision(
    body: DecisionRequest, cui: str = Depends(valid_cui), infra: Infra = Depends(get_infra)
) -> DecisionRecord:
    score = await infra.repository.get_latest_score(cui)
    record = DecisionRecord(
        decision_id=f"dec_{uuid.uuid4().hex}",
        cui=cui,
        decision=body.decision,
        comment=body.comment,
        analyst=body.analyst,
        run_id=score.run_id if score else None,
        band_at_decision=score.band if score else None,
        recorded_at=infra.clock.now(),
    )
    await infra.repository.record_decision(record)
    return record
