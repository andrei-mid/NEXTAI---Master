from datetime import UTC, datetime

import pytest

from verifirm.schema.identity import IdentitySheet
from verifirm.schema.scoring import Band, Score
from verifirm.schema.signals import AgentResult, AgentStatus, Component, Severity
from verifirm.scoring.engine import ScoringConfig, score

NOW = datetime(2026, 10, 28, tzinfo=UTC)


def _score(results: list[AgentResult], config: ScoringConfig, legal_form: str = "SRL") -> Score:
    identity = IdentitySheet(cui="99000017", current_name="TEST SRL", legal_form=legal_form)
    return score(
        cui="99000017", run_id="r1", identity=identity, results=results, config=config, now=NOW
    )


def test_clean_is_green(config, make_results) -> None:
    s = _score(make_results(), config)
    assert (s.band, s.trust_score, s.band_reasons) == (Band.GREEN, 100.0, [])


@pytest.mark.parametrize("down", list(Component))
@pytest.mark.parametrize(
    "status", [AgentStatus.UNAVAILABLE, AgentStatus.TIMEOUT, AgentStatus.PARTIAL]
)
def test_an_outage_never_yields_green(config, make_results, down, status) -> None:
    s = _score(make_results(statuses={down: status}), config)
    assert s.band == Band.YELLOW  # demo step 7: one source off -> YELLOW
    assert any(r.startswith("OUTAGE:") for r in s.band_reasons)


def test_low_coverage_is_grey(config, make_results) -> None:
    down = {
        c: AgentStatus.UNAVAILABLE
        for c in Component
        if c not in {Component.IDENTITY, Component.FINANCIALS, Component.TAX}
    }
    s = _score(make_results(statuses=down), config)  # 50% coverage
    assert s.band == Band.GREY


def test_nothing_available_is_grey_without_score(config, make_results) -> None:
    s = _score(make_results(statuses={c: AgentStatus.TIMEOUT for c in Component}), config)
    assert s.band == Band.GREY and s.trust_score is None


@pytest.mark.parametrize(
    "rule",
    ["ID-INACTIVE-01", "SAN-MATCH-CONFIRMED-01", "LIT-INSOLVENCY-OPENED-01", "LIT-CRIMINAL-01"],
)
def test_auto_stop_wins_even_with_low_coverage(config, make_results, make_signal, rule) -> None:
    comp = {"ID": Component.IDENTITY, "SAN": Component.SANCTIONS, "LIT": Component.LITIGATION}[
        rule.split("-")[0]
    ]
    sig = make_signal(comp, Severity.CRITICAL, rule_id=rule, auto_stop=True)
    down = {c: AgentStatus.UNAVAILABLE for c in Component if c != comp}
    s = _score(make_results(statuses=down, signals=[sig]), config)
    assert s.band == Band.STOP and s.band_reasons == [f"AUTO_STOP:{rule}"]
    assert s.auto_stop_signal_ids == [sig.signal_id]


def test_media_never_stops(config, make_results, make_signal) -> None:
    # even a (wrongly) validated critical media signal using an auto-stop rule id
    sig = make_signal(Component.MEDIA, Severity.CRITICAL, rule_id="LIT-CRIMINAL-01", auto_stop=True)
    s = _score(make_results(signals=[sig]), config)
    assert s.band != Band.STOP


def test_insolvency_request_is_not_stop(config, make_results, make_signal) -> None:
    sig = make_signal(Component.LITIGATION, Severity.HIGH, rule_id="LIT-INSOLVENCY-REQUEST-01")
    s = _score(make_results(signals=[sig]), config)
    assert s.band == Band.YELLOW  # one HIGH signal


def test_two_high_in_different_components_is_red(config, make_results, make_signal) -> None:
    sigs = [
        make_signal(Component.TAX, Severity.HIGH),
        make_signal(Component.NETWORK, Severity.HIGH),
    ]
    s = _score(make_results(signals=sigs), config)
    assert s.band == Band.RED and s.band_reasons == ["HIGH_SIGNALS:network,tax"]


def test_two_high_in_same_component_is_yellow(config, make_results, make_signal) -> None:
    sigs = [make_signal(Component.TAX, Severity.HIGH), make_signal(Component.TAX, Severity.HIGH)]
    s = _score(make_results(signals=sigs), config)
    assert s.band == Band.YELLOW


def test_low_score_is_red(config, make_results, make_signal) -> None:
    sigs = [
        make_signal(c, Severity.MEDIUM) for c in Component for _ in range(4)
    ]  # 100-60 = 40 everywhere
    s = _score(make_results(signals=sigs), config)
    assert s.trust_score == 40.0 and s.band == Band.RED and "SCORE<50" in s.band_reasons
