import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from verifirm.schema.identity import IdentitySheet
from verifirm.schema.scoring import Band
from verifirm.schema.signals import AgentResult, AgentStatus, Component, Severity, Signal
from verifirm.scoring.engine import ScoringConfig, component_score, score

NOW = datetime(2026, 10, 28, tzinfo=UTC)
FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "companies"


def _identity(legal_form: str = "SRL") -> IdentitySheet:
    return IdentitySheet(cui="99000017", current_name="TEST", legal_form=legal_form)


def test_penalty_formula(config: ScoringConfig, make_signal) -> None:
    sig = make_signal(Component.TAX, Severity.HIGH, confidence=0.9, match=0.5)
    assert component_score([sig], config) == round(100 - 35 * 0.9 * 0.5, 1)
    assert component_score([make_signal(Component.TAX, Severity.CRITICAL)] * 3, config) == 0.0


def test_weights_renormalize_over_available(
    config: ScoringConfig, make_results, make_signal
) -> None:
    sig = make_signal(Component.FINANCIALS, Severity.HIGH)  # financials -> 65
    results = make_results(statuses={Component.MEDIA: AgentStatus.UNAVAILABLE}, signals=[sig])
    s = score(cui="1", run_id="r", identity=_identity(), results=results, config=config, now=NOW)
    # 95 weight available: (65*20 + 100*75) / 95
    assert s.trust_score == round((65 * 20 + 100 * 75) / 95, 1)
    media = next(c for c in s.components if c.component == Component.MEDIA)
    assert media.available is False and media.score is None and media.effective_weight == 0


@pytest.mark.parametrize("severity", list(Severity))
@pytest.mark.parametrize("component", list(Component))
def test_adding_a_signal_never_raises_the_score(
    config, make_results, make_signal, severity, component
) -> None:
    base = [make_signal(Component.TAX, Severity.MEDIUM)]
    before = score(
        cui="1",
        run_id="r",
        identity=_identity(),
        results=make_results(signals=base),
        config=config,
        now=NOW,
    )
    after = score(
        cui="1",
        run_id="r",
        identity=_identity(),
        results=make_results(signals=[*base, make_signal(component, severity)]),
        config=config,
        now=NOW,
    )
    assert (after.trust_score or 0) <= (before.trust_score or 0)


@pytest.mark.parametrize(
    "form,expected", [("PFA", True), ("ii", True), ("IF", True), ("SRL", False), (None, False)]
)
def test_natural_person_flow(config, make_results, form, expected) -> None:
    identity = IdentitySheet(cui="1", current_name="X", legal_form=form)
    s = score(
        cui="1", run_id="r", identity=identity, results=make_results(), config=config, now=NOW
    )
    assert s.natural_person_flow is expected


def test_deterministic(config, make_results, make_signal) -> None:
    results = make_results(signals=[make_signal(Component.NETWORK, Severity.HIGH, confidence=0.7)])
    a = score(cui="1", run_id="r", identity=_identity(), results=results, config=config, now=NOW)
    b = score(cui="1", run_id="r", identity=_identity(), results=results, config=config, now=NOW)
    assert a == b


@pytest.mark.parametrize(
    "cui,band", [("99000017", Band.GREEN), ("99000025", Band.RED), ("99000033", Band.RED)]
)
def test_demo_fixtures_land_in_expected_band(config, make_results, cui, band) -> None:
    """Regression against the demo: the fixture signals, scored by the real engine."""
    folder = next(FIXTURES.glob(f"{cui}_*")) / "api"
    signals = [
        Signal.model_validate(s)
        for s in json.loads((folder / "signals.json").read_text(encoding="utf-8"))
    ]
    expected = json.loads((folder / "list_item.json").read_text(encoding="utf-8"))
    results: list[AgentResult] = make_results(signals=signals)
    s = score(cui=cui, run_id="r", identity=_identity(), results=results, config=config, now=NOW)
    assert s.band == band
    assert s.trust_score == expected["score"]
    assert s.band != Band.STOP
