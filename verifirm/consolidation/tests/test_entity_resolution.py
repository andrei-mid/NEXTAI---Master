from verifirm.consolidation.entity_resolution import resolve
from verifirm.schema.signals import AgentStatus, SourceType


def test_cui_exact_other_company_is_dropped_and_counted(identity, make_signal, make_result) -> None:  # type: ignore[no-untyped-def]
    ok = make_signal("A-01:1")
    wrong = make_signal("A-02:2", cui="99000099")
    out = resolve(identity, [make_result([ok, wrong])])
    assert [s.signal_id for s in out[0].signals] == ["A-01:1"]
    assert "dropped 1" in (out[0].notes or "")


def test_status_is_never_changed(identity, make_signal, make_result) -> None:  # type: ignore[no-untyped-def]
    failed = make_result([make_signal("A-02:2", cui="99000099")], status=AgentStatus.UNAVAILABLE)
    out = resolve(identity, [failed])
    assert out[0].status is AgentStatus.UNAVAILABLE
    assert out[0].sources_failed == ["anaf"] and out[0].signals == []


def test_inputs_are_not_mutated(identity, make_signal, make_result) -> None:  # type: ignore[no-untyped-def]
    sig = make_signal(method="name_fuzzy", data={"matched_name": "TOTALLY OTHER NAME"})
    result = make_result([sig, sig])
    resolve(identity, [result])
    assert len(result.signals) == 2 and result.notes is None


def test_name_county_match_mismatch_and_missing(identity, make_signal, make_result) -> None:  # type: ignore[no-untyped-def]
    same = make_signal("A:1", method="name+county", data={"county": "judetul fictiv"})
    other = make_signal("A:2", method="name+county", data={"county": "Cluj"})
    unknown = make_signal("A:3", method="name+county", data={})
    (res,) = resolve(identity, [make_result([same, other, unknown])])
    by_id = {s.signal_id: s for s in res.signals}
    assert set(by_id) == {"A:1", "A:3"}
    assert not by_id["A:1"].entity_match.ambiguous and by_id["A:1"].confidence == 0.9
    assert by_id["A:3"].entity_match.ambiguous and by_id["A:3"].confidence == 0.45


def test_name_fuzzy_three_outcomes(identity, make_signal, make_result) -> None:  # type: ignore[no-untyped-def]
    close = make_signal(
        "A:1", method="name_fuzzy", data={"matched_name": "Brunaldo Trade Impex S.R.L."}
    )
    middling = make_signal(
        "A:2", method="name_fuzzy", data={"matched_name": "BRUNALDO TRADING IMPORT"}
    )
    far = make_signal("A:3", method="name_fuzzy", data={"matched_name": "ORVANTO DISTRIBUTIE"})
    (res,) = resolve(identity, [make_result([close, middling, far])])
    by_id = {s.signal_id: s for s in res.signals}
    assert "A:3" not in by_id
    assert not by_id["A:1"].entity_match.ambiguous
    assert by_id["A:2"].entity_match.ambiguous


def test_person_name_checked_against_administrators_and_shareholders(  # type: ignore[no-untyped-def]
    identity, make_signal, make_result
) -> None:
    admin = make_signal("A:1", method="person_name", data={"person": "Sorin Imaginescu"})
    stranger = make_signal("A:2", method="person_name", data={"person": "Maria Necunoscuta"})
    (res,) = resolve(identity, [make_result([admin, stranger])])
    assert [s.signal_id for s in res.signals] == ["A:1"]


def test_unknown_method_is_ambiguous_not_trusted(identity, make_signal, make_result) -> None:  # type: ignore[no-untyped-def]
    (res,) = resolve(identity, [make_result([make_signal(method="vibes")])])
    assert res.signals[0].entity_match.ambiguous


def test_already_ambiguous_is_not_lowered_twice(identity, make_signal, make_result) -> None:  # type: ignore[no-untyped-def]
    sig = make_signal(method="vibes")
    (once,) = resolve(identity, [make_result([sig])])
    (twice,) = resolve(identity, [make_result(once.signals)])
    assert twice.signals[0].confidence == once.signals[0].confidence


def test_same_signal_id_is_kept_once_across_results(identity, make_signal, make_result) -> None:  # type: ignore[no-untyped-def]
    a = make_signal("A:1")
    r1, r2 = make_result([a], agent="tax"), make_result([a], agent="network")
    out = resolve(identity, [r1, r2])
    assert len(out[0].signals) + len(out[1].signals) == 1
    assert "merged 1" in (out[1].notes or "")


def test_same_fact_two_sources_keeps_official_and_mentions_the_other(  # type: ignore[no-untyped-def]
    identity, make_signal, make_result
) -> None:
    official = make_signal("A:2", confidence=0.5)
    mock_src = official.source.model_copy(
        update={"name": "Arrears (MOCK)", "type": SourceType.MOCK}
    )
    mock = make_signal("A:1", src=mock_src, confidence=0.99)
    out = resolve(
        identity, [make_result([mock], agent="tax"), make_result([official], agent="net")]
    )
    kept = [s for r in out for s in r.signals]
    assert [s.signal_id for s in kept] == ["A:2"]
    assert kept[0].data["also_seen_in"] == ["Arrears (MOCK)"]


def test_different_facts_are_not_merged(identity, make_signal, make_result) -> None:  # type: ignore[no-untyped-def]
    a = make_signal("A:1", data={"x": 1})
    b = make_signal("A:2", data={"x": 2}, src=a.source.model_copy(update={"name": "Other"}))
    out = resolve(identity, [make_result([a, b])])
    assert len(out[0].signals) == 2
