"""Condition detection is deterministic and comes from code, not from a model."""

from __future__ import annotations

import dataclasses

import pytest

from core.conditions import (
    Condition,
    ConditionCode,
    detect_conditions,
    failed_checks,
    rank_conditions,
)


def codes(conditions) -> list[str]:
    return [c.code.value for c in conditions]


def test_healthy_snapshot_produces_no_conditions(healthy_snapshot):
    assert detect_conditions(healthy_snapshot) == ()


def test_blocking_chain_is_detected_with_the_head_blocker(blocking_snapshot):
    found = detect_conditions(blocking_snapshot)
    assert codes(found) == [ConditionCode.BLOCKING_CHAIN.value]

    condition = found[0]
    assert condition.severity == "critical"          # 412s is past the 120s threshold
    assert condition.facts["head_blocker_session_id"] == 62
    assert condition.facts["blocked_session_count"] == 4
    assert "Sales.OrderLines" in condition.facts["head_blocker_statement"]
    # The statement holding the lock has to be in the evidence a DBA reads.
    assert any("Sales.OrderLines" in line for line in condition.evidence)
    assert any("session 62" in line for line in condition.evidence)


def test_detection_is_pure(multi_condition_snapshot):
    """Same snapshot in, same verdicts out. Nothing here samples anything live."""
    first = detect_conditions(multi_condition_snapshot)
    second = detect_conditions(multi_condition_snapshot)
    assert codes(first) == codes(second)
    assert [c.severity for c in first] == [c.severity for c in second]
    assert [c.impact_score for c in first] == [c.impact_score for c in second]


def test_conditions_are_ranked_by_blast_radius(multi_condition_snapshot):
    found = detect_conditions(multi_condition_snapshot)
    ordered = codes(found)

    # Everything critical here, so blast radius decides. A volume that will stop
    # the instance accepting writes outranks a blocking chain, which outranks a
    # failed job.
    assert ordered[0] == ConditionCode.DISK_PRESSURE.value
    assert ordered.index(ConditionCode.LOG_GROWTH.value) < ordered.index(
        ConditionCode.BLOCKING_CHAIN.value
    )
    assert ordered.index(ConditionCode.BLOCKING_CHAIN.value) < ordered.index(
        ConditionCode.AGENT_JOB_FAILURE.value
    )


def test_ranking_is_by_blast_radius_not_by_severity(multi_condition_snapshot):
    """A recoverability exposure outranks a louder but re-runnable failure.

    BACKUP_AGE_EXCEEDED is only a "warning" by threshold and still comes before
    a "critical" failed Agent job, because one of them means we cannot restore
    and the other means a job needs re-running.
    """
    found = detect_conditions(multi_condition_snapshot)
    ordered = codes(found)
    assert [c.impact_score for c in found] == sorted(
        (c.impact_score for c in found), reverse=True
    )

    backup = ordered.index(ConditionCode.BACKUP_AGE_EXCEEDED.value)
    job = ordered.index(ConditionCode.AGENT_JOB_FAILURE.value)
    assert found[backup].severity == "warning"
    assert found[job].severity == "critical"
    assert backup < job


def test_a_critical_condition_outranks_its_own_warning_form(blocking_snapshot):
    """Severity still counts: it is worth +10 inside the blast radius score."""
    snapshot = {**blocking_snapshot}
    critical = detect_conditions(snapshot)[0]

    quieter = {**blocking_snapshot}
    quieter["blocking"] = {**snapshot["blocking"], "max_wait_seconds": 45}
    warning = detect_conditions(quieter)[0]

    assert critical.severity == "critical" and warning.severity == "warning"
    assert critical.impact_score > warning.impact_score


def test_ranking_is_a_total_order_regardless_of_input_order(multi_condition_snapshot):
    found = list(detect_conditions(multi_condition_snapshot))
    assert codes(rank_conditions(found)) == codes(rank_conditions(list(reversed(found))))


