"""
SQLGuardian - Monitoring Engine
All DMV-based health checks. This is the brain of the project.

Checks covered:
- Server health (CPU, memory, uptime)
- Blocking chains
- Top waits (sys.dm_os_wait_stats)
- Long-running queries
- SQL Agent job status
- Disk / volume usage
- Database status + last backup
- Index fragmentation (light scan)
- Failed logins (ring buffer)
"""

from datetime import datetime
from typing import Optional
from loguru import logger

from core.db_connection import db_manager
from config.settings import settings


# ---------------------------------------------------------------------------
# Return type helpers
# ---------------------------------------------------------------------------

def _severity(value: float, warn: float, crit: float) -> str:
    if value >= crit:
        return "critical"
    if value >= warn:
        return "warning"
    return "healthy"


# ---------------------------------------------------------------------------
# 1. Server Health - CPU, Memory, Uptime
# ---------------------------------------------------------------------------

SERVER_HEALTH_SQL = """
SELECT
    -- CPU via ring buffer snapshot
    (
        SELECT TOP 1
            100 - record.value('(./Record/SchedulerMonitorEvent/SystemHealth/ProcessUtilization)[1]', 'int')
                + record.value('(./Record/SchedulerMonitorEvent/SystemHealth/ProcessUtilization)[1]', 'int')
            AS sql_cpu_pct
        FROM (
            SELECT TOP 1 CONVERT(XML, record) AS record
            FROM sys.dm_os_ring_buffers
            WHERE ring_buffer_type = N'RING_BUFFER_SCHEDULER_MONITOR'
            ORDER BY timestamp DESC
        ) AS rb
    ) AS cpu_pct,

    -- Memory
    physical_memory_in_use_kb / 1024.0 AS memory_used_mb,
    page_fault_count,
    memory_utilization_percentage,

    -- Uptime
    DATEDIFF(MINUTE, sqlserver_start_time, GETDATE()) AS uptime_minutes,
    sqlserver_start_time

FROM sys.dm_os_process_memory
CROSS JOIN (SELECT sqlserver_start_time FROM sys.dm_os_sys_info) si
"""

CPU_ONLY_SQL = """
SELECT
    (SELECT TOP 1
        record.value('(./Record/SchedulerMonitorEvent/SystemHealth/ProcessUtilization)[1]', 'int') AS cpu
     FROM (
         SELECT TOP 1 CONVERT(XML, record) AS record
         FROM sys.dm_os_ring_buffers
         WHERE ring_buffer_type = N'RING_BUFFER_SCHEDULER_MONITOR'
         ORDER BY timestamp DESC
     ) AS rb
    ) AS sql_cpu_pct,
    (SELECT TOP 1
        record.value('(./Record/SchedulerMonitorEvent/SystemHealth/SystemIdle)[1]', 'int') AS idle
     FROM (
         SELECT TOP 1 CONVERT(XML, record) AS record
         FROM sys.dm_os_ring_buffers
         WHERE ring_buffer_type = N'RING_BUFFER_SCHEDULER_MONITOR'
         ORDER BY timestamp DESC
     ) AS rb
    ) AS system_idle_pct
"""

MEMORY_SQL = """
SELECT
    total_physical_memory_kb / 1024 AS total_memory_mb,
    available_physical_memory_kb / 1024 AS available_memory_mb,
    total_page_file_kb / 1024 AS total_pagefile_mb,
    available_page_file_kb / 1024 AS available_pagefile_mb,
    system_memory_state_desc
FROM sys.dm_os_sys_memory
"""

UPTIME_SQL = """
SELECT
    DATEDIFF(HOUR, sqlserver_start_time, GETDATE()) AS uptime_hours,
    sqlserver_start_time,
    @@SERVERNAME AS server_name,
    @@VERSION AS version
FROM sys.dm_os_sys_info
"""


