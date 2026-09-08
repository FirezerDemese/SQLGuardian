// Demo-mode fixtures: a realistic 4-instance fleet with one live incident.
// Timestamps are generated at call time so the dashboard always looks "live".
// The `primary` scenario mirrors the recorded demo: session 62 holds row locks
// on Sales.OrderLines and starves four downstream sessions.
import type {
  Snapshot,
  BlockingSnapshot,
  WaitStats,
  AgentJobsSnapshot,
  DatabaseStatus,
  AiExplainResponse,
  AiSuggestResponse,
  AiAskResponse,
  Severity,
} from "../types/api";

const iso = (secondsAgo = 0) =>
  new Date(Date.now() - secondsAgo * 1000).toISOString();

const isoHoursAgo = (h: number) => iso(h * 3600);

export const DEMO_INSTANCES = [
  "primary",
  "prod-sql01",
  "reporting-sql01",
  "prod-sql02",
];

// small deterministic jitter so repeated polls look alive without flapping severity
const jitter = (base: number, spread: number) =>
  Math.round((base + (Math.sin(Date.now() / 15000) + 1) * 0.5 * spread) * 10) / 10;

// ----------------------------------------------------------------- blocking --
function primaryBlocking(): BlockingSnapshot {
  const wait = (base: number) => jitter(base, 6);
  return {
    collected_at: iso(),
    blocked_session_count: 4,
    head_blocker_count: 1,
    max_wait_seconds: wait(218.4),
    severity: "critical",
    head_blockers: [
      {
        session_id: 62,
        login_name: "wwi_app",
        host_name: "APP01",
        program_name: "OrderService (.NET)",
        status: "sleeping",
        wait_type: "LCK_M_X",
        cpu_time: 18240,
        reads: 91234,
        writes: 5121,
        sessions_blocked: 4,
        current_sql:
          "UPDATE Sales.OrderLines SET PickedQuantity = @qty, LastEditedBy = @user WHERE OrderLineID = @id;",
      },
    ],
    blocked_sessions: [
      {
        session_id: 71,
        blocking_session_id: 62,
        wait_type: "LCK_M_X",
        wait_seconds: wait(218.4),
        status: "suspended",
        command: "SELECT",
        database_name: "WideWorldImporters",
        login_name: "wwi_app",
        host_name: "APP01",
        program_name: "OrderService (.NET)",
        current_statement:
          "SELECT * FROM Sales.OrderLines WHERE OrderID = @order_id;",
        full_batch: "SELECT * FROM Sales.OrderLines WHERE OrderID = @order_id;",
      },
      {
        session_id: 84,
        blocking_session_id: 62,
        wait_type: "LCK_M_S",
        wait_seconds: wait(196.0),
        status: "suspended",
        command: "SELECT",
        database_name: "WideWorldImporters",
        login_name: "reporting_svc",
        host_name: "RPT02",
        program_name: "PowerBI Gateway",
        current_statement:
          "SELECT SUM(Quantity) FROM Sales.OrderLines WHERE PickingCompletedWhen IS NULL;",
        full_batch:
          "SELECT SUM(Quantity) FROM Sales.OrderLines WHERE PickingCompletedWhen IS NULL;",
      },
      {
        session_id: 93,
        blocking_session_id: 62,
        wait_type: "LCK_M_X",
        wait_seconds: wait(154.3),
        status: "suspended",
        command: "UPDATE",
        database_name: "WideWorldImporters",
        login_name: "wwi_app",
        host_name: "APP02",
        program_name: "OrderService (.NET)",
        current_statement:
          "UPDATE Sales.OrderLines SET Quantity = Quantity + @delta WHERE OrderLineID = @id;",
        full_batch:
          "UPDATE Sales.OrderLines SET Quantity = Quantity + @delta WHERE OrderLineID = @id;",
      },
      {
        session_id: 101,
        blocking_session_id: 62,
        wait_type: "LCK_M_S",
        wait_seconds: wait(131.7),
        status: "suspended",
        command: "SELECT",
        database_name: "WideWorldImporters",
        login_name: "wwi_app",
        host_name: "WEB03",
        program_name: "Storefront API",
        current_statement:
          "SELECT TOP 50 * FROM Sales.OrderLines ORDER BY LastEditedWhen DESC;",
        full_batch:
          "SELECT TOP 50 * FROM Sales.OrderLines ORDER BY LastEditedWhen DESC;",
      },
    ],
  };
}

