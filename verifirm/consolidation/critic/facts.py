"""Numbers and dates in text, normalised so "1.900.000", "1,9 mil." and "1900000" compare equal.

The critic's deterministic pass uses this: every number/date a memo sentence states must also
appear in the evidence it cites. A token can be read more than one way ("1.900" is a thousand
separator in Romanian and a decimal point in English), so a token yields a SET of candidate
values and it matches when any candidate is in the evidence's set of candidates.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?!\d)")
_DMY = re.compile(r"(?<![\d./])(\d{1,2})[./](\d{1,2})[./](\d{4})(?![\d])")
# A number is digits with . or , groups. Digits glued to letters (Q2, J99, FY2025) are labels.
_NUM = re.compile(
    r"(?<![\w.,])(\d+(?:[.,]\d+)*)"
    r"(?:\s*(mil(?:ioane|ion)?|mln|mld|miliarde?|milliard|million|billion|mii|k)\b\.?)?",
    re.IGNORECASE,
)
_MULTIPLIER = {
    "mil": 10**6,
    "milion": 10**6,
    "milioane": 10**6,
    "million": 10**6,
    "mln": 10**6,
    "mld": 10**9,
    "miliard": 10**9,
    "miliarde": 10**9,
    "milliard": 10**9,
    "billion": 10**9,
    "mii": 10**3,
    "k": 10**3,
}


def _valid_date(y: str, m: str, d: str) -> str | None:
    month, day = int(m), int(d)
    if 1 <= month <= 12 and 1 <= day <= 31:
        return f"{int(y):04d}-{month:02d}-{day:02d}"
    return None


def extract_dates(text: str) -> tuple[set[str], str]:
    """ISO dates found in `text` (ISO, dd.mm.yyyy and dd/mm/yyyy), and the text without them."""
    found: set[str] = set()

    def take_iso(m: re.Match[str]) -> str:
        iso = _valid_date(m.group(1), m.group(2), m.group(3))
        if iso is None:
            return m.group(0)
        found.add(iso)
        return " "

    def take_dmy(m: re.Match[str]) -> str:
        iso = _valid_date(m.group(3), m.group(2), m.group(1))
        if iso is None:
            return m.group(0)
        found.add(iso)
        return " "

    rest = _DMY.sub(take_dmy, _ISO.sub(take_iso, text))
    return found, rest


def _candidates(token: str) -> set[Decimal]:
    """Every sensible value of a number token like '1.900.000', '412,560', '64.8', '1,9'."""
    if token.isdigit():
        return {Decimal(token)}
    out: set[Decimal] = set()
    if "." in token and "," in token:
        last = max(token.rfind("."), token.rfind(","))  # the last separator is the decimal one
        out.add(Decimal(f"{re.sub(r'[.,]', '', token[:last])}.{token[last + 1 :]}"))
    else:
        sep = "." if "." in token else ","
        parts = token.split(sep)
        if all(len(p) == 3 for p in parts[1:]):  # thousands grouping
            out.add(Decimal("".join(parts)))
        if len(parts) == 2:  # decimal point
            out.add(Decimal(f"{parts[0]}.{parts[1]}"))
    if not out:  # something odd like 1.2.3: fall back to its parts
        out.update(Decimal(p) for p in re.split(r"[.,]", token) if p)
    return out


def number_tokens(text: str) -> list[tuple[str, set[Decimal]]]:
    """(token as written, candidate values) for every number in `text` (dates excluded first)."""
    _, rest = extract_dates(text)
    tokens: list[tuple[str, set[Decimal]]] = []
    for m in _NUM.finditer(rest):
        try:
            values = _candidates(m.group(1))
        except InvalidOperation:  # pragma: no cover (the regex only lets digits through)
            continue
        written = m.group(0).strip()
        if m.group(2):
            factor = _MULTIPLIER[m.group(2).lower()]
            values = values | {v * factor for v in values}
        tokens.append((written, values))
    return tokens


class Evidence:
    """All numbers and dates present in some JSON-like evidence."""

    def __init__(self) -> None:
        self.numbers: set[Decimal] = set()
        self.dates: set[str] = set()
        self.text: list[str] = []  # lowercase strings, for word checks

    def add(self, value: Any) -> Evidence:
        if isinstance(value, bool) or value is None:
            return self
        if isinstance(value, int | float):
            d = Decimal(str(value))
            self.numbers.add(abs(d))
            if isinstance(value, float) and abs(value) <= 1:
                self.numbers.add(abs(d) * 100)  # 0.18 is also "18%"
        elif isinstance(value, str):
            self.text.append(value.lower())
            dates, _ = extract_dates(value)
            self.dates |= dates
            self.numbers |= {Decimal(int(d[:4])) for d in dates}  # a year is a number too
            for _, values in number_tokens(value):
                self.numbers |= values
        elif isinstance(value, date):  # datetime is a date too
            self.add(value.isoformat())
        elif isinstance(value, dict):
            for k, v in value.items():
                self.add(k)
                self.add(v)
        elif isinstance(value, Iterable):
            for v in value:
                self.add(v)
        return self

    def mentions(self, word: str) -> bool:
        return any(word in t for t in self.text)


def unsupported(text: str, evidence: Evidence) -> list[str]:
    """Numbers and dates in `text` that the evidence does not contain (empty = all supported)."""
    dates, _ = extract_dates(text)
    missing = sorted(d for d in dates if d not in evidence.dates)
    for written, values in number_tokens(text):
        if not values & evidence.numbers:
            missing.append(written)
    return missing
