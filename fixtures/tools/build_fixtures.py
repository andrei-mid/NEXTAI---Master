"""Regenerate every file under fixtures/ from the demo facts below (`make fixtures`).

Owner: @role-6-frontend-demo. This script is the ONE place the demo numbers live (docs/DEMO.md).
- Raw files (anaf_v9.json, bilant_<year>.json, portal_just.xml, ...) mimic the real source
  responses. Fictional records carry "fictional": true (XML: a `fictional: true` comment).
- api/*.json files are what the API serves in FIXTURE_MODE. They're built from the schema models,
  so they're schema-valid by construction. Their scores use the PROPOSED formula in
  verifirm/scoring/config/weights.yaml. They are illustrations of the expected output, not the engine.
- DEDEMAN SRL (real) gets NO figures: live data at demo time only.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from verifirm.agents.base import make_signal_id
from verifirm.core.cui import checksum_digit
from verifirm.schema.api import (
    CompanyDetail,
    CompanyListItem,
    Graph,
    GraphEdge,
    GraphNode,
    MemoResponse,
    NodeType,
    TopSignal,
)
from verifirm.schema.financials import FinancialYear, SubmittedFinancials
from verifirm.schema.identity import (
    Address,
    CompanyName,
    CompanyStatus,
    IdentitySheet,
    Person,
    PersonRole,
)
from verifirm.schema.memo import ClientQuestion, RejectedSentence, VerifierReport
from verifirm.schema.runs import AgentProgressEvent
from verifirm.schema.scoring import Band, ComponentScore, Coverage
from verifirm.schema.signals import (
    SEVERITY_ORDER,
    AgentStatus,
    Component,
    EntityMatch,
    Severity,
    Signal,
    SourceRef,
    SourceType,
)

FIX = Path(__file__).resolve().parents[1]
COMPANIES = FIX / "companies"
SOURCES = FIX / "sources"
CHECKED_AT = datetime(2026, 10, 28, 8, 0, tzinfo=UTC)
TODAY = CHECKED_AT.date()
V9_URL = "https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva"
JUST_URL = "http://portalquery.just.ro/query.asmx"
WEIGHTS = {
    Component.IDENTITY: 15,
    Component.FINANCIALS: 20,
    Component.TAX: 15,
    Component.LITIGATION: 15,
    Component.NETWORK: 15,
    Component.SANCTIONS: 10,
    Component.MEDIA: 5,
    Component.PRESENCE: 5,
}
PENALTY = {
    Severity.INFO: 0,
    Severity.LOW: 5,
    Severity.MEDIUM: 15,
    Severity.HIGH: 35,
    Severity.CRITICAL: 60,
}
AGENT_ORDER = [
    "identity",
    "sanctions",
    "financials",
    "tax",
    "network",
    "presence",
    "litigation",
    "media",
]

# --------------------------------------------------------------------------- demo facts
SHARED_OFFICE = "Str. Exemplului nr. 1, Sector 9, București"

COMPANIES_FACTS: dict[str, dict[str, Any]] = {
    "99000017": dict(
        slug="aurora_soft_labs",
        name="AURORA SOFT LABS SRL",
        reg="J99/2101/2019",
        founded="2019-05-20",
        caen="6201",
        caen_name="Activități de realizare a soft-ului la comandă",
        address="Str. Algoritmului nr. 7, Localitatea Fictivă, Județul Fictiv",
        county="Județul Fictiv",
        admins=[("ANA EXEMPLESCU", "2019-05-20", None)],
        status="functiune",
        shareholders=[("ANA EXEMPLESCU", False, None, 100.0, "2019-05-20")],
    ),
    "99000025": dict(
        slug="zephyria_logistic_nova",
        name="ZEPHYRIA LOGISTIC NOVA SRL",
        reg="J99/1234/2021",
        founded="2021-03-15",
        caen="4941",
        caen_name="Transporturi rutiere de mărfuri",
        address=SHARED_OFFICE,
        county="București",
        admins=[
            ("MARCELA INVENTATU", "2021-03-15", "2025-11-02"),
            ("IONEL FICTIVESCU", "2025-11-02", None),
        ],
        status="functiune",
        shareholders=[("CALBRONA HOLDING FICTIV SRL", True, "99000090", 100.0, "2021-03-15")],
    ),
    "99000033": dict(
        slug="brunaldo_trade_impex",
        name="BRUNALDO TRADE IMPEX SRL",
        reg="J99/5678/2012",
        founded="2012-06-11",
        caen="4690",
        caen_name="Comerț cu ridicata nespecializat",
        address="Bd. Inventat nr. 42, Localitatea Fictivă, Județul Fictiv",
        county="Județul Fictiv",
        admins=[("SORIN IMAGINESCU", "2012-06-11", None)],
        status="functiune",
        shareholders=[("CALBRONA HOLDING FICTIV SRL", True, "99000090", 100.0, "2012-06-11")],
    ),
    "99000041": dict(
        slug="kestrel_fictiv_transport",
        name="KESTREL FICTIV TRANSPORT SRL",
        reg="J99/3001/2018",
        founded="2018-02-01",
        caen="4941",
        caen_name="Transporturi rutiere de mărfuri",
        address="Str. Paravanului nr. 3, Sector 9, București",
        county="București",
        admins=[("IONEL FICTIVESCU", "2018-02-01", None)],
        status="faliment",
        bpi=[
            dict(
                case_no="9001/99/2024",
                court="Tribunalul Fictiv",
                type="faliment",
                opened_on="2024-04-15",
                status="in_desfasurare",
                publication_no="BPI-FICTIV-2024-0415",
            )
        ],
    ),
    "99000058": dict(
        slug="orvanto_distributie",
        name="ORVANTO DISTRIBUTIE SRL",
        reg="J99/3002/2017",
        founded="2017-09-12",
        caen="4639",
        caen_name="Comerț cu ridicata nespecializat de alimente",
        address="Str. Umbrei nr. 5, Sector 9, București",
        county="București",
        admins=[("IONEL FICTIVESCU", "2017-09-12", "2023-07-20")],
        status="radiata",
        deregistered="2023-07-20",
    ),
    "99000066": dict(
        slug="pelinor_construct_grup",
        name="PELINOR CONSTRUCT GRUP SRL",
        reg="J99/3003/2020",
        founded="2020-01-10",
        caen="4120",
        caen_name="Lucrări de construcții a clădirilor",
        address="Str. Schelei nr. 8, Sector 9, București",
        county="București",
        admins=[("IONEL FICTIVESCU", "2020-01-10", None)],
        status="insolventa",
        bpi=[
            dict(
                case_no="9002/99/2025",
                court="Tribunalul Fictiv",
                type="insolventa",
                opened_on="2025-05-06",
                status="in_desfasurare",
                publication_no="BPI-FICTIV-2025-0506",
            )
        ],
    ),
    "99000074": dict(
        slug="vantiro_agro_fictiv",
        name="VANTIRO AGRO FICTIV SRL",
        reg="J99/3004/2019",
        founded="2019-03-03",
        caen="0111",
        caen_name="Cultivarea cerealelor",
        address="Sat Câmpul Fictiv nr. 12, Județul Fictiv",
        county="Județul Fictiv",
        admins=[("IONEL FICTIVESCU", "2019-03-03", None)],
        status="functiune",
        inactive_since="2024-06-01",
    ),
    "99000082": dict(
        slug="mirelda_servicii_imaginare",
        name="MIRELDA SERVICII IMAGINARE SRL",
        reg="J99/3005/2022",
        founded="2022-08-08",
        caen="8299",
        caen_name="Alte activități de servicii suport pentru întreprinderi",
        address="Str. Ecoului nr. 2, Sector 9, București",
        county="București",
        admins=[("IONEL FICTIVESCU", "2022-08-08", None)],
        status="functiune",
    ),
    "99000090": dict(
        slug="calbrona_holding_fictiv",
        name="CALBRONA HOLDING FICTIV SRL",
        reg="J99/3006/2011",
        founded="2011-11-11",
        caen="6420",
        caen_name="Activități ale holdingurilor",
        address="Str. Holdingului nr. 9, Localitatea Fictivă, Județul Fictiv",
        county="Județul Fictiv",
        admins=[("GELU INEXISTENTU", "2011-11-11", None)],
        status="functiune",
        inactive_since="2023-09-01",
    ),
}

# (turnover, net_profit, debts, equity, share_capital, employees) per year 2021..2025
FINANCIALS: dict[str, dict[int, tuple[int, int, int, int, int, int]]] = {
    "99000017": {
        2021: (2_100_000, 310_000, 300_000, 900_000, 5_000, 18),
        2022: (2_600_000, 390_000, 340_000, 1_290_000, 5_000, 22),
        2023: (3_200_000, 470_000, 380_000, 1_760_000, 5_000, 27),
        2024: (3_900_000, 560_000, 420_000, 2_320_000, 5_000, 31),
        2025: (4_600_000, 650_000, 450_000, 2_970_000, 5_000, 36),
    },
    # Zephyria: exactly the brief's table
    "99000025": {
        2021: (180_000, 12_000, 40_000, 14_000, 200, 1),
        2022: (410_000, 25_000, 150_000, 39_000, 200, 1),
        2023: (1_900_000, 60_000, 1_100_000, 99_000, 200, 2),
        2024: (9_800_000, 140_000, 6_900_000, 239_000, 200, 2),
        2025: (18_600_000, -350_000, 14_200_000, -111_000, 200, 2),
    },
    # Brunaldo: turnover, profit, debts range and employees range are from the brief.
    # Intermediate debts/employees, equity and share capital are fixture choices.
    "99000033": {
        2021: (32_000_000, 1_100_000, 9_800_000, 6_500_000, 1_500_000, 85),
        2022: (34_500_000, 900_000, 11_900_000, 7_400_000, 1_500_000, 79),
        2023: (29_100_000, -400_000, 14_200_000, 7_000_000, 1_500_000, 66),
        2024: (21_700_000, -1_900_000, 16_800_000, 5_100_000, 1_500_000, 52),
        2025: (15_200_000, -2_600_000, 19_400_000, 2_500_000, 1_500_000, 41),
    },
}

FICTIVESCU_COMPANIES = ["99000041", "99000058", "99000066", "99000074", "99000082"]


# --------------------------------------------------------------------------- helpers
def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_model(path: Path, model: Any) -> None:
    if isinstance(model, list):
        write_json(path, [m.model_dump(mode="json") for m in model])
    else:
        write_json(path, model.model_dump(mode="json"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cdir(cui: str) -> Path:
    return COMPANIES / f"{cui}_{COMPANIES_FACTS[cui]['slug']}"


def ref(cui: str, filename: str, name: str, type_: SourceType, url: str | None) -> SourceRef:
    path = cdir(cui) / filename
    return SourceRef(
        name=name,
        type=type_,
        url=url,
        retrieved_at=CHECKED_AT,  # type: ignore[arg-type]
        raw_ref=f"fixture:{path.relative_to(FIX).as_posix()}",
        content_hash=sha(path),
    )


def fictional_cuis(prefix: str, n: int) -> list[str]:
    """CUIs in a 99xxxxxx range with a deliberately INVALID check digit."""
    out, body = [], int(prefix)
    while len(out) < n:
        b = str(body)
        bad = (checksum_digit(b) + 1) % 10
        out.append(b + str(bad))
        body += 1
    return out


# --------------------------------------------------------------------------- raw sources
def anaf_v9(cui: str) -> dict[str, Any]:
    f = COMPANIES_FACTS[cui]
    vat_periods = [
        {
            "data_inceput_ScpTVA": f["founded"],
            "data_sfarsit_ScpTVA": "",
            "data_anul_imp_ScpTVA": "",
            "mesaj_ScpTVA": "",
        }
    ]
    if cui == "99000033":  # VAT cancelled 2025-02-01, re-registered 2025-09-15
        vat_periods = [
            {
                "data_inceput_ScpTVA": "2025-09-15",
                "data_sfarsit_ScpTVA": "",
                "data_anul_imp_ScpTVA": "",
                "mesaj_ScpTVA": "",
            },
            {
                "data_inceput_ScpTVA": "2012-07-01",
                "data_sfarsit_ScpTVA": "2025-02-01",
                "data_anul_imp_ScpTVA": "2025-02-01",
                "mesaj_ScpTVA": "anulare inregistrare in scopuri de TVA (fictiv)",
            },
        ]
    inactive = f.get("inactive_since")
    dereg = f.get("deregistered")
    return {
        "fictional": True,
        "found": [
            {
                "date_generale": {
                    "cui": int(cui),
                    "data": TODAY.isoformat(),
                    "denumire": f["name"],
                    "adresa": f["address"],
                    "nrRegCom": f["reg"],
                    "telefon": "",
                    "fax": "",
                    "codPostal": "",
                    "act": "",
                    "stare_inregistrare": "RADIERE"
                    if dereg
                    else f"INREGISTRAT din data {f['founded']}",
                    "data_inregistrare": f["founded"],
                    "cod_CAEN": f["caen"],
                    "iban": "",
                    "statusRO_e_Factura": not dereg,
                    "organFiscalCompetent": "Administrația Fiscală Fictivă",
                    "forma_de_proprietate": "PROPR.PRIVATA-CAPITAL PRIVAT AUTOHTON",
                    "forma_organizare": "PERSOANA JURIDICA",
                    "forma_juridica": "SOCIETATE COMERCIALĂ CU RĂSPUNDERE LIMITATĂ",
                },
                "inregistrare_scop_Tva": {
                    "scpTVA": not dereg and cui != "99000074",
                    "perioade_TVA": vat_periods,
                },
                "inregistrare_RTVAI": {
                    "dataInceputTvaInc": "",
                    "dataSfarsitTvaInc": "",
                    "dataActualizareTvaInc": "",
                    "dataPublicareTvaInc": "",
                    "tipActTvaInc": "",
                    "statusTvaIncasare": False,
                },
                "stare_inactiv": {
                    "dataInactivare": inactive or "",
                    "dataReactivare": "",
                    "dataPublicare": inactive or "",
                    "dataRadiere": dereg or "",
                    "statusInactivi": bool(inactive),
                },
                "inregistrare_SplitTVA": {
                    "dataInceputSplitTVA": "",
                    "dataAnulareSplitTVA": "",
                    "statusSplitTVA": False,
                },
                "adresa_sediu_social": {
                    "sdenumire_Strada": f["address"].split(",")[0],
                    "snumar_Strada": "",
                    "sdenumire_Localitate": "",
                    "scod_Localitate": "",
                    "sdenumire_Judet": f["county"],
                    "scod_Judet": "99",
                    "scod_JudetAuto": "FI",
                    "stara": "",
                    "sdetalii_Adresa": "",
                    "scod_Postal": "",
                },
                "adresa_domiciliu_fiscal": {
                    "ddenumire_Strada": f["address"].split(",")[0],
                    "dnumar_Strada": "",
                    "ddenumire_Localitate": "",
                    "dcod_Localitate": "",
                    "ddenumire_Judet": f["county"],
                    "dcod_Judet": "99",
                    "dcod_JudetAuto": "FI",
                    "dtara": "",
                    "ddetalii_Adresa": "",
                    "dcod_Postal": "",
                },
            }
        ],
        "notFound": [],
    }


def bilant(cui: str, year: int) -> dict[str, Any]:
    t, p, d, e, cap, emp = FINANCIALS[cui][year]
    f = COMPANIES_FACTS[cui]
    labels = [
        ("I1", "Active imobilizate - total", int(t * 0.08)),
        ("I2", "Active circulante - total, din care", d + e - int(t * 0.08)),
        (
            "I3",
            "Stocuri (materii prime, materiale, productie in curs de executie, semifabricate, produse finite, marfuri etc.)",
            int(t * 0.05),
        ),
        ("I4", "Creante", int(t * 0.2)),
        ("I5", "Casa si conturi la banci", max(0, int(t * 0.03))),
        ("I6", "Cheltuieli in avans", 0),
        ("I7", "Datorii", d),
        ("I8", "Venituri in avans", 0),
        ("I9", "Provizioane", 0),
        ("I10", "Capitaluri - total, din care:", e),
        ("I11", "Capital subscris varsat", cap),
        ("I12", "Patrimoniul regiei", 0),
        ("I13", "Cifra de afaceri neta", t),
        ("I14", "VENITURI TOTALE", int(t * 1.01)),
        ("I15", "CHELTUIELI TOTALE", int(t * 1.01) - (round(p * 1.16) if p > 0 else p)),
        ("I16", "Profit brut", round(p * 1.16) if p > 0 else 0),
        ("I17", "Pierdere bruta", -p if p < 0 else 0),
        ("I18", "Profit net", p if p > 0 else 0),
        ("I19", "Pierdere neta", -p if p < 0 else 0),
        ("I20", "Numar mediu de salariati", emp),
    ]
    return {
        "fictional": True,
        "an": year,
        "cui": int(cui),
        "deni": f["name"],
        "caen": int(f["caen"]),
        "den_caen": f["caen_name"],
        "i": [
            {"indicator": c, "val_indicator": v, "val_den_indicator": label}
            for c, label, v in labels
        ],
    }


def onrc_view(cui: str) -> dict[str, Any]:
    f = COMPANIES_FACTS[cui]
    return {
        "fictional": True,
        "cui": cui,
        "denumire": f["name"],
        "cod_inmatriculare": f["reg"],
        "data_inmatriculare": f["founded"],
        "forma_juridica": "SRL",
        "stare": f["status"],
        "adresa": f["address"],
        "judet": f["county"],
        "caen_principal": {"cod": f["caen"], "revizie": "rev2", "denumire": f["caen_name"]},
        "caen_autorizate": [{"cod": f["caen"], "revizie": "rev2"}],
        "istoric_denumiri": [{"denumire": f["name"], "de_la": f["founded"], "pana_la": None}],
        "istoric_sedii": [{"adresa": f["address"], "de_la": f["founded"], "pana_la": None}],
        "reprezentanti": [
            {"nume": n, "calitate": "ADMINISTRATOR", "de_la": a, "pana_la": b}
            for n, a, b in f["admins"]
        ],
    }


def soap(cases: list[dict[str, Any]]) -> str:
    def case_xml(c: dict[str, Any]) -> str:
        parti = "".join(
            f"<DosarParte><nume>{escape(n)}</nume><calitateParte>{escape(q)}</calitateParte></DosarParte>"
            for n, q in c["parti"]
        )
        sed = "".join(
            f"<DosarSedinta><complet>C{i + 1}</complet><data>{d}T00:00:00</data><ora>09:00</ora>"
            f"<solutie>{escape(sol)}</solutie><solutieSumar>{escape(sol)}</solutieSumar>"
            '<dataPronuntare xsi:nil="true" /><documentSedinta /><numarDocument /><dataDocument xsi:nil="true" />'
            "</DosarSedinta>"
            for i, (d, sol) in enumerate(c["sedinte"])
        )
        return (
            f"<Dosar><parti>{parti}</parti><sedinte>{sed}</sedinte><caiAtac />"
            f"<numar>{c['numar']}</numar><numarVechi /><data>{c['data']}T00:00:00</data>"
            f"<institutie>{c['institutie']}</institutie><departament>{escape(c['departament'])}</departament>"
            f"<categorieCaz>{c['categorie']}</categorieCaz><stadiuProcesual>{c['stadiu']}</stadiuProcesual>"
            f"<obiect>{escape(c['obiect'])}</obiect><dataModificare>{c['modificat']}T00:00:00</dataModificare>"
            f"<categorieCazNume>{c['categorie']}</categorieCazNume><stadiuProcesualNume>{c['stadiu']}</stadiuProcesualNume>"
            "</Dosar>"
        )

    body = "".join(case_xml(c) for c in cases)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<!-- fictional: true -->\n'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
        '<soap:Body><CautareDosareResponse xmlns="portalquery.just.ro"><CautareDosareResult>'
        f"{body}</CautareDosareResult></CautareDosareResponse></soap:Body></soap:Envelope>\n"
    )


CASES: dict[str, list[dict[str, Any]]] = {
    "99000033": [
        dict(
            numar="9101/99/2026",
            data="2026-07-14",
            institutie="TribunalulFICTIV",
            departament="Secția a II-a civilă",
            categorie="Insolventa",
            stadiu="Fond",
            obiect="procedura insolvenței - cerere de deschidere formulată de creditor",
            modificat="2026-10-02",
            parti=[
                ("AGENȚIA NAȚIONALĂ DE ADMINISTRARE FISCALĂ", "Creditor"),
                ("BRUNALDO TRADE IMPEX SRL", "Debitor"),
            ],
            sedinte=[("2026-09-18", "Amână cauza"), ("2026-11-20", "")],
        ),
        dict(
            numar="9102/99/2025",
            data="2025-03-03",
            institutie="CurteadeApelFICTIVA",
            departament="Secția a VI-a civilă",
            categorie="Civil",
            stadiu="Apel",
            obiect="pretenții - 1.800.000 RON contravaloare marfă livrată și neachitată",
            modificat="2026-09-30",
            parti=[("FURNIZOR EXEMPLU SA", "Apelant"), ("BRUNALDO TRADE IMPEX SRL", "Intimat")],
            sedinte=[("2025-11-12", "Admite în parte acțiunea"), ("2026-12-04", "")],
        ),
        dict(
            numar="9103/99/2025",
            data="2025-06-20",
            institutie="TribunalulFICTIV",
            departament="Secția conflicte de muncă",
            categorie="Litigii_cu_profesionistii",
            stadiu="Fond",
            obiect="litigiu de muncă - drepturi salariale",
            modificat="2026-08-21",
            parti=[("ANGAJAT EXEMPLU", "Reclamant"), ("BRUNALDO TRADE IMPEX SRL", "Pârât")],
            sedinte=[("2026-12-10", "")],
        ),
    ],
    "99000041": [
        dict(
            numar="9001/99/2024",
            data="2024-01-22",
            institutie="TribunalulFICTIV",
            departament="Secția a II-a civilă",
            categorie="Insolventa",
            stadiu="Fond",
            obiect="procedura insolvenței - faliment",
            modificat="2026-06-30",
            parti=[("KESTREL FICTIV TRANSPORT SRL", "Debitor")],
            sedinte=[("2024-04-15", "Deschide procedura simplificată de faliment")],
        ),
    ],
    "99000066": [
        dict(
            numar="9002/99/2025",
            data="2025-02-10",
            institutie="TribunalulFICTIV",
            departament="Secția a II-a civilă",
            categorie="Insolventa",
            stadiu="Fond",
            obiect="procedura insolvenței",
            modificat="2026-07-15",
            parti=[("PELINOR CONSTRUCT GRUP SRL", "Debitor")],
            sedinte=[("2025-05-06", "Deschide procedura generală a insolvenței")],
        ),
    ],
}


def write_raw() -> None:
    for cui, f in COMPANIES_FACTS.items():
        d = cdir(cui)
        write_json(d / "anaf_v9.json", anaf_v9(cui))
        write_json(d / "onrc.json", onrc_view(cui))
        (d / "portal_just.xml").write_text(soap(CASES.get(cui, [])), encoding="utf-8")
        write_json(d / "bpi.json", {"fictional": True, "cui": cui, "proceedings": f.get("bpi", [])})
        if "shareholders" in f:
            write_json(
                d / "shareholders.json",
                {
                    "fictional": True,
                    "cui": cui,
                    "shareholders": [
                        {"name": n, "is_company": c, "cui": sc, "share_pct": pct, "since": since}
                        for n, c, sc, pct, since in f["shareholders"]
                    ],
                },
            )
        for year in FINANCIALS.get(cui, {}):
            write_json(d / f"bilant_{year}.json", bilant(cui, year))

    # Mocks and web for the three main demo companies
    write_json(
        cdir("99000017") / "restante.json",
        {"fictional": True, "cui": "99000017", "list_period": "2026-Q2", "obligations": []},
    )
    write_json(
        cdir("99000025") / "restante.json",
        {"fictional": True, "cui": "99000025", "list_period": "2026-Q2", "obligations": []},
    )
    write_json(
        cdir("99000033") / "restante.json",
        {
            "fictional": True,
            "cui": "99000033",
            "list_period": "2026-Q2",
            "obligations": [
                {"type": "principal", "amount_ron": 412_560},
                {"type": "accesorii", "amount_ron": 96_300},
            ],
        },
    )

    period = {"from": "2025-01-01", "to": "2025-12-31"}
    write_json(
        cdir("99000017") / "efactura.json",
        {
            "fictional": True,
            "cui": "99000017",
            "period": period,
            "issued_total_ron": 4_600_000,
            "received_total_ron": 2_900_000,
            "flows": [],
        },
    )
    write_json(
        cdir("99000025") / "efactura.json",
        {
            "fictional": True,
            "cui": "99000025",
            "period": period,
            "issued_total_ron": 18_600_000,
            "received_total_ron": 18_400_000,
            "flows": [
                {
                    "from_cui": "99000025",
                    "to_cui": "99000082",
                    "total_ron": 2_100_000,
                    "n_invoices": 14,
                    "period": "2025",
                },
                {
                    "from_cui": "99000082",
                    "to_cui": "99000041",
                    "total_ron": 2_100_000,
                    "n_invoices": 9,
                    "period": "2025",
                },
                {
                    "from_cui": "99000041",
                    "to_cui": "99000025",
                    "total_ron": 2_100_000,
                    "n_invoices": 11,
                    "period": "2025",
                },
            ],
        },
    )
    write_json(
        cdir("99000033") / "efactura.json",
        {
            "fictional": True,
            "cui": "99000033",
            "period": period,
            "issued_total_ron": 15_200_000,
            "received_total_ron": 13_900_000,
            "flows": [],
        },
    )

    def quarters(total: int) -> list[dict[str, Any]]:
        q = total // 4
        return [
            {
                "period": f"2025-Q{i}",
                "taxable_base_ron": q,
                "vat_collected_ron": round(q * 0.19),
                "vat_deductible_ron": round(q * 0.15),
            }
            for i in range(1, 5)
        ]

    write_json(
        cdir("99000017") / "d300.json",
        {"fictional": True, "cui": "99000017", "returns": quarters(4_600_000)},
    )
    write_json(
        cdir("99000025") / "d300.json",
        {"fictional": True, "cui": "99000025", "returns": quarters(18_600_000)},
    )
    # Brunaldo: D300 declared sales 18% below e-Factura issued (12,464,000 vs 15,200,000)
    write_json(
        cdir("99000033") / "d300.json",
        {"fictional": True, "cui": "99000033", "returns": quarters(12_464_000)},
    )

    write_json(
        cdir("99000017") / "media.json",
        {"fictional": True, "query": "AURORA SOFT LABS SRL", "results": []},
    )
    write_json(
        cdir("99000025") / "media.json",
        {
            "fictional": True,
            "query": "ZEPHYRIA LOGISTIC NOVA SRL Ionel Fictivescu",
            "results": [
                {
                    "title": "Percheziții la firme de transport conduse de Ionel Fictivescu",
                    "url": "https://stiri-fictive.example/2026/04/perchezitii-transport",
                    "content": "Anchetatorii au efectuat percheziții la mai multe firme de transport administrate de Ionel Fictivescu, "
                    "într-un dosar privind o posibilă evaziune fiscală. (articol fictiv)",
                    "score": 0.81,
                    "published_date": "2026-04-12",
                }
            ],
        },
    )
    write_json(
        cdir("99000033") / "media.json",
        {
            "fictional": True,
            "query": "BRUNALDO TRADE IMPEX SRL",
            "results": [
                {
                    "title": "Furnizorii Brunaldo Trade Impex își așteaptă banii",
                    "url": "https://ziar-inventat.example/brunaldo-datorii",
                    "content": "Mai mulți furnizori spun că BRUNALDO TRADE IMPEX SRL are facturi neachitate de luni de zile. (articol fictiv)",
                    "score": 0.77,
                    "published_date": "2026-03-03",
                }
            ],
        },
    )

    write_json(
        cdir("99000017") / "presence.json",
        {
            "fictional": True,
            "website": {
                "url": "https://aurora-soft-labs.example",
                "address_on_site": COMPANIES_FACTS["99000017"]["address"],
            },
            "jobs": [
                {
                    "title": "Dezvoltator Python",
                    "url": "https://joburi-fictive.example/aurora/1",
                    "posted": "2026-09-30",
                },
                {
                    "title": "QA Engineer",
                    "url": "https://joburi-fictive.example/aurora/2",
                    "posted": "2026-10-12",
                },
            ],
            "seap": [],
            "kohesio": [],
        },
    )
    write_json(
        cdir("99000025") / "presence.json",
        {"fictional": True, "website": None, "jobs": [], "seap": [], "kohesio": []},
    )
    write_json(
        cdir("99000033") / "presence.json",
        {
            "fictional": True,
            "website": {
                "url": "https://brunaldo-trade.example",
                "address_on_site": COMPANIES_FACTS["99000033"]["address"],
            },
            "jobs": [],
            "seap": [],
            "kohesio": [],
        },
    )

    # Submitted documents (already extracted, SubmittedFinancials shape)
    for cui, years in {
        "99000025": [(2025, 25_400_000, 1_200_000, 14)],
        "99000033": [(2025, None, 300_000, None)],
    }.items():
        src = SourceRef(
            name="Documents submitted by the applicant",
            type=SourceType.SUBMITTED,
            retrieved_at=CHECKED_AT,
            raw_ref=f"fixture:companies/{cdir(cui).name}/submitted/financials.json",
        )
        sub = SubmittedFinancials(
            cui=cui,
            years=[
                FinancialYear(year=y, turnover=t, net_profit=p, employees=e, source=src)
                for y, t, p, e in years
            ],
            document_names=[f"situatii_financiare_2025_{COMPANIES_FACTS[cui]['slug']}.pdf"],
            extracted_at=CHECKED_AT,
        )
        write_json(
            cdir(cui) / "submitted" / "financials.json",
            {"fictional": True, **sub.model_dump(mode="json")},
        )


def write_sources() -> None:
    onrc = SOURCES / "onrc"
    onrc.mkdir(parents=True, exist_ok=True)
    fillers = fictional_cuis(
        "9900100", 62
    )  # 62 other companies at Zephyria's office -> 63 in total
    firms = [
        (f["name"], cui, f["reg"], f["founded"], f["address"], f["county"])
        for cui, f in COMPANIES_FACTS.items()
    ]
    firms += [
        (
            f"FIRMA PARAVAN FICTIVA {i + 1:02d} SRL",
            c,
            f"J99/{9000 + i}/2024",
            "2024-01-15",
            SHARED_OFFICE,
            "București",
        )
        for i, c in enumerate(fillers)
    ]
    lines = [
        "DENUMIRE^CUI^COD_INMATRICULARE^DATA_INMATRICULARE^FORMA_JURIDICA^ADRESA_COMPLETA^JUDET^FICTIONAL"
    ]
    lines += [f"{n}^{c}^{r}^{d}^SRL^{a}^{j}^true" for n, c, r, d, a, j in firms]
    (onrc / "OD_FIRME_sample.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    reps = ["COD_INMATRICULARE^PERSOANA_IMPUTERNICITA^CALITATE^DATA_NUMIRE^DATA_INCETARE^FICTIONAL"]
    for f in COMPANIES_FACTS.values():
        reps += [f"{f['reg']}^{n}^ADMINISTRATOR^{a}^{b or ''}^true" for n, a, b in f["admins"]]
    (onrc / "OD_REPREZENTANTI_LEGALI_sample.csv").write_text(
        "\n".join(reps) + "\n", encoding="utf-8"
    )

    status = {
        "functiune": "1048",
        "faliment": "1076",
        "insolventa": "1075",
        "radiata": "1999",
    }  # fictional codes
    st = ["COD_INMATRICULARE^COD_STARE^STARE^FICTIONAL"]
    st += [f"{f['reg']}^{status[f['status']]}^{f['status']}^true" for f in COMPANIES_FACTS.values()]
    (onrc / "OD_STARE_FIRMA_sample.csv").write_text("\n".join(st) + "\n", encoding="utf-8")

    caen = ["COD_INMATRICULARE^COD_CAEN_AUTORIZAT^VERSIUNE_CAEN^FICTIONAL"]
    caen += [f"{f['reg']}^{f['caen']}^2^true" for f in COMPANIES_FACTS.values()]
    (onrc / "OD_CAEN_AUTORIZAT_sample.csv").write_text("\n".join(caen) + "\n", encoding="utf-8")

    sanc = SOURCES / "sanctions"
    sanc.mkdir(parents=True, exist_ok=True)
    (sanc / "eu_fsf_sample.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<!-- fictional: true. Shape to be verified against the real FSF file. -->\n'
        '<export generationDate="2026-10-27T00:00:00">'
        '<sanctionEntity logicalId="900001"><subjectType code="person"/>'
        '<nameAlias wholeName="Exemplu Sancționatescu" firstName="Exemplu" lastName="Sancționatescu"/>'
        '<citizenship countryIso2Code="ZZ"/><birthdate birthdate="1970-01-01"/></sanctionEntity>'
        '<sanctionEntity logicalId="900002"><subjectType code="enterprise"/>'
        '<nameAlias wholeName="ENTITATE INTERZISA FICTIVA LTD"/></sanctionEntity></export>\n',
        encoding="utf-8",
    )
    (sanc / "un_sample.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<!-- fictional: true -->\n<CONSOLIDATED_LIST dateGenerated="2026-10-27">'
        "<INDIVIDUALS><INDIVIDUAL><DATAID>990001</DATAID><FIRST_NAME>NUMEFICTIV</FIRST_NAME>"
        "<SECOND_NAME>INEXISTENT</SECOND_NAME><UN_LIST_TYPE>FICTIV</UN_LIST_TYPE></INDIVIDUAL></INDIVIDUALS>"
        "<ENTITIES><ENTITY><DATAID>990002</DATAID><FIRST_NAME>ORGANIZATIA FICTIVA</FIRST_NAME></ENTITY></ENTITIES>"
        "</CONSOLIDATED_LIST>\n",
        encoding="utf-8",
    )
    (sanc / "ofac_sdn_sample.csv").write_text(
        '99901,"FICTIV, Persoana Exemplu","individual","FICTIV","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","fictional: true"\n'
        '99902,"COMPANIA BLOCATA FICTIVA SRL","-0- ","FICTIV","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","fictional: true"\n',
        encoding="utf-8",
    )
    write_json(
        SOURCES / "pep_sample.json",
        {
            "fictional": True,
            "entries": [
                {
                    "name": "DEMNITAR EXEMPLESCU",
                    "function": "Ministru fictiv",
                    "country": "RO",
                    "since": "2020-01-01",
                    "until": None,
                }
            ],
        },
    )
    (SOURCES / "caen_rev2_rev3.csv").write_text("cod_rev2,cod_rev3\n", encoding="utf-8")


# --------------------------------------------------------------------------- API-shaped fixtures
def identity_sheet(cui: str) -> IdentitySheet:
    f = COMPANIES_FACTS[cui]
    onrc_ref = ref(cui, "onrc.json", "ONRC open data (data.gov.ro)", SourceType.OFFICIAL, None)
    v9_ref = ref(cui, "anaf_v9.json", "ANAF VAT registry v9", SourceType.OFFICIAL, V9_URL)
    admins = [
        Person(
            name=n,
            role=PersonRole.ADMINISTRATOR,
            valid_from=date.fromisoformat(a),
            valid_to=date.fromisoformat(b) if b else None,
            source=onrc_ref,
        )
        for n, a, b in f["admins"]
    ]
    shareholders = []
    if "shareholders" in f:
        sh_ref = ref(cui, "shareholders.json", "Shareholders (MOCK)", SourceType.MOCK, None)
        shareholders = [
            Person(
                name=n,
                role=PersonRole.SHAREHOLDER,
                is_company=c,
                cui=sc,
                share_pct=pct,
                valid_from=date.fromisoformat(s),
                source=sh_ref,
            )
            for n, c, sc, pct, s in f["shareholders"]
        ]
    office = Address(
        raw=f["address"], county=f["county"], valid_from=date.fromisoformat(f["founded"])
    )
    return IdentitySheet(
        cui=cui,
        fictional=True,
        trade_register_no=f["reg"],
        current_name=f["name"],
        names=[CompanyName(name=f["name"], valid_from=date.fromisoformat(f["founded"]))],
        legal_form="SRL",
        status=CompanyStatus.ACTIVE,
        registration_date=date.fromisoformat(f["founded"]),
        registered_office=office,
        office_history=[office],
        caen_code=f["caen"],
        caen_revision="rev2",
        authorized_caen_codes=[f["caen"]],
        administrators=admins,
        shareholders=shareholders,
        vat_registered=True,
        anaf_inactive=False,
        sources=[v9_ref, onrc_ref],
    )


def sig(
    cui: str,
    agent: str,
    comp: Component,
    rule: str,
    sev: Severity,
    claim: str,
    source: SourceRef,
    evidence: str | None,
    conf: float,
    match: EntityMatch,
    data: dict[str, Any],
    disc: str = "",
    validated: bool = True,
    auto_stop: bool = False,
) -> Signal:
    return Signal(
        signal_id=make_signal_id(cui, rule, disc),
        cui=cui,
        agent=agent,
        component=comp,
        rule_id=rule,
        claim=claim,
        source=source,
        evidence_date=date.fromisoformat(evidence) if evidence else None,
        confidence=conf,
        severity=sev,
        validated=validated,
        auto_stop_candidate=auto_stop,
        entity_match=match,
        data={"fictional": True, **data},
    )


EXACT = EntityMatch(method="cui_exact", score=1.0)


def financials_signals(cui: str) -> list[Signal]:
    """Run the REAL financials agent on the raw fixtures just written, so the API fixtures
    always show exactly what the agent produces."""
    import asyncio
    import tempfile

    from verifirm.adapters.anaf_bilant import AnafBilantAdapter
    from verifirm.adapters.base import AdapterDeps
    from verifirm.agents.base import AgentContext
    from verifirm.agents.financials.agent import FinancialsAgent
    from verifirm.core.config import Settings
    from verifirm.core.impl_local.cache import MemoryCache
    from verifirm.core.impl_local.clock import FixedClock
    from verifirm.core.impl_local.object_store import FilesystemObjectStore
    from verifirm.core.impl_local.rate_limiter import MemoryRateLimiter

    settings = Settings(fixture_mode=True, fixtures_dir=FIX)
    clock = FixedClock(CHECKED_AT)
    with tempfile.TemporaryDirectory() as tmp:
        deps = AdapterDeps(
            settings=settings,
            cache=MemoryCache(),
            object_store=FilesystemObjectStore(Path(tmp)),
            rate_limiter=MemoryRateLimiter(),
            clock=clock,
        )
        ctx = AgentContext(
            run_id="fixture",
            cui=cui,
            identity=identity_sheet(cui),
            settings=settings,
            clock=clock,
            adapters={"anaf_bilant": AnafBilantAdapter(deps)},
        )
        result = asyncio.run(FinancialsAgent().run(ctx))
    assert result.status.value == "ok", result
    return [s.model_copy(update={"data": {"fictional": True, **s.data}}) for s in result.signals]


def signals_for(cui: str) -> list[Signal]:
    if cui == "99000017":
        return []
    onrc = ref(cui, "onrc.json", "ONRC open data (data.gov.ro)", SourceType.OFFICIAL, None)
    v9 = ref(cui, "anaf_v9.json", "ANAF VAT registry v9", SourceType.OFFICIAL, V9_URL)
    b25 = ref(
        cui,
        "bilant_2025.json",
        "ANAF financial statements (bilanț)",
        SourceType.OFFICIAL,
        f"https://webservicesp.anaf.ro/bilant?an=2025&cui={cui}",
    )
    media = ref(cui, "media.json", "Web search (Tavily)", SourceType.WEB, None)
    out: list[Signal] = []
    IDN, _FIN, T, L, N, M, P = (
        Component.IDENTITY,
        Component.FINANCIALS,
        Component.TAX,
        Component.LITIGATION,
        Component.NETWORK,
        Component.MEDIA,
        Component.PRESENCE,
    )
    if cui == "99000025":
        efa = ref(cui, "efactura.json", "RO e-Factura invoices (MOCK)", SourceType.MOCK, None)
        sh = ref(cui, "shareholders.json", "Shareholders (MOCK)", SourceType.MOCK, None)
        media_ref = SourceRef.model_validate(
            {
                **media.model_dump(),
                "url": "https://stiri-fictive.example/2026/04/perchezitii-transport",
            }
        )
        out += [
            sig(
                cui,
                "identity",
                IDN,
                "ID-ADMIN-CHANGE-01",
                Severity.MEDIUM,
                "The administrator changed on 2025-11-02 from Marcela Inventatu to Ionel Fictivescu.",
                onrc,
                "2025-11-02",
                1.0,
                EXACT,
                {
                    "previous": "MARCELA INVENTATU",
                    "current": "IONEL FICTIVESCU",
                    "changed_on": "2025-11-02",
                },
            ),
            sig(
                cui,
                "identity",
                IDN,
                "ID-SHARED-OFFICE-01",
                Severity.MEDIUM,
                "The registered office is shared by 63 companies.",
                onrc,
                None,
                1.0,
                EXACT,
                {"address": SHARED_OFFICE, "n_companies": 63, "threshold": 20},
            ),
            sig(
                cui,
                "tax",
                T,
                "TAX-DECLARED-GAP-01",
                Severity.HIGH,
                "Submitted 2025 figures differ from ANAF: turnover 25,400,000 vs 18,600,000 RON, net result +1,200,000 vs "
                "-350,000 RON, employees 14 vs 2.",
                b25,
                "2025-12-31",
                1.0,
                EXACT,
                {
                    "year": 2025,
                    "submitted": {"turnover": 25_400_000, "net_profit": 1_200_000, "employees": 14},
                    "official": {"turnover": 18_600_000, "net_profit": -350_000, "employees": 2},
                },
                disc="2025",
            ),
            sig(
                cui,
                "network",
                N,
                "NET-SERIAL-ADMIN-01",
                Severity.HIGH,
                "Administrator Ionel Fictivescu administers or administered 4 companies that failed since 2023: Kestrel "
                "(bankruptcy 2024), Orvanto (deregistered 2023), Pelinor (insolvency 2025), Vantiro (ANAF inactive since 2024-06-01).",
                onrc,
                "2025-05-06",
                0.9,
                EntityMatch(method="person_name", score=0.95),
                {
                    "person": "IONEL FICTIVESCU",
                    "failed": [
                        {
                            "cui": "99000041",
                            "name": "KESTREL FICTIV TRANSPORT SRL",
                            "event": "bankruptcy",
                            "date": "2024-04-15",
                            "case": "9001/99/2024",
                        },
                        {
                            "cui": "99000058",
                            "name": "ORVANTO DISTRIBUTIE SRL",
                            "event": "deregistered",
                            "date": "2023-07-20",
                        },
                        {
                            "cui": "99000066",
                            "name": "PELINOR CONSTRUCT GRUP SRL",
                            "event": "insolvency",
                            "date": "2025-05-06",
                            "case": "9002/99/2025",
                        },
                        {
                            "cui": "99000074",
                            "name": "VANTIRO AGRO FICTIV SRL",
                            "event": "anaf_inactive",
                            "date": "2024-06-01",
                        },
                    ],
                    "active": [{"cui": "99000082", "name": "MIRELDA SERVICII IMAGINARE SRL"}],
                },
                disc="IONEL FICTIVESCU",
            ),
            sig(
                cui,
                "network",
                N,
                "NET-CIRCULAR-INVOICE-01",
                Severity.HIGH,
                "Invoices of 2,100,000 RON form a cycle Zephyria -> Mirelda -> Kestrel -> Zephyria in 2025.",
                efa,
                "2025-12-31",
                0.95,
                EXACT,
                {"cycle": ["99000025", "99000082", "99000041", "99000025"], "total_ron": 2_100_000},
            ),
            sig(
                cui,
                "network",
                N,
                "NET-PARTNER-INACTIVE-01",
                Severity.MEDIUM,
                "The sole shareholder Calbrona Holding Fictiv SRL is ANAF inactive since 2023-09-01.",
                sh,
                "2023-09-01",
                0.95,
                EXACT,
                {"partner_cui": "99000090", "share_pct": 100.0, "inactive_since": "2023-09-01"},
            ),
            sig(
                cui,
                "media",
                M,
                "MED-ADVERSE-01",
                Severity.MEDIUM,
                "An article published on 2026-04-12 reports searches at transport firms run by Ionel Fictivescu in a "
                "suspected tax-evasion case.",
                media_ref,
                "2026-04-12",
                0.6,
                EntityMatch(method="person_name", score=0.7, ambiguous=True),
                {
                    "url": "https://stiri-fictive.example/2026/04/perchezitii-transport",
                    "published": "2026-04-12",
                },
                validated=False,
            ),
            sig(
                cui,
                "presence",
                P,
                "PRE-NO-FOOTPRINT-01",
                Severity.MEDIUM,
                "No website, job postings, SEAP contracts or EU-funded projects were found despite 18,600,000 RON 2025 turnover.",
                ref(
                    cui,
                    "presence.json",
                    "Public footprint (web, SEAP, Kohesio)",
                    SourceType.WEB,
                    None,
                ),
                None,
                0.8,
                EXACT,
                {"turnover": 18_600_000, "website": False, "jobs": 0, "seap": 0, "kohesio": 0},
            ),
        ]
    if cui == "99000033":
        just = ref(
            cui, "portal_just.xml", "Portal Just (portal.just.ro)", SourceType.OFFICIAL, JUST_URL
        )
        match = EntityMatch(method="name+county", score=0.9)
        sh = ref(cui, "shareholders.json", "Shareholders (MOCK)", SourceType.MOCK, None)
        media_ref = SourceRef.model_validate(
            {**media.model_dump(), "url": "https://ziar-inventat.example/brunaldo-datorii"}
        )
        out += [
            sig(
                cui,
                "tax",
                T,
                "TAX-ARREARS-01",
                Severity.HIGH,
                "The company is on the Q2 2026 ANAF arrears list with 412,560 RON principal and 96,300 RON accessories.",
                ref(cui, "restante.json", "ANAF tax arrears list (MOCK)", SourceType.MOCK, None),
                "2026-06-30",
                1.0,
                EXACT,
                {"list_period": "2026-Q2", "principal_ron": 412_560, "accessories_ron": 96_300},
            ),
            sig(
                cui,
                "tax",
                T,
                "TAX-VAT-CANCELLED-01",
                Severity.MEDIUM,
                "VAT registration was cancelled on 2025-02-01 and re-registered on 2025-09-15.",
                v9,
                "2025-02-01",
                1.0,
                EXACT,
                {"cancelled_on": "2025-02-01", "reregistered_on": "2025-09-15"},
            ),
            sig(
                cui,
                "tax",
                T,
                "TAX-EFACTURA-GAP-01",
                Severity.MEDIUM,
                "2025 D300 declared sales (12,464,000 RON) are 18% below e-Factura issued invoices (15,200,000 RON).",
                ref(cui, "d300.json", "D300 VAT returns (MOCK)", SourceType.MOCK, None),
                "2025-12-31",
                0.95,
                EXACT,
                {"d300_ron": 12_464_000, "efactura_ron": 15_200_000, "gap_pct": 18.0},
            ),
            sig(
                cui,
                "tax",
                T,
                "TAX-DECLARED-GAP-01",
                Severity.HIGH,
                "Submitted 2025 net result is +300,000 RON while ANAF shows -2,600,000 RON.",
                b25,
                "2025-12-31",
                1.0,
                EXACT,
                {
                    "year": 2025,
                    "submitted": {"net_profit": 300_000},
                    "official": {"net_profit": -2_600_000},
                },
                disc="2025",
            ),
            sig(
                cui,
                "litigation",
                L,
                "LIT-INSOLVENCY-REQUEST-01",
                Severity.HIGH,
                "ANAF requested the opening of insolvency in case 9101/99/2026 (first instance, next hearing 2026-11-20). "
                "The procedure is not opened.",
                just,
                "2026-07-14",
                0.9,
                match,
                {
                    "case_no": "9101/99/2026",
                    "stage": "first_instance",
                    "next_hearing": "2026-11-20",
                    "opened": False,
                    "becomes_stop_if": "LIT-INSOLVENCY-OPENED-01",
                },
                disc="9101/99/2026",
            ),
            sig(
                cui,
                "litigation",
                L,
                "LIT-MATERIAL-CLAIM-01",
                Severity.HIGH,
                "A supplier claims 1,800,000 RON in case 9102/99/2025, now on appeal.",
                just,
                "2025-03-03",
                0.9,
                match,
                {
                    "case_no": "9102/99/2025",
                    "claim_ron": 1_800_000,
                    "stage": "appeal",
                    "share_of_turnover_pct": 11.8,
                },
                disc="9102/99/2025",
            ),
            sig(
                cui,
                "litigation",
                L,
                "LIT-MINOR-01",
                Severity.LOW,
                "A labour dispute is pending in case 9103/99/2025 (first instance).",
                just,
                "2025-06-20",
                0.9,
                match,
                {"case_no": "9103/99/2025", "subject": "labour"},
                disc="9103/99/2025",
            ),
            sig(
                cui,
                "network",
                N,
                "NET-PARTNER-INACTIVE-01",
                Severity.MEDIUM,
                "The sole shareholder Calbrona Holding Fictiv SRL is ANAF inactive since 2023-09-01.",
                sh,
                "2023-09-01",
                0.95,
                EXACT,
                {"partner_cui": "99000090", "share_pct": 100.0, "inactive_since": "2023-09-01"},
            ),
            sig(
                cui,
                "media",
                M,
                "MED-NEGATIVE-01",
                Severity.LOW,
                "An article published on 2026-03-03 reports that suppliers say the company has unpaid invoices.",
                media_ref,
                "2026-03-03",
                0.6,
                EntityMatch(method="name_fuzzy", score=0.8),
                {
                    "url": "https://ziar-inventat.example/brunaldo-datorii",
                    "published": "2026-03-03",
                },
                validated=False,
            ),
        ]
    out += financials_signals(cui)  # produced by the real agent, never hand-written
    return out


def score(signals: list[Signal]) -> tuple[float, Band, list[ComponentScore], Coverage, list[str]]:
    comps = []
    for c, w in WEIGHTS.items():
        mine = [s for s in signals if s.component == c]
        value = max(
            0.0, 100 - sum(PENALTY[s.severity] * s.confidence * s.entity_match.score for s in mine)
        )
        comps.append(
            ComponentScore(
                component=c,
                status=AgentStatus.OK,
                available=True,
                score=round(value, 1),
                weight=w,
                effective_weight=w / 100,
                signal_ids=[s.signal_id for s in mine],
            )
        )
    trust = round(sum((cs.score or 0) * cs.weight for cs in comps) / 100, 1)
    cov = Coverage(weight_pct=100, available=8, total=8)
    high_comps = sorted({s.component.value for s in signals if s.severity == Severity.HIGH})
    if len(high_comps) >= 2 or trust < 50:
        return (
            trust,
            Band.RED,
            comps,
            cov,
            [f"HIGH_SIGNALS:{','.join(high_comps)}"] + (["SCORE<50"] if trust < 50 else []),
        )
    if high_comps or trust < 75:
        return trust, Band.YELLOW, comps, cov, ["YELLOW"]
    return trust, Band.GREEN, comps, cov, []


MEMOS: dict[str, dict[str, Any]] = {
    "99000017": dict(
        md=(
            "## Summary\n\nAURORA SOFT LABS SRL (fictional) scores 100.0 (GREEN) with 8/8 sources available. "
            "No signals were raised.\n\n## Coverage\n\nAll 8 agents completed. MOCK sources used: tax arrears list, "
            "D300, e-Factura, shareholders.\n"
        ),
        questions=[],
        rejected=[],
    ),
    "99000025": dict(
        md=(
            "## Summary\n\nZEPHYRIA LOGISTIC NOVA SRL (fictional) scores {score} (RED) with 8/8 sources available. "
            "High signals appear in financials, tax and network.\n\n"
            "## Red signals\n\n"
            "- Submitted 2025 figures differ from ANAF: turnover 25,400,000 vs 18,600,000 RON, net result +1,200,000 vs "
            "-350,000 RON, employees 14 vs 2. [TAX-DECLARED-GAP-01]\n"
            "- Administrator Ionel Fictivescu is linked to 4 failed companies (Kestrel, Orvanto, Pelinor, Vantiro). [NET-SERIAL-ADMIN-01]\n"
            "- Invoices of 2,100,000 RON form a cycle Zephyria -> Mirelda -> Kestrel -> Zephyria. [NET-CIRCULAR-INVOICE-01] (MOCK source)\n"
            "- 2025 equity was -111,000 RON, below half of the 200 RON share capital. [FIN-NET-ASSETS-01]\n\n"
            "## Yellow signals\n\n"
            "- Administrator changed on 2025-11-02. Registered office shared by 63 companies. [ID-ADMIN-CHANGE-01, ID-SHARED-OFFICE-01]\n"
            "- Turnover grew from 410,000 RON (2022) to 18,600,000 RON (2025) with 2 employees. [FIN-REVENUE-JUMP-01, FIN-HEADCOUNT-01]\n"
            "- No public footprint despite 18,600,000 RON turnover. [PRE-NO-FOOTPRINT-01]\n"
            "- **Unvalidated:** an article published on 2026-04-12 reports searches at firms run by Ionel Fictivescu. [MED-ADVERSE-01]\n\n"
            "## Coverage\n\nAll 8 agents completed. MOCK sources used: e-Factura, shareholders, tax arrears list, D300.\n"
        ),
        questions=[
            (
                "Please explain the difference between the submitted 2025 turnover (25,400,000 RON) and the ANAF figure (18,600,000 RON).",
                ["TAX-DECLARED-GAP-01"],
            ),
            (
                "What goods or services were invoiced to Mirelda Servicii Imaginare SRL, and by Kestrel Fictiv Transport SRL to you, in 2025?",
                ["NET-CIRCULAR-INVOICE-01"],
            ),
            (
                "What is Ionel Fictivescu's role in Kestrel, Orvanto, Pelinor and Vantiro, and why did they fail?",
                ["NET-SERIAL-ADMIN-01"],
            ),
            (
                "How is 18,600,000 RON of transport turnover delivered with 2 employees (subcontractors, fleet)?",
                ["FIN-HEADCOUNT-01"],
            ),
            (
                "What is the plan to bring equity back above half of the share capital?",
                ["FIN-NET-ASSETS-01"],
            ),
        ],
        rejected=[
            (
                "The company is very likely a missing-trader fraud vehicle.",
                "opinion / accusation not supported by any signal",
            )
        ],
    ),
    "99000033": dict(
        md=(
            "## Summary\n\nBRUNALDO TRADE IMPEX SRL (fictional) scores {score} (RED) with 8/8 sources available. "
            "High signals appear in tax and litigation. The band is not STOP: the insolvency procedure is requested, not opened.\n\n"
            "## Red signals\n\n"
            "- ANAF requested insolvency in case 9101/99/2026 (first instance, next hearing 2026-11-20). If the procedure is "
            "opened, the band becomes STOP. [LIT-INSOLVENCY-REQUEST-01]\n"
            "- On the Q2 2026 ANAF arrears list: 412,560 RON principal and 96,300 RON accessories. [TAX-ARREARS-01] (MOCK source)\n"
            "- Submitted 2025 net result +300,000 RON vs -2,600,000 RON at ANAF. [TAX-DECLARED-GAP-01]\n"
            "- Supplier claim of 1,800,000 RON on appeal in case 9102/99/2025. [LIT-MATERIAL-CLAIM-01]\n\n"
            "## Yellow signals\n\n"
            "- Turnover fell from 29,100,000 RON (2023) to 15,200,000 RON (2025), with net losses in 2023-2025. "
            "[FIN-REVENUE-DECLINE-01, FIN-LOSS-TREND-01]\n"
            "- VAT cancelled on 2025-02-01, re-registered on 2025-09-15. D300 is 18% below e-Factura. "
            "[TAX-VAT-CANCELLED-01, TAX-EFACTURA-GAP-01]\n"
            "- Sole shareholder Calbrona Holding Fictiv SRL is ANAF inactive. [NET-PARTNER-INACTIVE-01]\n"
            "- Labour dispute pending (case 9103/99/2025). [LIT-MINOR-01]\n"
            "- **Unvalidated:** an article published on 2026-03-03 reports unpaid suppliers. [MED-NEGATIVE-01]\n\n"
            "## Coverage\n\nAll 8 agents completed. MOCK sources used: tax arrears list, D300, e-Factura, BPI, shareholders.\n"
        ),
        questions=[
            (
                "Please provide a current tax compliance certificate (certificat de atestare fiscală).",
                ["TAX-ARREARS-01"],
            ),
            (
                "What is your position in insolvency case 9101/99/2026, and is a payment schedule agreed with ANAF?",
                ["LIT-INSOLVENCY-REQUEST-01", "TAX-ARREARS-01"],
            ),
            (
                "Please explain the submitted 2025 profit of +300,000 RON versus the -2,600,000 RON loss filed with ANAF.",
                ["TAX-DECLARED-GAP-01"],
            ),
            ("Why was the VAT registration cancelled in February 2025?", ["TAX-VAT-CANCELLED-01"]),
            (
                "How will the 1,800,000 RON supplier claim be covered if the appeal is lost?",
                ["LIT-MATERIAL-CLAIM-01"],
            ),
        ],
        rejected=[],
    ),
}


def graph_for(cui: str) -> Graph:
    def company(c: str) -> GraphNode:
        f = COMPANIES_FACTS[c]
        status = (
            "inactive_anaf"
            if f.get("inactive_since")
            else {
                "functiune": "active",
                "faliment": "bankruptcy",
                "insolventa": "insolvency",
                "radiata": "deregistered",
            }[f["status"]]
        )
        return GraphNode(
            id=f"company:{c}", type=NodeType.COMPANY, label=f["name"], status=status, fictional=True
        )

    def person(name: str) -> GraphNode:
        return GraphNode(
            id=f"person:{name.lower().replace(' ', '-')}",
            type=NodeType.PERSON,
            label=name,
            fictional=True,
        )

    nodes = {cui: company(cui)}
    edges: list[GraphEdge] = []
    f = COMPANIES_FACTS[cui]
    for n, _a, b in f["admins"]:
        p = person(n)
        nodes[p.id] = p
        edges.append(
            GraphEdge(
                source=p.id,
                target=f"company:{cui}",
                role="administrator" if b is None else "former_administrator",
            )
        )
    for n, is_co, sc, _pct, _s in f.get("shareholders", []):
        if is_co and sc:
            nodes[sc] = company(sc)
            edges.append(
                GraphEdge(source=f"company:{sc}", target=f"company:{cui}", role="shareholder")
            )
        else:
            p = person(n)
            nodes[p.id] = p
            edges.append(GraphEdge(source=p.id, target=f"company:{cui}", role="shareholder"))
    if cui == "99000025":
        fict = person("IONEL FICTIVESCU").id
        for c in FICTIVESCU_COMPANIES:
            nodes[c] = company(c)
            edges.append(
                GraphEdge(
                    source=fict,
                    target=f"company:{c}",
                    role="former_administrator" if c == "99000058" else "administrator",
                )
            )
        for a, b in [("99000025", "99000082"), ("99000082", "99000041"), ("99000041", "99000025")]:
            edges.append(GraphEdge(source=f"company:{a}", target=f"company:{b}", role="invoices"))
    return Graph(nodes=list(nodes.values()), edges=edges)


def write_api(cui: str) -> None:
    d = cdir(cui) / "api"
    signals = signals_for(cui)
    trust, band, comps, cov, reasons = score(signals)
    sheet = identity_sheet(cui)
    sources = sheet.sources + [s.source for s in signals if s.source not in sheet.sources]
    worst = max(signals, key=lambda s: (SEVERITY_ORDER[s.severity], s.confidence), default=None)
    write_model(
        d / "list_item.json",
        CompanyListItem(
            cui=cui,
            name=sheet.current_name,
            band=band,
            score=trust,
            coverage=cov,
            last_checked=CHECKED_AT,
            top_signal=TopSignal(rule_id=worst.rule_id, claim=worst.claim, severity=worst.severity)
            if worst
            else None,
            fictional=True,
        ),
    )
    unique_sources = list({(s.name, s.raw_ref): s for s in sources}.values())
    write_model(
        d / "company.json",
        CompanyDetail(
            identity_sheet=sheet,
            score=trust,
            band=band,
            components=comps,
            coverage=cov,
            sources=unique_sources,
            last_checked=CHECKED_AT,
        ),
    )
    write_model(d / "signals.json", signals)
    memo = MEMOS[cui]
    write_model(
        d / "memo.json",
        MemoResponse(
            markdown=memo["md"].format(score=trust),
            questions=[
                ClientQuestion(
                    question=q,
                    reason_signal_ids=[s.signal_id for s in signals if s.rule_id in rules],
                )
                for q, rules in memo["questions"]
            ],
            generated_at=CHECKED_AT,
            verifier_report=VerifierReport(
                passed=not memo["rejected"],
                checked_sentences=memo["md"].count("\n- ") + 2,
                rejected=[RejectedSentence(text=t, reason=r) for t, r in memo["rejected"]],
                verified_at=CHECKED_AT,
            ),
        ),
    )
    write_model(d / "graph.json", graph_for(cui))
    events: list[AgentProgressEvent] = [
        AgentProgressEvent(run_id="fixture", agent="identity_sheet", elapsed_ms=900)
    ]
    for i, agent in enumerate(AGENT_ORDER):
        n = len([s for s in signals if s.agent == agent])
        events.append(
            AgentProgressEvent(
                run_id="fixture",
                agent=agent,
                status=AgentStatus.OK,
                n_signals=n,
                elapsed_ms=1500 + 900 * i,
            )
        )
    events += [
        AgentProgressEvent(run_id="fixture", agent=a, elapsed_ms=ms)
        for a, ms in [("scoring", 9100), ("memo", 15200), ("critic", 18400)]
    ]
    events.append(
        AgentProgressEvent(run_id="fixture", agent="pipeline", elapsed_ms=18500, done=True)
    )
    write_model(d / "run_events.json", events)
    _ = reasons


def write_dedeman() -> None:
    d = COMPANIES / "2816464_dedeman"
    (d / "api").mkdir(parents=True, exist_ok=True)
    (d / "README.md").write_text(
        "# DEDEMAN SRL (CUI 2816464): REAL company, clean case\n\n"
        "No figures are committed for this company. Its real data is downloaded onto our server by\n"
        '`apps/worker/sync.py:sync_company("2816464")` (local-first, docs/LOCAL_DATA.md). The raw\n'
        "responses are archived in the ObjectStore and the agents read that local mirror only, so the\n"
        "demo does not depend on ANAF being up. Sync it before the demo.\n\n"
        "`api/list_item.json` and `api/company.json` contain only public identity facts (name, CUI) and\n"
        "`band: null` (never checked), so the portfolio view can list it before the live run.\n",
        encoding="utf-8",
    )
    write_model(
        d / "api" / "list_item.json",
        CompanyListItem(
            cui="2816464",
            name="DEDEMAN SRL",
            band=None,
            score=None,
            coverage=None,
            last_checked=None,
            top_signal=None,
            fictional=False,
        ),
    )
    write_model(
        d / "api" / "company.json",
        CompanyDetail(
            identity_sheet=IdentitySheet(
                cui="2816464", fictional=False, current_name="DEDEMAN SRL", legal_form="SRL"
            ),
            score=None,
            band=None,
            components=[],
            coverage=None,
            sources=[],
            last_checked=None,
        ),
    )


def main() -> None:
    if COMPANIES.exists():
        shutil.rmtree(COMPANIES)
    if SOURCES.exists():
        shutil.rmtree(SOURCES)
    write_raw()
    write_sources()
    for cui in ("99000017", "99000025", "99000033"):
        write_api(cui)
    write_dedeman()
    print(f"fixtures written to {FIX}")


if __name__ == "__main__":
    main()
