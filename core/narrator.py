"""
SQLGuardian - The narration boundary

This is the only place a model is allowed near an incident, and it is allowed
to do exactly one thing: put existing evidence into sentences.

The boundary is structural, not a convention:

  - `narrate()` accepts IncidentEvidence and nothing else. That type is frozen
    with tuple fields, so the narration layer cannot add a condition, remove
    one, or change a verdict. Mutation is a runtime error and a mypy error.

  - Nothing here returns a severity, a verdict, or an ordering. Those are
    computed in core/conditions.py and core/actions.py before narration runs,
    and core/reports.py reads them from the evidence, not from the narration.

  - Generated prose is verified against the evidence: every number in the text
    has to correspond to a number in the evidence object. Violations are
    reported on the Narration, not quietly dropped.

  - If the model is unavailable, reports still render. The narration is the
    part that goes missing, not the findings.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Mapping, Optional

from loguru import logger

from core.incident import IncidentEvidence
from core.llm import LLMUnavailable, complete_json, model_id


NARRATOR_SYSTEM_PROMPT = """You are a Senior SQL Server DBA writing up an incident that has
already been analysed. The analysis is finished and is not yours to revise.

You are given an evidence object. Your only job is to put what it contains into sentences.

Hard rules:
- Do not introduce any fact that is not in the evidence object.
- Do not state any number that is not in the evidence object. Do not convert units,
  do not round, do not compute totals, averages or percentages. If the evidence says
  412 seconds, write 412 seconds, not "about 7 minutes".
- Do not change, soften or contradict any severity or verdict. They were computed
  before you were called.
- Do not recommend actions that are not in the evidence object.
- If the evidence does not say why something happened, say that it is not established
  rather than proposing a cause.
- The business summary must contain no session ids, no SPIDs, no object names, no wait
  types, no T-SQL and no numbers other than durations already present in the evidence.

