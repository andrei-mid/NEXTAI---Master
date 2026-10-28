"""Identity agent: is the company who it says it is, and is its identity stable?

Inputs (as the pipeline contract says):
- ctx.identity (built from official sources by consolidation/identity_sheet): administrators,
  office history, main + authorized CAEN, legal form.
- anaf_v9.lookup(cui, today): the raw ANAF record (inactive, reactivation, deregistration dates).
- onrc_bulk.company(cui): the raw ONRC record (legal status, identity keys);
  onrc_bulk.companies_at_address(address): the shared-office count.

Source authority (see README): legal status and administrators -> ONRC, fiscal inactivity ->
ANAF, deregistration -> both. Local-first (docs/LOCAL_DATA.md): every call reads the local
mirror / tables, never the network. One anaf_v9 read per run.

A source that fails, is not implemented yet, or returns data the rules can't check goes into
`sources_failed` with a note. It is never reported clean.
Demo: Zephyria -> ID-ADMIN-CHANGE-01 + ID-SHARED-OFFICE-01 (63 companies).
"""

from __future__ import annotations

import asyncio
import csv
import time
from collections.abc import Awaitable, Callable
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from verifirm.adapters.anaf_v9 import AnafV9Adapter
from verifirm.adapters.base import Sourced, SourceUnavailable
from verifirm.adapters.onrc_bulk import OnrcBulkAdapter
from verifirm.agents.base import AgentContext, BaseAgent
from verifirm.agents.identity import rules
from verifirm.agents.identity.rules import RULES, IdentityConfig, load_config
from verifirm.core.logging import get_logger
from verifirm.core.registry import register_agent
from verifirm.schema.signals import AgentResult, Component, EntityMatch, Signal, SourceRef

log = get_logger(__name__)

EXACT = EntityMatch(method="cui_exact", score=1.0)