function cleanBlocking(): BlockingSnapshot {
  return {
    collected_at: iso(),
    blocked_session_count: 0,
    head_blocker_count: 0,
    max_wait_seconds: 0,
    severity: "healthy",
    blocked_sessions: [],
    head_blockers: [],
  };
}

// -------------------------------------------------------------------- waits --
function waits(rows: Array<[string, number, number, number]>): WaitStats {
  return {
    collected_at: iso(),
    mode: "delta",
    elapsed_seconds: 60,
    top_waits: rows.map(([wait_type, wait_seconds, tasks, signalPct]) => ({
      wait_type,
      wait_seconds,
      resource_wait_seconds:
        Math.round(wait_seconds * (1 - signalPct) * 10) / 10,
      signal_wait_seconds: Math.round(wait_seconds * signalPct * 10) / 10,
      waiting_tasks_count: tasks,
      avg_wait_seconds: Math.round((wait_seconds / Math.max(tasks, 1)) * 100) / 100,
    })),
  };
}

// --------------------------------------------------------------------- jobs --
function jobs(
  failed: boolean,
  running: boolean
): AgentJobsSnapshot {
  const all = [
    {
      job_name: "WWI Nightly Index Maintenance",
      enabled: 1,
      last_run_status: failed ? "Failed" : "Succeeded",
      last_run_time: isoHoursAgo(7),
      run_duration_hhmmss: 1240,
      last_run_message: failed
        ? "The job failed. Unable to acquire lock on Sales.OrderLines within timeout (error 1222)."
        : "The job succeeded.",
      last_run_seconds: 762,
    },
    {
      job_name: "Full Backup - User Databases",
      enabled: 1,
      last_run_status: "Succeeded",
      last_run_time: isoHoursAgo(11),
      run_duration_hhmmss: 2130,
      last_run_message: "The job succeeded.",
      last_run_seconds: 1290,
    },
    {
      job_name: "Log Backup - 15 min",
      enabled: 1,
      last_run_status: "Succeeded",
      last_run_time: iso(540),
      run_duration_hhmmss: 14,
      last_run_message: "The job succeeded.",
      last_run_seconds: 14,
    },
    {
      job_name: "DBCC CHECKDB - Weekly",
      enabled: 1,
      last_run_status: "Succeeded",
      last_run_time: isoHoursAgo(52),
      run_duration_hhmmss: 4515,
      last_run_message: "The job succeeded.",
      last_run_seconds: 2715,
    },
    {
      job_name: "Purge Audit History",
      enabled: 0,
      last_run_status: "Succeeded",
      last_run_time: isoHoursAgo(170),
      run_duration_hhmmss: 105,
      last_run_message: "The job succeeded.",
      last_run_seconds: 65,
    },
  ];
  const failedJobs = all.filter((j) => j.last_run_status === "Failed");
  return {
    collected_at: iso(),
    total_jobs: all.length,
    failed_count: failedJobs.length,
    running_count: running ? 1 : 0,
    severity: failedJobs.length ? "critical" : "healthy",
    jobs: all,
    running_jobs: running
      ? [
          {
            job_name: "ETL - Load Staging Warehouse",
            started_at: iso(310),
            running_seconds: 310,
          },
        ]
      : [],
    failed_jobs: failedJobs,
  };
}

// ---------------------------------------------------------------- databases --
function databases(missingBackup: boolean): DatabaseStatus {
  const dbs = [
    {
      database_name: "WideWorldImporters",
      state: "ONLINE",
      recovery_model: "FULL",
      log_reuse_wait_desc: "NOTHING",
      is_auto_shrink_on: false,
      is_auto_close_on: false,
      size_mb: 3720,
      last_full_backup: isoHoursAgo(11),
      hours_since_full_backup: 11,
      last_log_backup: iso(540),
    },
    {
      database_name: "AdventureWorks2022",
      state: "ONLINE",
      recovery_model: "FULL",
      log_reuse_wait_desc: "LOG_BACKUP",
      is_auto_shrink_on: false,
      is_auto_close_on: false,
      size_mb: 1280,
      last_full_backup: isoHoursAgo(11),
      hours_since_full_backup: 11,
      last_log_backup: iso(540),
    },
    {
      database_name: "StagingWarehouse",
      state: "ONLINE",
      recovery_model: "SIMPLE",
      log_reuse_wait_desc: "NOTHING",
      is_auto_shrink_on: false,
      is_auto_close_on: false,
      size_mb: 8450,
      last_full_backup: missingBackup ? null : isoHoursAgo(11),
      hours_since_full_backup: missingBackup ? null : 11,
      last_log_backup: null,
    },
  ];
  const missing = dbs.filter((d) => d.last_full_backup === null);
  return {
    collected_at: iso(),
    database_count: dbs.length,
    databases_missing_backup: missing.length,
    severity: missing.length ? "critical" : "healthy",
    databases: dbs,
    databases_missing_backup_names: missing.map((d) => d.database_name),
  };
}

