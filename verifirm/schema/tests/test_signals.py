from datetime import UTC, datetime

from verifirm.schema.signals import (
    Component,
    EntityMatch,
    Severity,
    Signal,
    SourceRef,
    SourceType,
)


def _signal(**overrides: object) -> Signal:
    base: dict[str, object] = dict(
        signal_id="s1",
        cui="99000025",
        agent="media",
        component=Component.MEDIA,
        rule_id="MED-ADVERSE-01",
        claim="An article reports searches at transport firms.",
        source=SourceRef(name="web", type=SourceType.WEB, retrieved_at=datetime.now(UTC)),
        evidence_date=None,
        confidence=0.6,
        severity=Severity.CRITICAL,
        validated=False,
        auto_stop_candidate=True,
        entity_match=EntityMatch(method="person_name", score=0.7, ambiguous=True),
    )
    base.update(overrides)
    return Signal.model_validate(base)


def test_unvalidated_signal_is_capped_and_cannot_stop() -> None:
    s = _signal()
    assert s.severity == Severity.MEDIUM
    assert s.auto_stop_candidate is False


def test_validated_signal_keeps_severity() -> None:
    s = _signal(validated=True, component=Component.LITIGATION, rule_id="LIT-CRIMINAL-01")
    assert s.severity == Severity.CRITICAL and s.auto_stop_candidate is True


def test_roundtrip_json() -> None:
    s = _signal()
    assert Signal.model_validate_json(s.model_dump_json()) == s