@lru_cache(maxsize=4)
def _load_caen_mapping(path: Path) -> dict[str, list[str]]:
    """fixtures/sources/caen_rev2_rev3.csv -> {rev2: [rev3, ...]}. Missing file -> {}."""
    if not path.exists():
        return {}
    mapping: dict[str, list[str]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            mapping.setdefault(row["cod_rev2"], []).append(row["cod_rev3"])
    return mapping


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _names(names: list[str]) -> str:
    return ", ".join(names) if names else "nobody"


def _title(names: list[str]) -> str:
    return _names([n.title() for n in names])


@register_agent("identity")
class IdentityAgent(BaseAgent):
    component = Component.IDENTITY
    sources = ("anaf_v9", "onrc_bulk")
    rules = RULES

    def __init__(self, config: IdentityConfig | None = None) -> None:
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
            log.warning("identity source not checked", extra={"source": source, "reason": reason})

        async def read[T](
            source: str, call: Callable[[], Awaitable[Sourced[T]]]
        ) -> Sourced[T] | None:
            try:
                result = await call()
            except SourceUnavailable as exc:
                fail(source, exc.reason)
                return None
            except NotImplementedError:
                fail(source, "adapter not implemented yet")
                return None
            if source not in failed and source not in checked:
                checked.append(source)
            if result.stale:
                notes.append(f"{source}: stale mirror copy (older than mirror_max_age_s)")
            return result

        def confidence(*sourced: Sourced[Any] | None, agree: bool = True) -> float:
            value = 1.0 if agree else cfg.conflict_confidence
            if any(s is not None and s.stale for s in sourced):
                value = min(value, cfg.stale_confidence)
            return value

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

        # --- 1. ANAF v9: one mirror read for today's date (synced upstream, 100 CUIs per call).
        v9 = None
        v9_adapter = await self._adapter(ctx, "anaf_v9", fail)
        if v9_adapter is not None:
            anaf = cast(AnafV9Adapter, v9_adapter)
            v9 = await read("anaf_v9", lambda: anaf.lookup(ctx.cui, today))
            if v9 is not None and v9.data is None:
                fail("anaf_v9", "CUI not found at ANAF (notFound)")
                v9 = None

        anaf_dereg: str | None = None
        if v9 is not None and v9.data is not None:
            record = v9.data
            try:
                inactive = rules.check_inactive(record)
                reactivated = rules.check_reactivated(record, today, cfg.window_days)
                anaf_dereg = record["stare_inactiv"].get("dataRadiere") or None
                if not isinstance(record.get("date_generale"), dict):
                    raise ValueError("no date_generale")
            except (ValueError, KeyError) as exc:
                fail("anaf_v9", f"record can't be checked ({exc})")
                v9, anaf_dereg = None, None  # never reuse a malformed record further down
            else:
                if inactive:
                    since = inactive["inactive_since"]
                    emit(
                        "ID-INACTIVE-01",
                        "ANAF lists the company as fiscally inactive since "
                        f"{_iso(since) or 'an unpublished date'}.",
                        v9.source,
                        since,
                        confidence(v9),
                        {
                            "inactive_since": _iso(since),
                            "published_on": _iso(inactive["published_on"]),
                        },
                    )
                if reactivated:
                    on = reactivated["reactivated_on"]
                    emit(
                        "ID-REACTIVATED-01",
                        f"ANAF reactivated the company on {_iso(on)}.",
                        v9.source,
                        on,
                        confidence(v9),
                        {
                            "reactivated_on": _iso(on),
                            "inactive_since": _iso(reactivated["inactive_since"]),
                            "window_days": cfg.window_days,
                        },
                    )

        # --- 2. ONRC: raw record for status + identity keys; the sheet for history and CAEN.
        onrc = None
        registry: OnrcBulkAdapter | None = None
        onrc_adapter = await self._adapter(ctx, "onrc_bulk", fail)
        if onrc_adapter is not None:
            registry = cast(OnrcBulkAdapter, onrc_adapter)
            onrc = await read("onrc_bulk", lambda: registry.company(ctx.cui))
            if onrc is not None and onrc.data is None:
                fail("onrc_bulk", "CUI not found in the ONRC tables")
                onrc = None

        if registry is not None and onrc is not None and onrc.data is not None:
            await self._check_onrc(
                ctx, today, onrc, v9, anaf_dereg, emit, confidence, fail, notes.append
            )

            address = ctx.identity.registered_office.raw if ctx.identity.registered_office else None
            if address:
                at_address = await read("onrc_bulk", lambda: registry.companies_at_address(address))
                if at_address is not None:
                    shared = rules.check_shared_office(
                        len(at_address.data), cfg.shared_office_min_companies
                    )
                    if shared:
                        emit(
                            "ID-SHARED-OFFICE-01",
                            f"The registered office is shared by {shared['n_companies']} companies.",
                            at_address.source,
                            None,
                            confidence(at_address),
                            {"address": address, **shared},
                        )
            else:
                fail("onrc_bulk", "no registered office in the identity sheet")

        # --- 3. Cross-source: do ANAF and ONRC describe the same company?
        if v9 is not None and v9.data is not None and onrc is not None and onrc.data is not None:
            mismatch = rules.check_source_mismatch(
                v9.data,
                {
                    "cui": onrc.data.get("cui"),
                    "trade_register_no": onrc.data.get("cod_inmatriculare"),
                    "name": onrc.data.get("denumire"),
                },
            )
            if mismatch:
                fields = ", ".join(sorted(mismatch["mismatches"]))
                emit(
                    "ID-SOURCE-MISMATCH-01",
                    f"ANAF and ONRC disagree on the company's {fields}.",
                    v9.source,
                    None,
                    confidence(v9, onrc),
                    {**mismatch, "onrc_source": onrc.source.model_dump(mode="json")},
                )

        # --- 4. Natural person (PFA/II/IF): ONRC form from the sheet, ANAF wording as backup.
        anaf_form = v9.data["date_generale"].get("forma_juridica") if v9 and v9.data else None
        for form, sourced in ((ctx.identity.legal_form, onrc), (anaf_form, v9)):
            person = rules.check_natural_person(form)
            if person and sourced is not None:
                emit(
                    "ID-NATURAL-PERSON-01",
                    f"The legal form is {person['legal_form']}, a natural person.",
                    sourced.source,
                    None,
                    confidence(sourced),
                    person,
                )
                break

        return self.result(
            started=started,
            sources_checked=checked,
            sources_failed=failed,
            signals=signals,
            notes="; ".join(notes) or None,
        )

    async def _check_onrc(
        self,
        ctx: AgentContext,
        today: date,
        onrc: Sourced[dict[str, Any] | None],
        v9: Sourced[dict[str, Any] | None] | None,
        anaf_dereg: str | None,
        emit: Callable[..., None],
        confidence: Callable[..., float],
        fail: Callable[[str, str], None],
        note: Callable[[str], None],
    ) -> None:
        """ONRC-authority rules: status, administrators, office, CAEN."""
        assert onrc.data is not None
        sheet = ctx.identity

        # Status: ONRC is the authority; deregistration is cross-checked with ANAF.
        try:
            status = rules.check_status(str(onrc.data.get("stare") or ""), anaf_dereg)
        except ValueError as exc:
            fail("onrc_bulk", f"status can't be checked ({exc})")
        else:
            if status:
                if v9 is None:  # unknown, not a disagreement: ONRC is the status authority
                    status["sources_agree"] = None
                    status["note"] = "ANAF deregistration not cross-checked (anaf_v9 failed)"
                agree = status["sources_agree"] is not False
                claim = f'ONRC lists the company\'s status as "{status["onrc_status"]}".'
                if status["anaf_deregistered_on"]:
                    claim = (
                        f"ANAF lists the company as deregistered on "
                        f"{_iso(status['anaf_deregistered_on'])}; ONRC lists its status as "
                        f'"{status["onrc_status"]}".'
                    )
                source = v9.source if status["anaf_deregistered_on"] and v9 else onrc.source
                emit(
                    "ID-STATUS-01",
                    claim,
                    source,
                    status["anaf_deregistered_on"],
                    confidence(onrc, v9, agree=agree),
                    {
                        **status,
                        "anaf_deregistered_on": _iso(status["anaf_deregistered_on"]),
                        "onrc_source": onrc.source.model_dump(mode="json"),
                    },
                    severity=rules.status_severity(status),
                )

        # Administrators (current + historical) from the sheet; each Person carries its source.
        admins = [
            {"name": p.name, "valid_from": p.valid_from, "valid_to": p.valid_to}
            for p in sheet.administrators
        ]
        try:
            change = rules.check_admin_change(admins, today, self.config.window_days)
        except ValueError as exc:
            fail("onrc_bulk", f"administrators can't be checked ({exc})")
        else:
            if change:
                admin_source = next(
                    (p.source for p in sheet.administrators if p.valid_to == change["changed_on"]),
                    onrc.source,
                )
                on = _iso(change["changed_on"])
                emit(
                    "ID-ADMIN-CHANGE-01",
                    f"The administrator changed on {on} from {_title(change['previous'])} "
                    f"to {_title(change['current'])}.",
                    admin_source,
                    change["changed_on"],
                    confidence(onrc),
                    {
                        "previous": _names(change["previous"]),
                        "current": _names(change["current"]),
                        "changed_on": on,
                    },
                )

        # Registered office history. Live ONRC / ANAF only publish the current office, so an
        # empty history with a known office means "no change detectable", not a failed source.
        offices = [
            {"address": a.raw, "valid_from": a.valid_from, "valid_to": a.valid_to}
            for a in sheet.office_history
        ]
        if not offices and sheet.registered_office is not None:
            office = sheet.registered_office
            offices = [{"address": office.raw, "valid_from": office.valid_from, "valid_to": None}]
            note("onrc_bulk: no office history, ID-OFFICE-CHANGE-01 can't see past moves")
        try:
            moved = rules.check_office_change(offices, today, self.config.window_days)
        except ValueError as exc:
            fail("onrc_bulk", f"office history can't be checked ({exc})")
        else:
            if moved:
                on = _iso(moved["changed_on"])
                emit(
                    "ID-OFFICE-CHANGE-01",
                    f"The registered office moved on {on} from {moved['previous']} "
                    f"to {moved['current']}.",
                    onrc.source,
                    moved["changed_on"],
                    confidence(onrc),
                    {**moved, "changed_on": on},
                )

        # Main CAEN vs authorized CAEN, Rev.2 <-> Rev.3 mapped.
        mapping_path = ctx.settings.fixtures_dir / "sources" / "caen_rev2_rev3.csv"
        mapping = await asyncio.to_thread(_load_caen_mapping, mapping_path)
        try:
            caen = rules.check_caen_authorized(
                sheet.caen_code or "", sheet.authorized_caen_codes, mapping
            )
        except ValueError as exc:
            fail("onrc_bulk", f"CAEN can't be checked ({exc})")
        else:
            if caen:
                emit(
                    "ID-CAEN-UNAUTH-01",
                    f"The main CAEN code {caen['main_caen']} is not among the authorized codes "
                    f"({', '.join(caen['authorized'])}).",
                    onrc.source,
                    None,
                    confidence(onrc),
                    {**caen, "rev2_rev3_mapping_rows": sum(len(v) for v in mapping.values())},
                )

    @staticmethod
    async def _adapter(
        ctx: AgentContext, name: str, fail: Callable[[str, str], None]
    ) -> Any | None:
        try:
            return ctx.adapter(name)
        except SourceUnavailable as exc:
            fail(name, exc.reason)
            return None