// ---------------------------------------------------------------- snapshots --
interface InstanceSpec {
  cpu: number;
  mem: number;
  severity: Severity;
  blocking: () => BlockingSnapshot;
  waits: () => WaitStats;
  jobs: () => AgentJobsSnapshot;
  databases: () => DatabaseStatus;
  diskMax: number;
  longRunning: boolean;
}

const SPECS: Record<string, InstanceSpec> = {
  primary: {
    cpu: 88,
    mem: 74,
    severity: "critical",
    blocking: primaryBlocking,
    waits: () =>
      waits([
        ["LCK_M_X", 118.6, 9, 0.04],
        ["LCK_M_S", 64.2, 7, 0.05],
        ["PAGEIOLATCH_SH", 12.8, 210, 0.1],
        ["WRITELOG", 6.4, 480, 0.22],
        ["SOS_SCHEDULER_YIELD", 4.1, 900, 1.0],
      ]),
    jobs: () => jobs(true, true),
    databases: () => databases(false),
    diskMax: 71,
    longRunning: true,
  },
  "prod-sql01": {
    cpu: 61,
    mem: 68,
    severity: "warning",
    blocking: cleanBlocking,
    waits: () =>
      waits([
        ["PAGEIOLATCH_SH", 28.4, 340, 0.08],
        ["CXPACKET", 19.6, 120, 0.35],
        ["WRITELOG", 8.2, 610, 0.2],
        ["ASYNC_NETWORK_IO", 5.1, 95, 0.1],
        ["SOS_SCHEDULER_YIELD", 3.3, 720, 1.0],
      ]),
    jobs: () => jobs(false, false),
    databases: () => databases(true),
    diskMax: 87,
    longRunning: false,
  },
  "reporting-sql01": {
    cpu: 22,
    mem: 45,
    severity: "healthy",
    blocking: cleanBlocking,
    waits: () =>
      waits([
        ["CXPACKET", 9.8, 60, 0.4],
        ["PAGEIOLATCH_SH", 4.2, 88, 0.09],
        ["ASYNC_NETWORK_IO", 2.6, 40, 0.12],
        ["WRITELOG", 1.1, 130, 0.25],
        ["LATCH_EX", 0.7, 25, 0.2],
      ]),
    jobs: () => jobs(false, false),
    databases: () => databases(false),
    diskMax: 54,
    longRunning: false,
  },
  "prod-sql02": {
    cpu: 34,
    mem: 51,
    severity: "healthy",
    blocking: cleanBlocking,
    waits: () =>
      waits([
        ["PAGEIOLATCH_SH", 7.4, 150, 0.1],
        ["WRITELOG", 3.8, 300, 0.2],
        ["CXPACKET", 2.9, 35, 0.3],
        ["ASYNC_NETWORK_IO", 1.8, 30, 0.11],
        ["SOS_SCHEDULER_YIELD", 1.2, 400, 1.0],
      ]),
    jobs: () => jobs(false, false),
    databases: () => databases(false),
    diskMax: 62,
    longRunning: false,
  },
};

