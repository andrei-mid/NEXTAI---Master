"""Tax agent: does the company owe the state, and do its declarations add up?

Five independent checks, each from its own source (one failing never hides the others):
1. Submitted vs official (TAX-DECLARED-GAP-01): ctx.submitted (the applicant's documents,
   None for portfolio re-checks) vs anaf_bilant, one signal per year. Source = the OFFICIAL
   statement. data["submitted"] / data["official"] hold both values (DEMO step 5).
2. Arrears (TAX-ARREARS-01): mock_restante, ANAF's quarterly debtors list.
3. VAT history (TAX-VAT-CANCELLED-01): anaf_v9 perioade_TVA.
4. D300 vs e-Factura (TAX-EFACTURA-GAP-01): mock_d300 + mock_efactura.
5. e-Factura enrollment (TAX-EFACTURA-REG-01): anaf_efactura_registry (derived from v9).

MOCK sources give signals with source.type == MOCK (the UI shows a badge). Local-first: every
read hits the mirror / fixtures, never the network. A source that fails, is missing, or
returns data the rules can't check goes into `sources_failed` with a note, never clean.
Demo: Zephyria -> DECLARED-GAP (high). Brunaldo -> ARREARS, VAT-CANCELLED, EFACTURA-GAP, DECLARED-GAP.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any, cast

from verifirm.adapters.anaf_bilant import AnafBilantAdapter
from verifirm.adapters.anaf_efactura_registry import AnafEfacturaRegistryAdapter
from verifirm.adapters.anaf_v9 import AnafV9Adapter
from verifirm.adapters.base import Sourced, SourceUnavailable
from verifirm.adapters.mocks.d300 import MockD300Adapter
from verifirm.adapters.mocks.efactura import MockEfacturaAdapter
from verifirm.adapters.mocks.restante import MockRestanteAdapter
from verifirm.agents.base import AgentContext, BaseAgent
from verifirm.agents.tax import rules
from verifirm.agents.tax.rules import RULES, TaxConfig, load_config
from verifirm.core.logging import get_logger
from verifirm.core.registry import register_agent
from verifirm.schema.financials import FinancialYear
from verifirm.schema.signals import AgentResult, Component, EntityMatch, Signal, SourceRef

log = get_logger(__name__)

EXACT = EntityMatch(method="cui_exact", score=1.0)

# How each compared field reads in a claim; money fields get "RON", profit gets a sign.
_LABELS = {
    "turnover": "turnover",
    "net_profit": "net result",
    "employees": "employees",
    "total_debts": "debts",
    "equity": "equity",
}
_MONEY = {"turnover", "net_profit", "total_debts", "equity"}


def _fmt(field: str, value: int) -> str:
    return f"{value:+,}" if field == "net_profit" else f"{value:,}"


def _declared_gap_claim(facts: dict[str, Any]) -> str:
    year, sub, off = facts["year"], facts["submitted"], facts["official"]
    if len(sub) == 1:
        (field,) = sub
        unit = " RON" if field in _MONEY else ""
        return (
            f"Submitted {year} {_LABELS[field]} is {_fmt(field, sub[field])}{unit} "
            f"while ANAF shows {_fmt(field, off[field])}{unit}."
        )
    parts = [
        f"{_LABELS[f]} {_fmt(f, sub[f])} vs {_fmt(f, off[f])}{' RON' if f in _MONEY else ''}"
        for f in sub
    ]
    return f"Submitted {year} figures differ from ANAF: {', '.join(parts)}."


def _statement(cui: str, year: int) -> Callable[[Any], Awaitable[Sourced[FinancialYear | None]]]:
    """The read() call for one year's ANAF statement."""

    def call(adapter: Any) -> Awaitable[Sourced[FinancialYear | None]]:
        return cast(AnafBilantAdapter, adapter).get_year(cui, year)

    return call


def _quarter_label(list_period: str) -> str:
    """'2026-Q2' -> 'Q2 2026' (anything else unchanged)."""
    year, _, quarter = list_period.partition("-")
    return f"{quarter} {year}" if quarter.startswith("Q") else list_period


def _period_label(period: dict[str, Any]) -> str:
    start, end = str(period.get("from", "")), str(period.get("to", ""))
    whole_year = start[:4] == end[:4] and start[5:] == "01-01" and end[5:] == "12-31"
    return start[:4] if whole_year else f"{start} to {end}"