def get_server_health(instance_name: Optional[str] = None) -> dict:
    """Pull CPU, memory, and uptime in one shot."""
    try:
        cpu_rows = db_manager.execute_query(CPU_ONLY_SQL, instance_name)
        mem_rows = db_manager.execute_query(MEMORY_SQL, instance_name)
        uptime_rows = db_manager.execute_query(UPTIME_SQL, instance_name)

        cpu_pct = cpu_rows[0].get("sql_cpu_pct", 0) or 0
        idle_pct = cpu_rows[0].get("system_idle_pct", 100) or 100
        total_mem = mem_rows[0]["total_memory_mb"]
        avail_mem = mem_rows[0]["available_memory_mb"]
        used_mem_pct = round(((total_mem - avail_mem) / total_mem) * 100, 1) if total_mem else 0

        return {
            "collected_at": datetime.utcnow().isoformat(),
            "server_name": uptime_rows[0]["server_name"],
            "uptime_hours": uptime_rows[0]["uptime_hours"],
            "start_time": str(uptime_rows[0]["sqlserver_start_time"]),
            "cpu": {
                "sql_cpu_pct": cpu_pct,
                "system_idle_pct": idle_pct,
                "severity": _severity(cpu_pct, settings.cpu_warning_pct, settings.cpu_critical_pct),
            },
            "memory": {
                "total_mb": total_mem,
                "available_mb": avail_mem,
                "used_pct": used_mem_pct,
                "state": mem_rows[0]["system_memory_state_desc"],
                "severity": _severity(used_mem_pct, settings.memory_warning_pct, settings.memory_critical_pct),
            },
        }
    except Exception as e:
        logger.error(f"get_server_health failed: {e}")
        return {"error": str(e), "collected_at": datetime.utcnow().isoformat()}


# ---------------------------------------------------------------------------
# 2. Blocking Chains
# ---------------------------------------------------------------------------

BLOCKING_SQL = """
SELECT
    r.session_id,
    r.blocking_session_id,
    r.wait_type,
    r.wait_time / 1000 AS wait_seconds,
    r.status,
    r.command,
    DB_NAME(r.database_id) AS database_name,
    s.login_name,
    s.host_name,
    s.program_name,
    SUBSTRING(qt.text, (r.statement_start_offset / 2) + 1,
        ((CASE r.statement_end_offset
            WHEN -1 THEN DATALENGTH(qt.text)
            ELSE r.statement_end_offset
          END - r.statement_start_offset) / 2) + 1
    ) AS current_statement,
    qt.text AS full_batch
FROM sys.dm_exec_requests r
JOIN sys.dm_exec_sessions s ON r.session_id = s.session_id
CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) qt
WHERE r.blocking_session_id > 0
  AND s.is_user_process = 1
ORDER BY r.wait_time DESC
"""

HEAD_BLOCKERS_SQL = """
SELECT
    s.session_id,
    s.login_name,
    s.host_name,
    s.program_name,
    s.status,
    r.wait_type,
    r.cpu_time,
    r.reads,
    r.writes,
    COUNT(*) OVER (PARTITION BY s.session_id) AS sessions_blocked,
    SUBSTRING(qt.text, 1, 500) AS current_sql
FROM sys.dm_exec_sessions s
LEFT JOIN sys.dm_exec_requests r ON s.session_id = r.session_id
OUTER APPLY (
    SELECT text FROM sys.dm_exec_sql_text(r.sql_handle)
) qt
WHERE s.session_id IN (
    SELECT blocking_session_id
    FROM sys.dm_exec_requests
    WHERE blocking_session_id > 0
)
ORDER BY sessions_blocked DESC
"""


def get_blocking(instance_name: Optional[str] = None) -> dict:
    """Detect active blocking chains and identify head blockers."""
    try:
        blocked = db_manager.execute_query(BLOCKING_SQL, instance_name)
        head_blockers = db_manager.execute_query(HEAD_BLOCKERS_SQL, instance_name)

        max_wait = max((r["wait_seconds"] for r in blocked), default=0)

        return {
            "collected_at": datetime.utcnow().isoformat(),
            "blocked_session_count": len(blocked),
            "head_blocker_count": len(head_blockers),
            "max_wait_seconds": max_wait,
            "severity": _severity(
                max_wait,
                settings.blocking_warning_seconds,
                settings.blocking_critical_seconds,
            ),
            "blocked_sessions": blocked,
            "head_blockers": head_blockers,
        }
    except Exception as e:
        logger.error(f"get_blocking failed: {e}")
        return {"error": str(e), "collected_at": datetime.utcnow().isoformat()}


# ---------------------------------------------------------------------------
# 3. Top Wait Stats
# ---------------------------------------------------------------------------