export function demoSnapshot(instance: string): Snapshot {
  const spec = SPECS[instance] ?? SPECS["prod-sql02"];
  const cpu = jitter(spec.cpu, 4);
  const mem = jitter(spec.mem, 2);
  return {
    snapshot_time: iso(),
    instance,
    overall_severity: spec.severity,
    server_health: {
      collected_at: iso(),
      server_name: instance.toUpperCase(),
      uptime_hours: 412.6,
      start_time: isoHoursAgo(412.6),
      cpu: {
        sql_cpu_pct: cpu,
        system_idle_pct: Math.max(0, 100 - cpu - 6),
        severity:
          cpu >= 85 ? "critical" : cpu >= 60 ? "warning" : "healthy",
      },
      memory: {
        total_mb: 65536,
        available_mb: Math.round(65536 * (1 - mem / 100)),
        used_pct: mem,
        state: "Available physical memory is high",
        severity: mem >= 90 ? "critical" : mem >= 75 ? "warning" : "healthy",
      },
    },
    blocking: spec.blocking(),
    wait_stats: spec.waits(),
    long_running_queries: {
      collected_at: iso(),
      threshold_seconds: 30,
      count: spec.longRunning ? 1 : 0,
      queries: spec.longRunning
        ? [
            {
              session_id: 62,
              status: "sleeping",
              command: "UPDATE",
              database_name: "WideWorldImporters",
              cpu_seconds: 18.2,
              elapsed_seconds: jitter(47.2, 6),
              reads: 91234,
              writes: 5121,
              logical_reads: 402118,
              blocking_session_id: null,
              login_name: "wwi_app",
              host_name: "APP01",
              program_name: "OrderService (.NET)",
              current_statement:
                "UPDATE Sales.OrderLines SET PickedQuantity = @qty WHERE OrderLineID = @id;",
            },
          ]
        : [],
    },
    agent_jobs: spec.jobs(),
    disk_usage: {
      collected_at: iso(),
      volume_count: 3,
      max_used_pct: spec.diskMax,
      severity:
        spec.diskMax >= 90
          ? "critical"
          : spec.diskMax >= 80
            ? "warning"
            : "healthy",
      volumes: [
        {
          volume_mount_point: "C:\\",
          file_system_type: "NTFS",
          logical_volume_name: "System",
          total_gb: 256,
          available_gb: 118,
          used_gb: 138,
          used_pct: 54,
          severity: "healthy",
        },
        {
          volume_mount_point: "D:\\",
          file_system_type: "NTFS",
          logical_volume_name: "Data",
          total_gb: 1024,
          available_gb: Math.round(1024 * (1 - spec.diskMax / 100)),
          used_gb: Math.round(1024 * (spec.diskMax / 100)),
          used_pct: spec.diskMax,
          severity:
            spec.diskMax >= 90
              ? "critical"
              : spec.diskMax >= 80
                ? "warning"
                : "healthy",
        },
        {
          volume_mount_point: "L:\\",
          file_system_type: "NTFS",
          logical_volume_name: "TLog",
          total_gb: 256,
          available_gb: 168,
          used_gb: 88,
          used_pct: 34,
          severity: "healthy",
        },
      ],
    },
    database_status: spec.databases(),
  };
}

