from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.deps import settings_dep
from verifirm import __version__
from verifirm.core.config import Settings
from verifirm.schema.api import Health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health)
async def health(settings: Settings = Depends(settings_dep)) -> Health:
    return Health(status="ok", fixture_mode=settings.fixture_mode, version=__version__)
