"""The contract exports to JSON Schema and every fixture round-trips through it."""

from __future__ import annotations

import json
from pathlib import Path

from verifirm.schema.export import contract_models, export
from verifirm.schema.signals import Signal

ROOT = Path(__file__).resolve().parents[2]


def test_every_contract_model_exports(tmp_path: Path) -> None:
    written = export(tmp_path)
    assert len(written) == len(contract_models()) >= 30
    for path in written:
        assert json.loads(path.read_text(encoding="utf-8"))


def test_fixture_signals_roundtrip() -> None:
    files = sorted((ROOT / "fixtures" / "companies").glob("*/api/signals.json"))
    assert files
    for path in files:
        for raw in json.loads(path.read_text(encoding="utf-8")):
            signal = Signal.model_validate(raw)
            assert Signal.model_validate_json(signal.model_dump_json()) == signal
            if not signal.validated:
                assert (
                    signal.severity.value in {"info", "low", "medium"}
                    and not signal.auto_stop_candidate
                )


def test_fixtures_check_passes() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "check_fixtures", ROOT / "fixtures" / "tools" / "check_fixtures.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.check() == []