WAIT_STATS_SQL = """
WITH waits AS (
    SELECT
        wait_type,
        wait_time_ms / 1000.0 AS wait_seconds,
        (wait_time_ms - signal_wait_time_ms) / 1000.0 AS resource_wait_seconds,
        signal_wait_time_ms / 1000.0 AS signal_wait_seconds,
        waiting_tasks_count,
        CASE WHEN waiting_tasks_count > 0
             THEN (wait_time_ms / 1000.0) / waiting_tasks_count
             ELSE 0 END AS avg_wait_seconds
    FROM sys.dm_os_wait_stats
    WHERE wait_type NOT IN (
        -- Benign background waits to exclude
        'SLEEP_TASK','SLEEP_SYSTEMTASK','SLEEP_DBSTARTUP','SLEEP_DCOMSTARTUP',
        'SLEEP_MASTERDBREADY','SLEEP_MASTERMDREADY','SLEEP_MASTERUPGRADED',
        'SLEEP_MSDBSTARTUP','SLEEP_TEMPDBSTARTUP','SLEEP_DBSTARTUP',
        'WAITFOR','WAIT_XTP_OFFLINE_CKPT_NEW_LOG','DISPATCHER_QUEUE_SEMAPHORE',
        'FT_IFTS_SCHEDULER_IDLE_WAIT','XE_DISPATCHER_WAIT','XE_TIMER_EVENT',
        'BROKER_TO_FLUSH','BROKER_TASK_STOP','CLR_AUTO_EVENT',
        'CLR_MANUAL_EVENT','DBMIRROR_EVENTS_QUEUE','SQLTRACE_BUFFER_FLUSH',
        'BROKER_EVENTHANDLER','CHECKPOINT_QUEUE','DBMIRROR_WORKER_QUEUE',
        'HADR_FILESTREAM_IOMGR_IOCOMPLETION','HADR_WORK_QUEUE',
        'ONDEMAND_TASK_QUEUE','REQUEST_FOR_DEADLOCK_SEARCH','RESOURCE_QUEUE',
        'SERVER_IDLE_CHECK','SLEEP_DCOMSTARTUP','SLEEP_MASTERDBREADY',
        'SLEEP_MASTERMDREADY','SLEEP_MASTERUPGRADED','SLEEP_TEMPDBSTARTUP',
        'SNI_HTTP_ACCEPT','SP_SERVER_DIAGNOSTICS_SLEEP','SQLTRACE_INCREMENTAL_FLUSH_SLEEP',
        'WAIT_XTP_OFFLINE_CKPT_NEW_LOG','WAITFOR','XE_DISPATCHER_WAIT',
        'XE_TIMER_EVENT','BROKER_TO_FLUSH','SLEEP_TASK'
    )
      AND wait_time_ms > 0
)
SELECT TOP 15
    wait_type,
    ROUND(wait_seconds, 2) AS wait_seconds,
    ROUND(resource_wait_seconds, 2) AS resource_wait_seconds,
    ROUND(signal_wait_seconds, 2) AS signal_wait_seconds,
    waiting_tasks_count,
    ROUND(avg_wait_seconds, 4) AS avg_wait_seconds
FROM waits
ORDER BY wait_seconds DESC
"""


def get_wait_stats(instance_name: Optional[str] = None) -> dict:
    """Return top 15 wait types, excluding benign background waits."""
    try:
        rows = db_manager.execute_query(WAIT_STATS_SQL, instance_name)
        return {
            "collected_at": datetime.utcnow().isoformat(),
            "top_waits": rows,
        }
    except Exception as e:
        logger.error(f"get_wait_stats failed: {e}")
        return {"error": str(e), "collected_at": datetime.utcnow().isoformat()}


# ---------------------------------------------------------------------------
# 4. Long-Running Queries
# ---------------------------------------------------------------------------

LONG_QUERIES_SQL = """
SELECT
    r.session_id,
    r.status,
    r.command,
    DB_NAME(r.database_id) AS database_name,
    r.cpu_time / 1000 AS cpu_seconds,
    r.total_elapsed_time / 1000 AS elapsed_seconds,
    r.reads,
    r.writes,
    r.logical_reads,
    r.blocking_session_id,
    s.login_name,
    s.host_name,
    s.program_name,
    SUBSTRING(qt.text, (r.statement_start_offset / 2) + 1,
        ((CASE r.statement_end_offset
            WHEN -1 THEN DATALENGTH(qt.text)
            ELSE r.statement_end_offset
          END - r.statement_start_offset) / 2) + 1
    ) AS current_statement
FROM sys.dm_exec_requests r
JOIN sys.dm_exec_sessions s ON r.session_id = s.session_id
CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) qt
WHERE r.total_elapsed_time > 30000   -- > 30 seconds
  AND s.is_user_process = 1
  AND r.session_id <> @@SPID
ORDER BY r.total_elapsed_time DESC
"""


