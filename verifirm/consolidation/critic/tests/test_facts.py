from decimal import Decimal

import pytest

from verifirm.consolidation.critic.facts import Evidence, extract_dates, number_tokens, unsupported


def values(text: str) -> set[Decimal]:
    return {v for _, vs in number_tokens(text) for v in vs}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.900.000 RON", Decimal(1_900_000)),
        ("412,560 RON", Decimal(412_560)),
        ("64.8", Decimal("64.8")),
        ("1.234,56", Decimal("1234.56")),
        ("1,234.56", Decimal("1234.56")),
        ("1,9 mil.", Decimal(1_900_000)),
        ("2 milioane", Decimal(2_000_000)),
        ("18%", Decimal(18)),
    ],
)
def test_number_formats(text: str, expected: Decimal) -> None:
    assert expected in values(text)


def test_labels_glued_to_letters_are_not_numbers() -> None:
    assert values("Q2 2026 list, J99 register") == {Decimal(2026)}


def test_dates_in_all_formats_and_removed_from_numbers() -> None:
    dates, rest = extract_dates("On 2025-11-02 and 12.04.2026 and 3/5/2024, not 2025-13-45.")
    assert dates == {"2025-11-02", "2026-04-12", "2024-05-03"}
    assert "2025" in rest  # the invalid date is left alone
    assert Decimal(11) not in values("on 2025-11-02")


def test_case_numbers_are_split_into_their_parts() -> None:
    ev = Evidence().add("case 9101/99/2026")
    assert unsupported("case 9101/99/2026", ev) == []


def test_unsupported_finds_invented_numbers_and_dates() -> None:
    ev = Evidence().add({"principal": 412560, "hearing": "2026-11-20", "ratio": 0.18})
    assert unsupported("412.560 RON", ev) == []
    assert unsupported("hearing on 20.11.2026", ev) == []
    assert unsupported("18% below", ev) == []
    assert unsupported("25.400.000 RON", ev) == ["25.400.000"]
    assert unsupported("hearing on 2026-12-01", ev) == ["2026-12-01"]


def test_no_rounding_allowed() -> None:
    ev = Evidence().add({"score": 64.83})
    assert unsupported("scores 64.8", ev) == ["64.8"]


def test_year_of_an_evidence_date_counts_as_a_number() -> None:
    assert unsupported("in 2025", Evidence().add("VAT cancelled on 2025-02-01")) == []
