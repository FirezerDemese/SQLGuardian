"""Shared fixtures. Nothing here touches a real SQL Server or a real model."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SAMPLES = ROOT / "docs" / "runbook-samples"


@pytest.fixture
def blocking_snapshot() -> dict:
    """A snapshot with a real blocking incident in it, shaped like core/monitor output."""
    return {
        "snapshot_time": "2026-08-30T02:14:00+00:00",
        "instance": "primary",
        "overall_severity": "critical",
        "server_health": {
            "server_name": "SQLPROD01",
            "uptime_hours": 412,
            "cpu": {"sql_cpu_pct": 38, "system_idle_pct": 55, "severity": "healthy"},
            "memory": {"total_mb": 65536, "available_mb": 20480, "used_pct": 68.8,
                       "state": "Available physical memory is high", "severity": "healthy"},
        },
        "blocking": {
            "blocked_session_count": 4,
            "head_blocker_count": 1,
            "max_wait_seconds": 412,
            "severity": "critical",
            "head_blockers": [{
                "session_id": 62,
                "login_name": "APP\\svc_ordersync",
                "host_name": "APPWEB03",
                "program_name": "OrderSync",
                "status": "sleeping",
                "sessions_blocked": 4,
                "current_sql": "UPDATE Sales.OrderLines SET PickedQty = PickedQty - 1 "
                               "WHERE OrderLineID BETWEEN 900000 AND 940000",
            }],
            "blocked_sessions": [
                {"session_id": 71, "blocking_session_id": 62, "wait_type": "LCK_M_S",
                 "wait_seconds": 412, "database_name": "WideWorldImporters",
                 "current_statement": "SELECT * FROM Sales.OrderLines WHERE OrderID = 41219"},
                {"session_id": 74, "blocking_session_id": 62, "wait_type": "LCK_M_S",
                 "wait_seconds": 388, "database_name": "WideWorldImporters",
                 "current_statement": "SELECT TOP 100 * FROM Sales.OrderLines"},
                {"session_id": 79, "blocking_session_id": 62, "wait_type": "LCK_M_U",
                 "wait_seconds": 201, "database_name": "WideWorldImporters",
                 "current_statement": "UPDATE Sales.OrderLines SET Status = 2"},
                {"session_id": 83, "blocking_session_id": 62, "wait_type": "LCK_M_S",
                 "wait_seconds": 96, "database_name": "WideWorldImporters",
                 "current_statement": "SELECT COUNT(*) FROM Sales.OrderLines"},
            ],
        },
        "wait_stats": {
            "mode": "delta",
            "elapsed_seconds": 60.0,
            "top_waits": [
                {"wait_type": "LCK_M_S", "wait_seconds": 1180.4, "waiting_tasks_count": 3,
                 "resource_wait_seconds": 1180.0, "signal_wait_seconds": 0.4},
                {"wait_type": "WRITELOG", "wait_seconds": 4.2, "waiting_tasks_count": 610,
                 "resource_wait_seconds": 3.9, "signal_wait_seconds": 0.3},
            ],
        },
        "long_running_queries": {"threshold_seconds": 30, "count": 0, "queries": []},
        "agent_jobs": {
            "total_jobs": 9, "failed_count": 0, "running_count": 1,
            "severity": "healthy", "jobs": [], "running_jobs": [], "failed_jobs": [],
        },
        "disk_usage": {
            "volume_count": 3, "max_used_pct": 61.0, "severity": "healthy",
            "volumes": [{"volume_mount_point": "E:\\", "used_pct": 61.0,
                         "total_gb": 2048.0, "available_gb": 798.7, "severity": "healthy"}],
        },
        "database_status": {
            "database_count": 2, "databases_missing_backup": 0, "severity": "healthy",
            "databases": [
                {"database_name": "WideWorldImporters", "state": "ONLINE",
                 "recovery_model": "FULL", "log_reuse_wait_desc": "NOTHING",
                 "hours_since_full_backup": 6, "size_mb": 4096.0,
                 "log_size_mb": 2048.0, "log_used_mb": 410.0, "log_used_pct": 20.0},
                {"database_name": "AdventureWorks2022", "state": "ONLINE",
                 "recovery_model": "SIMPLE", "log_reuse_wait_desc": "NOTHING",
                 "hours_since_full_backup": 11, "size_mb": 8192.0,
                 "log_size_mb": 1024.0, "log_used_mb": 92.0, "log_used_pct": 9.0},
            ],
            "databases_missing_backup_names": [],
        },
    }


@pytest.fixture
def healthy_snapshot(blocking_snapshot) -> dict:
    """The same instance with nothing wrong."""
    snapshot = {**blocking_snapshot}
    snapshot["overall_severity"] = "healthy"
    snapshot["blocking"] = {
        "blocked_session_count": 0, "head_blocker_count": 0, "max_wait_seconds": 0,
        "severity": "healthy", "head_blockers": [], "blocked_sessions": [],
    }
    snapshot["wait_stats"] = {
        "mode": "delta", "elapsed_seconds": 60.0,
        "top_waits": [{"wait_type": "WRITELOG", "wait_seconds": 3.1,
                       "waiting_tasks_count": 500, "resource_wait_seconds": 3.0,
                       "signal_wait_seconds": 0.1}],
    }
    return snapshot


@pytest.fixture
def multi_condition_snapshot(blocking_snapshot) -> dict:
    """Blocking, a failed backup job, stale backups, log pressure and a full volume."""
    snapshot = {**blocking_snapshot}
    snapshot["agent_jobs"] = {
        "total_jobs": 9, "failed_count": 1, "running_count": 0, "severity": "critical",
        "jobs": [], "running_jobs": [],
        "failed_jobs": [{
            "job_name": "WWI Nightly Full Backup", "last_run_status": "Failed",
            "last_run_time": "2026-08-29 22:00:04",
            "last_run_message": "Write on 'E:\\Backup\\WWI_full.bak' failed: "
                                "112(There is not enough space on the disk.)",
        }],
    }
    snapshot["disk_usage"] = {
        "volume_count": 3, "max_used_pct": 96.4, "severity": "critical",
        "volumes": [
            {"volume_mount_point": "E:\\", "used_pct": 96.4, "total_gb": 2048.0,
             "available_gb": 73.7, "severity": "critical"},
            {"volume_mount_point": "L:\\", "used_pct": 42.0, "total_gb": 512.0,
             "available_gb": 297.0, "severity": "healthy"},
        ],
    }
    snapshot["database_status"] = {
        "database_count": 2, "databases_missing_backup": 1, "severity": "critical",
        "databases": [
            {"database_name": "WideWorldImporters", "state": "ONLINE",
             "recovery_model": "FULL", "log_reuse_wait_desc": "LOG_BACKUP",
             "hours_since_full_backup": 31, "size_mb": 4096.0,
             "log_size_mb": 2048.0, "log_used_mb": 1925.0, "log_used_pct": 94.0},
            {"database_name": "AdventureWorks2022", "state": "ONLINE",
             "recovery_model": "SIMPLE", "log_reuse_wait_desc": "NOTHING",
             "hours_since_full_backup": 11, "size_mb": 8192.0,
             "log_size_mb": 1024.0, "log_used_mb": 92.0, "log_used_pct": 9.0},
        ],
        "databases_missing_backup_names": ["WideWorldImporters"],
    }
    return snapshot


@pytest.fixture
def store(tmp_path):
    """A runbook store loaded with the sample corpus, isolated per test."""
    from core.runbooks import RunbookStore

    store = RunbookStore(tmp_path / "runbooks")
    for path in sorted(SAMPLES.iterdir()):
        if path.is_file():
            store.ingest_path(path)
    return store


@pytest.fixture
def empty_store(tmp_path):
    from core.runbooks import RunbookStore

    return RunbookStore(tmp_path / "empty-runbooks")