Return valid JSON only. No markdown, no preamble."""


@dataclass(frozen=True)
class Narration:
    """Prose only. Carries no verdict and no ordering."""

    technical_narrative: str
    business_summary: str
    model: str
    generated_at: str
    unsupported_numbers: tuple[str, ...] = ()
    business_leaks: tuple[str, ...] = ()
    available: bool = True
    unavailable_reason: Optional[str] = None

    @property
    def verified(self) -> bool:
        """True only when prose exists AND it passed every check.

        An unavailable narration is not "verified" - there is nothing to
        verify. Reporting it as verified would be exactly the kind of empty
        assurance this module exists to prevent.
        """
        return (
            self.available
            and not self.unsupported_numbers
            and not self.business_leaks
        )

    def to_dict(self) -> dict:
        return {
            "technical_narrative": self.technical_narrative,
            "business_summary": self.business_summary,
            "model": self.model,
            "generated_at": self.generated_at,
            "available": self.available,
            "unavailable_reason": self.unavailable_reason,
            "verified": self.verified,
            "unsupported_numbers": list(self.unsupported_numbers),
            "business_leaks": list(self.business_leaks),
        }


def unavailable(reason: str) -> Narration:
    """The narration failed. Reports render without it; findings are unaffected."""
    return Narration(
        technical_narrative="",
        business_summary="",
        model=model_id(),
        generated_at=datetime.now(timezone.utc).isoformat(),
        available=False,
        unavailable_reason=reason,
    )


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

# Trailing letters are part of the unit, not part of the number: the evidence
# says "waiting 388s", the narration says "388 seconds", and those are the same
# number. The match is incomplete only when a digit follows, or when a decimal
# point followed by a digit does - a bare "." is the end of a sentence, and
# rejecting those made every sentence-final number ("the count was 7.") escape
# extraction, and therefore escape verification entirely.
_NUMBER_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?!\d|\.\d)")

# Timestamps are stripped from BOTH the evidence and the generated text before
# any number is extracted. An evidence object is full of ISO timestamps, and
# leaving their digits in the allowed set means a clock reading of 09:47 quietly
# authorises the sentence "the chain affected 47 sessions". The window in which
# an invented number is accepted would then depend on the time of day, which is
# not a guarantee worth having. Clock times in prose are neither validated nor
# flagged: they carry no magnitude claim.
_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?"
    r"|\d{1,2}:\d{2}(?::\d{2})?"
)


def _without_timestamps(text: str) -> str:
    return _TIMESTAMP_RE.sub(" ", text)

# Session identifiers must never reach the business summary. Deterministic
# patterns, checked after generation - the instruction in the prompt is the
# request, this is the enforcement.
_SESSION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsession[\s_-]*(?:id\s*)?\d+", re.IGNORECASE),
    re.compile(r"\bspid\s*\d+", re.IGNORECASE),
    re.compile(r"\bsession_id\b", re.IGNORECASE),
)


# ---------------------------------------------------------------------------
# What a number is a number OF
# ---------------------------------------------------------------------------
# Checking that a number appears somewhere in the evidence is membership, not
# association: it cannot tell that the "1" in "1 session was blocked" came from
# check_count rather than from a session count, so a misattributed small integer
# passes. Binding each number to the thing it quantifies closes that.
#
# Both sides are parsed by the same extractor. The evidence's own lines are
# already written as "4 session(s) blocked, longest wait 412s", so the units
# they use are the units the narration is held to, and the grounding and the
# check cannot drift apart.

_KIND_BY_UNIT: Mapping[str, str] = MappingProxyType({
    "%": "percent", "percent": "percent", "pct": "percent",
    "s": "seconds", "sec": "seconds", "secs": "seconds",
    "second": "seconds", "seconds": "seconds",
    "m": "minutes", "min": "minutes", "mins": "minutes",
    "minute": "minutes", "minutes": "minutes",
    "h": "hours", "hr": "hours", "hrs": "hours", "hour": "hours", "hours": "hours",
    "day": "days", "days": "days",
    "session": "sessions", "sessions": "sessions",
    "database": "databases", "databases": "databases", "db": "databases",
    "job": "jobs", "jobs": "jobs",
    "volume": "volumes", "volumes": "volumes", "drive": "volumes", "drives": "volumes",
    "request": "requests", "requests": "requests",
    "query": "requests", "queries": "requests",
    "task": "tasks", "tasks": "tasks",
    "gb": "gb", "mb": "mb", "kb": "kb", "tb": "tb",
})

# Structured fact and observation keys, matched on substring, first hit wins.
_KIND_BY_KEY_HINT: tuple[tuple[str, str], ...] = (
    ("session_id", "session_id"),
    ("session_count", "sessions"),
    ("seconds", "seconds"),
    ("hours", "hours"),
    ("pct", "percent"),
    ("_gb", "gb"),
    ("_mb", "mb"),
    ("waiting_tasks", "tasks"),
    ("database", "databases"),
    ("job", "jobs"),
    ("volume", "volumes"),
    ("long_running", "requests"),
)

# "session 62", "SPID 62" - an identifier, not a quantity.
_IDENTIFIER_RE = re.compile(
    r"\b(?:session|spid)s?\b[\s_-]*(?:id[\s:]*)?(\d+)", re.IGNORECASE
)
# "412 seconds", "96.4% used", "73.7 GB free"
_QUANTITY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(%|[A-Za-z]+)")


@dataclass(frozen=True)
class Claim:
    """One number in a piece of text, and what it is a number of."""

    token: str
    value: float
    kind: str          # "sessions", "seconds", "session_id", ... or "" when untyped

    def __str__(self) -> str:
        return f"{self.token} {self.kind}" if self.kind else self.token


def _blank(match: "re.Match[str]") -> str:
    """Replace a match with spaces, so later passes cannot re-read its digits."""
    return " " * len(match.group(0))


def extract_claims(text: str) -> tuple[Claim, ...]:
    """Pull (number, kind) pairs out of prose, then untyped leftovers.

    Identifiers are read first and blanked, so "session 62" is a session id and
    not 62 of something. Quantities follow. Anything still unmatched stays
    untyped and is checked against the evidence as a whole, exactly as before -
    this narrows what is accepted and never widens it.
    """
    cleaned = _without_timestamps(text)
    claims: list[Claim] = []

    for match in _IDENTIFIER_RE.finditer(cleaned):
        claims.append(Claim(match.group(1), float(match.group(1)), "session_id"))
    cleaned = _IDENTIFIER_RE.sub(_blank, cleaned)

    for match in _QUANTITY_RE.finditer(cleaned):
        kind = _KIND_BY_UNIT.get(match.group(2).lower())
        if kind:
            claims.append(Claim(match.group(1), float(match.group(1)), kind))
    cleaned = _QUANTITY_RE.sub(
        lambda m: _blank(m) if _KIND_BY_UNIT.get(m.group(2).lower()) else m.group(0),
        cleaned,
    )

    for token in _NUMBER_RE.findall(cleaned):
        claims.append(Claim(token, float(token), ""))
    return tuple(claims)


def evidence_numbers(evidence: IncidentEvidence) -> frozenset[float]:
    """Every number the evidence object contains, at any depth.

    Built from the serialised evidence rather than a curated list, so a report
    may cite anything actually recorded and nothing else.
    """
    blob = _without_timestamps(json.dumps(evidence.to_dict(), default=str))
    found = {float(match) for match in _NUMBER_RE.findall(blob)}
    found.update(evidence.numeric_facts().values())
    return frozenset(found)


def _kind_for_key(key: str) -> str:
    lowered = key.lower()
    for hint, kind in _KIND_BY_KEY_HINT:
        if hint in lowered:
            return kind
    return ""


def evidence_claims(evidence: IncidentEvidence) -> Mapping[str, frozenset[float]]:
    """Numbers the evidence supports, grouped by what they are numbers of.

    Two sources, unioned: the structured facts and observations, keyed by their
    own field names, and the evidence's prose lines parsed by the same extractor
    that reads the narration.
    """
    by_kind: dict[str, set[float]] = {}

    def add(kind: str, value: float) -> None:
        if kind:
            by_kind.setdefault(kind, set()).add(value)

    def add_text(text: str) -> None:
        for claim in extract_claims(text):
            add(claim.kind, claim.value)

    for condition in evidence.conditions:
        for key, value in condition.facts.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                add(_kind_for_key(key), float(value))
        for line in condition.evidence:
            add_text(line)
        for line in (condition.title, condition.detail, condition.scope):
            add_text(line)

    for observation in evidence.checks:
        for key, value in observation.observed.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                add(_kind_for_key(key), float(value))

    for action in evidence.actions:
        add_text(action.action)
        add_text(action.outcome)

    for seconds in evidence.phase_durations().values():
        add("seconds", float(seconds))
    if evidence.duration_seconds is not None:
        add("seconds", float(evidence.duration_seconds))

    return MappingProxyType({k: frozenset(v) for k, v in by_kind.items()})


def _supported(value: float, token: str, allowed: frozenset[float]) -> bool:
    """Equal to an allowed value, or that value rounded to the precision written."""
    decimals = len(token.split(".")[1]) if "." in token else 0
    return any(round(candidate, decimals) == value for candidate in allowed)


def unsupported_numbers(evidence: IncidentEvidence, text: str) -> tuple[str, ...]:
    """Numbers in the text the evidence does not support, as written.

    A typed number ("4 sessions", "session 62", "412 seconds") is checked
    against the evidence values of that same kind, so a number that exists in
    the evidence as something else does not license it. An untyped number is
    checked against the evidence as a whole, as before.

    A generated number is supported if it equals an evidence value, or if it is
    that value rounded to the precision written (91.3 for 91.34). Unit
    conversion is not accepted: the prompt forbids it precisely so this check
    can stay strict, and a unit the evidence never uses is a violation rather
    than a free pass.

    Violations are returned as written ("1 sessions", "7 minutes") rather than
    as bare digits, because a number can now fail while still existing in the
    evidence as something else - and a report that said "not present in the
    evidence" about it would itself be wrong.
    """
    by_kind = evidence_claims(evidence)
    everything = evidence_numbers(evidence)

    violations: list[str] = []
    for claim in extract_claims(text):
        allowed = by_kind.get(claim.kind, frozenset()) if claim.kind else everything
        if _supported(claim.value, claim.token, allowed):
            continue
        violations.append(str(claim))
    return tuple(dict.fromkeys(violations))


def business_summary_leaks(text: str) -> tuple[str, ...]:
    """Technical identifiers that must not appear in the business summary."""
    leaks: list[str] = []
    for pattern in _SESSION_PATTERNS:
        leaks.extend(match.group(0) for match in pattern.finditer(text))
    return tuple(dict.fromkeys(leaks))


# ---------------------------------------------------------------------------
# Narration
# ---------------------------------------------------------------------------

def narration_view(evidence: IncidentEvidence) -> dict:
    """A compacted evidence object for the prompt.

    Strictly a subset of the full evidence: the per-condition `facts` map is
    dropped because the same values are already spelled out in the evidence
    lines, and the timeline's value dictionaries go with it. That halves the
    prompt - a five-condition incident serialises to more than 8k tokens in
    full, which is past the rate limit on a small account - and it cannot widen
    what the model is able to say, because verification still runs against the
    complete evidence object, which is a superset of this.
    """
    return {
        "incident_id": evidence.incident_id,
        "instance": evidence.instance,
        "severity": evidence.severity,
        "opened_at": evidence.opened_at,
        "closed_at": evidence.closed_at,
        "duration_seconds": evidence.duration_seconds,
        "phase_durations": dict(evidence.phase_durations()),
        "conditions": [
            {
                "code": condition.code.value,
                "severity": condition.severity,
                "title": condition.title,
                "detail": condition.detail,
                "scope": condition.scope,
                "evidence": list(condition.evidence[:6]),
            }
            for condition in evidence.conditions
        ],
        "checks": [
            {
                "check": observation.check,
                "verdict": observation.verdict,
                "observed": {k: v for k, v in observation.observed.items() if v is not None},
            }
            for observation in evidence.checks
        ],
        "actions": [
            {
                "action": action.action,
                "by": action.by,
                "source": action.source,
                "outcome": action.outcome,
                "resolved_condition": action.resolved_condition,
            }
            for action in evidence.actions
        ],
        "resolution": evidence.resolution,
        "citations": list(evidence.citations),
    }


def build_narration_prompt(evidence: IncidentEvidence) -> str:
    """The evidence, compacted, plus the shape of the answer."""
    return f"""Write up this incident. Everything you may state is in the evidence object below.

