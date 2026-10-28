"""CUI gate: the first step of every pipeline. Invalid CUI -> the run is rejected.

Checksum (ANAF): take the CUI without its last (control) digit, left-pad it to 9 digits,
multiply digit-by-digit with the key 753217532, sum, multiply by 10, take mod 11.
A remainder of 10 becomes 0. The result must equal the control digit.

Fictional demo CUIs (99000xxx) have a deliberately INVALID check digit so they can never
collide with a real company. They are accepted only when FIXTURE_MODE=1.
"""

from __future__ import annotations

import re

CHECKSUM_KEY = "753217532"

# Every fictional CUI used in fixtures/. `make fixtures-check` asserts none of these
# passes the real checksum, and that fixtures/companies/ uses no other 99000xxx CUI.
FICTIONAL_CUIS: frozenset[str] = frozenset(
    {
        "99000017",  # AURORA SOFT LABS SRL
        "99000025",  # ZEPHYRIA LOGISTIC NOVA SRL
        "99000033",  # BRUNALDO TRADE IMPEX SRL
        "99000041",  # Kestrel Fictiv Transport SRL
        "99000058",  # Orvanto Distributie SRL
        "99000066",  # Pelinor Construct Grup SRL
        "99000074",  # Vantiro Agro Fictiv SRL
        "99000082",  # Mirelda Servicii Imaginare SRL
        "99000090",  # Calbrona Holding Fictiv SRL
    }
)

_CUI_RE = re.compile(r"^\d{2,10}$")


class InvalidCUIError(ValueError):
    """Raised when a CUI fails the format or checksum gate."""


def normalize_cui(raw: str | int) -> str:
    """Strip whitespace and an optional 'RO' VAT prefix. Does not validate."""
    text = str(raw).strip().upper().replace(" ", "")
    if text.startswith("RO"):
        text = text[2:]
    return text


def checksum_digit(body: str) -> int:
    """Control digit for a CUI body (the CUI without its last digit)."""
    padded = body.zfill(9)
    total = sum(int(d) * int(k) for d, k in zip(padded, CHECKSUM_KEY, strict=True))
    rest = total * 10 % 11
    return 0 if rest == 10 else rest


def has_valid_checksum(cui: str) -> bool:
    """True if `cui` (normalized, digits only) passes the real ANAF checksum."""
    if not _CUI_RE.match(cui):
        return False
    return checksum_digit(cui[:-1]) == int(cui[-1])


def is_fictional(cui: str) -> bool:
    return normalize_cui(cui) in FICTIONAL_CUIS


def validate_cui(raw: str | int, *, fixture_mode: bool) -> str:
    """Return the normalized CUI or raise InvalidCUIError.

    Fictional CUIs pass only when `fixture_mode` is True.
    """
    cui = normalize_cui(raw)
    if not _CUI_RE.match(cui):
        raise InvalidCUIError(f"CUI must be 2-10 digits, got {raw!r}")
    if cui in FICTIONAL_CUIS:
        if fixture_mode:
            return cui
        raise InvalidCUIError(f"CUI {cui} is fictional and only accepted with FIXTURE_MODE=1")
    if not has_valid_checksum(cui):
        raise InvalidCUIError(f"CUI {cui} fails the checksum")
    return cui
