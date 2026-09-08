"""The safety boundary, as tests rather than as a README claim.

Four things are asserted here:
  1. The evidence handed to the narration layer cannot be mutated.
  2. A narration layer that says "everything is fine" cannot change the
     reported status of a failing check.
  3. Numbers in generated prose are verified against the evidence.
  4. Session identifiers cannot reach the business summary.
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from core.conditions import detect_conditions
from core.incident import IncidentEvidence, evidence_from_snapshot
from core.narrator import (
    Narration,
    business_summary_leaks,
    unsupported_numbers,
)
from core.reports import render_both, render_business_report, render_technical_report


ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def evidence(multi_condition_snapshot) -> IncidentEvidence:
    conditions = detect_conditions(multi_condition_snapshot)
    return evidence_from_snapshot(multi_condition_snapshot, conditions, instance="SQLPROD01")


def _narration(technical: str, business: str, **kwargs) -> Narration:
    return Narration(
        technical_narrative=technical,
        business_summary=business,
        model="stub",
        generated_at="2026-08-30T02:20:00+00:00",
        **kwargs,
    )


# ---------------------------------------------------------------------------
# 1. The evidence is read-only at the boundary
# ---------------------------------------------------------------------------

def test_evidence_cannot_be_mutated(evidence):
    with pytest.raises(dataclasses.FrozenInstanceError):
        evidence.conditions = ()                       # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        evidence.resolution = "nothing was wrong"      # type: ignore[misc]


def test_evidence_collections_cannot_be_appended_to(evidence):
    assert isinstance(evidence.conditions, tuple)
    assert isinstance(evidence.timeline, tuple)
    assert isinstance(evidence.checks, tuple)
    assert isinstance(evidence.actions, tuple)
    with pytest.raises(AttributeError):
        evidence.conditions.append(None)               # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        evidence.checks[0].observed["max_used_pct"] = 0   # type: ignore[index]


def test_severity_is_derived_and_has_no_setter(evidence):
    assert evidence.severity == "critical"
    with pytest.raises(AttributeError):
        evidence.severity = "healthy"                  # type: ignore[misc]


def test_mutating_evidence_is_a_static_type_error():
    """Not just a runtime error: mypy rejects it too.

    Skipped rather than failed if mypy is not installed, so the suite still runs
    in a bare environment - but the check is real where it can run.
    """
    pytest.importorskip("mypy")
    snippet = textwrap.dedent(
        """
        from core.incident import IncidentEvidence

        def tamper(evidence: IncidentEvidence) -> None:
            evidence.conditions = ()
            evidence.resolution = "nothing was wrong"
        """
    )
    target = ROOT / "_mypy_boundary_check.py"
    target.write_text(snippet, encoding="utf-8")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--no-error-summary", "--ignore-missing-imports",
             str(target)],
            capture_output=True, text=True, cwd=str(ROOT),
        )
    finally:
        target.unlink(missing_ok=True)

    assert result.returncode != 0, "mypy accepted a write to frozen evidence"
    assert "conditions" in result.stdout
    assert "misc" in result.stdout or "read-only" in result.stdout.lower() \
        or "frozen" in result.stdout.lower()


# ---------------------------------------------------------------------------
# 2. Narration cannot flip a verdict
# ---------------------------------------------------------------------------

EVERYTHING_IS_FINE = (
    "Everything is fine. All checks passed and no issues were found on this instance. "
    "The server is healthy and no action is required."
)


def test_a_narrator_claiming_everything_is_fine_cannot_change_the_status(evidence):
    """The stubbed model contradicts the checks. The checks win."""
    narration = _narration(EVERYTHING_IS_FINE, EVERYTHING_IS_FINE)

    assert evidence.severity == "critical"
    report = render_technical_report(evidence, narration)
    assert "Severity: **critical**" in report
    # The findings survive intact underneath the narration.
    assert "DISK_PRESSURE" in report
    assert "BLOCKING_CHAIN" in report
    assert "96.4% used" in report

    both = render_both(evidence, narration)
    assert both["severity"] == "critical"


def test_a_missing_narration_does_not_downgrade_anything(evidence):
    """No model at all is not the same as no problem."""
    from core.narrator import unavailable

    report = render_technical_report(evidence, unavailable("GROQ_API_KEY is not set."))
    assert "Severity: **critical**" in report
    assert "DISK_PRESSURE" in report
    assert "Narration unavailable" in report

    business = render_business_report(evidence, unavailable("GROQ_API_KEY is not set."))
    assert "critical" in business


def test_reports_render_with_no_narration_argument_at_all(evidence):
    report = render_technical_report(evidence)
    assert "Severity: **critical**" in report
    assert "96.4% used" in report


def test_the_two_documents_agree_because_they_share_a_source(evidence):
    narration = _narration(EVERYTHING_IS_FINE, EVERYTHING_IS_FINE)
    both = render_both(evidence, narration)
    assert both["severity"] in both["technical_report"]
    assert both["severity"] in both["business_summary"]


# ---------------------------------------------------------------------------
# 3. Numbers in the narration have to exist in the evidence
# ---------------------------------------------------------------------------

def test_numbers_in_the_narration_must_appear_in_the_evidence(evidence):
    invented = (
        "The blocking chain affected 47 sessions and cost the business 12000 pounds "
        "over 93 minutes."
    )
    violations = unsupported_numbers(evidence, invented)

    # Violations are reported as written, because a number can fail while still
    # existing in the evidence as something else.
    assert "47 sessions" in violations
    assert "93 minutes" in violations
    assert "12000" in violations        # no unit, so checked against the whole evidence


def test_numbers_actually_present_in_the_evidence_pass(evidence):
    grounded = (
        "4 sessions were blocked behind session 62, the longest for 412 seconds, "
        "while volume usage reached 96.4 percent."
    )
    assert unsupported_numbers(evidence, grounded) == ()


def test_a_value_written_with_its_unit_in_the_evidence_is_still_recognised(evidence):
    """The evidence says "waiting 388s"; the narration says "388 seconds"."""
    assert any("388s" in line for c in evidence.conditions for line in c.evidence)
    assert unsupported_numbers(evidence, "One session waited 388 seconds.") == ()
    assert unsupported_numbers(evidence, "One session waited 201 seconds.") == ()


def test_rounding_to_the_stated_precision_is_accepted(evidence):
    """91.34 written as 91.3 is the same number, not an invented one."""
    from core.incident import IncidentBuilder

    builder = IncidentBuilder(instance="SQLPROD01")
    builder.checked("disk_usage", "critical", {"max_used_pct": 91.34})
    built = builder.build()
    assert unsupported_numbers(built, "The volume was 91.3 percent full.") == ()
    assert unsupported_numbers(built, "The volume was 74.0 percent full.") == ("74.0 percent",)


def test_an_unverified_narration_is_flagged_on_the_report(evidence):
    narration = _narration(
        "The chain affected 47 sessions.",
        "Users saw delays.",
        unsupported_numbers=("47",),
    )
    assert narration.verified is False
    report = render_technical_report(evidence, narration)
    assert "Narration verification failed" in report
    assert "47" in report
    # The findings are still reported in full underneath.
    assert "Severity: **critical**" in report


# ---------------------------------------------------------------------------
# 4. The business summary is free of technical identifiers, by construction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Session 62 was blocking four other sessions.",
    "SPID 62 held the lock.",
    "The session_id column showed the blocker.",
    "session id 62 was terminated",
])
def test_session_identifiers_are_detected(text):
    assert business_summary_leaks(text)


def test_a_leaking_business_summary_is_not_used(evidence):
    narration = _narration(
        "Session 62 blocked 4 sessions.",
        "Session 62 was the cause of the delay for our warehouse users.",
        business_leaks=("Session 62",),
    )
    business = render_business_report(evidence, narration)

    assert "Session 62" not in business
    assert "62" not in business.replace(evidence.incident_id, "")
    assert "did not pass verification" in business


def test_the_deterministic_business_summary_never_leaks(evidence):
    business = render_business_report(evidence, None)
    assert business_summary_leaks(business) == ()
    assert "LCK_M_S" not in business
    assert "Sales.OrderLines" not in business


def test_a_clean_business_summary_is_used_as_written(evidence):
    clean = (
        "Warehouse users saw slow order screens for a period this morning. "
        "Storage on one server is close to full and a scheduled backup did not "
        "complete. The situation is being worked on now."
    )
    narration = _narration("Technical detail here.", clean)
    assert clean in render_business_report(evidence, narration)


def test_the_business_summary_says_which_version_the_reader_is_holding(evidence):
    """A director cannot tell a drafted paragraph from a generated one by looking."""
    from core.narrator import unavailable

    unavailable_report = render_business_report(evidence, unavailable("HTTP 429: rate limit."))
    assert "deterministically" in unavailable_report
    assert "model was unavailable" in unavailable_report

    rejected = _narration(
        "Session 62 blocked 4 sessions.",
        "Session 62 caused the delay.",
        business_leaks=("Session 62",),
    )
    rejected_report = render_business_report(evidence, rejected)
    assert "deterministically" in rejected_report
    assert "did not pass verification" in rejected_report

    # A clean narration is used as written, with no disclaimer attached.
    clean = _narration("Technical detail.", "Warehouse users saw slow order screens.")
    clean_report = render_business_report(evidence, clean)
    assert "deterministically" not in clean_report


def test_a_clock_reading_cannot_authorise_an_invented_number():
    """Regression: the allowed set is built from evidence, not from timestamps.

    Before this was fixed, an incident opened at 09:47 put "47" into the allowed
    set through its own ISO timestamps, so "the chain affected 47 sessions"
    passed verification - and whether an invented number was caught depended on
    the time of day.
    """
    from core.incident import IncidentBuilder

    builder = IncidentBuilder(instance="SQLPROD01", incident_id="INC-TEST")
    builder.opened_at = "2026-09-01T09:47:47+00:00"
    builder.checked(
        "blocking", "critical", {"blocked_session_count": 4},
        at="2026-09-01T09:47:47+00:00",
    )
    built = builder.build()

    assert "47" in built.opened_at
    assert unsupported_numbers(built, "The chain affected 47 sessions.") == ("47 sessions",)
    # The real value is still accepted.
    assert unsupported_numbers(built, "The chain affected 4 sessions.") == ()


def test_a_clock_time_in_prose_is_not_itself_flagged():
    """Times carry no magnitude claim, so they are neither validated nor flagged."""
    from core.incident import IncidentBuilder

    built = IncidentBuilder(instance="SQLPROD01").checked(
        "blocking", "critical", {"blocked_session_count": 4}
    ).build()

    assert unsupported_numbers(built, "The incident opened at 02:14 UTC on 2026-09-01.") == ()


def test_an_unavailable_narration_is_not_reported_as_verified():
    """There is nothing to verify when there is no prose."""
    from core.narrator import unavailable

    missing = unavailable("Provider returned HTTP 429: rate limit reached.")
    assert missing.available is False
    assert missing.verified is False
    assert missing.to_dict()["verified"] is False

    clean = _narration("Technical detail.", "Business detail.")
    assert clean.verified is True


# ---------------------------------------------------------------------------
# 5. A number must match what it is a number OF, not just exist somewhere
# ---------------------------------------------------------------------------

def test_a_number_that_exists_as_something_else_does_not_license_the_claim(evidence):
    """The gap this closes: membership is not association.

    "1" is genuinely in the evidence - one failed job, one affected database -
    so a flat membership check accepted "1 session was blocked" even though the
    evidence says four. Binding each number to the kind it quantifies is what
    makes the difference.
    """
    from core.narrator import evidence_claims

    by_kind = evidence_claims(evidence)
    assert by_kind["sessions"] == frozenset({4.0})
    assert 1.0 in by_kind["jobs"], "1 really is in the evidence, as a job count"

    assert unsupported_numbers(evidence, "1 session was blocked.") == ("1 sessions",)
    assert unsupported_numbers(evidence, "1 job failed.") == ()


@pytest.mark.parametrize("claim,flagged", [
    ("The volume was 4% full.", "4 percent"),              # 4 is a session count
    ("The database was 62 hours past its window.", "62 hours"),  # 62 is a session id
    ("Session 99 was the head blocker.", "99 session_id"),  # no such session
    ("The chain lasted about 7 minutes.", "7 minutes"),     # unit conversion
])
def test_misattributed_and_converted_numbers_are_caught(evidence, claim, flagged):
    assert flagged in unsupported_numbers(evidence, claim)


@pytest.mark.parametrize("claim", [
    "4 sessions were blocked behind session 62, the longest for 412 seconds.",
    "Volume usage reached 96.4% with 73.7 GB free.",
    "The database was 31 hours past its 25 hour threshold.",
    "One session waited 388 seconds and another 201 seconds.",
    "The transaction log was 94.0% used.",
])
def test_true_statements_still_pass(evidence, claim):
    """An over-strict checker is worse than the hole: it would reject every report."""
    assert unsupported_numbers(evidence, claim) == ()


def test_an_identifier_is_not_read_as_a_quantity(evidence):
    """"session 62" is a session id, not 62 of anything."""
    from core.narrator import extract_claims

    kinds = {(c.token, c.kind) for c in extract_claims("session 62 blocked 4 sessions")}
    assert ("62", "session_id") in kinds
    assert ("4", "sessions") in kinds
    assert ("62", "sessions") not in kinds


def test_an_untyped_number_still_falls_back_to_the_whole_evidence(evidence):
    """The kind check narrows what is accepted; it never widens it."""
    from core.narrator import extract_claims

    assert [c.kind for c in extract_claims("run_status was 0")] == [""]
    assert unsupported_numbers(evidence, "The job exited with run_status 0.") == ()
    assert unsupported_numbers(evidence, "The job exited with run_status 8675309.") == (
        "8675309",
    )


def test_a_number_at_the_end_of_a_sentence_is_still_verified(evidence):
    """Regression: a trailing full stop made the number invisible to extraction.

    The lookahead that stops "1180.4" being split into "1180" and "4" also
    rejected any number followed by a period, so "the count was 7." was never
    extracted and never checked - a silent gap in the guarantee at the most
    ordinary place a number can sit.
    """
    from core.narrator import _NUMBER_RE

    assert _NUMBER_RE.findall("the count was 7.") == ["7"]
    assert _NUMBER_RE.findall("wait 1180.4 seconds") == ["1180.4"]

    assert unsupported_numbers(evidence, "The job exited with run_status 8675309.") == (
        "8675309",
    )
    assert unsupported_numbers(evidence, "Sessions blocked: 4.") == ()