def test_every_condition_carries_hold_off_guidance(multi_condition_snapshot):
    """Saying what not to do yet is half of the judgment being encoded."""
    for condition in detect_conditions(multi_condition_snapshot):
        assert condition.hold_off, f"{condition.code.value} has no hold_off guidance"


def test_log_growth_fires_on_a_blocked_reuse_even_when_percentage_is_low(blocking_snapshot):
    snapshot = {**blocking_snapshot}
    databases = [dict(d) for d in snapshot["database_status"]["databases"]]
    databases[0]["log_used_pct"] = 12.0
    databases[0]["log_reuse_wait_desc"] = "ACTIVE_TRANSACTION"
    snapshot["database_status"] = {**snapshot["database_status"], "databases": databases}

    found = [c for c in detect_conditions(snapshot) if c.code is ConditionCode.LOG_GROWTH]
    assert found, "a log that cannot truncate is a condition whatever the percentage says"
    assert found[0].severity == "critical"
    assert "WideWorldImporters=ACTIVE_TRANSACTION" in found[0].facts["log_reuse_blockers"]


def test_blocked_sessions_are_not_double_counted_as_long_running(blocking_snapshot):
    """A blocked request is a blocking incident, not a separate slow-query one."""
    snapshot = {**blocking_snapshot}
    snapshot["long_running_queries"] = {
        "threshold_seconds": 30, "count": 1,
        "queries": [{
            "session_id": 71, "blocking_session_id": 62, "elapsed_seconds": 412,
            "cpu_seconds": 0, "logical_reads": 12, "database_name": "WideWorldImporters",
            "login_name": "reporting", "program_name": "PowerBI",
            "current_statement": "SELECT * FROM Sales.OrderLines",
        }],
    }
    assert ConditionCode.LONG_RUNNING_REQUEST.value not in codes(detect_conditions(snapshot))


def test_lock_wait_spike_is_not_reported_alongside_the_blocking_chain(blocking_snapshot):
    """The lock wait is the chain measured differently, not a second incident."""
    found = detect_conditions(blocking_snapshot)
    assert ConditionCode.BLOCKING_CHAIN.value in codes(found)
    assert ConditionCode.WAIT_SPIKE.value not in codes(found)


def test_a_non_lock_wait_spike_still_fires_during_blocking(blocking_snapshot):
    """Only the duplicate view is suppressed, not unrelated resource waits."""
    snapshot = {**blocking_snapshot}
    snapshot["wait_stats"] = {
        "mode": "delta", "elapsed_seconds": 60.0,
        "top_waits": [{"wait_type": "PAGEIOLATCH_SH", "wait_seconds": 51.0,
                       "waiting_tasks_count": 900, "resource_wait_seconds": 50.0,
                       "signal_wait_seconds": 1.0}],
    }
    found = codes(detect_conditions(snapshot))
    assert ConditionCode.BLOCKING_CHAIN.value in found
    assert ConditionCode.WAIT_SPIKE.value in found


def test_cumulative_waits_never_produce_a_spike(blocking_snapshot):
    """Totals since restart cannot show a spike; only a delta window can."""
    snapshot = {**blocking_snapshot}
    snapshot["wait_stats"] = {
        "mode": "cumulative", "elapsed_seconds": None,
        "top_waits": [{"wait_type": "LCK_M_S", "wait_seconds": 9_000_000.0,
                       "waiting_tasks_count": 4000}],
    }
    assert ConditionCode.WAIT_SPIKE.value not in codes(detect_conditions(snapshot))


def test_a_failed_check_is_not_reported_as_healthy(blocking_snapshot):
    """"I could not tell" must never render as "nothing is wrong"."""
    snapshot = {**blocking_snapshot}
    snapshot["disk_usage"] = {"error": "Login failed for user 'sqlguardian'.",
                              "collected_at": "2026-08-30T02:14:00"}

    assert "disk_usage" in failed_checks(snapshot)
    assert ConditionCode.DISK_PRESSURE.value not in codes(detect_conditions(snapshot))


