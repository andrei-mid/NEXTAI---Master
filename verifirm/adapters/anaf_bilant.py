"""Owner: @role-3-official-agents. ANAF annual financial statements (OFFICIAL, free).

Facts:
- GET https://webservicesp.anaf.ro/bilant?an={year}&cui={cui}
- One CUI-year per call. Max 1 request/second (shares the webservicesp.anaf.ro limit).
- Response: {"an", "cui", "deni", "caen", "den_caen", "i": [{"indicator": "I1",
  "val_indicator": 123, "val_den_indicator": "Active imobilizate - total"}, ...]}
- Map indicators BY LABEL (`val_den_indicator`), NOT by code: the I-codes differ between
  company types (large/small/micro, banks, NGOs) and between years.
- Labels to map into FinancialYear (match case/diacritics-insensitively, keep the label table
  in this module): "Cifra de afaceri neta" -> turnover, "Profit net"/"Pierdere neta" ->
  net_profit (loss is negative), "Datorii" -> total_debts, "Capitaluri - total" -> equity,
  "Capital subscris varsat" -> share_capital, "Numar mediu de salariati" -> employees.
  Put everything else in FinancialYear.extra by label.
- An empty `i` list means "no statement filed for that year". That is NOT zero turnover.
- Fixture: fixtures/companies/<cui>_<slug>/bilant_<year>.json, the exact response shape.

Local-first (docs/LOCAL_DATA.md): `sync(cui)` downloads 6 years into the mirror (filed years
only once, ever). `get_year` / `get_history` read the mirror only when the instance has no
network (agents), and never call ANAF.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

import httpx

from verifirm.adapters.base import (
    BaseAdapter,
    FetchResult,
    Sourced,
    SourceUnavailable,
    SyncReport,
)
from verifirm.core.ports.rate_limiter import RateLimit
from verifirm.core.registry import register_adapter
from verifirm.schema.financials import FinancialYear
from verifirm.schema.signals import SourceRef, SourceType

URL = "https://webservicesp.anaf.ro/bilant"


def normalize_label(label: str) -> str:
    """'Capitaluri - total, din care:' -> 'capitaluri total din care' (no diacritics/punctuation)."""
    text = unicodedata.normalize("NFKD", label)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _first(labels: dict[str, int], *prefixes: str) -> int | None:
    for prefix in prefixes:
        for label, value in labels.items():
            if label.startswith(prefix):
                return value
    return None


def _debts(labels: dict[str, int]) -> int | None:
    """Small/micro formats publish one 'Datorii' line. Large-company formats split it into
    'datorii ... pana la un an' + '... mai mare de un an', so those are summed."""
    for label, value in labels.items():
        if label == "datorii" or label.startswith(("datorii total", "datorii din care")):
            return value
    parts = [v for label, v in labels.items() if label.startswith("datorii") and "un an" in label]
    return sum(parts) if parts else None


def parse_bilant(payload: dict[str, Any], source: SourceRef) -> FinancialYear | None:
    """Map one /bilant response to FinancialYear BY LABEL. Empty `i` = nothing filed -> None."""
    rows = payload.get("i") or []
    if not rows:
        return None
    labels: dict[str, int] = {}
    for row in rows:
        value = row.get("val_indicator")
        if value is None:
            continue
        labels.setdefault(
            normalize_label(str(row.get("val_den_indicator", ""))), round(float(value))
        )

    profit = _first(labels, "profit net")
    loss = _first(labels, "pierdere neta")
    net_profit = None if profit is None and loss is None else (profit or 0) - (loss or 0)
    return FinancialYear(
        year=int(payload["an"]),
        turnover=_first(labels, "cifra de afaceri neta"),
        net_profit=net_profit,
        total_debts=_debts(labels),
        equity=_first(labels, "capitaluri total", "capitaluri proprii total"),
        share_capital=_first(labels, "capital subscris varsat"),
        employees=_first(labels, "numar mediu de salariati"),
        extra=labels,
        source=source,
    )


def _is_filed(result: FetchResult) -> bool:
    try:
        return bool(result.json().get("i"))
    except (ValueError, AttributeError):
        return False


@dataclass
class BilantHistory:
    """Years oldest first. `years` maps each fetched year to its data (None = nothing filed).
    `failed` lists the years the source could not be read for (unknown, never 'clean')."""

    years: dict[int, Sourced[FinancialYear | None]] = field(default_factory=dict)
    failed: list[int] = field(default_factory=list)

    @property
    def filed(self) -> list[FinancialYear]:
        return [s.data for _, s in sorted(self.years.items()) if s.data is not None]


@register_adapter("anaf_bilant")
class AnafBilantAdapter(BaseAdapter):
    source_label = "ANAF financial statements (bilanț)"
    source_type = SourceType.OFFICIAL
    rate_limit = RateLimit.per_second(1)
    rate_limit_key = "anaf_webservicesp"
    # Only "nothing filed yet" answers expire. A filed statement never changes, so it's
    # downloaded once and then always served from the mirror as fresh.
    mirror_max_age_s = 7 * 86_400
    sync_years = 6  # covers the agents' 5-year window on both sides of the mid-year filing date

    async def sync(self, cui: str) -> SyncReport:
        """Download the last `sync_years` years into the mirror. Years already filed in the
        mirror are reused (no call). Unfiled years are re-asked only after mirror_max_age_s."""
        report = SyncReport(adapter=self.name, cui=cui)
        last = self.deps.clock.today().year - 1
        for year in range(last - self.sync_years + 1, last + 1):
            try:
                result = await self._load(cui, year)
            except SourceUnavailable:
                report.failed.append(f"{cui}:{year}")
                continue
            if result.from_mirror and not result.stale:
                report.reused += 1
            else:
                report.downloaded += 1
        return report

    async def get_year(self, cui: str, year: int) -> Sourced[FinancialYear | None]:
        """One year. None if nothing was filed. Agents: mirror only. Fixture: bilant_<year>.json."""
        result = await self._load(cui, year)
        try:
            payload = result.json()
        except ValueError as exc:
            raise SourceUnavailable(self.name, f"invalid JSON for {cui}/{year}") from exc
        return Sourced(
            data=parse_bilant(payload, result.source), source=result.source, stale=result.stale
        )

    async def _load(self, cui: str, year: int) -> FetchResult:
        key = f"{cui}:{year}"
        if not self.settings.fixture_mode:
            mirrored = await self.from_mirror(key)
            if mirrored is not None and _is_filed(mirrored):
                return mirrored  # immutable: never stale, never re-downloaded

        async def request(client: httpx.AsyncClient) -> httpx.Response:
            return await client.get(URL, params={"an": year, "cui": cui})

        return await self.fetch(
            cache_key=key,
            request=request,
            url=f"{URL}?an={year}&cui={cui}",
            fixture=self.company_fixture(cui, f"bilant_{year}.json"),
        )

    async def get_history(self, cui: str, last_year: int, years: int = 5) -> BilantHistory:
        """`years` consecutive years ending at `last_year` (one call each, rate limited)."""
        history = BilantHistory()
        for year in range(last_year - years + 1, last_year + 1):
            try:
                history.years[year] = await self.get_year(cui, year)
            except SourceUnavailable:
                history.failed.append(year)
        return history
