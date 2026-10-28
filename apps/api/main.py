"""FastAPI app (D4). Contract-first: in FIXTURE_MODE every read route serves fixtures, so the
frontend is never blocked by the backend.

Run: `make run-api` (uvicorn apps.api.main:app --reload). OpenAPI at /docs.
Owner: @role-5-ai-api.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routes import applications, companies, decisions, health, runs
from apps.wiring import build_infra
from verifirm.core.config import get_settings
from verifirm.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    app.state.infra = build_infra(settings)
    yield
    await app.state.infra.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="verifirm API",
        version="0.1.0",
        description="Agentic background checks. The AI never decides: the analyst does.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (health, companies, applications, runs, decisions):
        app.include_router(module.router)
    return app


app = create_app()