// ----------------------------------------------------------------------- AI --
export function demoAiExplain(instance: string): AiExplainResponse {
  if (instance === "primary" || instance === undefined) {
    return {
      severity_label: "critical",
      headline:
        "Active blocking chain is starving 4 sessions — one long-running UPDATE is holding row locks on Sales.OrderLines.",
      dba_summary:
        "Session 62 opened a transaction against Sales.OrderLines and hasn't committed. Four sessions are queued on LCK_M_X / LCK_M_S, the longest waiting 47s. The head blocker is sleeping (awaiting app commit), so this will not clear on its own if the application has stalled. Wait stats confirm lock waits dominate the last interval; CPU at 88% is elevated but secondary.",
      manager_summary:
        "A stuck order-update job is slowing order lookups. No data risk — just a short delay resolving on its own or with a quick intervention by the DBA team.",
      top_issues: [
        {
          issue: "Blocking chain on Sales.OrderLines",
          detail:
            "Head blocker SPID 62 (wwi_app, APP01) holds row locks; 4 downstream sessions queued up to 47s.",
          impact: "4 downstream queries stalled; page load delays",
          priority: "high",
        },
        {
          issue: "SQL CPU at 88%",
          detail:
            "Sustained SQL CPU above the 85% critical threshold during the blocking window.",
          impact: "Reduced headroom for concurrent workloads",
          priority: "medium",
        },
        {
          issue: "Nightly index maintenance failed",
          detail:
            "WWI Nightly Index Maintenance failed with lock timeout (error 1222) — likely the same contention.",
          impact: "Index fragmentation will grow until re-run",
          priority: "low",
        },
      ],
      root_cause:
        "An application transaction (SPID 62) updated Sales.OrderLines and never committed — the session has been sleeping with an open transaction for ~47s, serializing all readers and writers behind its row locks.",
      generated_at: iso(),
      model: "openai/gpt-oss-120b (demo replay)",
    };
  }
  if (instance === "prod-sql01") {
    return {
      severity_label: "warning",
      headline:
        "Data volume at 87% and one database missing a full backup — no active incidents.",
      dba_summary:
        "No blocking. Waits are IO-flavored (PAGEIOLATCH_SH) but within baseline. Two things need attention: the D: data volume is at 87% (warning threshold 80%), and StagingWarehouse has no full backup recorded.",
      manager_summary:
        "The server is healthy for users, but disk space is filling up and one internal database isn't backed up yet. Both are routine maintenance items.",
      top_issues: [
        {
          issue: "D: volume at 87%",
          detail: "1TB data volume has ~133GB free and is trending up.",
          impact: "Risk of autogrow failures if it reaches 100%",
          priority: "medium",
        },
        {
          issue: "StagingWarehouse missing full backup",
          detail: "No full backup recorded in msdb for this database.",
          impact: "No restore point if the volume is lost",
          priority: "medium",
        },
      ],
      root_cause:
        "Routine capacity and backup-coverage gaps — no active performance incident.",
      generated_at: iso(),
      model: "openai/gpt-oss-120b (demo replay)",
    };
  }
  return {
    severity_label: "healthy",
    headline: "All checks green — no blocking, jobs succeeded, backups current.",
    dba_summary:
      "No blocking sessions, wait profile is baseline (light CXPACKET from parallel reporting queries), all agent jobs succeeded, every database has a recent full backup, and disk headroom is comfortable.",
    manager_summary:
      "Everything is running normally. No action needed.",
    top_issues: [],
    root_cause: "No incident — server operating within all thresholds.",
    generated_at: iso(),
    model: "openai/gpt-oss-120b (demo replay)",
  };
}

export function demoAiSuggest(instance: string): AiSuggestResponse {
  if (instance === "primary") {
    return {
      remediations: [
        {
          title: "Identify and confirm the head blocker before acting",
          description:
            "Verify SPID 62 still holds the open transaction and see exactly what it ran and how long it has been idle.",
          risk_level: "safe",
          requires_approval: false,
          tsql: `SELECT s.session_id, s.status, s.host_name, s.program_name,
       s.last_request_end_time,
       t.text AS last_sql
FROM sys.dm_exec_sessions s
JOIN sys.dm_exec_connections c ON c.session_id = s.session_id
CROSS APPLY sys.dm_exec_sql_text(c.most_recent_sql_handle) t
WHERE s.session_id = 62;`,
          expected_outcome:
            "Confirms the blocker is idle-in-transaction and shows the exact statement holding locks.",
        },
        {
          title: "Ask the application owner to commit or roll back",
          description:
            "The blocker belongs to OrderService on APP01. A graceful commit/rollback from the app side clears the chain with zero data risk.",
          risk_level: "low",
          requires_approval: false,
          tsql: `-- No T-SQL: coordinate with the OrderService owner (host APP01).
-- Monitor the chain while you wait:
SELECT session_id, blocking_session_id, wait_type, wait_time/1000.0 AS wait_s
FROM sys.dm_exec_requests
WHERE blocking_session_id <> 0
ORDER BY wait_time DESC;`,
          expected_outcome:
            "Blocking chain drains naturally once the transaction ends; blocked sessions complete in order.",
        },
        {
          title: "KILL the head blocker (last resort)",
          description:
            "If the app is unresponsive and business impact is growing, kill SPID 62. Its open transaction will roll back — measure rollback size first.",
          risk_level: "high",
          requires_approval: true,
          tsql: `-- Check how much work would roll back first:
DBCC OPENTRAN ('WideWorldImporters');

-- Then, only with approval:
KILL 62;

-- Watch rollback progress:
KILL 62 WITH STATUSONLY;`,
          expected_outcome:
            "Locks released within seconds (plus rollback time); the four blocked sessions proceed. The app transaction is lost and must be retried.",
        },
      ],
      immediate_actions: [
        "Confirm SPID 62 is idle-in-transaction (safe query above)",
        "Page the OrderService owner for APP01",
        "Hold off on KILL until rollback size is known",
      ],
      monitoring_followup:
        "Watch sys.dm_exec_requests for new waiters on Sales.OrderLines for the next 15 minutes, and re-run the nightly index job once the chain clears.",
      generated_at: iso(),
      model: "openai/gpt-oss-120b (demo replay)",
    };
  }
  return {
    remediations: [
      {
        title: "Reclaim space on the D: data volume",
        description:
          "Identify the biggest space consumers before expanding the disk.",
        risk_level: "safe",
        requires_approval: false,
        tsql: `SELECT TOP 10 d.name, mf.name AS file_name,
       mf.size * 8 / 1024 AS size_mb
FROM sys.master_files mf
JOIN sys.databases d ON d.database_id = mf.database_id
WHERE mf.physical_name LIKE 'D:%'
ORDER BY mf.size DESC;`,
        expected_outcome: "A ranked list of files to target for cleanup or moves.",
      },
      {
        title: "Take the missing full backup",
        description: "StagingWarehouse has no restore point.",
        risk_level: "safe",
        requires_approval: false,
        tsql: `BACKUP DATABASE StagingWarehouse
TO DISK = 'L:\\Backup\\StagingWarehouse_full.bak'
WITH COMPRESSION, CHECKSUM, STATS = 10;`,
        expected_outcome: "A verified full backup and a restore point for the database.",
      },
    ],
    immediate_actions: ["Run the space report", "Schedule the full backup off-peak"],
    monitoring_followup:
      "Track D: volume growth daily; alert again at 90%.",
    generated_at: iso(),
    model: "openai/gpt-oss-120b (demo replay)",
  };
}