def test_conditions_are_immutable(blocking_snapshot):
    condition = detect_conditions(blocking_snapshot)[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        condition.severity = "healthy"          # type: ignore[misc]
    with pytest.raises(TypeError):
        condition.facts["blocked_session_count"] = 0    # type: ignore[index]


def test_impact_score_is_a_function_of_the_condition_only(blocking_snapshot):
    condition = detect_conditions(blocking_snapshot)[0]
    twin = Condition(
        code=condition.code,
        severity=condition.severity,
        title="a different title entirely",
        detail="different prose",
        facts=condition.facts,
        evidence=(),
        scope="different scope",
    )
    assert twin.impact_score == condition.impact_score


def test_a_snapshot_where_every_check_failed_is_not_healthy(blocking_snapshot):
    """"I could not reach the instance" must never roll up to "nothing is wrong"."""
    from core.monitor import get_full_snapshot
    import core.monitor as monitor

    def unreachable(*args, **kwargs):
        raise ConnectionError("[primary] is unreachable and inside its 30s cooldown.")

    original = monitor.db_manager.execute_query
    monitor.db_manager.execute_query = unreachable
    try:
        snapshot = get_full_snapshot()
    finally:
        monitor.db_manager.execute_query = original

    assert snapshot["overall_severity"] == "unknown"
    assert len(snapshot["failed_checks"]) == 7
    assert detect_conditions(snapshot) == ()
    assert failed_checks(snapshot) == tuple(snapshot["failed_checks"])


# ---------------------------------------------------------------------------
# Regressions found by running against a real SQL Server
# ---------------------------------------------------------------------------

def test_the_head_of_the_chain_is_not_a_session_that_is_itself_blocked():
    """Found live: lock queues make an intermediate blocker look like the head.

    With A blocking B, and B blocking C and D, ordering candidates by how many
    sessions they block puts B first - B blocks two, A blocks one. B is itself a
    victim, so naming it sends the DBA after the wrong session and killing it
    would not release the chain. The query orders is_itself_blocked first; this
    asserts the detector honours that ordering.
    """
    snapshot = {
        "blocking": {
            "blocked_session_count": 3,
            "head_blocker_count": 2,
            "max_wait_seconds": 200,
            "head_blockers": [
                # As the fixed query returns them: true head first.
                {"session_id": 92, "login_name": "app", "is_itself_blocked": 0,
                 "sessions_blocked": 1, "is_idle": 1, "open_transaction_count": 1,
                 "idle_seconds": 13, "current_sql": "UPDATE dbo.Orders SET Amount = Amount"},
                {"session_id": 93, "login_name": "app", "is_itself_blocked": 1,
                 "sessions_blocked": 2, "is_idle": 0, "current_sql": "SELECT ..."},
            ],
            "blocked_sessions": [
                {"session_id": 93, "wait_seconds": 200, "wait_type": "LCK_M_U",
                 "database_name": "GuardianTest_OLTP"},
                {"session_id": 94, "wait_seconds": 190, "wait_type": "LCK_M_U",
                 "database_name": "GuardianTest_OLTP"},
                {"session_id": 95, "wait_seconds": 180, "wait_type": "LCK_M_U",
                 "database_name": "GuardianTest_OLTP"},
            ],
        },
    }
    condition = detect_conditions(snapshot)[0]

    assert condition.facts["head_blocker_session_id"] == 92, "named a victim as the head"
    assert condition.facts["intermediate_blocker_count"] == 1
    assert any("this is a chain" in line for line in condition.evidence)
    assert any("93" in line for line in condition.evidence)


def test_an_idle_head_blocker_still_shows_the_statement_it_ran():
    """Found live: the commonest real head blocker has no active request.

    An application that opened a transaction and went idle has no row in
    sys.dm_exec_requests, so the statement came back blank - the one fact a DBA
    most needs. The query falls back to most_recent_sql_handle, and the evidence
    says who owns the problem.
    """
    snapshot = {
        "blocking": {
            "blocked_session_count": 3,
            "head_blocker_count": 1,
            "max_wait_seconds": 200,
            "head_blockers": [{
                "session_id": 92, "login_name": "app_svc", "program_name": "OrderSync",
                "status": "sleeping", "is_idle": 1, "open_transaction_count": 1,
                "idle_seconds": 13, "sessions_blocked": 3, "is_itself_blocked": 0,
                "current_sql": "UPDATE TOP (50) dbo.Orders SET Amount = Amount",
            }],
            "blocked_sessions": [
                {"session_id": 93, "wait_seconds": 200, "wait_type": "LCK_M_U",
                 "database_name": "GuardianTest_OLTP"},
            ],
        },
    }
    condition = detect_conditions(snapshot)[0]

    assert condition.facts["head_blocker_is_idle"] is True
    assert condition.facts["head_blocker_open_transactions"] == 1
    assert "UPDATE TOP (50)" in condition.facts["head_blocker_statement"]
    # Labelled as the last statement, not as one currently holding a lock.
    assert any("Last statement it ran" in line for line in condition.evidence)
    assert any("application problem" in line for line in condition.evidence)


def test_an_active_head_blocker_is_still_labelled_as_holding_the_lock(blocking_snapshot):
    """The idle path must not relabel a genuinely running blocker."""
    condition = detect_conditions(blocking_snapshot)[0]
    assert condition.facts["head_blocker_is_idle"] is False
    assert any("Statement holding the lock" in line for line in condition.evidence)


def test_a_volume_with_no_mount_point_still_gets_a_usable_name():
    """Found live: SQL Server on Linux reports NULL for every volume name column.

    The condition read "Disk pressure on None" and the generated script filtered
    on the literal string 'None', which matches no volume at all.
    """
    from core.monitor import _volume_label

    linux_row = {
        "volume_mount_point": None, "logical_volume_name": None,
        "sample_file_path": "/var/opt/mssql/data/GuardianTest_OLTP.mdf",
    }
    assert _volume_label(linux_row) == "/var/opt/mssql/data"

    windows_row = {"volume_mount_point": "E:\\", "logical_volume_name": "Data",
                   "sample_file_path": "E:\\SQL\\data\\wwi.mdf"}
    assert _volume_label(windows_row) == "E:\\"

    assert _volume_label({}) == "(unnamed volume)"


def test_disk_pressure_never_reports_a_none_volume():
    snapshot = {
        "disk_usage": {
            "volume_count": 1, "max_used_pct": 96.0, "severity": "critical",
            "volumes": [{
                "volume_mount_point": None, "logical_volume_name": None,
                "volume_label": "/var/opt/mssql/data",
                "used_pct": 96.0, "total_gb": 1006.9, "available_gb": 40.3,
            }],
        },
    }
    condition = detect_conditions(snapshot)[0]
    assert "None" not in condition.title
    assert condition.facts["volume_mount_points"] == ("/var/opt/mssql/data",)
    # Nothing to filter a T-SQL script on, and the action says so rather than
    # emitting a predicate that cannot match.
    assert condition.facts["queryable_mount_points"] == ()

    from core.actions import build_action_plan
    script = [a for a in build_action_plan(condition)["actions"]
              if "consuming" in a["action"]][0]["tsql"]
    assert "N'None'" not in script
    assert "reports no volume mount point" in script


def test_the_agent_job_query_does_not_need_an_extra_execute_grant():
    """Found live: msdb.dbo.agent_datetime needs EXECUTE, which
    SQLAgentReaderRole does not include - one more grant purely to format a
    date. The conversion is inline instead."""
    import core.monitor as monitor

    assert "agent_datetime" not in monitor.AGENT_JOBS_SQL
    from core.actions import ACTION_CATALOG
    from core.conditions import ConditionCode

    actions = ACTION_CATALOG[ConditionCode.AGENT_JOB_FAILURE](
        {"failed_job_names": ("Nightly Backup",), "failed_job_count": 1}
    )
    for action in actions:
        assert "agent_datetime" not in (action.tsql or "")
