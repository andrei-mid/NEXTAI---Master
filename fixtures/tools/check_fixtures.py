"""`make fixtures-check`: the fictional-data rules, enforced. Exit code 1 on any violation.

1. No fictional CUI passes the real checksum (core.cui.FICTIONAL_CUIS + every 990xxxxx CUI in fixtures/).
2. Every fixtures/companies/990* folder is a whitelisted fictional CUI.
3. Every raw fictional record carries "fictional": true (XML/CSV: a `fictional: true` marker).
4. Every web URL in fixtures uses the reserved .example domain (official source endpoints excepted).
5. Trade-register numbers in fixtures use county code J99 only.
6. Every api/*.json file validates against the schema models.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from pydantic import TypeAdapter

from verifirm.core.cui import FICTIONAL_CUIS, has_valid_checksum
from verifirm.schema.api import CompanyDetail, CompanyListItem, Graph, MemoResponse
from verifirm.schema.runs import AgentProgressEvent
from verifirm.schema.signals import Signal

FIX = Path(__file__).resolve().parents[1]
OFFICIAL_HOSTS = (
    "webservicesp.anaf.ro",
    "portalquery.just.ro",
    "api.scj.ro",
    "webgate.ec.europa.eu",
    "scsanctions.un.org",
    "sanctionslistservice.ofac.treas.gov",
    "data.gov.ro",
    "kohesio.ec.europa.eu",
    "api.tavily.com",
    "schemas.xmlsoap.org",
    "www.w3.org",
)  # the last two are XML namespace URIs, not links
API_MODELS = {
    "list_item.json": TypeAdapter(CompanyListItem),
    "company.json": TypeAdapter(CompanyDetail),
    "signals.json": TypeAdapter(list[Signal]),
    "memo.json": TypeAdapter(MemoResponse),
    "graph.json": TypeAdapter(Graph),
    "run_events.json": TypeAdapter(list[AgentProgressEvent]),
}
CUI_RE = re.compile(r"(?<!\d)(99\d{6})(?!\d)")
URL_RE = re.compile(r"https?://([^/\"'\s<>]+)")
REG_RE = re.compile(r"\bJ(\d{2})/\d+/\d{4}\b")


def check() -> list[str]:
    errors: list[str] = []
    for cui in sorted(FICTIONAL_CUIS):
        if has_valid_checksum(cui):
            errors.append(f"fictional CUI {cui} passes the real checksum")

    for folder in sorted((FIX / "companies").iterdir()):
        cui = folder.name.split("_", 1)[0]
        if cui.startswith("990") and cui not in FICTIONAL_CUIS:
            errors.append(f"{folder.name}: CUI {cui} is not in core.cui.FICTIONAL_CUIS")

    for path in sorted(
        p for p in FIX.rglob("*") if p.is_file() and p.suffix in {".json", ".xml", ".csv"}
    ):
        rel = path.relative_to(FIX).as_posix()
        text = path.read_text(encoding="utf-8")
        for cui in set(CUI_RE.findall(text)):
            if has_valid_checksum(cui):
                errors.append(f"{rel}: CUI {cui} passes the real checksum")
        for host in set(URL_RE.findall(text)):
            if not host.endswith(".example") and host not in OFFICIAL_HOSTS:
                errors.append(
                    f"{rel}: URL host {host} is neither .example nor an official source endpoint"
                )
        for county in set(REG_RE.findall(text)):
            if county != "99":
                errors.append(
                    f"{rel}: trade-register number with county J{county} (fictional data must use J99)"
                )

        is_fictional_company = rel.startswith("companies/990")
        is_raw = "/api/" not in rel and rel != "sources/caen_rev2_rev3.csv"
        if (is_fictional_company or rel.startswith("sources/")) and is_raw:
            if path.suffix == ".json":
                data = json.loads(text)
                if not (isinstance(data, dict) and data.get("fictional") is True):
                    errors.append(f'{rel}: missing top-level "fictional": true')
            elif "fictional" not in text.lower():
                errors.append(f"{rel}: missing a fictional marker")

        if "/api/" in rel and path.name in API_MODELS:
            try:
                API_MODELS[path.name].validate_json(text)
            except Exception as exc:
                errors.append(f"{rel}: does not match the schema: {exc}")
    return errors


def main() -> int:
    errors = check()
    for e in errors:
        print(f"FAIL {e}")
    print("fixtures-check: OK" if not errors else f"fixtures-check: {len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
