"""
SQLGuardian - Candidate actions and their ordering

Every commercial monitor tells you something is wrong. The gap this fills is
what to do about it, in what order, and what not to do yet.

Two rules the rest of the system depends on:

  1. Ordering is a deterministic function of action metadata. `order_actions`
     sorts on blast radius, reversibility and approval - never on prose, never
     on a model's opinion. The UI renders the order it is given.

  2. Destructive actions come last and carry a rollback. If an action cannot be
     undone, it says so in the field the UI reads, not in a sentence a reader
     has to notice.

Actions come from two sources and the difference is visible everywhere:
  - source "runbook": a step from the team's own documented procedure, with a
    citation back to the document and section it came from.
  - source "generic": SQLGuardian's own baseline, shown labelled as generic.
    It is what a competent DBA would do; it is not what YOUR team does.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence

from core.conditions import Condition, ConditionCode
from core.runbooks import RetrievedSection


class BlastRadius(str, Enum):
    """What an action can affect if it goes wrong. Drives the ordering."""

    READ_ONLY = "read_only"          # observes; changes nothing
    SESSION = "session"              # affects one session
    DATABASE = "database"            # affects one database
    INSTANCE = "instance"            # affects every connection on the instance
    HOST = "host"                    # affects the machine or its storage


BLAST_RANK: Mapping[BlastRadius, int] = MappingProxyType({
    BlastRadius.READ_ONLY: 0,
    BlastRadius.SESSION: 1,
    BlastRadius.DATABASE: 2,
    BlastRadius.INSTANCE: 3,
    BlastRadius.HOST: 4,
})


@dataclass(frozen=True)
class Action:
    """One candidate action, as structured data. Never prose."""

    action: str                     # short imperative name
    what_it_does: str
    expected_effect: str
    blast_radius: BlastRadius
    reversible: bool
    how_to_undo: str                # "not reversible - ..." when reversible is False
    requires_approval: bool
    source: str                     # "runbook" | "generic"
    tsql: Optional[str] = None
    citation: Optional[str] = None  # required when source == "runbook"
    destructive: bool = False

    def __post_init__(self) -> None:
        if self.source == "runbook" and not self.citation:
            raise ValueError(
                f"Runbook-sourced action '{self.action}' has no citation. A step with "
                f"no citation is not usable in an incident."
            )
        if self.destructive and not self.requires_approval:
            raise ValueError(
                f"Destructive action '{self.action}' must require approval."
            )
        if not self.reversible and self.how_to_undo.strip().lower().startswith(("run ", "execute ")):
            raise ValueError(
                f"Action '{self.action}' is marked irreversible but how_to_undo reads "
                f"like an undo procedure."
            )

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "what_it_does": self.what_it_does,
            "expected_effect": self.expected_effect,
            "blast_radius": self.blast_radius.value,
            "reversible": self.reversible,
            "how_to_undo": self.how_to_undo,
            "requires_approval": self.requires_approval,
            "source": self.source,
            "tsql": self.tsql,
            "citation": self.citation,
            "destructive": self.destructive,
        }


def order_actions(actions: Sequence[Action]) -> tuple[Action, ...]:
    """Order strictly by risk. Least destructive first, destructive always last.

    Deterministic and total: no ties are broken by input order, so the same
    action set always renders in the same sequence.
    """
    return tuple(sorted(
        actions,
        key=lambda a: (
            a.destructive,                      # destructive last, unconditionally
            BLAST_RANK[a.blast_radius],         # then by what it can affect
            a.requires_approval,                # gated actions after ungated
            not a.reversible,                   # irreversible after reversible
            0 if a.source == "runbook" else 1,  # your procedure before our generic one
            a.action,                           # stable
        ),
    ))


# ---------------------------------------------------------------------------
# Generic baseline catalogue
# ---------------------------------------------------------------------------
# What a competent DBA does when a condition fires and there is no team
# procedure. Always rendered labelled as generic. `{placeholders}` are filled
# from condition facts; a missing fact drops that action rather than emitting a
# script with a hole in it.

def _blocking_actions(facts: Mapping[str, Any]) -> list[Action]:
    spid = facts.get("head_blocker_session_id")
    if spid is None:
        return []
    return [
        Action(
            action=f"Re-read what session {spid} is actually running",
            what_it_does=(
                f"Runs DBCC INPUTBUFFER({spid}) and pulls the live request text. The "
                f"statement captured in the snapshot can be seconds stale by the time "
                f"anyone acts on it."
            ),
            expected_effect="Confirms the head blocker is still running the same statement.",
            blast_radius=BlastRadius.READ_ONLY,
            reversible=True,
            how_to_undo="Nothing to undo; this only reads.",
            requires_approval=False,
            source="generic",
            tsql=(
                f"DBCC INPUTBUFFER({spid});\n"
                f"SELECT r.session_id, r.status, r.command, r.wait_type, r.wait_time,\n"
                f"       t.text AS running_batch\n"
                f"FROM sys.dm_exec_requests r\n"
                f"CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) t\n"
                f"WHERE r.session_id = {spid};"
            ),
        ),
        Action(
            action=f"Identify who owns session {spid}",
            what_it_does=(
                "Returns login, host, application name and client address for the head "
                "blocker so the owning person or team can be contacted first."
            ),
            expected_effect="You know who to call before you consider killing anything.",
            blast_radius=BlastRadius.READ_ONLY,
            reversible=True,
            how_to_undo="Nothing to undo; this only reads.",
            requires_approval=False,
            source="generic",
            tsql=(
                f"SELECT s.session_id, s.login_name, s.host_name, s.program_name,\n"
                f"       s.login_time, s.last_request_start_time, c.client_net_address,\n"
                f"       s.open_transaction_count\n"
                f"FROM sys.dm_exec_sessions s\n"
                f"LEFT JOIN sys.dm_exec_connections c ON c.session_id = s.session_id\n"
                f"WHERE s.session_id = {spid};"
            ),
        ),
        Action(
            action=f"Check whether session {spid} has an open transaction that is idle",
            what_it_does=(
                "Distinguishes a slow statement from an application that opened a "
                "transaction and stopped. The two have completely different fixes."
            ),
            expected_effect=(
                "An idle session with open_transaction_count > 0 points at the "
                "application, not at the database."
            ),
            blast_radius=BlastRadius.READ_ONLY,
            reversible=True,
            how_to_undo="Nothing to undo; this only reads.",
            requires_approval=False,
            source="generic",
            tsql=(
                f"SELECT s.session_id, s.status, s.open_transaction_count,\n"
                f"       DATEDIFF(SECOND, s.last_request_end_time, GETDATE()) AS idle_seconds,\n"
                f"       t.transaction_begin_time\n"
                f"FROM sys.dm_exec_sessions s\n"
                f"LEFT JOIN sys.dm_tran_session_transactions st ON st.session_id = s.session_id\n"
                f"LEFT JOIN sys.dm_tran_active_transactions t ON t.transaction_id = st.transaction_id\n"
                f"WHERE s.session_id = {spid};"
            ),
        ),
        Action(
            action=f"Kill session {spid}",
            what_it_does=(
                "Terminates the head blocker and rolls back its open transaction, "
                "releasing the locks the chain is waiting on."
            ),
            expected_effect=(
                "The blocked sessions proceed once the rollback completes. On a large "
                "transaction the rollback itself can hold the locks longer than the "
                "original block did."
            ),
            blast_radius=BlastRadius.SESSION,
            reversible=False,
            how_to_undo=(
                "Not reversible. The transaction is rolled back and its work is lost; "
                "the owning application has to resubmit it."
            ),
            requires_approval=True,
            destructive=True,
            source="generic",
            tsql=(
                f"-- Confirm the owner and the statement first (actions above).\n"
                f"-- Watch the rollback afterwards; it is not instant:\n"
                f"--   KILL {spid} WITH STATUSONLY;\n"
                f"KILL {spid};"
            ),
        ),
    ]


def _agent_job_actions(facts: Mapping[str, Any]) -> list[Action]:
    names = facts.get("failed_job_names") or ()
    first = names[0] if names else None
    if first is None:
        return []
    return [
        Action(
            action=f"Read the failing step output for '{first}'",
            what_it_does=(
                "Pulls the per-step history rows, not the job-level summary, so the "
                "actual error text is visible."
            ),
            expected_effect="You see why it failed rather than that it failed.",
            blast_radius=BlastRadius.READ_ONLY,
            reversible=True,
            how_to_undo="Nothing to undo; this only reads.",
            requires_approval=False,
            source="generic",
            tsql=(
                "SELECT TOP 20 j.name AS job_name, h.step_id, h.step_name,\n"
                "       CASE WHEN h.run_date > 0 THEN CONVERT(DATETIME,\n"
                "           STUFF(STUFF(CONVERT(CHAR(8), h.run_date), 7, 0, '-'), 5, 0, '-') + ' ' +\n"
                "           STUFF(STUFF(RIGHT('000000' + CONVERT(VARCHAR(6), h.run_time), 6), 5, 0, ':'), 3, 0, ':')\n"
                "       ) END AS run_time,\n"
                "       h.run_status, h.message\n"
                "FROM msdb.dbo.sysjobhistory h\n"
                "JOIN msdb.dbo.sysjobs j ON j.job_id = h.job_id\n"
                f"WHERE j.name = N'{first}'\n"
                "ORDER BY h.instance_id DESC;"
            ),
        ),
        Action(
            action=f"Re-run '{first}' after the cause is understood",
            what_it_does="Starts the job again through msdb.dbo.sp_start_job.",
            expected_effect=(
                "The job runs on its normal schedule path. If the underlying cause is "
                "still present it fails the same way."
            ),
            blast_radius=BlastRadius.INSTANCE,
            reversible=False,
            how_to_undo=(
                "Not reversible in general: whatever the job does - a backup, an ETL "
                "load, an index rebuild - is done. sp_stop_job halts a run in progress "
                "but does not undo completed steps."
            ),
            requires_approval=True,
            source="generic",
            tsql=f"EXEC msdb.dbo.sp_start_job @job_name = N'{first}';",
        ),
    ]


def _backup_actions(facts: Mapping[str, Any]) -> list[Action]:
    names = facts.get("database_names") or ()
    first = names[0] if names else None
    if first is None:
        return []
    return [
        Action(
            action=f"Confirm the real backup history for {first}",
            what_it_does=(
                "Reads msdb.dbo.backupset directly. Rules out a backup that succeeded "
                "to a different server, or history cleared by a maintenance job."
            ),
            expected_effect="You know whether this is a missing backup or missing history.",
            blast_radius=BlastRadius.READ_ONLY,
            reversible=True,
            how_to_undo="Nothing to undo; this only reads.",
            requires_approval=False,
            source="generic",
            tsql=(
                "SELECT TOP 20 bs.database_name, bs.type, bs.backup_start_date,\n"
                "       bs.backup_finish_date, bs.backup_size / 1048576.0 AS size_mb,\n"
                "       bmf.physical_device_name\n"
                "FROM msdb.dbo.backupset bs\n"
                "JOIN msdb.dbo.backupmediafamily bmf ON bmf.media_set_id = bs.media_set_id\n"
                f"WHERE bs.database_name = N'{first}'\n"
                "ORDER BY bs.backup_finish_date DESC;"
            ),
        ),
        Action(
            action="Check free space on the backup target before running one",
            what_it_does="Compares database size against free space on the volumes in use.",
            expected_effect=(
                "Prevents an ad-hoc backup from filling the volume and turning a "
                "recoverability problem into an outage."
            ),
            blast_radius=BlastRadius.READ_ONLY,
            reversible=True,
            how_to_undo="Nothing to undo; this only reads.",
            requires_approval=False,
            source="generic",
            tsql=(
                "SELECT DISTINCT vs.volume_mount_point,\n"
                "       vs.total_bytes / 1073741824.0 AS total_gb,\n"
                "       vs.available_bytes / 1073741824.0 AS available_gb\n"
                "FROM sys.master_files mf\n"
                "CROSS APPLY sys.dm_os_volume_stats(mf.database_id, mf.file_id) vs;"
            ),
        ),
        Action(
            action=f"Take an out-of-band COPY_ONLY full backup of {first}",
            what_it_does=(
                "Takes a full backup that does not reset the differential base, so the "
                "existing backup chain and schedule are unaffected."
            ),
            expected_effect=f"{first} has a current restore point.",
            blast_radius=BlastRadius.DATABASE,
            reversible=True,
            how_to_undo=(
                "Delete the backup file. COPY_ONLY means nothing about the existing "
                "backup chain changed."
            ),
            requires_approval=True,
            source="generic",
            tsql=(
                f"BACKUP DATABASE [{first}]\n"
                f"TO DISK = N'<backup_path>\\{first}_copyonly.bak'\n"
                f"WITH COPY_ONLY, INIT, COMPRESSION, CHECKSUM, STATS = 5;"
            ),
        ),
    ]


def _log_growth_actions(facts: Mapping[str, Any]) -> list[Action]:
    names = facts.get("database_names") or ()
    first = names[0] if names else None
    if first is None:
        return []
    return [
        Action(
            action=f"Find out what is stopping the log from truncating in {first}",
            what_it_does=(
                "Reads log_reuse_wait_desc plus the oldest active transaction. That one "
                "value names the cause: an open transaction, a log backup that has not "
                "run, an unread replication or CDC log reader, an AG replica behind."
            ),
            expected_effect="You know which of the causes applies before changing anything.",
            blast_radius=BlastRadius.READ_ONLY,
            reversible=True,
            how_to_undo="Nothing to undo; this only reads.",
            requires_approval=False,
            source="generic",
            tsql=(
                "SELECT name, log_reuse_wait_desc, recovery_model_desc\n"
                "FROM sys.databases\n"
                f"WHERE name = N'{first}';\n\n"
                "SELECT s.session_id, s.login_name, s.host_name, s.program_name,\n"
                "       t.transaction_begin_time,\n"
                "       DATEDIFF(MINUTE, t.transaction_begin_time, GETDATE()) AS open_minutes\n"
                "FROM sys.dm_tran_active_transactions t\n"
                "JOIN sys.dm_tran_session_transactions st ON st.transaction_id = t.transaction_id\n"
                "JOIN sys.dm_exec_sessions s ON s.session_id = st.session_id\n"
                "ORDER BY t.transaction_begin_time;"
            ),
        ),
        Action(
            action=f"Take a transaction log backup of {first}",
            what_it_does=(
                "The correct fix when log_reuse_wait_desc is LOG_BACKUP: backing up the "
                "log marks the space reusable."
            ),
            expected_effect=(
                "Used log space drops without the file changing size. If the value is "
                "not LOG_BACKUP this does nothing."
            ),
            blast_radius=BlastRadius.DATABASE,
            reversible=True,
            how_to_undo=(
                "Nothing to undo - a log backup extends the chain, it does not alter "
                "the database. Keep the file: deleting it breaks the restore chain."
            ),
            requires_approval=True,
            source="generic",
            tsql=(
                f"BACKUP LOG [{first}]\n"
                f"TO DISK = N'<backup_path>\\{first}_log.trn'\n"
                f"WITH COMPRESSION, CHECKSUM, STATS = 5;"
            ),
        ),
        Action(
            action=f"Grow the log file on {first} to buy time",
            what_it_does=(
                "Adds space in one deliberate step instead of leaving autogrowth to add "
                "it in small increments during the incident."
            ),
            expected_effect="Percent-used drops; the underlying reuse blocker is unchanged.",
            blast_radius=BlastRadius.DATABASE,
            reversible=True,
            how_to_undo=(
                "Shrink the log back to its previous size once the reuse blocker is "
                "cleared and a log backup has run."
            ),
            requires_approval=True,
            source="generic",
            tsql=(
                f"-- Check current size and the volume's free space first.\n"
                f"ALTER DATABASE [{first}]\n"
                f"MODIFY FILE (NAME = N'<logical_log_file_name>', SIZE = <new_size_MB>MB);"
            ),
        ),
    ]


def _disk_actions(facts: Mapping[str, Any]) -> list[Action]:
    mounts = facts.get("volume_mount_points") or ()
    first = mounts[0] if mounts else None
    if first is None:
        return []
    # Only Windows reports a mount point. On Linux the column is NULL, so
    # filtering on the label would produce a script that silently returns no
    # rows; list every volume instead and say why.
    queryable = facts.get("queryable_mount_points") or ()
    volume_filter = (
        f"WHERE vs.volume_mount_point = N'{queryable[0]}'" if queryable
        else "-- This instance reports no volume mount point (SQL Server on Linux),\n"
             "-- so every volume is listed rather than filtered to one."
    )
    return [
        Action(
            action=f"Find what is consuming {first}",
            what_it_does=(
                "Lists SQL Server files on the volume by size, with free space inside "
                "each file, separating 'the data grew' from 'a file is over-allocated'."
            ),
            expected_effect="You know whether SQL Server owns the growth at all.",
            blast_radius=BlastRadius.READ_ONLY,
            reversible=True,
            how_to_undo="Nothing to undo; this only reads.",
            requires_approval=False,
            source="generic",
            tsql=(
                "SELECT DB_NAME(mf.database_id) AS database_name, mf.name AS logical_name,\n"
                "       mf.physical_name, mf.type_desc,\n"
                "       mf.size * 8 / 1024.0 AS allocated_mb,\n"
                "       vs.volume_mount_point,\n"
                "       vs.available_bytes / 1073741824.0 AS volume_free_gb\n"
                "FROM sys.master_files mf\n"
                "CROSS APPLY sys.dm_os_volume_stats(mf.database_id, mf.file_id) vs\n"
                f"{volume_filter}\n"
                "ORDER BY mf.size DESC;"
            ),
        ),
        Action(
            action="Check whether old backup files are the consumer",
            what_it_does=(
                "Lists backup history with device paths and sizes so retention can be "
                "assessed against what is actually on the volume."
            ),
            expected_effect="Identifies reclaimable space that is already copied off-box.",
            blast_radius=BlastRadius.READ_ONLY,
            reversible=True,
            how_to_undo="Nothing to undo; this only reads.",
            requires_approval=False,
            source="generic",
            tsql=(
                "SELECT TOP 50 bs.database_name, bs.backup_finish_date,\n"
                "       bs.backup_size / 1073741824.0 AS size_gb, bmf.physical_device_name\n"
                "FROM msdb.dbo.backupset bs\n"
                "JOIN msdb.dbo.backupmediafamily bmf ON bmf.media_set_id = bs.media_set_id\n"
                "ORDER BY bs.backup_finish_date DESC;"
            ),
        ),
        Action(
            action="Delete backup files outside the retention window",
            what_it_does=(
                "Removes backup files from the volume, at the OS level or via a "
                "maintenance cleanup task."
            ),
            expected_effect="Free space is reclaimed immediately.",
            blast_radius=BlastRadius.HOST,
            reversible=False,
            how_to_undo=(
                "Not reversible. Deleted backups are gone; if they were the only copy, "
                "the restore points they represented are gone with them. Confirm the "
                "off-box copy exists before this runs."
            ),
            requires_approval=True,
            destructive=True,
            source="generic",
            tsql=(
                "-- No T-SQL by design: this is an OS-level file deletion, and the\n"
                "-- decision needs the retention policy and the off-box copy confirmed\n"
                "-- by a human first.\n"
                "-- Verify off-box copies, then delete through the agreed cleanup task."
            ),
        ),
    ]


def _wait_spike_actions(facts: Mapping[str, Any]) -> list[Action]:
    wait_type = facts.get("dominant_wait_type")
    if not wait_type:
        return []
    return [
        Action(
            action=f"Find the sessions currently waiting on {wait_type}",
            what_it_does=(
                "Moves from aggregate wait statistics to the live requests actually "
                "waiting right now, with their statements."
            ),
            expected_effect=f"Names the queries responsible for the {wait_type} time.",
            blast_radius=BlastRadius.READ_ONLY,
            reversible=True,
            how_to_undo="Nothing to undo; this only reads.",
            requires_approval=False,
            source="generic",
            tsql=(
                "SELECT r.session_id, r.wait_type, r.wait_time, r.blocking_session_id,\n"
                "       DB_NAME(r.database_id) AS database_name, s.login_name, s.program_name,\n"
                "       SUBSTRING(t.text, (r.statement_start_offset/2)+1,\n"
                "           ((CASE r.statement_end_offset WHEN -1 THEN DATALENGTH(t.text)\n"
                "             ELSE r.statement_end_offset END - r.statement_start_offset)/2)+1\n"
                "       ) AS statement_text\n"
                "FROM sys.dm_exec_requests r\n"
                "JOIN sys.dm_exec_sessions s ON s.session_id = r.session_id\n"
                "CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) t\n"
                f"WHERE r.wait_type = N'{wait_type}'\n"
                "ORDER BY r.wait_time DESC;"
            ),
        ),
        Action(
            action=f"Record a {wait_type} baseline before changing anything",
            what_it_does=(
                "Captures the current wait profile so the effect of any change can be "
                "measured instead of asserted."
            ),
            expected_effect="You can prove whether the next action helped.",
            blast_radius=BlastRadius.READ_ONLY,
            reversible=True,
            how_to_undo="Nothing to undo; this only reads.",
            requires_approval=False,
            source="generic",
            tsql=(
                "SELECT wait_type, waiting_tasks_count, wait_time_ms, signal_wait_time_ms\n"
                "FROM sys.dm_os_wait_stats\n"
                "WHERE wait_time_ms > 0\n"
                "ORDER BY wait_time_ms DESC;"
            ),
        ),
    ]


def _long_running_actions(facts: Mapping[str, Any]) -> list[Action]:
    spid = facts.get("longest_session_id")
    if spid is None:
        return []
    return [
        Action(
            action=f"Get the live plan for session {spid}",
            what_it_does=(
                "Pulls the actual running plan and the wait it is on, which shows "
                "whether it is scanning, spilling, or waiting on something."
            ),
            expected_effect="You can tell whether the query is progressing or stuck.",
            blast_radius=BlastRadius.READ_ONLY,
            reversible=True,
            how_to_undo="Nothing to undo; this only reads.",
            requires_approval=False,
            source="generic",
            tsql=(
                "SELECT r.session_id, r.status, r.command, r.wait_type, r.wait_resource,\n"
                "       r.percent_complete, r.estimated_completion_time / 1000 AS est_seconds,\n"
                "       qp.query_plan\n"
                "FROM sys.dm_exec_requests r\n"
                "OUTER APPLY sys.dm_exec_query_plan(r.plan_handle) qp\n"
                f"WHERE r.session_id = {spid};"
            ),
        ),
        Action(
            action=f"Check whether session {spid} is a scheduled maintenance task",
            what_it_does=(
                "Matches the session's program name and login against running Agent "
                "jobs before anyone considers cancelling it."
            ),
            expected_effect=(
                "Avoids killing an index rebuild or a large DELETE, where the rollback "
                "runs longer than the statement already has."
            ),
            blast_radius=BlastRadius.READ_ONLY,
            reversible=True,
            how_to_undo="Nothing to undo; this only reads.",
            requires_approval=False,
            source="generic",
            tsql=(
                "SELECT s.session_id, s.program_name, s.login_name, j.name AS agent_job\n"
                "FROM sys.dm_exec_sessions s\n"
                "LEFT JOIN msdb.dbo.sysjobs j\n"
                "  ON s.program_name LIKE '%' + CONVERT(NVARCHAR(36), j.job_id) + '%'\n"
                f"WHERE s.session_id = {spid};"
            ),
        ),
        Action(
            action=f"Kill session {spid}",
            what_it_does="Terminates the request and rolls back any open transaction.",
            expected_effect=(
                "The request stops. Rollback time is proportional to the work already "
                "done and can exceed the elapsed time so far."
            ),
            blast_radius=BlastRadius.SESSION,
            reversible=False,
            how_to_undo=(
                "Not reversible. The work is rolled back and has to be resubmitted."
            ),
            requires_approval=True,
            destructive=True,
            source="generic",
            tsql=f"-- KILL {spid} WITH STATUSONLY; -- to watch a rollback in progress\nKILL {spid};",
        ),
    ]


ACTION_CATALOG: Mapping[ConditionCode, Any] = MappingProxyType({
    ConditionCode.BLOCKING_CHAIN: _blocking_actions,
    ConditionCode.AGENT_JOB_FAILURE: _agent_job_actions,
    ConditionCode.BACKUP_AGE_EXCEEDED: _backup_actions,
    ConditionCode.LOG_GROWTH: _log_growth_actions,
    ConditionCode.DISK_PRESSURE: _disk_actions,
    ConditionCode.WAIT_SPIKE: _wait_spike_actions,
    ConditionCode.LONG_RUNNING_REQUEST: _long_running_actions,
})


# ---------------------------------------------------------------------------
# Runbook steps as actions
# ---------------------------------------------------------------------------
# A step from the team's own procedure is the point of the product, so it is
# never silently downgraded. What it is NOT allowed to do is claim a risk
# profile it has not stated. Absent explicit metadata, a runbook step is
# classified conservatively by the deterministic rules below and shown with the
# text of the step itself, so the DBA reads the team's words, not a paraphrase.

_DESTRUCTIVE_PATTERNS: tuple[tuple[str, BlastRadius, str], ...] = (
    ("kill ", BlastRadius.SESSION, "terminates a session and rolls its transaction back"),
    ("drop ", BlastRadius.DATABASE, "drops an object"),
    ("truncate ", BlastRadius.DATABASE, "empties a table with no row-level undo"),
    ("delete ", BlastRadius.DATABASE, "removes rows"),
    ("shrink", BlastRadius.DATABASE, "shrinks a file"),
    ("failover", BlastRadius.INSTANCE, "moves the workload to another replica"),
    ("fail over", BlastRadius.INSTANCE, "moves the workload to another replica"),
    ("freeproccache", BlastRadius.INSTANCE, "clears the plan cache instance-wide"),
    ("restart", BlastRadius.INSTANCE, "restarts the service"),
    ("offline", BlastRadius.DATABASE, "takes a database offline"),
    ("detach", BlastRadius.DATABASE, "detaches a database"),
    ("rebuild", BlastRadius.DATABASE, "rebuilds an index, fully logged"),
)

_WRITE_PATTERNS = ("alter ", "backup ", "restore ", "update ", "insert ", "exec ", "create ", "set ")


# Runbooks are full of steps that name a destructive verb in order to forbid it
# ("Do not kill it while they are still investigating"). Classifying those as
# destructive pushes a team's own safety instruction to the bottom of the list,
# which is the exact opposite of what it says.
_NEGATIONS = ("do not ", "don't ", "dont ", "never ", "avoid ", "without ", "instead of ")
_NEGATION_WINDOW = 40


def _is_negated(text: str, position: int) -> bool:
    """Is the verb at `position` inside a "do not ..." instruction?"""
    window = text[max(0, position - _NEGATION_WINDOW) : position]
    return any(negation in window for negation in _NEGATIONS)


def classify_step(step_text: str) -> tuple[BlastRadius, bool, bool]:
    """Return (blast_radius, destructive, requires_approval) for a runbook step.

    Deterministic keyword classification, biased toward caution: an unrecognised
    step that contains a write verb is treated as requiring approval rather than
    assumed safe. A verb that appears only inside a prohibition is not treated
    as an instruction to perform it.
    """
    lowered = step_text.lower()
    for pattern, radius, _ in _DESTRUCTIVE_PATTERNS:
        position = lowered.find(pattern)
        while position != -1:
            if not _is_negated(lowered, position):
                return radius, True, True
            position = lowered.find(pattern, position + 1)
    for pattern in _WRITE_PATTERNS:
        position = lowered.find(pattern)
        while position != -1:
            if not _is_negated(lowered, position):
                return BlastRadius.DATABASE, False, True
            position = lowered.find(pattern, position + 1)
    return BlastRadius.READ_ONLY, False, False


def actions_from_runbook(retrieved: RetrievedSection) -> list[Action]:
    """Turn a retrieved procedure into ordered, cited, risk-classified actions."""
    actions: list[Action] = []
    for index, step in enumerate(retrieved.section.steps(), start=1):
        radius, destructive, approval = classify_step(step)
        why = next(
            (reason for pattern, _, reason in _DESTRUCTIVE_PATTERNS
             if destructive and pattern in step.lower()),
            None,
        )
        actions.append(Action(
            action=f"Step {index}: {step[:120]}",
            what_it_does=step,
            expected_effect=(
                f"As documented in {retrieved.section.doc_title}. SQLGuardian does not "
                "restate the expected effect of your team's step."
            ),
            blast_radius=radius,
            reversible=not destructive,
            how_to_undo=(
                f"Not reversible: this step {why}. Confirm the rollback plan in "
                f"{retrieved.section.doc_title} before running it."
                if destructive else
                "No change, or reversible by the procedure that documents it."
            ),
            requires_approval=approval,
            destructive=destructive,
            source="runbook",
            citation=retrieved.section.citation,
        ))
    return actions


def build_action_plan(
    condition: Condition,
    retrieved: Sequence[RetrievedSection] = (),
) -> dict:
    """The full ordered response to one condition.

    Runbook steps and generic baseline actions are pooled and then ordered by
    the same deterministic risk function, so the DBA reads one list in risk
    order rather than two lists they have to merge in their head. Every entry
    carries its source, and runbook entries carry their citation.
    """
    runbook_actions: list[Action] = []
    for item in retrieved:
        runbook_actions.extend(actions_from_runbook(item))

    builder = ACTION_CATALOG.get(condition.code)
    generic_actions = list(builder(condition.facts)) if builder else []

    ordered = order_actions(runbook_actions + generic_actions)
    return {
        "condition": condition.code.value,
        "has_team_procedure": bool(runbook_actions),
        "guidance_source": "runbook" if runbook_actions else "generic",
        "citations": [item.section.citation for item in retrieved],
        "hold_off": list(condition.hold_off),
        "actions": [action.to_dict() for action in ordered],
    }