def get_long_running_queries(
    min_elapsed_seconds: int = 30,
    instance_name: Optional[str] = None,
) -> dict:
    """Return currently running queries over the threshold."""
    try:
        rows = db_manager.execute_query(LONG_QUERIES_SQL, instance_name)
        return {
            "collected_at": datetime.utcnow().isoformat(),
            "threshold_seconds": min_elapsed_seconds,
            "count": len(rows),
            "queries": rows,
        }
    except Exception as e:
        logger.error(f"get_long_running_queries failed: {e}")
        return {"error": str(e), "collected_at": datetime.utcnow().isoformat()}


# ---------------------------------------------------------------------------
# 5. SQL Agent Jobs
# ---------------------------------------------------------------------------

AGENT_JOBS_SQL = """
SELECT
    j.name AS job_name,
    j.enabled,
    CASE h.run_status
        WHEN 0 THEN 'Failed'
        WHEN 1 THEN 'Succeeded'
        WHEN 2 THEN 'Retry'
        WHEN 3 THEN 'Cancelled'
        WHEN 4 THEN 'Running'
        ELSE 'Unknown'
    END AS last_run_status,
    msdb.dbo.agent_datetime(h.run_date, h.run_time) AS last_run_time,
    h.run_duration AS run_duration_hhmmss,
    h.message AS last_run_message,
    -- Convert HHMMSS integer to total seconds
    (h.run_duration / 10000 * 3600)
        + ((h.run_duration % 10000) / 100 * 60)
        + (h.run_duration % 100) AS last_run_seconds
FROM msdb.dbo.sysjobs j
LEFT JOIN (
    SELECT jh.*,
           ROW_NUMBER() OVER (PARTITION BY jh.job_id ORDER BY jh.run_date DESC, jh.run_time DESC) AS rn
    FROM msdb.dbo.sysjobhistory jh
    WHERE jh.step_id = 0   -- Job-level outcome only
) h ON j.job_id = h.job_id AND h.rn = 1
ORDER BY last_run_time DESC
"""

RUNNING_JOBS_SQL = """
SELECT
    j.name AS job_name,
    a.start_execution_date AS started_at,
    DATEDIFF(SECOND, a.start_execution_date, GETDATE()) AS running_seconds
FROM msdb.dbo.sysjobactivity a
JOIN msdb.dbo.sysjobs j ON a.job_id = j.job_id
WHERE a.run_requested_date IS NOT NULL
  AND a.stop_execution_date IS NULL
  AND a.session_id = (SELECT MAX(session_id) FROM msdb.dbo.sysjobactivity)
ORDER BY a.start_execution_date
"""


def get_agent_jobs(instance_name: Optional[str] = None) -> dict:
    """Return SQL Agent job statuses and any currently running jobs."""
    try:
        jobs = db_manager.execute_query(AGENT_JOBS_SQL, instance_name)
        running = db_manager.execute_query(RUNNING_JOBS_SQL, instance_name)

        failed_jobs = [j for j in jobs if j["last_run_status"] == "Failed"]

        return {
            "collected_at": datetime.utcnow().isoformat(),
            "total_jobs": len(jobs),
            "failed_count": len(failed_jobs),
            "running_count": len(running),
            "severity": "critical" if failed_jobs else "healthy",
            "jobs": jobs,
            "running_jobs": running,
            "failed_jobs": failed_jobs,
        }
    except Exception as e:
        logger.error(f"get_agent_jobs failed: {e}")
        return {"error": str(e), "collected_at": datetime.utcnow().isoformat()}


# ---------------------------------------------------------------------------
# 6. Disk / Volume Usage
# ---------------------------------------------------------------------------

DISK_USAGE_SQL = """
SELECT DISTINCT
    vs.volume_mount_point,
    vs.file_system_type,
    vs.logical_volume_name,
    ROUND(vs.total_bytes / 1073741824.0, 2) AS total_gb,
    ROUND(vs.available_bytes / 1073741824.0, 2) AS available_gb,
    ROUND((vs.total_bytes - vs.available_bytes) / 1073741824.0, 2) AS used_gb,
    ROUND(
        ((vs.total_bytes - vs.available_bytes) * 100.0) / vs.total_bytes,
        1
    ) AS used_pct
FROM sys.master_files mf
CROSS APPLY sys.dm_os_volume_stats(mf.database_id, mf.file_id) vs
ORDER BY used_pct DESC
"""


