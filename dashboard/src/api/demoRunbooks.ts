// Demo fixtures for the runbook-automation endpoints.
//
// These mirror what the real API returns when the sample corpus in
// docs/runbook-samples is ingested against the demo snapshot: the blocking
// chain has a documented team procedure, disk pressure on prod-sql01 does not,
// and the gap report says so.
import type {
  ActionCandidate,
  ConditionsResponse,
  DetectedCondition,
  GapReport,
  IncidentReportResponse,
  RunbookListResponse,
} from "../types/api";

const iso = (offsetSeconds = 0) =>
  new Date(Date.now() - offsetSeconds * 1000).toISOString();

const BLOCKING_CITATION =
  "dba blocking and long queries - Platform DBA Runbook - Contention > Blocking chain on a " +
  "production OLTP instance (dba-blocking-and-long-queries.md#platform-dba-runbook-contention-" +
  "blocking-chain-on-a-production-oltp-instance, lines 7-26)";

const STORAGE_CITATION =
  "confluence export storage - Storage and Volume Procedures > Data or log volume above 80 " +
  "percent (confluence-export-storage.html#storage-and-volume-procedures-data-or-log-volume-" +
  "above-80-percent, heading \"Data or log volume above 80 percent\")";

// ------------------------------------------------------------------ corpus --

export const demoRunbookList: RunbookListResponse = {
  supported_formats: ["docx", "html", "markdown", "pdf", "text"],
  supported_extensions: [".docx", ".htm", ".html", ".markdown", ".md", ".pdf", ".txt"],
  document_count: 4,
  section_count: 11,
  conditions_covered: [
    "AGENT_JOB_FAILURE",
    "BACKUP_AGE_EXCEEDED",
    "BLOCKING_CHAIN",
    "LOG_GROWTH",
    "LONG_RUNNING_REQUEST",
  ],
  conditions_not_covered: ["DISK_PRESSURE", "WAIT_SPIKE"],
  documents: [
    {
      doc_id: "a1b2c3d4e5f6",
      title: "dba blocking and long queries",
      filename: "dba-blocking-and-long-queries.md",
      format: "markdown",
      section_count: 3,
      mapped_section_count: 2,
      byte_size: 2894,
      ingested_at: iso(86_400 * 12),
      conditions_covered: ["BLOCKING_CHAIN", "LONG_RUNNING_REQUEST"],
    },
    {
      doc_id: "b2c3d4e5f6a1",
      title: "backup and log procedures",
      filename: "backup-and-log-procedures.txt",
      format: "text",
      section_count: 3,
      mapped_section_count: 3,
      byte_size: 3211,
      ingested_at: iso(86_400 * 12),
      conditions_covered: ["BACKUP_AGE_EXCEEDED", "LOG_GROWTH"],
    },
    {
      doc_id: "c3d4e5f6a1b2",
      title: "confluence export storage",
      filename: "confluence-export-storage.html",
      format: "html",
      section_count: 3,
      mapped_section_count: 1,
      byte_size: 3402,
      ingested_at: iso(86_400 * 3),
      conditions_covered: ["AGENT_JOB_FAILURE"],
    },
    {
      doc_id: "d4e5f6a1b2c3",
      title: "oncall escalation quick reference",
      filename: "oncall-escalation-quick-reference.pdf",
      format: "pdf",
      section_count: 2,
      mapped_section_count: 0,
      byte_size: 2140,
      ingested_at: iso(86_400 * 30),
      conditions_covered: [],
    },
  ],
};

// -------------------------------------------------------------- conditions --

function runbookStep(
  index: number,
  step: string,
  options: Partial<ActionCandidate> = {}
): ActionCandidate {
  return {
    action: `Step ${index}: ${step}`,
    what_it_does: step,
    expected_effect:
      "As documented in dba blocking and long queries. SQLGuardian does not restate the " +
      "expected effect of your team's step.",
    blast_radius: "read_only",
    reversible: true,
    how_to_undo: "No change, or reversible by the procedure that documents it.",
    requires_approval: false,
    source: "runbook",
    tsql: null,
    citation: BLOCKING_CITATION,
    destructive: false,
    ...options,
  };
}

