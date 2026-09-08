"""
SQLGuardian - Incident evidence

The documentation is the part nobody has time for, so it does not happen, so
the same incident gets debugged from scratch six months later. This module
collects what actually happened while it is happening, as structured data.

One evidence object, two documents (core/reports.py): a technical write-up with
session ids and values, and a paragraph in business language with none. Both
render from the same source, so they cannot disagree.

Everything here is frozen. The builder is mutable while an incident is open;
`build()` returns an immutable IncidentEvidence, and that is the only type the
narration layer accepts.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence

from core.conditions import Condition


class Phase(str, Enum):
    """Incident phases, in order. Used to report where the time actually went."""

    DETECT = "detect"        # condition fired
    DIAGNOSE = "diagnose"    # checks run, evidence gathered
    ACT = "act"              # actions taken
    RESOLVE = "resolve"      # condition cleared


PHASE_ORDER: tuple[Phase, ...] = (Phase.DETECT, Phase.DIAGNOSE, Phase.ACT, Phase.RESOLVE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TimelineEntry:
    at: str
    phase: Phase
    actor: str               # "sqlguardian" or a person / team
    description: str
    values: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def to_dict(self) -> dict:
        return {
            "at": self.at,
            "phase": self.phase.value,
            "actor": self.actor,
            "description": self.description,
            "values": dict(self.values),
        }


@dataclass(frozen=True)
class CheckObservation:
    """A check that was run during the incident and the value it returned.

    "what was checked and the values seen" - including checks that came back
    clean, because ruling something out is part of the write-up.
    """

    check: str
    verdict: str             # "healthy" | "warning" | "critical" | "failed"
    observed: Mapping[str, Any]
    at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "check": self.check,
            "verdict": self.verdict,
            "observed": dict(self.observed),
            "at": self.at,
        }


@dataclass(frozen=True)
class ActionTaken:
    action: str
    at: str
    by: str
    source: str              # "runbook" | "generic"
    citation: Optional[str]
    outcome: str
    resolved_condition: bool = False

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "at": self.at,
            "by": self.by,
            "source": self.source,
            "citation": self.citation,
            "outcome": self.outcome,
            "resolved_condition": self.resolved_condition,
        }


@dataclass(frozen=True)
class IncidentEvidence:
    """Immutable record of one incident. The only input the narrator accepts.

    Frozen with tuple fields throughout: the narration layer is handed this
    object and cannot alter a verdict, add a condition, or change a number.
    Attempting to is a runtime error and a mypy error - see
    tests/test_narration_boundary.py.
    """

    incident_id: str
    instance: str
    opened_at: str
    conditions: tuple[Condition, ...]
    timeline: tuple[TimelineEntry, ...]
    checks: tuple[CheckObservation, ...]
    actions: tuple[ActionTaken, ...]
    citations: tuple[str, ...]
    closed_at: Optional[str] = None
    resolution: Optional[str] = None

    # -- derived, all deterministic ---------------------------------------

    @property
    def severity(self) -> str:
        """The incident verdict. Computed from conditions, never narrated."""
        if any(c.severity == "critical" for c in self.conditions):
            return "critical"
        if any(c.severity == "warning" for c in self.conditions):
            return "warning"
        return "healthy"

    @property
    def primary_condition(self) -> Optional[Condition]:
        return self.conditions[0] if self.conditions else None

    @property
    def duration_seconds(self) -> Optional[float]:
        if not self.closed_at:
            return None
        return (
            datetime.fromisoformat(self.closed_at) - datetime.fromisoformat(self.opened_at)
        ).total_seconds()

    def phase_durations(self) -> Mapping[str, float]:
        """Seconds spent in each phase, from the timeline. How long each phase took."""
        marks: list[tuple[Phase, datetime]] = [
            (entry.phase, datetime.fromisoformat(entry.at)) for entry in self.timeline
        ]
        if not marks:
            return MappingProxyType({})
        end = (
            datetime.fromisoformat(self.closed_at) if self.closed_at
            else max(when for _, when in marks)
        )
        durations: dict[str, float] = {}
        for index, (phase, when) in enumerate(marks):
            next_when = marks[index + 1][1] if index + 1 < len(marks) else end
            durations[phase.value] = round(
                durations.get(phase.value, 0.0) + (next_when - when).total_seconds(), 1
            )
        return MappingProxyType(durations)

    def numeric_facts(self) -> Mapping[str, float]:
        """Every number this incident is allowed to state.

        The narration verifier checks generated prose against this set. If a
        report should be able to mention a number, it has to be here first.
        """
        out: dict[str, float] = {}
        for condition in self.conditions:
            for key, value in condition.numeric_facts().items():
                out[f"{condition.code.value}.{key}"] = value
        out["condition_count"] = float(len(self.conditions))
        out["action_count"] = float(len(self.actions))
        out["check_count"] = float(len(self.checks))
        for phase, seconds in self.phase_durations().items():
            out[f"phase_seconds.{phase}"] = float(seconds)
        if self.duration_seconds is not None:
            out["incident_duration_seconds"] = float(self.duration_seconds)
        for observation in self.checks:
            for key, value in observation.observed.items():
                if isinstance(value, bool):
                    continue
                if isinstance(value, (int, float)):
                    out[f"{observation.check}.{key}"] = float(value)
        return MappingProxyType(out)

    def to_dict(self) -> dict:
        from core.conditions import condition_to_dict

        return {
            "incident_id": self.incident_id,
            "instance": self.instance,
            "opened_at": self.opened_at,
            "closed_at": self.closed_at,
            "severity": self.severity,
            "duration_seconds": self.duration_seconds,
            "phase_durations": dict(self.phase_durations()),
            "conditions": [condition_to_dict(c) for c in self.conditions],
            "timeline": [entry.to_dict() for entry in self.timeline],
            "checks": [observation.to_dict() for observation in self.checks],
            "actions": [action.to_dict() for action in self.actions],
            "citations": list(self.citations),
            "resolution": self.resolution,
        }


class IncidentBuilder:
    """Collects evidence while an incident is open. Produces a frozen object."""

    def __init__(self, instance: str = "primary", incident_id: Optional[str] = None) -> None:
        self.incident_id = incident_id or f"INC-{uuid.uuid4().hex[:8].upper()}"
        self.instance = instance
        self.opened_at = _now()
        self._conditions: list[Condition] = []
        self._timeline: list[TimelineEntry] = []
        self._checks: list[CheckObservation] = []
        self._actions: list[ActionTaken] = []
        self._citations: list[str] = []
        self._closed_at: Optional[str] = None
        self._resolution: Optional[str] = None

    def condition_fired(self, condition: Condition, at: Optional[str] = None) -> "IncidentBuilder":
        self._conditions.append(condition)
        self._timeline.append(TimelineEntry(
            at=at or condition.detected_at,
            phase=Phase.DETECT,
            actor="sqlguardian",
            description=f"{condition.code.value} fired ({condition.severity}): {condition.title}",
            values=condition.facts,
        ))
        return self

    def checked(
        self,
        check: str,
        verdict: str,
        observed: Mapping[str, Any],
        at: Optional[str] = None,
        description: Optional[str] = None,
    ) -> "IncidentBuilder":
        stamp = at or _now()
        self._checks.append(CheckObservation(
            check=check, verdict=verdict, observed=MappingProxyType(dict(observed)), at=stamp
        ))
        self._timeline.append(TimelineEntry(
            at=stamp,
            phase=Phase.DIAGNOSE,
            actor="sqlguardian",
            description=description or f"Checked {check}: {verdict}",
            values=MappingProxyType(dict(observed)),
        ))
        return self

    def acted(
        self,
        action: str,
        by: str,
        outcome: str,
        source: str = "generic",
        citation: Optional[str] = None,
        resolved_condition: bool = False,
        at: Optional[str] = None,
    ) -> "IncidentBuilder":
        stamp = at or _now()
        self._actions.append(ActionTaken(
            action=action, at=stamp, by=by, source=source, citation=citation,
            outcome=outcome, resolved_condition=resolved_condition,
        ))
        if citation and citation not in self._citations:
            self._citations.append(citation)
        self._timeline.append(TimelineEntry(
            at=stamp,
            phase=Phase.ACT,
            actor=by,
            description=f"{action} - {outcome}",
            values=MappingProxyType({"source": source, "citation": citation}),
        ))
        return self

    def cite(self, citation: str) -> "IncidentBuilder":
        if citation not in self._citations:
            self._citations.append(citation)
        return self

    def resolved(self, resolution: str, at: Optional[str] = None) -> "IncidentBuilder":
        stamp = at or _now()
        self._closed_at = stamp
        self._resolution = resolution
        self._timeline.append(TimelineEntry(
            at=stamp, phase=Phase.RESOLVE, actor="sqlguardian",
            description=f"Resolved: {resolution}",
        ))
        return self

    def build(self) -> IncidentEvidence:
        return IncidentEvidence(
            incident_id=self.incident_id,
            instance=self.instance,
            opened_at=self.opened_at,
            conditions=tuple(self._conditions),
            timeline=tuple(sorted(self._timeline, key=lambda e: e.at)),
            checks=tuple(self._checks),
            actions=tuple(self._actions),
            citations=tuple(self._citations),
            closed_at=self._closed_at,
            resolution=self._resolution,
        )


def evidence_from_snapshot(
    snapshot: Mapping[str, Any],
    conditions: Sequence[Condition],
    instance: str = "primary",
    citations: Sequence[str] = (),
) -> IncidentEvidence:
    """Build evidence from a single snapshot: what fired, and what was checked.

    Used by /incidents/draft, where the incident is the current state of the
    instance rather than something a human has been working for an hour. Every
    check that ran is recorded, including the clean ones.
    """
    builder = IncidentBuilder(instance=instance)
    for condition in conditions:
        builder.condition_fired(condition)
    for citation in citations:
        builder.cite(citation)

    checks: tuple[tuple[str, str, dict], ...] = (
        ("server_health", *_server_observation(snapshot)),
        ("blocking", *_blocking_observation(snapshot)),
        ("wait_stats", *_waits_observation(snapshot)),
        ("long_running_queries", *_long_running_observation(snapshot)),
        ("agent_jobs", *_jobs_observation(snapshot)),
        ("disk_usage", *_disk_observation(snapshot)),
        ("database_status", *_database_observation(snapshot)),
    )
    for name, verdict, observed in checks:
        builder.checked(name, verdict, observed)
    return builder.build()


def _verdict(section: Any, default: str = "healthy") -> str:
    if not isinstance(section, Mapping):
        return "failed"
    if "error" in section:
        return "failed"
    return str(section.get("severity") or default)


def _server_observation(snapshot: Mapping[str, Any]) -> tuple[str, dict]:
    section = snapshot.get("server_health") or {}
    if not isinstance(section, Mapping) or "error" in section:
        return "failed", {}
    cpu = section.get("cpu") or {}
    memory = section.get("memory") or {}
    verdict = "critical" if "critical" in (cpu.get("severity"), memory.get("severity")) else (
        "warning" if "warning" in (cpu.get("severity"), memory.get("severity")) else "healthy"
    )
    return verdict, {
        "cpu_pct": cpu.get("sql_cpu_pct"),
        "memory_used_pct": memory.get("used_pct"),
        "uptime_hours": section.get("uptime_hours"),
    }


def _blocking_observation(snapshot: Mapping[str, Any]) -> tuple[str, dict]:
    section = snapshot.get("blocking") or {}
    return _verdict(section), {
        "blocked_session_count": section.get("blocked_session_count") if isinstance(section, Mapping) else None,
        "max_wait_seconds": section.get("max_wait_seconds") if isinstance(section, Mapping) else None,
    }


def _waits_observation(snapshot: Mapping[str, Any]) -> tuple[str, dict]:
    section = snapshot.get("wait_stats") or {}
    if not isinstance(section, Mapping) or "error" in section:
        return "failed", {}
    top = (section.get("top_waits") or [{}])[0]
    return "healthy", {
        "mode": section.get("mode"),
        "window_seconds": section.get("elapsed_seconds"),
        "top_wait_type": top.get("wait_type"),
        "top_wait_seconds": top.get("wait_seconds"),
    }


def _long_running_observation(snapshot: Mapping[str, Any]) -> tuple[str, dict]:
    section = snapshot.get("long_running_queries") or {}
    if not isinstance(section, Mapping) or "error" in section:
        return "failed", {}
    count = int(section.get("count") or 0)
    return ("warning" if count else "healthy"), {"long_running_count": count}


def _jobs_observation(snapshot: Mapping[str, Any]) -> tuple[str, dict]:
    section = snapshot.get("agent_jobs") or {}
    return _verdict(section), {
        "failed_count": section.get("failed_count") if isinstance(section, Mapping) else None,
        "total_jobs": section.get("total_jobs") if isinstance(section, Mapping) else None,
    }


def _disk_observation(snapshot: Mapping[str, Any]) -> tuple[str, dict]:
    section = snapshot.get("disk_usage") or {}
    return _verdict(section), {
        "max_used_pct": section.get("max_used_pct") if isinstance(section, Mapping) else None,
        "volume_count": section.get("volume_count") if isinstance(section, Mapping) else None,
    }


def _database_observation(snapshot: Mapping[str, Any]) -> tuple[str, dict]:
    section = snapshot.get("database_status") or {}
    return _verdict(section), {
        "database_count": section.get("database_count") if isinstance(section, Mapping) else None,
        "databases_missing_backup": section.get("databases_missing_backup") if isinstance(section, Mapping) else None,
    }
