from verifirm.schema.signals import AgentStatus, Component
from verifirm.scoring.coverage import compute_coverage
from verifirm.scoring.engine import ScoringConfig


def test_full_coverage(config: ScoringConfig, make_results) -> None:
    cov = compute_coverage(make_results(), config)
    assert cov.weight_pct == 100 and cov.label == "8/8 sources" and cov.missing == []


def test_one_source_down(config: ScoringConfig, make_results) -> None:
    cov = compute_coverage(
        make_results(statuses={Component.PRESENCE: AgentStatus.UNAVAILABLE}), config
    )
    assert (
        cov.weight_pct == 95 and cov.label == "7/8 sources" and cov.missing == [Component.PRESENCE]
    )


def test_partial_counts_as_available_timeout_does_not(config: ScoringConfig, make_results) -> None:
    cov = compute_coverage(
        make_results(
            statuses={Component.TAX: AgentStatus.PARTIAL, Component.MEDIA: AgentStatus.TIMEOUT}
        ),
        config,
    )
    assert cov.available == 7 and cov.missing == [Component.MEDIA]


def test_missing_result_is_missing_not_clean(config: ScoringConfig, make_results) -> None:
    cov = compute_coverage(make_results(omit={Component.FINANCIALS}), config)
    assert cov.weight_pct == 80 and Component.FINANCIALS in cov.missing