def get_disk_usage(instance_name: Optional[str] = None) -> dict:
    """Return volume-level disk usage for all drives used by SQL Server files."""
    try:
        rows = db_manager.execute_query(DISK_USAGE_SQL, instance_name)

        max_used_pct = max((r["used_pct"] for r in rows), default=0)

        # Tag severity per volume
        for row in rows:
            row["severity"] = _severity(
                row["used_pct"],
                settings.disk_warning_pct,
                settings.disk_critical_pct,
            )

        return {
            "collected_at": datetime.utcnow().isoformat(),
            "volume_count": len(rows),
            "max_used_pct": max_used_pct,
            "severity": _severity(max_used_pct, settings.disk_warning_pct, settings.disk_critical_pct),
            "volumes": rows,
        }
    except Exception as e:
        logger.error(f"get_disk_usage failed: {e}")
        return {"error": str(e), "collected_at": datetime.utcnow().isoformat()}


# ---------------------------------------------------------------------------
# 7. Database Status + Backup Health
# ---------------------------------------------------------------------------

DATABASE_STATUS_SQL = """
SELECT
    d.name AS database_name,
    d.state_desc AS state,
    d.recovery_model_desc AS recovery_model,
    d.log_reuse_wait_desc,
    d.is_auto_shrink_on,
    d.is_auto_close_on,
    ROUND(SUM(mf.size) * 8 / 1024.0, 2) AS size_mb,

    -- Last full backup
    MAX(CASE WHEN bs.type = 'D' THEN bs.backup_finish_date END) AS last_full_backup,
    DATEDIFF(HOUR,
        MAX(CASE WHEN bs.type = 'D' THEN bs.backup_finish_date END),
        GETDATE()
    ) AS hours_since_full_backup,

    -- Last log backup
    MAX(CASE WHEN bs.type = 'L' THEN bs.backup_finish_date END) AS last_log_backup

FROM sys.databases d
LEFT JOIN sys.master_files mf ON d.database_id = mf.database_id
LEFT JOIN msdb.dbo.backupset bs ON bs.database_name = d.name
    AND bs.backup_finish_date >= DATEADD(DAY, -30, GETDATE())
WHERE d.database_id > 4   -- Exclude system DBs
  AND d.state = 0          -- Online only
GROUP BY
    d.name, d.state_desc, d.recovery_model_desc,
    d.log_reuse_wait_desc, d.is_auto_shrink_on, d.is_auto_close_on
ORDER BY size_mb DESC
"""


def get_database_status(instance_name: Optional[str] = None) -> dict:
    """Return status, size, and backup health for all user databases."""
    try:
        rows = db_manager.execute_query(DATABASE_STATUS_SQL, instance_name)

        no_recent_backup = [
            r for r in rows
            if r["hours_since_full_backup"] is None or r["hours_since_full_backup"] > 25
        ]

        return {
            "collected_at": datetime.utcnow().isoformat(),
            "database_count": len(rows),
            "databases_missing_backup": len(no_recent_backup),
            "severity": "critical" if no_recent_backup else "healthy",
            "databases": rows,
            "databases_missing_backup_names": [r["database_name"] for r in no_recent_backup],
        }
    except Exception as e:
        logger.error(f"get_database_status failed: {e}")
        return {"error": str(e), "collected_at": datetime.utcnow().isoformat()}


# ---------------------------------------------------------------------------
# 8. Full Health Snapshot (all checks in one call)
# ---------------------------------------------------------------------------

def get_full_snapshot(instance_name: Optional[str] = None) -> dict:
    """Run all health checks and return a combined snapshot."""
    logger.info(f"Running full health snapshot on [{instance_name or 'primary'}]")

    snapshot = {
        "snapshot_time": datetime.utcnow().isoformat(),
        "instance": instance_name or "primary",
        "server_health": get_server_health(instance_name),
        "blocking": get_blocking(instance_name),
        "wait_stats": get_wait_stats(instance_name),
        "long_running_queries": get_long_running_queries(instance_name=instance_name),
        "agent_jobs": get_agent_jobs(instance_name),
        "disk_usage": get_disk_usage(instance_name),
        "database_status": get_database_status(instance_name),
    }

    # Roll up overall severity
    severities = []
    for key in ["server_health", "blocking", "disk_usage", "agent_jobs", "database_status"]:
        section = snapshot.get(key, {})
        cpu_sev = section.get("cpu", {}).get("severity")
        mem_sev = section.get("memory", {}).get("severity")
        sev = section.get("severity") or cpu_sev or mem_sev
        if sev:
            severities.append(sev)

    if "critical" in severities:
        overall = "critical"
    elif "warning" in severities:
        overall = "warning"
    else:
        overall = "healthy"

    snapshot["overall_severity"] = overall
    logger.info(f"Snapshot complete | overall_severity={overall}")
    return snapshot
