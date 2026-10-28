"""The API serves schema-valid fixture data from day one (contract-first)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from verifirm.core.config import get_settings
from verifirm.schema.api import (
    CompanyDetail,
    CompanyList,
    DecisionRecord,
    Graph,
    MemoResponse,
    RunCreated,
)
from verifirm.schema.runs import AgentProgressEvent
from verifirm.schema.signals import Signal


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("FIXTURE_MODE", "1")
    monkeypatch.setenv("FIXTURE_SSE_DELAY_S", "0")
    monkeypatch.setenv("REPOSITORY_BACKEND", "memory")
    monkeypatch.setenv("QUEUE_BACKEND", "memory")
    get_settings.cache_clear()
    from apps.api.main import create_app

    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def test_health(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["fixture_mode"] is True


def test_portfolio(client: TestClient) -> None:
    page = CompanyList.model_validate(client.get("/companies").json())
    assert {i.cui for i in page.items} == {"2816464", "99000017", "99000025", "99000033"}
    red = CompanyList.model_validate(client.get("/companies", params={"band": "red"}).json())
    assert {i.cui for i in red.items} == {"99000025", "99000033"}


@pytest.mark.parametrize("cui", ["99000017", "99000025", "99000033"])
def test_company_views(client: TestClient, cui: str) -> None:
    CompanyDetail.model_validate(client.get(f"/companies/{cui}").json())
    [Signal.model_validate(s) for s in client.get(f"/companies/{cui}/signals").json()]
    MemoResponse.model_validate(client.get(f"/companies/{cui}/memo").json())
    Graph.model_validate(client.get(f"/companies/{cui}/graph", params={"depth": 2}).json())


def test_invalid_cui_is_rejected(client: TestClient) -> None:
    assert client.get("/companies/12345678").status_code == 422


def test_application_and_sse_progress(client: TestClient) -> None:
    resp = client.post(
        "/applications",
        data={"cui": "99000025"},
        files=[("files", ("bilant.pdf", b"%PDF-1.4 fictional", "application/pdf"))],
    )
    assert resp.status_code == 202
    run_id = RunCreated.model_validate(resp.json()).run_id
    events = []
    with client.stream("GET", f"/runs/{run_id}/events") as stream:
        for line in stream.iter_lines():
            if line.startswith("data: "):
                events.append(AgentProgressEvent.model_validate(json.loads(line[6:])))
    assert events[-1].done and {e.agent for e in events} >= {"identity", "network", "media"}


def test_decision_is_recorded(client: TestClient) -> None:
    resp = client.post(
        "/companies/99000033/decision",
        json={
            "decision": "escalate",
            "comment": "Wait for case 9101/99/2026",
            "analyst": "demo-analyst",
        },
    )
    assert resp.status_code == 201
    assert DecisionRecord.model_validate(resp.json()).decision.value == "escalate"