function blockingCondition(): DetectedCondition {
  const actions: ActionCandidate[] = [
    runbookStep(
      1,
      "Confirm the head blocker is still live and still running the same statement before " +
        "acting on anything the alert showed you."
    ),
    runbookStep(
      2,
      "Record the head blocker session id, login, host and program name in the incident " +
        "channel. The alert is a snapshot; the incident record needs the values you saw."
    ),
    runbookStep(
      3,
      "If program_name is OrderSync or WMS-Bridge, page the Fulfilment on-call before doing " +
        "anything else. Those two open long transactions by design and killing them leaves " +
        "partial picks that have to be reconciled by hand."
    ),
    runbookStep(
      4,
      "If the head blocker is idle with an open transaction, it is an application problem. " +
        "Ask Fulfilment to release it. Do not kill it while they are still investigating."
    ),
    runbookStep(
      5,
      "If the chain is longer than 8 sessions, or any session has waited over 300 seconds, " +
        "declare a P2 in #incident and continue."
    ),
    runbookStep(
      7,
      "After the chain clears, capture the blocking statement into the incident record so the " +
        "owning team can fix the query."
    ),
    {
      action: "Check whether session 62 has an open transaction that is idle",
      what_it_does:
        "Distinguishes a slow statement from an application that opened a transaction and " +
        "stopped. The two have completely different fixes.",
      expected_effect:
        "An idle session with open_transaction_count > 0 points at the application, not at " +
        "the database.",
      blast_radius: "read_only",
      reversible: true,
      how_to_undo: "Nothing to undo; this only reads.",
      requires_approval: false,
      source: "generic",
      citation: null,
      destructive: false,
      tsql:
        "SELECT s.session_id, s.status, s.open_transaction_count,\n" +
        "       DATEDIFF(SECOND, s.last_request_end_time, GETDATE()) AS idle_seconds,\n" +
        "       t.transaction_begin_time\n" +
        "FROM sys.dm_exec_sessions s\n" +
        "LEFT JOIN sys.dm_tran_session_transactions st ON st.session_id = s.session_id\n" +
        "LEFT JOIN sys.dm_tran_active_transactions t ON t.transaction_id = st.transaction_id\n" +
        "WHERE s.session_id = 62;",
    },
    {
      action: "Identify who owns session 62",
      what_it_does:
        "Returns login, host, application name and client address for the head blocker so the " +
        "owning person or team can be contacted first.",
      expected_effect: "You know who to call before you consider killing anything.",
      blast_radius: "read_only",
      reversible: true,
      how_to_undo: "Nothing to undo; this only reads.",
      requires_approval: false,
      source: "generic",
      citation: null,
      destructive: false,
      tsql:
        "SELECT s.session_id, s.login_name, s.host_name, s.program_name,\n" +
        "       s.login_time, s.last_request_start_time, c.client_net_address,\n" +
        "       s.open_transaction_count\n" +
        "FROM sys.dm_exec_sessions s\n" +
        "LEFT JOIN sys.dm_exec_connections c ON c.session_id = s.session_id\n" +
        "WHERE s.session_id = 62;",
    },
    {
      action: "Re-read what session 62 is actually running",
      what_it_does:
        "Runs DBCC INPUTBUFFER(62) and pulls the live request text. The statement captured in " +
        "the snapshot can be seconds stale by the time anyone acts on it.",
      expected_effect: "Confirms the head blocker is still running the same statement.",
      blast_radius: "read_only",
      reversible: true,
      how_to_undo: "Nothing to undo; this only reads.",
      requires_approval: false,
      source: "generic",
      citation: null,
      destructive: false,
      tsql:
        "DBCC INPUTBUFFER(62);\n" +
        "SELECT r.session_id, r.status, r.command, r.wait_type, r.wait_time,\n" +
        "       t.text AS running_batch\n" +
        "FROM sys.dm_exec_requests r\n" +
        "CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) t\n" +
        "WHERE r.session_id = 62;",
    },
    runbookStep(
      6,
      "Kill the head blocker only with duty manager approval, and only after steps 1-5. Note " +
        "in the channel that the rollback may hold the locks for as long again.",
      {
        blast_radius: "session",
        reversible: false,
        requires_approval: true,
        destructive: true,
        how_to_undo:
          "Not reversible: this step terminates a session and rolls its transaction back. " +
          "Confirm the rollback plan in dba blocking and long queries before running it.",
      }
    ),
    {
      action: "Kill session 62",
      what_it_does:
        "Terminates the head blocker and rolls back its open transaction, releasing the locks " +
        "the chain is waiting on.",
      expected_effect:
        "The blocked sessions proceed once the rollback completes. On a large transaction the " +
        "rollback itself can hold the locks longer than the original block did.",
      blast_radius: "session",
      reversible: false,
      how_to_undo:
        "Not reversible. The transaction is rolled back and its work is lost; the owning " +
        "application has to resubmit it.",
      requires_approval: true,
      source: "generic",
      citation: null,
      destructive: true,
      tsql:
        "-- Confirm the owner and the statement first (actions above).\n" +
        "-- Watch the rollback afterwards; it is not instant:\n" +
        "--   KILL 62 WITH STATUSONLY;\n" +
        "KILL 62;",
    },
  ];

  return {
    code: "BLOCKING_CHAIN",
    severity: "critical",
    title: "Blocking chain: 4 session(s) blocked behind session 62",
    detail:
      "4 session(s) are blocked, the longest for 218 seconds. The head of the chain is " +
      "session 62.",
    scope: "session 62 / WideWorldImporters",
    impact_score: 86,
    facts: {
      blocked_session_count: 4,
      max_wait_seconds: 218,
      head_blocker_session_id: 62,
      head_blocker_login: "wwi_app",
      head_blocker_program: "OrderService (.NET)",
    },
    evidence: [
      "4 session(s) blocked, longest wait 218s (sys.dm_exec_requests.blocking_session_id > 0).",
      "Head blocker is session 62, login wwi_app, program OrderService (.NET).",
      "Statement holding the lock: UPDATE Sales.OrderLines SET PickedQuantity = @qty, " +
        "LastEditedBy = @user WHERE OrderLineID = @id;",
      "Session 71 waiting 218s on LCK_M_X in WideWorldImporters.",
      "Session 84 waiting 196s on LCK_M_S in WideWorldImporters.",
      "Session 93 waiting 154s on LCK_M_X in WideWorldImporters.",
      "Session 101 waiting 131s on LCK_M_S in WideWorldImporters.",
    ],
    hold_off: [
      "Do not KILL the head blocker before identifying who owns it. A rollback of a large open " +
        "transaction can hold the same locks for longer than the original block.",
      "Do not enable READ_COMMITTED_SNAPSHOT mid-incident to clear a block: it needs a " +
        "database-level change and tempdb headroom, and it does not release the locks already " +
        "held.",
    ],
    detected_at: iso(180),
    runbook: {
      has_team_procedure: true,
      sections: [
        {
          doc_id: "a1b2c3d4e5f6",
          doc_title: "dba blocking and long queries",
          doc_filename: "dba-blocking-and-long-queries.md",
          heading: "Blocking chain on a production OLTP instance",
          heading_path: [
            "Platform DBA Runbook - Contention",
            "Blocking chain on a production OLTP instance",
          ],
          anchor:
            "platform-dba-runbook-contention-blocking-chain-on-a-production-oltp-instance",
          citation: BLOCKING_CITATION,
          source_ref: "lines 7-26",
          body: "",
          steps: [],
          conditions: ["BLOCKING_CHAIN"],
          mapping_reason: "declared in the document",
          score: 4.5,
          match_reason:
            "document declares this condition explicitly; body matches \"wideworldimporters\"",
        },
      ],
      note: null,
    },
    plan: {
      condition: "BLOCKING_CHAIN",
      has_team_procedure: true,
      guidance_source: "runbook",
      citations: [BLOCKING_CITATION],
      hold_off: [],
      actions,
    },
  };
}

