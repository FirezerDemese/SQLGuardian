"""
SQLGuardian - Condition detection

The deterministic core. Every verdict in this file is produced by comparing a
number from a DMV against a threshold from config. No model is consulted here,
and nothing downstream is permitted to change what this module decides.

A Condition is the unit the whole product is keyed on:
  - runbook retrieval is scoped by condition code (core/runbooks.py)
  - candidate actions are catalogued per condition code (core/actions.py)
  - runbook coverage gaps are recorded per condition code (core/gap_report.py)

Conditions are frozen dataclasses. Mutating one raises at runtime and is a type
error under mypy - see tests/test_narration_boundary.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence

from config.settings import settings


class ConditionCode(str, Enum):
    """The conditions SQLGuardian can recognise.

    Adding a code here without adding it to ACTION_CATALOG in core/actions.py
    fails tests/test_actions.py::test_every_condition_has_actions.
    """

    BLOCKING_CHAIN = "BLOCKING_CHAIN"
    AGENT_JOB_FAILURE = "AGENT_JOB_FAILURE"
    BACKUP_AGE_EXCEEDED = "BACKUP_AGE_EXCEEDED"
    LOG_GROWTH = "LOG_GROWTH"
    DISK_PRESSURE = "DISK_PRESSURE"
    WAIT_SPIKE = "WAIT_SPIKE"
    LONG_RUNNING_REQUEST = "LONG_RUNNING_REQUEST"


SEVERITY_RANK: Mapping[str, int] = MappingProxyType({"critical": 0, "warning": 1, "healthy": 2})


# ---------------------------------------------------------------------------
# Blast radius
# ---------------------------------------------------------------------------
# What is at stake if this condition is left alone, independent of how loud it
# is right now. This is the encoded judgment: a 91%-full log volume outranks a
# CPU spike because the failure mode at the end of it is a database that stops
# accepting writes, not a slow query.

BASE_IMPACT: Mapping[ConditionCode, int] = MappingProxyType({
    # Ends in a hard stop for the instance or in data loss.
    ConditionCode.DISK_PRESSURE: 90,
    ConditionCode.LOG_GROWTH: 85,
    ConditionCode.BACKUP_AGE_EXCEEDED: 80,
    # Ends in application-visible failure but the instance stays up.
    ConditionCode.BLOCKING_CHAIN: 70,
    ConditionCode.AGENT_JOB_FAILURE: 50,
    # Degradation. Real, but nothing stops.
    ConditionCode.LONG_RUNNING_REQUEST: 40,
    ConditionCode.WAIT_SPIKE: 30,
})


@dataclass(frozen=True)
class Condition:
    """One detected condition and the evidence that produced it.

    `facts` holds every number the narration layer is allowed to mention. The
    narration verifier in core/narrator.py checks generated prose against these
    values, so anything a report may state has to be in here.
    """

    code: ConditionCode
    severity: str                       # "warning" | "critical"
    title: str
    detail: str                         # deterministic, templated - not model output
    facts: Mapping[str, Any]
    evidence: tuple[str, ...]           # human-readable lines, each traceable to a DMV
    scope: str                          # what is affected: instance / database name / session
    hold_off: tuple[str, ...] = ()      # what NOT to do yet, and why
    detected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def impact_score(self) -> int:
        """Blast radius, 0-100. Deterministic function of code + severity + facts."""
        score = BASE_IMPACT[self.code]
        if self.severity == "critical":
            score += 10
        # Amplifiers: breadth of effect, drawn from facts the checks already collect.
        blocked = int(self.facts.get("blocked_session_count") or 0)
        score += min(blocked, 10)
        affected_dbs = len(self.facts.get("database_names") or ())
        score += min(affected_dbs * 2, 10)
        return min(score, 120)

    def numeric_facts(self) -> Mapping[str, float]:
        """Every fact that is a number, for narration verification."""
        out: dict[str, float] = {}
        for key, value in self.facts.items():
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                out[key] = float(value)
        return MappingProxyType(out)


# ---------------------------------------------------------------------------
# Detectors - one per condition code
# ---------------------------------------------------------------------------
# Each takes the snapshot section it needs and returns 0..n Conditions. A
# section carrying an "error" key means the check could not run; that is not a
# healthy verdict and it is not a condition either, so the detector returns
# nothing and the caller reports the check as failed.


def _section(snapshot: Mapping[str, Any], key: str) -> Optional[Mapping[str, Any]]:
    section = snapshot.get(key)
    if not isinstance(section, Mapping) or "error" in section:
        return None
    return section


def _detect_blocking(snapshot: Mapping[str, Any]) -> list[Condition]:
    blocking = _section(snapshot, "blocking")
    if not blocking:
        return []
    blocked_count = int(blocking.get("blocked_session_count") or 0)
    if blocked_count == 0:
        return []

    max_wait = float(blocking.get("max_wait_seconds") or 0)
    severity = (
        "critical" if max_wait >= settings.blocking_critical_seconds
        else "warning" if max_wait >= settings.blocking_warning_seconds
        else "warning"
    )

    head_blockers: Sequence[Mapping[str, Any]] = blocking.get("head_blockers") or ()
    head = head_blockers[0] if head_blockers else {}
    head_spid = head.get("session_id")
    head_sql = (head.get("current_sql") or "").strip()
    databases = tuple(sorted({
        str(s.get("database_name")) for s in (blocking.get("blocked_sessions") or ())
        if s.get("database_name")
    }))

    evidence = [
        f"{blocked_count} session(s) blocked, longest wait {max_wait:.0f}s "
        f"(sys.dm_exec_requests.blocking_session_id > 0).",
    ]
    if head_spid is not None:
        evidence.append(
            f"Head blocker is session {head_spid}"
            + (f", login {head.get('login_name')}" if head.get("login_name") else "")
            + (f", program {head.get('program_name')}" if head.get("program_name") else "")
            + "."
        )
    intermediates = [
        b for b in head_blockers[1:] if b.get("is_itself_blocked")
    ]
    if intermediates:
        evidence.append(
            f"{len(intermediates)} further session(s) block others while waiting themselves "
            f"({', '.join(str(b.get('session_id')) for b in intermediates)}): this is a chain, "
            f"and clearing the head is what releases it."
        )
    if head.get("is_idle"):
        evidence.append(
            f"Head blocker is idle with {head.get('open_transaction_count') or 0} open "
            f"transaction(s), last request ended {head.get('idle_seconds')}s ago. An idle "
            f"session holding locks is an application problem, not a query problem."
        )
    if head_sql:
        label = "Last statement it ran" if head.get("is_idle") else "Statement holding the lock"
        evidence.append(f"{label}: {head_sql[:400]}")
    for blocked in list(blocking.get("blocked_sessions") or ())[:5]:
        evidence.append(
            f"Session {blocked.get('session_id')} waiting {blocked.get('wait_seconds')}s "
            f"on {blocked.get('wait_type')} in {blocked.get('database_name')}."
        )

    facts = {
        "blocked_session_count": blocked_count,
        "max_wait_seconds": max_wait,
        "head_blocker_session_id": head_spid,
        "head_blocker_login": head.get("login_name"),
        "head_blocker_program": head.get("program_name"),
        "head_blocker_host": head.get("host_name"),
        "head_blocker_statement": head_sql[:400] or None,
        "head_blocker_is_idle": bool(head.get("is_idle")),
        "intermediate_blocker_count": len(intermediates),
        "head_blocker_open_transactions": head.get("open_transaction_count"),
        "head_blocker_count": int(blocking.get("head_blocker_count") or 0),
        "database_names": databases,
    }

    return [Condition(
        code=ConditionCode.BLOCKING_CHAIN,
        severity=severity,
        title=f"Blocking chain: {blocked_count} session(s) blocked behind session {head_spid}",
        detail=(
            f"{blocked_count} session(s) are blocked, the longest for {max_wait:.0f} seconds. "
            f"The head of the chain is session {head_spid}."
        ),
        facts=MappingProxyType(facts),
        evidence=tuple(evidence),
        scope=f"session {head_spid}" + (f" / {', '.join(databases)}" if databases else ""),
        hold_off=(
            "Do not KILL the head blocker before identifying who owns it. A rollback "
            "of a large open transaction can hold the same locks for longer than the "
            "original block.",
            "Do not enable READ_COMMITTED_SNAPSHOT mid-incident to clear a block: it "
            "needs a database-level change and tempdb headroom, and it does not "
            "release the locks already held.",
        ),
    )]


def _detect_agent_jobs(snapshot: Mapping[str, Any]) -> list[Condition]:
    jobs = _section(snapshot, "agent_jobs")
    if not jobs:
        return []
    failed = list(jobs.get("failed_jobs") or ())
    if not failed:
        return []

    names = tuple(str(j.get("job_name")) for j in failed if j.get("job_name"))
    evidence = [
        f"{len(failed)} SQL Agent job(s) last finished with run_status = 0 (Failed) "
        f"in msdb.dbo.sysjobhistory."
    ]
    for job in failed[:5]:
        message = (job.get("last_run_message") or "").strip().replace("\n", " ")
        evidence.append(
            f"{job.get('job_name')} failed at {job.get('last_run_time')}"
            + (f": {message[:240]}" if message else ".")
        )

    return [Condition(
        code=ConditionCode.AGENT_JOB_FAILURE,
        severity="critical",
        title=f"{len(failed)} SQL Agent job(s) failed on last run",
        detail=f"Failed jobs: {', '.join(names)}.",
        facts=MappingProxyType({
            "failed_job_count": len(failed),
            "failed_job_names": names,
            "total_job_count": int(jobs.get("total_jobs") or 0),
        }),
        evidence=tuple(evidence),
        scope=", ".join(names) or "SQL Agent",
        hold_off=(
            "Do not re-run a failed backup or ETL job before reading the step output. "
            "A job that failed on disk space or a lock will fail the same way and can "
            "make the underlying condition worse.",
        ),
    )]


def _detect_backup_age(snapshot: Mapping[str, Any]) -> list[Condition]:
    databases = _section(snapshot, "database_status")
    if not databases:
        return []

    stale: list[Mapping[str, Any]] = []
    for row in databases.get("databases") or ():
        hours = row.get("hours_since_full_backup")
        if hours is None or float(hours) > settings.backup_age_warning_hours:
            stale.append(row)
    if not stale:
        return []

    worst = max(
        (float(r["hours_since_full_backup"]) for r in stale
         if r.get("hours_since_full_backup") is not None),
        default=None,
    )
    never = [r for r in stale if r.get("hours_since_full_backup") is None]
    names = tuple(str(r.get("database_name")) for r in stale)

    severity = "critical" if never or (worst or 0) > settings.backup_age_critical_hours else "warning"

    evidence = [
        f"{len(stale)} database(s) have no full backup inside "
        f"{settings.backup_age_warning_hours}h (msdb.dbo.backupset, type = 'D')."
    ]
    for row in stale[:8]:
        hours = row.get("hours_since_full_backup")
        evidence.append(
            f"{row.get('database_name')} ({row.get('recovery_model')}): "
            + (f"last full backup {float(hours):.0f}h ago." if hours is not None
               else "no full backup recorded in the last 30 days.")
        )

    facts: dict[str, Any] = {
        "stale_backup_database_count": len(stale),
        "database_names": names,
        "never_backed_up_count": len(never),
        "threshold_hours": settings.backup_age_warning_hours,
    }
    if worst is not None:
        facts["oldest_backup_age_hours"] = worst

    return [Condition(
        code=ConditionCode.BACKUP_AGE_EXCEEDED,
        severity=severity,
        title=f"{len(stale)} database(s) outside the backup window",
        detail=(
            f"{', '.join(names)} exceed the {settings.backup_age_warning_hours}h "
            f"full-backup threshold."
        ),
        facts=MappingProxyType(facts),
        evidence=tuple(evidence),
        scope=", ".join(names),
        hold_off=(
            "Do not start an ad-hoc full backup to the same volume before checking free "
            "space. A backup that fills the volume converts a recoverability problem "
            "into an availability one.",
        ),
    )]


def _detect_log_growth(snapshot: Mapping[str, Any]) -> list[Condition]:
    databases = _section(snapshot, "database_status")
    if not databases:
        return []

    affected: list[tuple[Mapping[str, Any], str]] = []
    for row in databases.get("databases") or ():
        used_pct = row.get("log_used_pct")
        reuse_wait = (row.get("log_reuse_wait_desc") or "NOTHING").upper()
        # Two independent triggers. Either alone is worth a page.
        if used_pct is not None and float(used_pct) >= settings.log_used_warning_pct:
            affected.append((row, "full"))
        elif reuse_wait not in ("NOTHING", "CHECKPOINT"):
            # The log physically cannot truncate. It will grow until the volume
            # fills, whatever the current percentage says.
            affected.append((row, "blocked"))
    if not affected:
        return []

    names = tuple(str(r.get("database_name")) for r, _ in affected)
    worst_pct = max(
        (float(r["log_used_pct"]) for r, _ in affected if r.get("log_used_pct") is not None),
        default=0.0,
    )
    blocked_reuse = tuple(
        f"{r.get('database_name')}={r.get('log_reuse_wait_desc')}"
        for r, reason in affected if reason == "blocked"
    )
    severity = (
        "critical" if worst_pct >= settings.log_used_critical_pct or blocked_reuse
        else "warning"
    )

    evidence = []
    for row, reason in affected[:8]:
        if reason == "full":
            evidence.append(
                f"{row.get('database_name')} transaction log {float(row['log_used_pct']):.1f}% used "
                f"(sys.dm_os_performance_counters, Percent Log Used)."
            )
        else:
            evidence.append(
                f"{row.get('database_name')} log cannot truncate: log_reuse_wait_desc = "
                f"{row.get('log_reuse_wait_desc')} (sys.databases). Recovery model "
                f"{row.get('recovery_model')}."
            )

    return [Condition(
        code=ConditionCode.LOG_GROWTH,
        severity=severity,
        title=f"Transaction log pressure on {len(affected)} database(s)",
        detail=(
            f"{', '.join(names)} show log growth pressure"
            + (f"; reuse blocked by {', '.join(blocked_reuse)}" if blocked_reuse else "")
            + "."
        ),
        facts=MappingProxyType({
            "affected_database_count": len(affected),
            "database_names": names,
            "max_log_used_pct": worst_pct,
            "log_reuse_blockers": blocked_reuse,
        }),
        evidence=tuple(evidence),
        scope=", ".join(names),
        hold_off=(
            "Do not shrink the log file first. Shrinking before the reuse blocker is "
            "cleared frees nothing, and the file grows straight back with the VLF "
            "fragmentation that shrink-grow cycles cause.",
            "Do not switch recovery model to SIMPLE to force truncation unless the "
            "point-in-time recovery requirement for that database has been waived in "
            "writing. It breaks the log chain.",
        ),
    )]


def _detect_disk_pressure(snapshot: Mapping[str, Any]) -> list[Condition]:
    disk = _section(snapshot, "disk_usage")
    if not disk:
        return []

    hot = [
        v for v in (disk.get("volumes") or ())
        if float(v.get("used_pct") or 0) >= settings.disk_warning_pct
    ]
    if not hot:
        return []

    worst = max(float(v["used_pct"]) for v in hot)
    severity = "critical" if worst >= settings.disk_critical_pct else "warning"
    # volume_label is always populated; volume_mount_point is NULL on Linux, and
    # a generated script that filters on the string "None" matches nothing.
    mounts = tuple(
        str(v.get("volume_label") or v.get("volume_mount_point") or "(unnamed volume)")
        for v in hot
    )
    real_mount_points = tuple(
        str(v["volume_mount_point"]) for v in hot if v.get("volume_mount_point")
    )

    evidence = [
        f"{v.get('volume_label') or v.get('volume_mount_point')} is "
        f"{float(v.get('used_pct')):.1f}% used, "
        f"{float(v.get('available_gb') or 0):.1f} GB free of "
        f"{float(v.get('total_gb') or 0):.1f} GB (sys.dm_os_volume_stats)."
        for v in hot[:8]
    ]

    return [Condition(
        code=ConditionCode.DISK_PRESSURE,
        severity=severity,
        title=f"Disk pressure on {', '.join(mounts)}",
        detail=f"Highest volume usage {worst:.1f}% against a {settings.disk_warning_pct:.0f}% threshold.",
        facts=MappingProxyType({
            "volume_count": len(hot),
            "max_used_pct": worst,
            "volume_mount_points": mounts,
            "queryable_mount_points": real_mount_points,
            "min_available_gb": min(float(v.get("available_gb") or 0) for v in hot),
            "warning_threshold_pct": settings.disk_warning_pct,
        }),
        evidence=tuple(evidence),
        scope=", ".join(mounts),
        hold_off=(
            "Do not delete backup files to reclaim space before confirming they are "
            "already copied off-box and outside the retention window. That is the one "
            "action here that cannot be undone.",
            "Do not run DBCC SHRINKFILE on a data file during business hours. It is "
            "single-threaded, fully logged, and leaves index fragmentation behind.",
        ),
    )]


# Wait types that indicate a real resource problem, and what each one means.
# Anything not in this map is reported by wait time but not classified.
ACTIONABLE_WAITS: Mapping[str, str] = MappingProxyType({
    "LCK_M_S": "shared-lock waits: readers blocked by an uncommitted writer",
    "LCK_M_X": "exclusive-lock waits: writers queued behind another writer",
    "LCK_M_U": "update-lock waits: contention on the same rows",
    "LCK_M_IX": "intent-exclusive lock waits: page or table level contention",
    "PAGEIOLATCH_SH": "reads waiting on storage: data pages fetched from disk",
    "PAGEIOLATCH_EX": "writes waiting on storage",
    "WRITELOG": "commits waiting on log-file storage latency",
    "IO_COMPLETION": "non-data file I/O waits",
    "ASYNC_NETWORK_IO": "the client is not consuming results fast enough",
    "RESOURCE_SEMAPHORE": "queries queued waiting for a memory grant",
    "SOS_SCHEDULER_YIELD": "CPU pressure: tasks yielding the scheduler",
    "CXPACKET": "parallelism skew across worker threads",
    "CXCONSUMER": "parallelism: consumer waiting on producer",
    "THREADPOOL": "worker thread exhaustion - often a symptom of blocking",
    "HADR_SYNC_COMMIT": "synchronous AG replica commit latency",
    "PAGELATCH_UP": "in-memory page contention, often tempdb allocation",
})

# A wait spike only means something relative to the sampling window. Below this
# share of the interval, it is noise on an idle instance.
WAIT_SPIKE_MIN_SHARE = 0.25
WAIT_SPIKE_CRITICAL_SHARE = 0.75


def _detect_wait_spike(snapshot: Mapping[str, Any]) -> list[Condition]:
    waits = _section(snapshot, "wait_stats")
    if not waits:
        return []
    # Cumulative-since-restart numbers cannot show a spike. Only delta mode can.
    if waits.get("mode") != "delta":
        return []
    elapsed = float(waits.get("elapsed_seconds") or 0)
    if elapsed <= 0:
        return []

    top = list(waits.get("top_waits") or ())
    spikes = []
    for wait in top[:5]:
        wait_type = str(wait.get("wait_type"))
        if wait_type not in ACTIONABLE_WAITS:
            continue
        share = float(wait.get("wait_seconds") or 0) / elapsed
        if share >= WAIT_SPIKE_MIN_SHARE:
            spikes.append((wait, share))
    if not spikes:
        return []

    worst_wait, worst_share = spikes[0]
    wait_type = str(worst_wait.get("wait_type"))
    severity = "critical" if worst_share >= WAIT_SPIKE_CRITICAL_SHARE else "warning"

    evidence = [
        f"{w.get('wait_type')} accumulated {float(w.get('wait_seconds')):.1f}s of waits "
        f"across {w.get('waiting_tasks_count')} task(s) in a {elapsed:.0f}s window "
        f"({share:.1f}x the window) - {ACTIONABLE_WAITS[str(w.get('wait_type'))]}."
        for w, share in spikes[:5]
    ]

    return [Condition(
        code=ConditionCode.WAIT_SPIKE,
        severity=severity,
        title=f"Wait spike: {wait_type}",
        detail=(
            f"{wait_type} is the dominant wait in the last {elapsed:.0f}s window "
            f"({ACTIONABLE_WAITS[wait_type]})."
        ),
        facts=MappingProxyType({
            "dominant_wait_type": wait_type,
            "dominant_wait_seconds": float(worst_wait.get("wait_seconds") or 0),
            "waiting_tasks_count": int(worst_wait.get("waiting_tasks_count") or 0),
            "window_seconds": elapsed,
            "wait_share_of_window": round(worst_share, 2),
            "spiking_wait_types": tuple(str(w.get("wait_type")) for w, _ in spikes),
        }),
        evidence=tuple(evidence),
        scope="instance",
        hold_off=(
            "Do not clear the plan cache or run DBCC FREEPROCCACHE to 'reset' waits. It "
            "forces a recompile storm on a server that is already under pressure.",
        ),
    )]


def _detect_long_running(snapshot: Mapping[str, Any]) -> list[Condition]:
    long_running = _section(snapshot, "long_running_queries")
    if not long_running:
        return []

    # Blocked requests belong to BLOCKING_CHAIN, not here. Counting them twice
    # would double-rank the same incident.
    queries = [
        q for q in (long_running.get("queries") or ())
        if not q.get("blocking_session_id")
        and float(q.get("elapsed_seconds") or 0) >= settings.long_query_warning_seconds
    ]
    if not queries:
        return []

    worst = max(queries, key=lambda q: float(q.get("elapsed_seconds") or 0))
    worst_elapsed = float(worst.get("elapsed_seconds") or 0)
    severity = "critical" if worst_elapsed >= settings.long_query_critical_seconds else "warning"

    evidence = [
        f"Session {q.get('session_id')} running {float(q.get('elapsed_seconds')):.0f}s "
        f"({float(q.get('cpu_seconds') or 0):.0f}s CPU, {q.get('logical_reads')} logical reads) "
        f"in {q.get('database_name')} as {q.get('login_name')} via {q.get('program_name')}."
        for q in sorted(queries, key=lambda q: -float(q.get("elapsed_seconds") or 0))[:5]
    ]
    statement = (worst.get("current_statement") or "").strip()
    if statement:
        evidence.append(f"Longest-running statement: {statement[:400]}")

    return [Condition(
        code=ConditionCode.LONG_RUNNING_REQUEST,
        severity=severity,
        title=f"{len(queries)} request(s) running longer than {settings.long_query_warning_seconds}s",
        detail=(
            f"Longest is session {worst.get('session_id')} at {worst_elapsed:.0f}s in "
            f"{worst.get('database_name')}."
        ),
        facts=MappingProxyType({
            "long_running_count": len(queries),
            "longest_elapsed_seconds": worst_elapsed,
            "longest_session_id": worst.get("session_id"),
            "longest_cpu_seconds": float(worst.get("cpu_seconds") or 0),
            "longest_statement": statement[:400] or None,
            "database_names": tuple(sorted({
                str(q.get("database_name")) for q in queries if q.get("database_name")
            })),
            "threshold_seconds": settings.long_query_warning_seconds,
        }),
        evidence=tuple(evidence),
        scope=f"session {worst.get('session_id')} / {worst.get('database_name')}",
        hold_off=(
            "Do not kill a long-running request that is not blocking anything until you "
            "know whether it is a scheduled maintenance task. Killing an index rebuild "
            "or a large DELETE starts a rollback that runs longer than the statement did.",
        ),
    )]


_DETECTORS = (
    _detect_blocking,
    _detect_agent_jobs,
    _detect_backup_age,
    _detect_log_growth,
    _detect_disk_pressure,
    _detect_wait_spike,
    _detect_long_running,
)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def detect_conditions(snapshot: Mapping[str, Any]) -> tuple[Condition, ...]:
    """Return every condition present in a snapshot, ranked by blast radius.

    Pure: same snapshot in, same conditions out, apart from detected_at.
    """
    found: list[Condition] = []
    for detector in _DETECTORS:
        found.extend(detector(snapshot))
    return rank_conditions(_deduplicate(found))


def _deduplicate(conditions: Sequence[Condition]) -> list[Condition]:
    """Drop conditions that are another condition seen from a second angle.

    A blocking chain shows up in wait statistics as LCK_ wait time, because it
    is the same event measured differently. Reporting both makes a DBA triage
    one incident twice and dilutes the ranking. The lock wait is the symptom;
    the chain is the condition, and the chain carries the head blocker.
    """
    codes = {c.code for c in conditions}
    if ConditionCode.BLOCKING_CHAIN not in codes:
        return list(conditions)
    return [
        c for c in conditions
        if not (
            c.code is ConditionCode.WAIT_SPIKE
            and str(c.facts.get("dominant_wait_type", "")).startswith("LCK_")
        )
    ]


def rank_conditions(conditions: Sequence[Condition]) -> tuple[Condition, ...]:
    """Order conditions by what to deal with first: blast radius, not loudness.

    Deliberately not severity-first. Severity says how far past a threshold a
    number is right now; blast radius says what happens if this is left alone.
    A database 31 hours outside its backup window is only a "warning" by
    threshold, and it still outranks a "critical" failed job, because one of
    them is a recoverability exposure and the other is a job that can be
    re-run. Severity contributes +10 to the score, so the critical form of a
    condition always outranks its warning form.

    Total and stable: code breaks any remaining tie. The UI renders this order;
    nothing else chooses it.
    """
    return tuple(sorted(
        conditions,
        key=lambda c: (-c.impact_score, SEVERITY_RANK.get(c.severity, 9), c.code.value),
    ))


def failed_checks(snapshot: Mapping[str, Any]) -> tuple[str, ...]:
    """Sections whose query errored.

    A check that could not run is neither healthy nor a condition. Surfacing
    these separately is the difference between "nothing is wrong" and "I could
    not tell".
    """
    return tuple(
        key for key in (
            "server_health", "blocking", "wait_stats", "long_running_queries",
            "agent_jobs", "disk_usage", "database_status",
        )
        if isinstance(snapshot.get(key), Mapping) and "error" in snapshot[key]
    )


def condition_to_dict(condition: Condition) -> dict:
    """Serialise for the API. Kept out of the dataclass so the type stays frozen."""
    return {
        "code": condition.code.value,
        "severity": condition.severity,
        "title": condition.title,
        "detail": condition.detail,
        "scope": condition.scope,
        "impact_score": condition.impact_score,
        "facts": dict(condition.facts),
        "evidence": list(condition.evidence),
        "hold_off": list(condition.hold_off),
        "detected_at": condition.detected_at,
    }