EVIDENCE OBJECT:
{json.dumps(narration_view(evidence), indent=2, default=str)}

The severity of this incident is "{evidence.severity}". It was computed from the checks
above before you were called. Do not restate it as anything else.

Respond with ONLY this JSON structure:
{{
  "technical_narrative": "4-8 sentences for an engineer: what fired, what the evidence showed, what was done, what resolved it or what is still open. Use the exact values from the evidence.",
  "business_summary": "ONE paragraph, 2-4 sentences, for a director. Plain business language: what was affected, whether it is resolved, what it meant for the service. No session ids, no wait types, no object names, no T-SQL."
}}"""


async def narrate(evidence: IncidentEvidence) -> Narration:
    """Turn evidence into prose. Never returns a verdict.

    The parameter is typed IncidentEvidence - frozen, tuple-backed - so this
    function is structurally unable to hand back a modified incident. It
    returns text and verification results, and the caller composes the report
    from the original evidence.
    """
    try:
        result = await complete_json(
            build_narration_prompt(evidence),
            NARRATOR_SYSTEM_PROMPT,
            # Two short passages plus the reasoning pass. The requested budget
            # counts against the provider's tokens-per-minute limit, so asking
            # for room that will never be used costs real headroom.
            max_tokens=2000,
        )
    except LLMUnavailable as exc:
        logger.warning(f"Narration unavailable for {evidence.incident_id}: {exc}")
        return unavailable(str(exc))

    technical = str(result.get("technical_narrative") or "").strip()
    business = str(result.get("business_summary") or "").strip()

    violations = unsupported_numbers(evidence, f"{technical}\n{business}")
    leaks = business_summary_leaks(business)
    if violations:
        logger.warning(
            f"Narration for {evidence.incident_id} stated numbers absent from the "
            f"evidence: {', '.join(violations)}"
        )
    if leaks:
        logger.warning(
            f"Business summary for {evidence.incident_id} leaked technical identifiers: "
            f"{', '.join(leaks)}"
        )

    return Narration(
        technical_narrative=technical,
        business_summary=business,
        model=model_id(),
        generated_at=datetime.now(timezone.utc).isoformat(),
        unsupported_numbers=violations,
        business_leaks=leaks,
    )