function diskCondition(usedPct: number): DetectedCondition {
  return {
    code: "DISK_PRESSURE",
    severity: usedPct >= 90 ? "critical" : "warning",
    title: "Disk pressure on D:\\",
    detail: `Highest volume usage ${usedPct}% against a 80% threshold.`,
    scope: "D:\\",
    impact_score: usedPct >= 90 ? 100 : 90,
    facts: { max_used_pct: usedPct, volume_mount_points: ["D:\\"] },
    evidence: [
      `D:\\ is ${usedPct}% used, ${Math.round(1024 * (1 - usedPct / 100))} GB free of 1024.0 ` +
        `GB (sys.dm_os_volume_stats).`,
    ],
    hold_off: [
      "Do not delete backup files to reclaim space before confirming they are already copied " +
        "off-box and outside the retention window. That is the one action here that cannot be " +
        "undone.",
      "Do not run DBCC SHRINKFILE on a data file during business hours. It is single-threaded, " +
        "fully logged, and leaves index fragmentation behind.",
    ],
    detected_at: iso(240),
    runbook: {
      has_team_procedure: false,
      sections: [],
      note:
        "No team procedure covers DISK_PRESSURE. The actions below are SQLGuardian's generic " +
        "baseline, not your team's documented process. This gap is recorded in the runbook gap " +
        "report.",
    },
    plan: {
      condition: "DISK_PRESSURE",
      has_team_procedure: false,
      guidance_source: "generic",
      citations: [],
      hold_off: [],
      actions: [
        {
          action: "Find what is consuming D:\\",
          what_it_does:
            "Lists SQL Server files on the volume by size, with free space inside each file, " +
            "separating 'the data grew' from 'a file is over-allocated'.",
          expected_effect: "You know whether SQL Server owns the growth at all.",
          blast_radius: "read_only",
          reversible: true,
          how_to_undo: "Nothing to undo; this only reads.",
          requires_approval: false,
          source: "generic",
          citation: null,
          destructive: false,
          tsql:
            "SELECT DB_NAME(mf.database_id) AS database_name, mf.name AS logical_name,\n" +
            "       mf.physical_name, mf.type_desc,\n" +
            "       mf.size * 8 / 1024.0 AS allocated_mb,\n" +
            "       vs.volume_mount_point,\n" +
            "       vs.available_bytes / 1073741824.0 AS volume_free_gb\n" +
            "FROM sys.master_files mf\n" +
            "CROSS APPLY sys.dm_os_volume_stats(mf.database_id, mf.file_id) vs\n" +
            "WHERE vs.volume_mount_point = N'D:\\'\n" +
            "ORDER BY mf.size DESC;",
        },
        {
          action: "Check whether old backup files are the consumer",
          what_it_does:
            "Lists backup history with device paths and sizes so retention can be assessed " +
            "against what is actually on the volume.",
          expected_effect: "Identifies reclaimable space that is already copied off-box.",
          blast_radius: "read_only",
          reversible: true,
          how_to_undo: "Nothing to undo; this only reads.",
          requires_approval: false,
          source: "generic",
          citation: null,
          destructive: false,
          tsql:
            "SELECT TOP 50 bs.database_name, bs.backup_finish_date,\n" +
            "       bs.backup_size / 1073741824.0 AS size_gb, bmf.physical_device_name\n" +
            "FROM msdb.dbo.backupset bs\n" +
            "JOIN msdb.dbo.backupmediafamily bmf ON bmf.media_set_id = bs.media_set_id\n" +
            "ORDER BY bs.backup_finish_date DESC;",
        },
        {
          action: "Delete backup files outside the retention window",
          what_it_does:
            "Removes backup files from the volume, at the OS level or via a maintenance " +
            "cleanup task.",
          expected_effect: "Free space is reclaimed immediately.",
          blast_radius: "host",
          reversible: false,
          how_to_undo:
            "Not reversible. Deleted backups are gone; if they were the only copy, the restore " +
            "points they represented are gone with them. Confirm the off-box copy exists before " +
            "this runs.",
          requires_approval: true,
          source: "generic",
          citation: null,
          destructive: true,
          tsql:
            "-- No T-SQL by design: this is an OS-level file deletion, and the\n" +
            "-- decision needs the retention policy and the off-box copy confirmed\n" +
            "-- by a human first.\n" +
            "-- Verify off-box copies, then delete through the agreed cleanup task.",
        },
      ],
    },
  };
}

