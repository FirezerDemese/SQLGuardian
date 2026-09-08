"""
SQLGuardian - /incidents routes

The response path: what fired, what your runbook says about it, what to do in
what order, and the write-up afterwards.

Every verdict on these endpoints is computed in core/conditions.py before any
model is called. /incidents/report calls the narration layer; if it is
unavailable the reports still render, with the deterministic summary in place
of the prose and the failure stated on the page.
"""

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from core.actions import build_action_plan
from core.conditions import condition_to_dict, detect_conditions, failed_checks
from core.gap_report import record_firings
from core.incident import evidence_from_snapshot
from core.monitor import get_full_snapshot
from core.narrator import narrate
from core.reports import render_both
from core.runbooks import runbook_store
from core.scheduler import get_cached_snapshot

router = APIRouter()


def _snapshot(fresh: bool, instance: Optional[str] = None) -> dict:
    if fresh or instance:
        return get_full_snapshot(instance)
    cached = get_cached_snapshot()
    return cached or get_full_snapshot()


@router.get("/conditions")
def conditions(
    instance: Optional[str] = Query(None),
    fresh: bool = Query(False),
    record: bool = Query(False, description="Record these firings in the runbook gap log"),
):
    """Current conditions, ranked by blast radius, with the team procedure for each.

    For every condition: the deterministic evidence, what the runbooks say (with
    citations), the ordered actions, and what not to do yet.
    """
    snapshot = _snapshot(fresh, instance)
    found = detect_conditions(snapshot)

    if record and found:
        # Pass the store this route reads from, so coverage is recorded against
        # the corpus that actually answered the condition.
        record_firings(
            found, instance=snapshot.get("instance", "primary"), store=runbook_store
        )

    payload = []
    for condition in found:
        retrieved = runbook_store.retrieve(condition)
        payload.append({
            **condition_to_dict(condition),
            "runbook": {
                "has_team_procedure": bool(retrieved),
                "sections": [item.to_dict() for item in retrieved],
                "note": (
                    None if retrieved else
                    f"No team procedure covers {condition.code.value}. The actions below "
                    f"are SQLGuardian's generic baseline, not your team's documented "
                    f"process. This gap is recorded in the runbook gap report."
                ),
            },
            "plan": build_action_plan(condition, retrieved),
        })

    return {
        "instance": snapshot.get("instance", "primary"),
        "snapshot_time": snapshot.get("snapshot_time"),
        "overall_severity": snapshot.get("overall_severity"),
        "condition_count": len(found),
        "failed_checks": list(failed_checks(snapshot)),
        "conditions": payload,
    }


class ReportRequest(BaseModel):
    instance: Optional[str] = None
    fresh: bool = False


@router.post("/report")
async def draft_report(req: ReportRequest = ReportRequest()):
    """Draft both incident documents from one evidence object.

    Technical write-up and business summary render from the same
    IncidentEvidence, so they cannot disagree. The model narrates only; numbers
    in the narration are verified against the evidence and violations are
    reported on the response.
    """
    snapshot = _snapshot(req.fresh, req.instance)
    found = detect_conditions(snapshot)

    # Whatever team procedure was retrieved during the incident is cited in the
    # write-up, so the report says which document was followed.
    citations = [
        item.section.citation
        for condition in found
        for item in runbook_store.retrieve(condition)
    ]

    evidence = evidence_from_snapshot(
        snapshot,
        found,
        instance=snapshot.get("instance", "primary"),
        citations=citations,
    )
    narration = await narrate(evidence)
    return render_both(evidence, narration)


@router.get("/evidence")
def evidence(instance: Optional[str] = Query(None), fresh: bool = Query(False)):
    """The raw evidence object, with no narration. What the reports are built from."""
    snapshot = _snapshot(fresh, instance)
    found = detect_conditions(snapshot)
    return evidence_from_snapshot(
        snapshot, found, instance=snapshot.get("instance", "primary")
    ).to_dict()
