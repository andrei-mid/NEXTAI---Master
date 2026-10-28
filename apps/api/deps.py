"""FastAPI dependencies: infra access + the fixture read model used in FIXTURE_MODE.

Fixture read model: fixtures/companies/<cui>_<slug>/api/{list_item,company,signals,memo,graph,
run_events}.json, each already in the schema.api / schema.signals shape (contract tests
validate them). Outside fixture mode the routes will read from the Repository (TODO role 5).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Depends, HTTPException, Request

from apps.wiring import Infra
from verifirm.core.config import Settings, get_settings
from verifirm.core.cui import InvalidCUIError, validate_cui


def get_infra(request: Request) -> Infra:
    infra: Infra = request.app.state.infra
    return infra


def settings_dep() -> Settings:
    return get_settings()


class FixtureStore:
    """Reads the API-shaped fixtures. Read-only, no state."""

    def __init__(self, fixtures_dir: Path) -> None:
        self.root = fixtures_dir / "companies"

    def company_dirs(self) -> list[Path]:
        return sorted(p for p in self.root.iterdir() if p.is_dir() and (p / "api").is_dir())

    def dir_for(self, cui: str) -> Path | None:
        matches = sorted(self.root.glob(f"{cui}_*"))
        return matches[0] if matches and (matches[0] / "api").is_dir() else None

    def read(self, cui: str, name: str) -> Any:
        directory = self.dir_for(cui)
        if directory is None or not (directory / "api" / name).exists():
            raise HTTPException(status_code=404, detail=f"no data for CUI {cui}")
        return json.loads((directory / "api" / name).read_text(encoding="utf-8"))

    def list_items(self) -> list[dict[str, Any]]:
        items = []
        for d in self.company_dirs():
            path = d / "api" / "list_item.json"
            if path.exists():
                items.append(json.loads(path.read_text(encoding="utf-8")))
        return items


@lru_cache(maxsize=4)
def _store(fixtures_dir: Path) -> FixtureStore:
    return FixtureStore(fixtures_dir)


def fixture_store(settings: Settings = Depends(settings_dep)) -> FixtureStore:
    if not settings.fixture_mode:
        raise HTTPException(status_code=501, detail="live read model not implemented yet (role 5)")
    return _store(settings.fixtures_dir)


def valid_cui(cui: str, settings: Settings = Depends(settings_dep)) -> str:
    """CUI gate for path/form parameters: 422 on an invalid checksum."""
    try:
        return validate_cui(cui, fixture_mode=settings.fixture_mode)
    except InvalidCUIError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