function jobCondition(): DetectedCondition {
  return {
    code: "AGENT_JOB_FAILURE",
    severity: "critical",
    title: "1 SQL Agent job(s) failed on last run",
    detail: "Failed jobs: WWI - Nightly Full Backup.",
    scope: "WWI - Nightly Full Backup",
    impact_score: 60,
    facts: { failed_job_count: 1, failed_job_names: ["WWI - Nightly Full Backup"] },
    evidence: [
      "1 SQL Agent job(s) last finished with run_status = 0 (Failed) in msdb.dbo.sysjobhistory.",
      "WWI - Nightly Full Backup failed: the step could not write to the backup device.",
    ],
    hold_off: [
      "Do not re-run a failed backup or ETL job before reading the step output. A job that " +
        "failed on disk space or a lock will fail the same way and can make the underlying " +
        "condition worse.",
    ],
    detected_at: iso(600),
    runbook: {
      has_team_procedure: true,
      sections: [
        {
          doc_id: "c3d4e5f6a1b2",
          doc_title: "confluence export storage",
          doc_filename: "confluence-export-storage.html",
          heading: "SQL Agent job failed overnight",
          heading_path: ["Storage and Volume Procedures", "SQL Agent job failed overnight"],
          anchor: "storage-and-volume-procedures-sql-agent-job-failed-overnight",
          citation:
            "confluence export storage - Storage and Volume Procedures > SQL Agent job failed " +
            "overnight (confluence-export-storage.html#storage-and-volume-procedures-sql-agent-" +
            "job-failed-overnight, heading \"SQL Agent job failed overnight\")",
          source_ref: "heading \"SQL Agent job failed overnight\"",
          body: "",
          steps: [],
          conditions: ["AGENT_JOB_FAILURE"],
          mapping_reason: "declared in the document",
          score: 2.5,
          match_reason: "document declares this condition explicitly",
        },
      ],
      note: null,
    },
    plan: {
      condition: "AGENT_JOB_FAILURE",
      has_team_procedure: true,
      guidance_source: "runbook",
      citations: [STORAGE_CITATION],
      hold_off: [],
      actions: [
        {
          action:
            "Step 1: Read the failing step output, not the job-level summary.",
          what_it_does:
            "Read the failing step output, not the job-level summary. The job history summary " +
            "almost never contains the actual error.",
          expected_effect:
            "As documented in confluence export storage. SQLGuardian does not restate the " +
            "expected effect of your team's step.",
          blast_radius: "read_only",
          reversible: true,
          how_to_undo: "No change, or reversible by the procedure that documents it.",
          requires_approval: false,
          source: "runbook",
          citation: STORAGE_CITATION,
          destructive: false,
          tsql: null,
        },
        {
          action: "Read the failing step output for 'WWI - Nightly Full Backup'",
          what_it_does:
            "Pulls the per-step history rows, not the job-level summary, so the actual error " +
            "text is visible.",
          expected_effect: "You see why it failed rather than that it failed.",
          blast_radius: "read_only",
          reversible: true,
          how_to_undo: "Nothing to undo; this only reads.",
          requires_approval: false,
          source: "generic",
          citation: null,
          destructive: false,
          tsql:
            "SELECT TOP 20 j.name AS job_name, h.step_id, h.step_name,\n" +
            "       msdb.dbo.agent_datetime(h.run_date, h.run_time) AS run_time,\n" +
            "       h.run_status, h.message\n" +
            "FROM msdb.dbo.sysjobhistory h\n" +
            "JOIN msdb.dbo.sysjobs j ON j.job_id = h.job_id\n" +
            "WHERE j.name = N'WWI - Nightly Full Backup'\n" +
            "ORDER BY h.instance_id DESC;",
        },
        {
          action: "Re-run 'WWI - Nightly Full Backup' after the cause is understood",
          what_it_does: "Starts the job again through msdb.dbo.sp_start_job.",
          expected_effect:
            "The job runs on its normal schedule path. If the underlying cause is still " +
            "present it fails the same way.",
          blast_radius: "instance",
          reversible: false,
          how_to_undo:
            "Not reversible in general: whatever the job does - a backup, an ETL load, an " +
            "index rebuild - is done. sp_stop_job halts a run in progress but does not undo " +
            "completed steps.",
          requires_approval: true,
          source: "generic",
          citation: null,
          destructive: false,
          tsql: "EXEC msdb.dbo.sp_start_job @job_name = N'WWI - Nightly Full Backup';",
        },
      ],
    },
  };
}