export function demoAiAsk(question: string, instance: string): AiAskResponse {
  const q = question.toLowerCase();
  if (instance === "primary" && (q.includes("slow") || q.includes("block"))) {
    return {
      question,
      answer:
        "Your server is slow because of lock contention, not resources. Session 62 (wwi_app from APP01) has an uncommitted UPDATE holding exclusive row locks on Sales.OrderLines. Four sessions are queued behind it — the longest has waited about 47 seconds. Lock waits (LCK_M_X, LCK_M_S) dominate the last polling interval, which tells us this is a blocking problem: the CPU spike is a symptom, not the cause.",
      supporting_data:
        "sys.dm_exec_requests: 4 rows with blocking_session_id = 62 · sys.dm_os_wait_stats delta: LCK_M_X 118.6s, LCK_M_S 64.2s over 60s window · head blocker status: sleeping, open_transaction_count = 1",
      follow_up_suggestion:
        "Ask 'what is session 62 running?' or open Suggest Fixes for a step-by-step remediation with T-SQL.",
      generated_at: iso(),
      model: "openai/gpt-oss-120b (demo replay)",
    };
  }
  if (q.includes("backup")) {
    return {
      question,
      answer:
        instance === "prod-sql01"
          ? "Backups are mostly healthy: WideWorldImporters and AdventureWorks2022 both have full backups from ~11 hours ago and log backups within the last 15 minutes. The gap is StagingWarehouse — msdb has no full backup recorded for it, so it currently has no restore point."
          : "Backups are healthy. Every database has a full backup from the last nightly window (~11 hours ago), and log backups are running on the 15-minute cadence. The most recent log backup completed about 9 minutes ago.",
      supporting_data:
        "msdb.dbo.backupset: latest full per database · log chain intact · backup job 'Full Backup - User Databases' last status: Succeeded",
      follow_up_suggestion:
        "Ask 'which database is largest?' or 'when did the last CHECKDB run?'",
      generated_at: iso(),
      model: "openai/gpt-oss-120b (demo replay)",
    };
  }
  return {
    question,
    answer:
      instance === "primary"
        ? "Overall this instance is in a critical state driven by one issue: an active blocking chain on Sales.OrderLines (head blocker SPID 62, four waiters, ~218s max wait). Outside of that, backups are current, disks have headroom, and memory is stable. Resolve the blocker and this instance returns to green."
        : "This instance is operating normally: no blocking, baseline wait profile, all agent jobs succeeded, backups current, and disk usage within thresholds. Nothing needs attention right now.",
    supporting_data:
      "health snapshot: blocking, waits, jobs, disk, databases collected in the last 60s",
    follow_up_suggestion:
      "Try 'why is my server slow?' on the primary instance to see incident analysis.",
    generated_at: iso(),
    model: "openai/gpt-oss-120b (demo replay)",
  };
}
