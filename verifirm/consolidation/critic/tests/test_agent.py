from datetime import UTC, datetime

from verifirm.consolidation.critic.agent import verify_memo
from verifirm.core.impl_local.llm import FakeLLMClient
from verifirm.schema.memo import Memo, MemoSection, SectionKind

SIG = "TAX-ARREARS-01:aaaa"


def memo(*sentences: tuple[str, list[str]], kind: SectionKind = SectionKind.RED_SIGNALS, questions=()) -> Memo:  # type: ignore[no-untyped-def]
    return Memo(
        cui="99000033",
        run_id="run_1",
        sections=[
            MemoSection(
                kind=kind,
                title="S",
                sentences=[{"text": t, "signal_ids": ids} for t, ids in sentences],  # type: ignore[misc]
            )
        ],
        questions=list(questions),
        markdown="old",
        generated_at=datetime.now(UTC),
    )


def reasons(result: Memo) -> dict[str, str]:
    assert result.verifier_report is not None
    return {r.text: r.reason for r in result.verifier_report.rejected}


async def test_supported_sentence_passes_without_llm(make_signal, make_report) -> None:  # type: ignore[no-untyped-def]
    report = make_report([make_signal(SIG)])
    out = await verify_memo(memo(("The company owes 412.560 RON.", [SIG])), report, None, "m")
    assert out.verifier_report is not None
    assert out.verifier_report.passed and out.verifier_report.checked_sentences == 1
    assert "412.560" in out.markdown and out.markdown != "old"


async def test_invented_number_is_removed(make_signal, make_report) -> None:  # type: ignore[no-untyped-def]
    report = make_report([make_signal(SIG)])
    bad = "The company owes 25.400.000 RON."
    out = await verify_memo(memo((bad, [SIG]), ("It owes 412,560 RON.", [SIG])), report, None, "m")
    assert reasons(out) == {bad: "number 25.400.000 not in consolidated JSON"}
    assert out.verifier_report is not None and not out.verifier_report.passed
    assert bad not in out.markdown and "412,560" in out.markdown
    assert len(out.sections[0].sentences) == 1


async def test_number_must_come_from_the_cited_signal_not_another(make_signal, make_report) -> None:  # type: ignore[no-untyped-def]
    a = make_signal(SIG)
    b = make_signal("LIT-X-01:bbbb", claim="Claim of 1,800,000 RON.", data={"amount": 1800000})
    out = await verify_memo(memo(("Claim of 1,800,000 RON.", [SIG])), make_report([a, b]), None, "m")
    assert out.verifier_report is not None and not out.verifier_report.passed


async def test_unknown_signal_id_and_missing_citation(make_signal, make_report) -> None:  # type: ignore[no-untyped-def]
    report = make_report([make_signal(SIG)])
    out = await verify_memo(
        memo(("Something happened.", ["NOPE-01:zzz"]), ("Something else happened.", [])),
        report,
        None,
        "m",
    )
    r = reasons(out)
    assert "NOPE-01:zzz" in r["Something happened."]
    assert r["Something else happened."] == "no cited signal"
    assert out.sections == []  # nothing left, the empty section is gone


async def test_summary_may_quote_score_and_counts_without_citing(make_signal, make_report) -> None:  # type: ignore[no-untyped-def]
    report = make_report([make_signal(SIG)])
    ok = memo(("The score is 64.8 with 8/8 sources.", []), kind=SectionKind.SUMMARY)
    assert (await verify_memo(ok, report, None, "m")).verifier_report.passed  # type: ignore[union-attr]
    bad = memo(("The score is 71.2.", []), kind=SectionKind.SUMMARY)
    assert not (await verify_memo(bad, report, None, "m")).verifier_report.passed  # type: ignore[union-attr]


async def test_media_claim_must_say_unvalidated(make_signal, make_report) -> None:  # type: ignore[no-untyped-def]
    media = make_signal("MED-NEGATIVE-01:m", claim="Press says suppliers unpaid.", data={}, validated=False)
    report = make_report([media])
    plain = "Press says suppliers are unpaid."
    labelled = "An unvalidated article says suppliers are unpaid."
    out = await verify_memo(memo((plain, [media.signal_id]), (labelled, [media.signal_id])), report, None, "m")
    assert list(reasons(out)) == [plain]


async def test_decision_and_fraud_wording_is_removed_unless_in_a_signal(make_signal, make_report) -> None:  # type: ignore[no-untyped-def]
    court = make_signal("LIT-X-01:c", claim="The court rejected the appeal.", data={})
    report = make_report([court, make_signal(SIG)])
    ok = "The court rejected the appeal."
    rec = "We recommend to approve the credit."
    fraud = "This looks like fraud."
    out = await verify_memo(
        memo((ok, [court.signal_id]), (rec, [SIG]), (fraud, [SIG])), report, None, "m"
    )
    assert set(reasons(out)) == {rec, fraud}


async def test_questions_are_checked_too(make_signal, make_report) -> None:  # type: ignore[no-untyped-def]
    from verifirm.schema.memo import ClientQuestion

    report = make_report([make_signal(SIG)])
    good = ClientQuestion(question="Explain the 412,560 RON arrears.", reason_signal_ids=[SIG])
    bad = ClientQuestion(question="Explain the 999,999 RON arrears.", reason_signal_ids=[SIG])
    orphan = ClientQuestion(question="Anything else?", reason_signal_ids=[])
    out = await verify_memo(memo(questions=[good, bad, orphan]), report, None, "m")
    assert out.questions == [good]
    assert set(reasons(out)) == {bad.question, orphan.question}


async def test_llm_pass_rejects_unsupported_and_missing_verdicts(make_signal, make_report) -> None:  # type: ignore[no-untyped-def]
    report = make_report([make_signal(SIG)])
    llm = FakeLLMClient(
        json_responses={
            "CriticVerdicts": {
                "verdicts": [
                    {"index": 0, "supported": True},
                    {"index": 1, "supported": False, "reason": "inference"},
                ]
            }
        }
    )
    out = await verify_memo(
        memo(
            ("It owes 412,560 RON.", [SIG]),
            ("It owes 412,560 RON and is failing.", [SIG]),
            ("It owes 412,560 RON, a lot.", [SIG]),
        ),
        report,
        llm,
        "critic-model",
    )
    r = reasons(out)
    assert r["It owes 412,560 RON and is failing."] == "inference"
    assert "no verdict" in r["It owes 412,560 RON, a lot."]
    assert [s.text for s in out.sections[0].sentences] == ["It owes 412,560 RON."]


async def test_llm_pass_only_sees_what_pass_one_kept(make_signal, make_report) -> None:  # type: ignore[no-untyped-def]
    report = make_report([make_signal(SIG)])
    llm = FakeLLMClient(json_responses={"CriticVerdicts": {"verdicts": [{"index": 1, "supported": True}]}})
    out = await verify_memo(memo(("Owes 7777 RON.", [SIG]), ("Owes 412,560 RON.", [SIG])), report, llm, "m")
    assert "Owes 412,560 RON." in out.markdown
    assert "<untrusted_data" in llm.calls[0]["messages"][0].content


async def test_llm_failure_is_never_a_silent_pass(make_signal, make_report) -> None:  # type: ignore[no-untyped-def]
    report = make_report([make_signal(SIG)])
    out = await verify_memo(memo(("It owes 412,560 RON.", [SIG])), report, FakeLLMClient(), "m")
    assert out.verifier_report is not None and not out.verifier_report.passed
    assert "unavailable" in out.verifier_report.rejected[0].reason
    assert "412,560" in out.markdown  # deterministic checks passed, so the text stays