export function demoConditions(instance: string): ConditionsResponse {
  const conditions: DetectedCondition[] =
    instance === "primary"
      ? [blockingCondition()]
      : instance === "prod-sql01"
        ? [diskCondition(87), jobCondition()]
        : [];

  return {
    instance,
    snapshot_time: iso(20),
    overall_severity:
      conditions.length === 0
        ? "healthy"
        : conditions.some((c) => c.severity === "critical")
          ? "critical"
          : "warning",
    condition_count: conditions.length,
    failed_checks: [],
    conditions,
  };
}

// ------------------------------------------------------------- gap  report --

export const demoGapReport: GapReport = {
  generated_at: iso(),
  window_days: 90,
  total_firings: 23,
  documents_in_corpus: 4,
  conditions_covered_by_corpus: [
    "AGENT_JOB_FAILURE",
    "BACKUP_AGE_EXCEEDED",
    "BLOCKING_CHAIN",
    "LOG_GROWTH",
    "LONG_RUNNING_REQUEST",
  ],
  conditions_not_covered_by_corpus: ["DISK_PRESSURE", "WAIT_SPIKE"],
  uncovered_firings: [
    {
      condition: "DISK_PRESSURE",
      firings: 7,
      last_seen: iso(240),
      severity_seen: ["critical", "warning"],
    },
    {
      condition: "WAIT_SPIKE",
      firings: 2,
      last_seen: iso(86_400 * 6),
      severity_seen: ["warning"],
    },
  ],
  covered_firings: [
    {
      condition: "BLOCKING_CHAIN",
      firings: 9,
      last_seen: iso(180),
      citations: [BLOCKING_CITATION],
    },
    {
      condition: "AGENT_JOB_FAILURE",
      firings: 5,
      last_seen: iso(600),
      citations: [STORAGE_CITATION],
    },
  ],
  never_fired_gaps: [],
  headline:
    "2 condition type(s) fired 9 time(s) in the last 90 days with no documented procedure: " +
    "DISK_PRESSURE, WAIT_SPIKE.",
};

