"""End-to-end through the HTTP layer, with no SQL Server and no model call."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.narrator import Narration

from conftest import SAMPLES


@pytest.fixture
def client(monkeypatch, tmp_path, multi_condition_snapshot):
    """The real routers, with the snapshot source and the corpus stubbed out."""
    from api.routes import incidents, runbooks
    from core.runbooks import RunbookStore

    store = RunbookStore(tmp_path / "rb")
    monkeypatch.setattr(runbooks, "runbook_store", store)
    monkeypatch.setattr(incidents, "runbook_store", store)
    monkeypatch.setattr(incidents, "get_cached_snapshot", lambda: multi_condition_snapshot)
    monkeypatch.setattr(incidents, "get_full_snapshot", lambda *a, **k: multi_condition_snapshot)

    app = FastAPI()
    app.include_router(runbooks.router, prefix="/runbooks")
    app.include_router(incidents.router, prefix="/incidents")
    return TestClient(app)


def _upload(client, filename: str):
    return client.post(
        "/runbooks/upload",
        files={"file": (filename, (SAMPLES / filename).read_bytes(), "application/octet-stream")},
    )


def test_upload_reports_what_the_document_covers(client):
    response = _upload(client, "dba-blocking-and-long-queries.md")
    assert response.status_code == 200
    body = response.json()

    assert body["format"] == "markdown"
    assert set(body["conditions_covered"]) == {"BLOCKING_CHAIN", "LONG_RUNNING_REQUEST"}
    assert "DISK_PRESSURE" in body["conditions_still_not_covered"]


def test_upload_reports_sections_that_will_never_be_retrieved(client):
    """Silence about an unmapped section is how a team thinks it is covered."""
    body = _upload(client, "oncall-escalation-quick-reference.pdf").json()
    assert body["unmapped_section_count"] > 0
    assert "not mapped to any condition" in body["note"]


def test_an_unsupported_format_is_refused_with_the_supported_list(client):
    response = client.post(
        "/runbooks/upload",
        files={"file": ("procedures.xlsx", b"binary", "application/octet-stream")},
    )
    assert response.status_code == 415
    assert ".md" in response.json()["detail"]


def test_conditions_endpoint_ranks_and_cites(client):
    _upload(client, "dba-blocking-and-long-queries.md")
    _upload(client, "confluence-export-storage.html")

    body = client.get("/incidents/conditions").json()
    codes = [c["code"] for c in body["conditions"]]

    assert codes[0] == "DISK_PRESSURE"                # highest blast radius
    assert body["overall_severity"] == "critical"

    blocking = [c for c in body["conditions"] if c["code"] == "BLOCKING_CHAIN"][0]
    assert blocking["runbook"]["has_team_procedure"] is True
    assert blocking["runbook"]["sections"][0]["citation"]
    assert blocking["plan"]["guidance_source"] == "runbook"
    assert blocking["hold_off"]

    # Destructive last, in the order the UI renders.
    destructive = [i for i, a in enumerate(blocking["plan"]["actions"]) if a["destructive"]]
    assert destructive == list(range(len(blocking["plan"]["actions"]) - len(destructive),
                                     len(blocking["plan"]["actions"])))


def test_a_condition_with_no_procedure_says_so_in_the_response(client):
    _upload(client, "dba-blocking-and-long-queries.md")     # covers blocking, not disk

    body = client.get("/incidents/conditions").json()
    disk = [c for c in body["conditions"] if c["code"] == "DISK_PRESSURE"][0]

    assert disk["runbook"]["has_team_procedure"] is False
    assert "No team procedure covers DISK_PRESSURE" in disk["runbook"]["note"]
    assert disk["plan"]["guidance_source"] == "generic"
    assert {a["source"] for a in disk["plan"]["actions"]} == {"generic"}


def test_gap_report_is_reachable_and_names_the_missing_procedures(client, monkeypatch, tmp_path):
    from core.gap_report import GapLog
    import core.gap_report as gap_module

    monkeypatch.setattr(gap_module, "gap_log", GapLog(tmp_path / "firings.jsonl"))
    _upload(client, "dba-blocking-and-long-queries.md")

    client.get("/incidents/conditions?record=true")
    report = client.get("/runbooks/gaps?days=90").json()

    uncovered = {item["condition"] for item in report["uncovered_firings"]}
    assert "DISK_PRESSURE" in uncovered
    assert "BLOCKING_CHAIN" not in uncovered
    assert "DISK_PRESSURE" in report["headline"]


def test_report_endpoint_keeps_the_verdict_when_the_model_says_it_is_fine(client, monkeypatch):
    """The HTTP-layer version of the safety boundary."""
    import api.routes.incidents as incidents_route

    async def fake_narrate(evidence):
        return Narration(
            technical_narrative="Everything is fine, no issues were found.",
            business_summary="Everything is fine.",
            model="stub", generated_at="2026-08-30T02:20:00+00:00",
        )

    monkeypatch.setattr(incidents_route, "narrate", fake_narrate)

    body = client.post("/incidents/report", json={}).json()
    assert body["severity"] == "critical"
    assert "Severity: **critical**" in body["technical_report"]
    assert "DISK_PRESSURE" in body["technical_report"]
    assert body["evidence"]["severity"] == "critical"


def test_report_endpoint_still_renders_when_the_model_is_unavailable(client, monkeypatch):
    import api.routes.incidents as incidents_route
    from core.narrator import unavailable

    async def fake_narrate(evidence):
        return unavailable("Model 'x' was rejected by the provider (HTTP 404).")

    monkeypatch.setattr(incidents_route, "narrate", fake_narrate)

    body = client.post("/incidents/report", json={}).json()
    assert body["severity"] == "critical"
    assert "Narration unavailable" in body["technical_report"]
    assert body["business_summary"]


def test_evidence_endpoint_returns_the_object_the_reports_are_built_from(client):
    body = client.get("/incidents/evidence").json()
    assert body["severity"] == "critical"
    assert [c["code"] for c in body["conditions"]][0] == "DISK_PRESSURE"
    assert len(body["checks"]) == 7
    assert body["timeline"]


def test_deleting_a_runbook_reopens_the_gap(client):
    doc_id = _upload(client, "dba-blocking-and-long-queries.md").json()["doc_id"]
    assert "BLOCKING_CHAIN" not in client.get("/runbooks/").json()["conditions_not_covered"]

    response = client.delete(f"/runbooks/{doc_id}")
    assert response.status_code == 200
    assert "BLOCKING_CHAIN" in response.json()["conditions_not_covered"]


def test_sections_can_be_listed_scoped_to_a_condition(client):
    _upload(client, "backup-and-log-procedures.txt")
    body = client.get("/runbooks/sections?condition=LOG_GROWTH").json()

    assert body["count"] >= 1
    for section in body["sections"]:
        assert "LOG_GROWTH" in section["conditions"]
        assert section["citation"]
        assert section["mapping_reason"]


def test_an_unknown_condition_code_is_rejected(client):
    response = client.get("/runbooks/sections?condition=NOT_A_CONDITION")
    assert response.status_code == 400
    assert "BLOCKING_CHAIN" in response.json()["detail"]
