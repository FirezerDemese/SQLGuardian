"""
SQLGuardian - Incident report rendering

Two documents from one evidence object. An engineer needs the session id and
the blocking statement; a director needs one paragraph. Same source, so they
cannot disagree about what happened.

Every fact in either document is read from IncidentEvidence. The narration is
inserted as clearly delimited prose and is never the source of a verdict, a
number, or an ordering. If narration is unavailable or fails verification, both
documents still render - with the deterministic summary in its place and the
failure stated on the page rather than hidden.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from core.incident import IncidentEvidence
from core.narrator import Narration, business_summary_leaks


def _clock(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M:%S UTC")
    except ValueError:
        return iso


def _duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "still open"
    if seconds < 90:
        return f"{seconds:.0f}s"
    return f"{seconds / 60:.1f} min"


def deterministic_technical_summary(evidence: IncidentEvidence) -> str:
    """The write-up with no model involved. Always correct, never eloquent."""
    if not evidence.conditions:
        return "No conditions fired. All checks returned within threshold."
    lines = []
    for condition in evidence.conditions:
        lines.append(f"{condition.code.value} ({condition.severity}): {condition.detail}")
    return " ".join(lines)


def deterministic_business_summary(evidence: IncidentEvidence) -> str:
    """The one-paragraph version with no model involved and no identifiers."""
    if not evidence.conditions:
        return (
            f"No issues were detected on {evidence.instance} during this check. "
            f"All monitored areas were within their agreed thresholds."
        )
    worst = evidence.conditions[0]
    impact = {
        "BLOCKING_CHAIN": "some requests were queued behind another piece of work and were slow to complete",
        "AGENT_JOB_FAILURE": "a scheduled overnight task did not complete",
        "BACKUP_AGE_EXCEEDED": "at least one database was outside its agreed backup window, which affects how far back we could recover",
        "LOG_GROWTH": "a database was approaching the limit of its transaction log, which would eventually stop it accepting changes",
        "DISK_PRESSURE": "a storage volume was close to full, which would eventually stop the database accepting changes",
        "WAIT_SPIKE": "the database spent an unusual share of its time waiting on a resource, which shows up as slower responses",
        "LONG_RUNNING_REQUEST": "at least one request ran far longer than expected, which shows up as a slow screen or report",
    }.get(worst.code.value, "a monitored condition was outside its threshold")

    state = (
        f"The issue was resolved after {_duration(evidence.duration_seconds)}."
        if evidence.closed_at else "The issue was still open at the time of writing."
    )
    return (
        f"On {evidence.instance}, {impact}. This was assessed as {evidence.severity}. "
        f"{state}"
    )


def render_technical_report(
    evidence: IncidentEvidence,
    narration: Optional[Narration] = None,
) -> str:
    """Full write-up for an engineer: timeline, values, actions, citations."""
    out: list[str] = []
    add = out.append

    add(f"# Incident {evidence.incident_id} - {evidence.instance}")
    add("")
    add(f"- Severity: **{evidence.severity}** (computed from checks, not narrated)")
    add(f"- Opened: {_clock(evidence.opened_at)}")
    add(f"- Closed: {_clock(evidence.closed_at) if evidence.closed_at else 'still open'}")
    add(f"- Duration: {_duration(evidence.duration_seconds)}")
    add("")

    add("## Summary")
    add("")
    if narration and narration.available and narration.technical_narrative:
        add(narration.technical_narrative)
        if not narration.verified:
            add("")
            add(
                "> Narration verification failed. "
                + (f"Numbers the evidence does not support as written: "
                   f"{', '.join(narration.unsupported_numbers)}. "
                   if narration.unsupported_numbers else "")
                + (f"Identifiers leaked into the business summary: "
                   f"{', '.join(narration.business_leaks)}. "
                   if narration.business_leaks else "")
                + "Treat the summary above as unverified; the findings below are unaffected."
            )
    else:
        add(deterministic_technical_summary(evidence))
        if narration and not narration.available:
            add("")
            add(f"> Narration unavailable ({narration.unavailable_reason}). "
                f"The summary above is generated deterministically from the evidence.")
    add("")

    add("## What fired")
    add("")
    if not evidence.conditions:
        add("No conditions fired.")
    for condition in evidence.conditions:
        add(f"### {condition.code.value} - {condition.title}")
        add("")
        add(f"- Severity: {condition.severity}")
        add(f"- Blast radius score: {condition.impact_score}")
        add(f"- Scope: {condition.scope}")
        add(f"- Detected: {_clock(condition.detected_at)}")
        add("")
        add("Evidence:")
        add("")
        for line in condition.evidence:
            add(f"- {line}")
        if condition.hold_off:
            add("")
            add("Not yet:")
            add("")
            for line in condition.hold_off:
                add(f"- {line}")
        add("")

    add("## What was checked")
    add("")
    add("| Check | Verdict | Observed |")
    add("|---|---|---|")
    for observation in evidence.checks:
        observed = ", ".join(
            f"{key}={value}" for key, value in observation.observed.items() if value is not None
        ) or "-"
        add(f"| {observation.check} | {observation.verdict} | {observed} |")
    add("")

    add("## Timeline")
    add("")
    add("| Time | Phase | Actor | What happened |")
    add("|---|---|---|---|")
    for entry in evidence.timeline:
        add(f"| {_clock(entry.at)} | {entry.phase.value} | {entry.actor} | {entry.description} |")
    add("")
    durations = evidence.phase_durations()
    if durations:
        add("Time in each phase: "
            + ", ".join(f"{phase} {_duration(seconds)}" for phase, seconds in durations.items())
            + ".")
        add("")

    add("## Actions taken")
    add("")
    if not evidence.actions:
        add("No actions were recorded against this incident.")
    for action in evidence.actions:
        label = "team runbook" if action.source == "runbook" else "generic guidance"
        add(f"- **{action.action}** ({label}, {action.by}, {_clock(action.at)}): {action.outcome}"
            + (f"  \n  Source: {action.citation}" if action.citation else "")
            + ("  \n  This is what resolved the condition." if action.resolved_condition else ""))
    add("")

    if evidence.resolution:
        add("## Resolution")
        add("")
        add(evidence.resolution)
        add("")

    add("## Sources")
    add("")
    if evidence.citations:
        for citation in evidence.citations:
            add(f"- {citation}")
    else:
        add("No team runbook was cited for this incident. Guidance shown during the "
            "incident was SQLGuardian's generic baseline.")
    add("")
    return "\n".join(out)


def render_business_report(
    evidence: IncidentEvidence,
    narration: Optional[Narration] = None,
) -> str:
    """One paragraph for a director. No session ids, by construction.

    If the generated paragraph contains a technical identifier, it is not used:
    the deterministic summary is rendered instead. The rule is enforced here,
    not requested in a prompt.
    """
    paragraph = deterministic_business_summary(evidence)
    used_narration = False

    if narration and narration.available and narration.business_summary:
        candidate = narration.business_summary
        if not business_summary_leaks(candidate) and not narration.unsupported_numbers:
            paragraph = candidate
            used_narration = True

    out = [
        f"# {evidence.instance} - incident summary",
        "",
        f"Reference: {evidence.incident_id}  ",
        f"Date: {_clock(evidence.opened_at)}  ",
        f"Status: {'resolved' if evidence.closed_at else 'open'}  ",
        f"Assessed severity: {evidence.severity}",
        "",
        paragraph,
        "",
    ]
    if not used_narration and narration:
        # Say which one the reader is holding. A director cannot tell a drafted
        # paragraph from a generated one by looking, and silence about the
        # difference is the same failure this tool exists to fix.
        out.append(
            "> This summary was generated deterministically from the incident record "
            + ("because the drafted version did not pass verification."
               if narration.available else
               "because the narration model was unavailable.")
        )
        out.append("")
    return "\n".join(out)


def render_both(evidence: IncidentEvidence, narration: Optional[Narration] = None) -> dict:
    """Both documents plus the evidence they were rendered from."""
    return {
        "incident_id": evidence.incident_id,
        "instance": evidence.instance,
        "severity": evidence.severity,
        "technical_report": render_technical_report(evidence, narration),
        "business_summary": render_business_report(evidence, narration),
        "narration": narration.to_dict() if narration else None,
        "evidence": evidence.to_dict(),
    }
