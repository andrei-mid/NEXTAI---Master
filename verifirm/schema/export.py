"""Write the JSON Schema of every contract model to docs/schema/ (run via `make schema`)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import BaseModel

from verifirm.schema import analyst, api, financials, identity, memo, runs, scoring, signals

MODULES = [signals, identity, financials, scoring, memo, runs, api, analyst]


def contract_models() -> dict[str, type[BaseModel]]:
    """All BaseModel subclasses defined in the schema modules, by class name."""
    found: dict[str, type[BaseModel]] = {}
    for module in MODULES:
        for name, obj in vars(module).items():
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseModel)
                and obj is not BaseModel
                and obj.__module__ == module.__name__
            ):
                found[name] = obj
    return found


def export(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, model in sorted(contract_models().items()):
        path = out_dir / f"{name}.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/schema")
    for p in export(target):
        print(p)
