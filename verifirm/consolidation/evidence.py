"""The JSON view of a ConsolidatedReport that the memo and the critic see.

One shared function, so the memo can only say what the critic can check. Internals the LLM has
no use for (content hashes, raw archive keys) are left out.
"""

from __future__ import annotations

from typing import Any

from verifirm.schema.memo import ConsolidatedReport
from verifirm.schema.signals import Signal


def signal_view(signal: Signal) -> dict[str, Any]:
    return {
        "signal_id": signal.signal_id,
        "rule_id": signal.rule_id,
        "component": signal.component.value,
        "claim": signal.claim,
        "severity": signal.severity.value,
        "validated": signal.validated,
        "auto_stop_candidate": signal.auto_stop_candidate,
        "evidence_date": signal.evidence_date.isoformat() if signal.evidence_date else None,
        "confidence": signal.confidence,
        "ambiguous_entity_match": signal.entity_match.ambiguous,
        "source": {"name": signal.source.name, "type": signal.source.type.value},
        "data": signal.data,
    }


def score_view(report: ConsolidatedReport) -> dict[str, Any]:
    s = report.score
    return {
        "trust_score": s.trust_score,
        "band": s.band.value,
        "band_reasons": s.band_reasons,
        "coverage": {
            "label": s.coverage.label,
            "weight_pct": s.coverage.weight_pct,
            "available": s.coverage.available,
            "total": s.coverage.total,
            "missing": [c.value for c in s.coverage.missing],
        },
        "components": [
            {
                "component": c.component.value,
                "status": c.status.value,
                "score": c.score,
                "signal_ids": c.signal_ids,
            }
            for c in s.components
        ],
        "auto_stop_signal_ids": s.auto_stop_signal_ids,
        "natural_person_flow": s.natural_person_flow,
    }


def identity_view(report: ConsolidatedReport) -> dict[str, Any]:
    i = report.identity
    return {
        "cui": i.cui,
        "fictional": i.fictional,
        "current_name": i.current_name,
        "legal_form": i.legal_form,
        "status": i.status.value,
        "trade_register_no": i.trade_register_no,
        "registration_date": i.registration_date.isoformat() if i.registration_date else None,
        "registered_office": i.registered_office.raw if i.registered_office else None,
        "caen_code": i.caen_code,
        "administrators": [
            {
                "name": p.name,
                "valid_from": p.valid_from.isoformat() if p.valid_from else None,
                "valid_to": p.valid_to.isoformat() if p.valid_to else None,
            }
            for p in i.administrators
        ],
        "shareholders": [
            {"name": p.name, "share_pct": p.share_pct, "source_type": p.source.type.value}
            for p in i.shareholders
        ],
    }


def results_view(report: ConsolidatedReport) -> list[dict[str, Any]]:
    """Per-agent status: what the memo's coverage section is written from."""
    return [
        {
            "agent": r.agent,
            "status": r.status.value,
            "sources_checked": r.sources_checked,
            "sources_failed": r.sources_failed,
            "n_signals": len(r.signals),
            "notes": r.notes,
        }
        for r in report.results
    ]


def report_view(report: ConsolidatedReport) -> dict[str, Any]:
    mock_sources = sorted({s.source.name for s in report.signals if s.source.type.value == "mock"})
    mock_sources += [
        p.source.name for p in report.identity.shareholders if p.source.type.value == "mock"
    ]
    return {
        "cui": report.cui,
        "identity": identity_view(report),
        "score": score_view(report),
        "agents": results_view(report),
        "mock_sources_used": sorted(set(mock_sources)),
        "signals": [signal_view(s) for s in report.signals],
    }
