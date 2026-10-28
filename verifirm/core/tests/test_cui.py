import pytest

from verifirm.core.cui import (
    FICTIONAL_CUIS,
    InvalidCUIError,
    has_valid_checksum,
    normalize_cui,
    validate_cui,
)


def test_real_cui_passes() -> None:
    assert has_valid_checksum("2816464")  # DEDEMAN SRL
    assert validate_cui("RO 2816464", fixture_mode=False) == "2816464"


def test_wrong_check_digit_fails() -> None:
    with pytest.raises(InvalidCUIError):
        validate_cui("2816465", fixture_mode=False)


@pytest.mark.parametrize("raw", ["", "abc", "1", "12345678901", "RO"])
def test_bad_format_fails(raw: str) -> None:
    with pytest.raises(InvalidCUIError):
        validate_cui(raw, fixture_mode=True)


@pytest.mark.parametrize("cui", sorted(FICTIONAL_CUIS))
def test_fictional_cuis_never_pass_real_checksum(cui: str) -> None:
    assert not has_valid_checksum(cui)


@pytest.mark.parametrize("cui", sorted(FICTIONAL_CUIS))
def test_fictional_cuis_only_in_fixture_mode(cui: str) -> None:
    assert validate_cui(cui, fixture_mode=True) == cui
    with pytest.raises(InvalidCUIError):
        validate_cui(cui, fixture_mode=False)


def test_normalize() -> None:
    assert normalize_cui(" ro2816464 ") == "2816464"
    assert normalize_cui(2816464) == "2816464"
