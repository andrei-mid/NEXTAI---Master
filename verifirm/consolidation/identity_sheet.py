"""Owner: @role-5-ai-api. Build the IdentitySheet from OFFICIAL sources only (never the web).

Sources, all read from the local mirror / tables (local-first: never a network call here):
- anaf_v9.lookup(cui, today): name, address, reg. no., CAEN, legal form, VAT, inactive status.
- onrc_bulk.company(cui): name history, office history, status, authorized CAEN, legal
  representatives -> Person(role=ADMINISTRATOR). Optional: live ONRC needs the bulk ingest.
- mock_shareholders.shareholders(cui): shareholders (MOCK). Optional.
Current values prefer ANAF (it is dated today). ONRC fills what ANAF doesn't publish, plus the
history. Every SourceRef used ends up in `sources`.
If BOTH anaf_v9 and onrc_bulk are unavailable -> SourceUnavailable: no run without identity.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from verifirm.adapters.base import BaseAdapter, Sourced, SourceUnavailable
from verifirm.core.cui import is_fictional
from verifirm.core.logging import get_logger
from verifirm.core.ports.clock import Clock
from verifirm.schema.identity import (
    Address,
    CompanyName,
    CompanyStatus,
    IdentitySheet,
    Person,
    PersonRole,
)
from verifirm.schema.signals import SourceRef

log = get_logger(__name__)

# ANAF writes the legal form out in full. The sheet uses the short form.
_LEGAL_FORMS = [
    ("RASPUNDERE LIMITATA", "SRL"),
    ("IN COMANDITA PE ACTIUNI", "SCA"),
    ("PE ACTIUNI", "SA"),
    ("IN NUME COLECTIV", "SNC"),
    ("IN COMANDITA SIMPLA", "SCS"),
    ("PERSOANA FIZICA AUTORIZATA", "PFA"),
    ("INTREPRINDERE INDIVIDUALA", "II"),
    ("INTREPRINDERE FAMILIALA", "IF"),
]
_ONRC_STATUS = {
    "functiune": CompanyStatus.ACTIVE,
    "suspendata": CompanyStatus.SUSPENDED,
    "dizolvare": CompanyStatus.IN_DISSOLUTION,
    "insolventa": CompanyStatus.INSOLVENCY,
    "faliment": CompanyStatus.BANKRUPTCY,
    "radiata": CompanyStatus.DEREGISTERED,
}


def _fold(text: str) -> str:
    table = str.maketrans("ĂÂÎȘŞȚŢăâîșşțţ", "AAISSTTaaisstt")
    return text.translate(table).upper()


def short_legal_form(anaf_form: str | None) -> str | None:
    """'SOCIETATE COMERCIALĂ CU RĂSPUNDERE LIMITATĂ' -> 'SRL'. Unknown forms pass through."""
    if not anaf_form:
        return None
    folded = _fold(anaf_form)
    for needle, short in _LEGAL_FORMS:
        if needle in folded:
            return short
    return anaf_form.strip() or None


def _date(value: Any) -> date | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()[:10]
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


async def _read(
    adapters: Mapping[str, BaseAdapter], name: str, call: str, *args: Any
) -> Sourced[Any] | None:
    adapter = adapters.get(name)
    if adapter is None:
        return None
    try:
        sourced: Sourced[Any] = await getattr(adapter, call)(*args)
        return sourced
    except (SourceUnavailable, NotImplementedError) as exc:
        log.info("identity source unavailable", extra={"adapter": name, "reason": str(exc)})
        return None


def _status(v9: dict[str, Any] | None, onrc: dict[str, Any] | None) -> CompanyStatus:
    if v9 is not None:
        inactive = v9.get("stare_inactiv") or {}
        general = v9.get("date_generale") or {}
        registration = _fold(str(general.get("stare_inregistrare", "")))
        if inactive.get("dataRadiere") or "RADIERE" in registration:
            return CompanyStatus.DEREGISTERED
        if inactive.get("statusInactivi"):
            return CompanyStatus.INACTIVE_ANAF
    if onrc is not None:
        status = _ONRC_STATUS.get(str(onrc.get("stare", "")).strip().lower())
        if status is not None:
            return status
    return CompanyStatus.ACTIVE if v9 is not None else CompanyStatus.UNKNOWN


def _persons(
    onrc_s: Sourced[Any] | None, sh_s: Sourced[Any] | None
) -> tuple[list[Person], list[Person]]:
    administrators: list[Person] = []
    if onrc_s is not None and onrc_s.data is not None:
        for rep in onrc_s.data.get("reprezentanti") or []:
            if not rep.get("nume"):
                continue
            role = (
                PersonRole.ADMINISTRATOR
                if "ADMINISTRATOR" in _fold(str(rep.get("calitate") or "ADMINISTRATOR"))
                else PersonRole.LEGAL_REPRESENTATIVE
            )
            administrators.append(
                Person(
                    name=rep["nume"],
                    role=role,
                    valid_from=_date(rep.get("de_la")),
                    valid_to=_date(rep.get("pana_la")),
                    source=onrc_s.source,
                )
            )
    shareholders: list[Person] = []
    if sh_s is not None:
        for sh in sh_s.data or []:
            shareholders.append(
                Person(
                    name=sh["name"],
                    role=PersonRole.SHAREHOLDER,
                    is_company=bool(sh.get("is_company")),
                    cui=sh.get("cui"),
                    share_pct=sh.get("share_pct"),
                    valid_from=_date(sh.get("since")),
                    source=sh_s.source,
                )
            )
    return administrators, shareholders


async def build_identity_sheet(
    cui: str, adapters: Mapping[str, BaseAdapter], clock: Clock
) -> IdentitySheet:
    v9_s = await _read(adapters, "anaf_v9", "lookup", cui, clock.today())
    onrc_s = await _read(adapters, "onrc_bulk", "company", cui)
    v9: dict[str, Any] | None = v9_s.data if v9_s is not None else None
    onrc: dict[str, Any] | None = onrc_s.data if onrc_s is not None else None
    if v9 is None and onrc is None:
        raise SourceUnavailable(
            "identity", f"neither ANAF v9 nor ONRC has data for {cui} (synced? found at ANAF?)"
        )

    general = (v9 or {}).get("date_generale") or {}
    office_v9 = (v9 or {}).get("adresa_sediu_social") or {}
    onrc_data = onrc or {}

    names = [
        CompanyName(
            name=n["denumire"], valid_from=_date(n.get("de_la")), valid_to=_date(n.get("pana_la"))
        )
        for n in onrc_data.get("istoric_denumiri") or []
        if n.get("denumire")
    ]
    current_name = str(general.get("denumire") or onrc_data.get("denumire") or "").strip()
    if current_name and not any(n.name == current_name and n.valid_to is None for n in names):
        names.append(CompanyName(name=current_name))

    county = office_v9.get("sdenumire_Judet") or onrc_data.get("judet") or None
    office_history = [
        Address(
            raw=a["adresa"],
            county=county,
            valid_from=_date(a.get("de_la")),
            valid_to=_date(a.get("pana_la")),
        )
        for a in onrc_data.get("istoric_sedii") or []
        if a.get("adresa")
    ]
    raw_address = str(general.get("adresa") or onrc_data.get("adresa") or "").strip()
    registered_office = None
    if raw_address:
        registered_office = Address(
            raw=raw_address,
            county=county,
            locality=office_v9.get("sdenumire_Localitate") or None,
            street=office_v9.get("sdenumire_Strada") or None,
            number=office_v9.get("snumar_Strada") or None,
            postal_code=office_v9.get("scod_Postal") or general.get("codPostal") or None,
        )

    sh_s = await _read(adapters, "mock_shareholders", "shareholders", cui)
    administrators, shareholders = _persons(onrc_s, sh_s)
    sources: list[SourceRef] = [
        s.source for s in (v9_s, onrc_s, sh_s) if s is not None and s.data is not None
    ]

    onrc_caen = onrc_data.get("caen_principal") or {}
    inactive = (v9 or {}).get("stare_inactiv") or {}
    vat = (v9 or {}).get("inregistrare_scop_Tva") or {}
    return IdentitySheet(
        cui=cui,
        fictional=is_fictional(cui),
        trade_register_no=general.get("nrRegCom") or onrc_data.get("cod_inmatriculare") or None,
        current_name=current_name or cui,
        names=names,
        legal_form=onrc_data.get("forma_juridica")
        or short_legal_form(general.get("forma_juridica")),
        status=_status(v9, onrc),
        registration_date=_date(general.get("data_inregistrare"))
        or _date(onrc_data.get("data_inmatriculare")),
        registered_office=registered_office,
        office_history=office_history,
        caen_code=str(general.get("cod_CAEN") or onrc_caen.get("cod") or "") or None,
        caen_revision=onrc_caen.get("revizie"),
        authorized_caen_codes=[
            c["cod"] for c in onrc_data.get("caen_autorizate") or [] if c.get("cod")
        ],
        administrators=administrators,
        shareholders=shareholders,
        vat_registered=vat.get("scpTVA") if v9 is not None else None,
        anaf_inactive=bool(inactive.get("statusInactivi")) if v9 is not None else None,
        sources=sources,
    )