// ----------------------------------------------------------------- reports --

export function demoIncidentReport(instance: string): IncidentReportResponse {
  const technical = `# Incident INC-4C1A9F20 - ${instance}

- Severity: **critical** (computed from checks, not narrated)
- Opened: ${new Date().toISOString().replace("T", " ").slice(0, 19)} UTC
- Closed: still open
- Duration: still open

## Summary

A blocking chain formed on WideWorldImporters behind session 62, an OrderService (.NET)
connection running an UPDATE against Sales.OrderLines. Four sessions were blocked, the longest
for 218 seconds. Server health, disk and backup checks were all inside threshold at the time,
so the chain is the whole incident rather than a symptom of resource pressure. The documented
team procedure for this condition was retrieved and is cited below.

## What fired

### BLOCKING_CHAIN - Blocking chain: 4 session(s) blocked behind session 62

- Severity: critical
- Blast radius score: 86
- Scope: session 62 / WideWorldImporters

Evidence:

- 4 session(s) blocked, longest wait 218s (sys.dm_exec_requests.blocking_session_id > 0).
- Head blocker is session 62, login wwi_app, program OrderService (.NET).
- Statement holding the lock: UPDATE Sales.OrderLines SET PickedQuantity = @qty, LastEditedBy = @user WHERE OrderLineID = @id;

Not yet:

- Do not KILL the head blocker before identifying who owns it. A rollback of a large open transaction can hold the same locks for longer than the original block.

## What was checked

| Check | Verdict | Observed |
|---|---|---|
| server_health | healthy | cpu_pct=34, memory_used_pct=61.2 |
| blocking | critical | blocked_session_count=4, max_wait_seconds=218 |
| wait_stats | healthy | mode=delta, top_wait_type=LCK_M_X |
| long_running_queries | healthy | long_running_count=0 |
| agent_jobs | healthy | failed_count=0 |
| disk_usage | healthy | max_used_pct=71 |
| database_status | healthy | databases_missing_backup=0 |

## Sources

- ${BLOCKING_CITATION}
`;

  const business = `# ${instance} - incident summary

Reference: INC-4C1A9F20
Status: open
Assessed severity: critical

Order processing was slow for a period this morning because one piece of work held a lock that
several other requests were waiting behind. Nothing was lost and no data was affected. The team
is following its documented procedure for this situation, which requires contacting the owning
application team before any disruptive step is taken.
`;

  return {
    incident_id: "INC-4C1A9F20",
    instance,
    severity: "critical",
    technical_report: technical,
    business_summary: business,
    narration: {
      technical_narrative: "",
      business_summary: "",
      model: "openai/gpt-oss-120b (demo replay)",
      generated_at: iso(),
      available: true,
      unavailable_reason: null,
      verified: true,
      unsupported_numbers: [],
      business_leaks: [],
    },
    evidence: {},
  };
}
