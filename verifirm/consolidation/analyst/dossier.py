"""Company dossier for the AI analyst: everything we know about one CUI, compared and computed
by code before any LLM sees it (docs/DECISIONS.md, "AI analyst opinion").

Two steps, so the building is pure and testable:
1. `collect_inputs` reads the local mirror / tables (local-first: never the network):
   anaf_v9.lookup + anaf_v9.history (today + the last quarter-ends), onrc_bulk.company,
   anaf_bilant.get_history. A source that fails is recorded as unavailable, never as empty.
2. `build_dossier` turns those inputs + the run's ConsolidatedReport into a CompanyDossier:
   - cross_checks: each identity fact as ANAF and ONRC publish it, plus `match`;
   - anaf_snapshots + anaf_changes: what changed between the quarterly ANAF snapshots;
   - financials + indicators: /bilant years and ratios computed here (the LLM never computes);
   - administrators under aliases, and every known person name replaced in the signals.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from itertools import pairwise
from typing import Any

from verifirm.adapters.anaf_bilant import BilantHistory
from verifirm.adapters.base import BaseAdapter, Sourced, SourceUnavailable
from verifirm.adapters.onrc_bulk import fold, normalize_address
from verifirm.core.logging import get_logger
from verifirm.schema.analyst import (
    AnafSnapshot,
    CompanyDossier,
    CrossCheck,
    DossierPerson,
    DossierSignal,
    DossierYear,
    OfficialScore,
    SnapshotChange,
    SourceState,
    YearIndicators,
)
from verifirm.schema.identity import Person
from verifirm.schema.memo import ConsolidatedReport

log = get_logger(__name__)

SNAPSHOT_FIELDS = ("name", "address", "caen_code", "registration_status", "vat_payer", "inactive")
# Address words that carry no identity (both sources spell them differently or not at all).
_ADDRESS_NOISE = {"str", "nr", "bd", "sos", "sector", "jud", "mun", "loc", "com", "sat", "oras"}
_ADDRESS_NOISE |= {"bl", "sc", "et", "ap", "al", "pta", "cod", "postal", "romania"}
_LEGAL_SUFFIX = re.compile(r"\b(s ?r ?l|s ?a|s ?n ?c|s ?c ?s|s ?c ?a|pfa|ii|if)\b")


# ---------------------------------------------------------------------- inputs (I/O)
@dataclass
class DossierInputs:
    v9: Sourced[dict[str, Any] | None] | None = None
    v9_history: dict[str, dict[str, Any] | None] = field(default_factory=dict)
    onrc: Sourced[dict[str, Any] | None] | None = None
    bilant: BilantHistory | None = None
    failures: dict[str, str] = field(default_factory=dict)  # adapter -> reason


async def collect_inputs(
    cui: str,
    adapters: Mapping[str, BaseAdapter],
    today: date,
    *,
    last_year: int,
    years: int,
    disabled: frozenset[str] = frozenset(),
) -> DossierInputs:
    """Read every source the dossier needs from the local mirror / tables. Never raises for a
    failing source: it lands in `failures` (unavailable, never clean). `disabled` are the sources
    switched off for this run (RunRequest.disabled_sources)."""
    inputs = DossierInputs()

    async def read(name: str, method: str, *args: Any) -> Any:
        if name in disabled:
            inputs.failures[name] = "source switched off for this run"
            return None
        adapter = adapters.get(name)
        if adapter is None:
            inputs.failures[name] = "adapter not configured"
            return None
        try:
            return await getattr(adapter, method)(*args)
        except (SourceUnavailable, NotImplementedError) as exc:
            reason = exc.reason if isinstance(exc, SourceUnavailable) else "not implemented yet"
            inputs.failures.setdefault(name, reason)
            return None

    inputs.v9 = await read("anaf_v9", "lookup", cui, today)
    history = await read("anaf_v9", "history", cui)
    if history is not None:
        inputs.v9_history = dict(history.data)
    inputs.onrc = await read("onrc_bulk", "company", cui)
    inputs.bilant = await read("anaf_bilant", "get_history", cui, last_year, years)
    return inputs


# ---------------------------------------------------------------------- pure helpers
def _text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def compact_name(name: str | None) -> str:
    """'Dedeman S.R.L.' == 'DEDEMAN SRL': folded, legal form dropped, no spaces."""
    folded = fold(name or "")
    return _LEGAL_SUFFIX.sub(" ", folded).replace(" ", "")


def address_tokens(raw: str | None) -> set[str]:
    words = normalize_address(raw or "").split()
    return {w for w in words if w not in _ADDRESS_NOISE}


def addresses_match(anaf: str | None, onrc: str | None) -> bool | None:
    """Same place if the meaningful words of one address are all in the other (the two
    registers order and abbreviate addresses differently)."""
    a, o = address_tokens(anaf), address_tokens(onrc)
    if not a or not o:
        return None
    return a <= o or o <= a


def _county(raw: str | None) -> str:
    words = [w for w in fold(raw or "").split() if w not in {"jud", "judetul", "mun", "municipiul"}]
    return " ".join(words)


def _compare(anaf: str | None, onrc: str | None, key: Any = lambda v: v) -> bool | None:
    if anaf is None or onrc is None:
        return None
    return bool(key(anaf) == key(onrc))


def _reg_no(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()


def onrc_deregistered(status: str | None) -> bool | None:
    return None if status is None else "radiat" in fold(status)


def anaf_deregistered(record: dict[str, Any] | None) -> bool | None:
    if record is None:
        return None
    inactive = record.get("stare_inactiv") or {}
    general = record.get("date_generale") or {}
    return bool(inactive.get("dataRadiere")) or "radiere" in fold(
        str(general.get("stare_inregistrare") or "")
    )


def cross_checks(v9: dict[str, Any] | None, onrc: dict[str, Any] | None) -> dict[str, CrossCheck]:
    general = (v9 or {}).get("date_generale") or {}
    office = (v9 or {}).get("adresa_sediu_social") or {}
    o = onrc or {}
    caen_onrc = (o.get("caen_principal") or {}).get("cod")

    def check(
        anaf: Any, onrc_value: Any, key: Any = lambda v: v, note: str | None = None
    ) -> CrossCheck:
        a, b = _text(anaf), _text(onrc_value)
        return CrossCheck(anaf=a, onrc=b, match=_compare(a, b, key), note=note)

    a_dereg, o_dereg = (
        anaf_deregistered(v9 if v9 else None),
        onrc_deregistered(_text(o.get("stare"))),
    )
    return {
        "name": check(general.get("denumire"), o.get("denumire"), compact_name),
        "address": CrossCheck(
            anaf=_text(general.get("adresa")),
            onrc=_text(o.get("adresa")),
            match=addresses_match(_text(general.get("adresa")), _text(o.get("adresa"))),
            note="compared on the meaningful words: the registers order addresses differently",
        ),
        "county": check(office.get("sdenumire_Judet"), o.get("judet"), _county),
        "caen_code": check(
            general.get("cod_CAEN"),
            caen_onrc,
            note="ONRC may list the CAEN Rev.3 code while ANAF still shows Rev.2",
        ),
        "trade_register_no": check(general.get("nrRegCom"), o.get("cod_inmatriculare"), _reg_no),
        "deregistered": CrossCheck(
            anaf=None if a_dereg is None else str(a_dereg).lower(),
            onrc=None if o_dereg is None else str(o_dereg).lower(),
            match=None if a_dereg is None or o_dereg is None else a_dereg == o_dereg,
        ),
        "status": CrossCheck(
            anaf=_text(general.get("stare_inregistrare")),
            onrc=_text(o.get("stare")),
            match=None,
            note="not comparable: ANAF registers taxpayers, ONRC the legal status "
            "(ANAF 'INREGISTRAT' next to ONRC 'faliment' is normal)",
        ),
    }


def snapshot(record: dict[str, Any] | None) -> AnafSnapshot:
    if record is None:
        return AnafSnapshot(
            name=None,
            address=None,
            caen_code=None,
            registration_status=None,
            vat_payer=None,
            inactive=None,
            found=False,
        )
    general = record.get("date_generale") or {}
    vat = record.get("inregistrare_scop_Tva") or {}
    inactive = record.get("stare_inactiv") or {}
    return AnafSnapshot(
        name=_text(general.get("denumire")),
        address=_text(general.get("adresa")),
        caen_code=_text(general.get("cod_CAEN")),
        registration_status=_text(general.get("stare_inregistrare")),
        vat_payer=vat.get("scpTVA") if "scpTVA" in vat else None,
        inactive=inactive.get("statusInactivi") if "statusInactivi" in inactive else None,
    )


def snapshot_changes(snapshots: dict[str, AnafSnapshot]) -> list[SnapshotChange]:
    """Field changes between consecutive snapshots (oldest first)."""
    ordered = sorted(snapshots.items())
    changes: list[SnapshotChange] = []
    for (d0, s0), (d1, s1) in pairwise(ordered):
        for name in (*SNAPSHOT_FIELDS, "found"):
            old, new = getattr(s0, name), getattr(s1, name)
            if old != new:
                changes.append(
                    SnapshotChange(
                        field=name,
                        date_from=date.fromisoformat(d0),
                        date_to=date.fromisoformat(d1),
                        old=None if old is None else str(old),
                        new=None if new is None else str(new),
                    )
                )
    return changes


def financial_years(bilant: BilantHistory | None) -> dict[str, DossierYear]:
    if bilant is None:
        return {}
    years: dict[int, DossierYear] = {y: DossierYear(filed=None) for y in bilant.failed}
    for year, sourced in bilant.years.items():
        fy = sourced.data
        years[year] = (
            DossierYear(filed=False)
            if fy is None
            else DossierYear(
                filed=True,
                turnover=fy.turnover,
                net_profit=fy.net_profit,
                total_debts=fy.total_debts,
                equity=fy.equity,
                share_capital=fy.share_capital,
                employees=fy.employees,
            )
        )
    return {str(y): years[y] for y in sorted(years)}


def _ratio(num: int | None, den: int | None, digits: int) -> float | None:
    if num is None or not den:
        return None
    return round(num / den, digits)


def indicators(financials: dict[str, DossierYear]) -> dict[str, YearIndicators]:
    out: dict[str, YearIndicators] = {}
    previous: DossierYear | None = None
    for year, fy in financials.items():
        if not fy.filed:
            continue
        growth = None
        if previous is not None and previous.turnover and fy.turnover is not None:
            growth = round((fy.turnover - previous.turnover) / abs(previous.turnover) * 100, 1)
        margin = _ratio(fy.net_profit, fy.turnover, 3)
        per_employee = _ratio(fy.turnover, fy.employees, 0)
        out[year] = YearIndicators(
            turnover_growth_pct=growth,
            net_margin_pct=None if margin is None else round(margin * 100, 1),
            equity_to_share_capital=_ratio(fy.equity, fy.share_capital, 2),
            turnover_per_employee=None if per_employee is None else int(per_employee),
            debts_to_turnover=_ratio(fy.total_debts, fy.turnover, 2),
        )
        previous = fy
    return out


def aliases(administrators: list[Person], shareholders: list[Person]) -> dict[str, str]:
    """Real person name -> alias. Companies keep their names (they are not personal data)."""
    out: dict[str, str] = {}
    people = sorted(administrators, key=lambda p: (p.valid_from or date.min, p.name))
    for i, person in enumerate(dict.fromkeys(p.name for p in people)):
        out[person] = f"Administrator {_letter(i)}"
    natural = [p.name for p in shareholders if not p.is_company and p.name not in out]
    for i, name in enumerate(dict.fromkeys(natural)):
        out[name] = f"Shareholder {_letter(i)}"
    return out


def _letter(i: int) -> str:
    letters = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        letters = chr(65 + r) + letters
    return letters


def redact(value: Any, names: dict[str, str]) -> Any:
    """Replace every known person name (any case) inside strings, recursively."""
    if not names:
        return value
    if isinstance(value, str):
        for name, alias in sorted(names.items(), key=lambda kv: -len(kv[0])):
            value = re.sub(re.escape(name), alias, value, flags=re.IGNORECASE)
        return value
    if isinstance(value, dict):
        return {k: redact(v, names) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, names) for v in value]
    return value


def _state(sourced: Sourced[Any] | None, failure: str | None, missing: str) -> SourceState:
    if sourced is None:
        return SourceState(status="unavailable", note=failure or "no data")
    note = missing if sourced.data is None else ("stale mirror copy" if sourced.stale else None)
    return SourceState(status="ok", retrieved_at=sourced.source.retrieved_at, note=note)


def _bilant_state(bilant: BilantHistory | None, failure: str | None) -> SourceState:
    if bilant is None or not bilant.years:
        failed = f"years not readable: {bilant.failed}" if bilant else None
        return SourceState(status="unavailable", note=failure or failed)
    at = next(iter(bilant.years.values())).source.retrieved_at
    if bilant.failed:
        return SourceState(
            status="partial", retrieved_at=at, note=f"years not readable: {bilant.failed}"
        )
    return SourceState(status="ok", retrieved_at=at)


def source_states(inputs: DossierInputs) -> dict[str, SourceState]:
    f = inputs.failures
    return {
        "anaf_v9": _state(inputs.v9, f.get("anaf_v9"), "CUI not found at ANAF"),
        "onrc_bulk": _state(inputs.onrc, f.get("onrc_bulk"), "CUI not found in ONRC"),
        "anaf_bilant": _bilant_state(inputs.bilant, f.get("anaf_bilant")),
    }


def build_dossier(report: ConsolidatedReport, inputs: DossierInputs) -> CompanyDossier:
    identity = report.identity
    names = aliases(identity.administrators, identity.shareholders)
    v9 = inputs.v9.data if inputs.v9 is not None else None
    onrc = inputs.onrc.data if inputs.onrc is not None else None

    history = dict(inputs.v9_history)
    if v9 is not None and inputs.v9 is not None:
        today = (v9.get("date_generale") or {}).get(
            "data"
        ) or report.generated_at.date().isoformat()
        history.setdefault(str(today), v9)
    snapshots = {d: snapshot(r) for d, r in sorted(history.items())}
    financials = financial_years(inputs.bilant)

    checks = cross_checks(v9, onrc)
    signals = {
        s.signal_id: DossierSignal(
            rule_id=s.rule_id,
            agent=s.agent,
            severity=s.severity,
            claim=redact(s.claim, names),
            evidence_date=s.evidence_date,
            validated=s.validated,
            source_type=s.source.type.value,
            data=redact(s.data, names),
        )
        for s in report.signals
    }
    return CompanyDossier(
        cui=report.cui,
        fictional=identity.fictional,
        run_id=report.run_id,
        generated_at=report.generated_at,
        name=identity.current_name,
        legal_form=identity.legal_form,
        cross_checks=checks,
        anaf_snapshots=snapshots,
        anaf_changes=snapshot_changes(snapshots),
        financials=financials,
        indicators=indicators(financials),
        administrators=[
            DossierPerson(
                alias=names[p.name],
                role=p.role.value,
                valid_from=p.valid_from,
                valid_to=p.valid_to,
            )
            for p in sorted(
                identity.administrators, key=lambda p: (p.valid_from or date.min, p.name)
            )
        ],
        sources=source_states(inputs),
        agents={r.agent: r.status.value for r in report.results},
        signals=signals,
        official_score=OfficialScore(
            trust_score=report.score.trust_score,
            band=report.score.band,
            coverage=report.score.coverage.label,
        ),
    )