@register_agent("tax")
class TaxAgent(BaseAgent):
    component = Component.TAX
    sources = (
        "documents",
        "anaf_bilant",
        "anaf_v9",
        "mock_restante",
        "mock_d300",
        "mock_efactura",
        "anaf_efactura_registry",
    )
    rules = RULES

    def __init__(self, config: TaxConfig | None = None) -> None:
        self.config = config or load_config()

    async def run(self, ctx: AgentContext) -> AgentResult:
        cfg = self.config
        started = time.monotonic()
        today = ctx.clock.today()
        checked: list[str] = []
        failed: list[str] = []
        notes: list[str] = []
        signals: list[Signal] = []

        def fail(source: str, reason: str) -> None:
            if source not in failed:
                failed.append(source)
            if source in checked:
                checked.remove(source)
            notes.append(f"{source}: {reason}")
            log.warning("tax source not checked", extra={"source": source, "reason": reason})

        def ok(source: str) -> None:
            if source not in failed and source not in checked:
                checked.append(source)

        async def read[T](
            source: str, call: Callable[[Any], Awaitable[Sourced[T]]]
        ) -> Sourced[T] | None:
            """Adapter lookup + call. Every failure lands in sources_failed, never raises."""
            try:
                result = await call(ctx.adapter(source))
            except SourceUnavailable as exc:
                fail(source, exc.reason)
                return None
            except NotImplementedError:
                fail(source, "adapter not implemented yet")
                return None
            ok(source)
            if result.stale:
                notes.append(f"{source}: stale mirror copy (older than mirror_max_age_s)")
            return result

        def confidence(*sourced: Sourced[Any], base: float = 1.0) -> float:
            stale = any(s.stale for s in sourced)
            return min(base, cfg.stale_confidence) if stale else base

        def emit(
            rule_id: str,
            claim: str,
            source: SourceRef,
            evidence_date: date | None,
            conf: float,
            data: dict[str, Any],
            **kwargs: Any,
        ) -> None:
            facts = {"fictional": True, **data} if ctx.identity.fictional else data
            signals.append(
                self.signal(
                    ctx,
                    rule_id=rule_id,
                    claim=claim,
                    source=source,
                    evidence_date=evidence_date,
                    confidence=conf,
                    entity_match=EXACT,
                    data=facts,
                    **kwargs,
                )
            )

        # --- 1. Submitted documents vs ANAF statements (applications only).
        submitted = ctx.submitted
        if submitted is None:
            notes.append("documents: none submitted (portfolio re-check), DECLARED-GAP skipped")
        elif submitted.cui != ctx.cui:
            fail("documents", f"documents belong to CUI {submitted.cui}, not {ctx.cui}")
        else:
            ok("documents")
            for sub_year in sorted(submitted.years, key=lambda y: y.year):
                y = sub_year.year
                official = await read("anaf_bilant", _statement(ctx.cui, y))
                if official is None:
                    continue
                if official.data is None:
                    notes.append(f"anaf_bilant: no {y} statement filed at ANAF, not compared")
                    continue
                try:
                    gap = rules.check_declared_gap(
                        sub_year, official.data, cfg.declared_gap_tolerance_pct
                    )
                except ValueError as exc:
                    notes.append(f"documents: {exc}")
                    continue
                if gap:
                    emit(
                        "TAX-DECLARED-GAP-01",
                        _declared_gap_claim(gap),
                        official.source,
                        date(y, 12, 31),
                        confidence(official),
                        gap,
                        discriminator=str(y),
                    )

        # --- 2. ANAF arrears list (MOCK).
        arrears = await read(
            "mock_restante", lambda a: cast(MockRestanteAdapter, a).arrears(ctx.cui)
        )
        if arrears is not None:
            try:
                debt = rules.check_arrears(arrears.data)
            except ValueError as exc:
                fail("mock_restante", str(exc))
            else:
                period = str(arrears.data["list_period"])
                if debt:
                    emit(
                        "TAX-ARREARS-01",
                        f"The company is on the {_quarter_label(period)} ANAF arrears list with "
                        f"{debt['principal_ron']:,} RON principal and "
                        f"{debt['accessories_ron']:,} RON accessories.",
                        arrears.source,
                        rules.quarter_end(period),
                        confidence(arrears),
                        debt,
                    )
                else:
                    notes.append(
                        f"mock_restante: not on the {_quarter_label(period)} arrears list "
                        "(ANAF lists only debts above its thresholds; a certificat de atestare "
                        "fiscală is the definitive proof)"
                    )

        # --- 3. VAT registration history (ANAF v9).
        v9 = await read("anaf_v9", lambda a: cast(AnafV9Adapter, a).lookup(ctx.cui, today))
        if v9 is not None:
            vat = (v9.data or {}).get("inregistrare_scop_Tva")
            if v9.data is None:
                fail("anaf_v9", "CUI not found at ANAF (notFound)")
            elif not isinstance(vat, dict):
                fail("anaf_v9", "record has no inregistrare_scop_Tva")
            else:
                try:
                    # Passed as-is: a missing list must fail the rule's check, never read as [].
                    periods = cast(list[dict[str, Any]], vat.get("perioade_TVA"))
                    cancelled = rules.check_vat_cancelled(
                        periods, today, cfg.vat_cancelled_window_days
                    )
                except ValueError as exc:
                    fail("anaf_v9", str(exc))
                else:
                    if cancelled:
                        on, back = cancelled["cancelled_on"], cancelled["reregistered_on"]
                        tail = (
                            f"and re-registered on {back.isoformat()}"
                            if back
                            else "and has not been re-registered"
                        )
                        emit(
                            "TAX-VAT-CANCELLED-01",
                            f"VAT registration was cancelled on {on.isoformat()} {tail}.",
                            v9.source,
                            on,
                            confidence(v9),
                            {
                                "cancelled_on": on.isoformat(),
                                "reregistered_on": back.isoformat() if back else None,
                            },
                        )
                    elif vat.get("scpTVA") is False:
                        notes.append(
                            "anaf_v9: not VAT-registered, no cancellation date published "
                            "(identity covers inactive / deregistered companies)"
                        )

        # --- 4. D300 declared sales vs e-Factura issued invoices (both MOCK).
        d300 = await read("mock_d300", lambda a: cast(MockD300Adapter, a).returns(ctx.cui))
        invoices = await read(
            "mock_efactura", lambda a: cast(MockEfacturaAdapter, a).invoice_flows(ctx.cui)
        )
        if d300 is not None and invoices is not None:
            try:
                ef_gap = rules.check_efactura_gap(
                    d300.data, invoices.data, cfg.efactura_gap_tolerance_pct
                )
            except (ValueError, KeyError, TypeError) as exc:
                fail("mock_d300", f"D300 vs e-Factura can't be compared ({exc})")
            else:
                if ef_gap:
                    period = invoices.data["period"]
                    direction = "below" if ef_gap["gap_pct"] > 0 else "above"
                    emit(
                        "TAX-EFACTURA-GAP-01",
                        f"{_period_label(period)} D300 declared sales ({ef_gap['d300_ron']:,} RON) "
                        f"are {abs(ef_gap['gap_pct']):g}% {direction} e-Factura issued invoices "
                        f"({ef_gap['efactura_ron']:,} RON).",
                        d300.source,
                        date.fromisoformat(str(period["to"])),
                        confidence(d300, invoices, base=cfg.efactura_gap_confidence),
                        ef_gap,
                        severity=rules.efactura_gap_severity(ef_gap),
                    )

        # --- 5. RO e-Factura enrollment (derived from v9, no extra call).
        enrolled = await read(
            "anaf_efactura_registry",
            lambda a: cast(AnafEfacturaRegistryAdapter, a).is_registered(ctx.cui),
        )
        if enrolled is not None:
            if enrolled.data is None:
                fail("anaf_efactura_registry", "enrollment status not published")
            elif rules.check_efactura_registration(enrolled.data):
                emit(
                    "TAX-EFACTURA-REG-01",
                    "ANAF does not list the company as enrolled in RO e-Factura.",
                    enrolled.source,
                    None,
                    confidence(enrolled),
                    {"registered": False},
                )

        return self.result(
            started=started,
            sources_checked=checked,
            sources_failed=failed,
            signals=signals,
            notes="; ".join(notes) or None,
        )
