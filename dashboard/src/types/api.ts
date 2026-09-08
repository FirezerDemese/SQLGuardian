export type Severity = "healthy" | "warning" | "critical" | "unknown";

export interface ServerHealth {
  collected_at: string;
  server_name: string;
  uptime_hours: number;
  start_time: string;
  cpu: { sql_cpu_pct: number; system_idle_pct: number; severity: Severity };
  memory: {
    total_mb: number;
    available_mb: number;
    used_pct: number;
    state: string;
    severity: Severity;
  };
  error?: string;
}

export interface BlockedSession {
  session_id: number;
  blocking_session_id: number;
  wait_type: string;
  wait_seconds: number;
  status: string;
  command: string;
  database_name: string;
  login_name: string;
  host_name: string;
  program_name: string;
  current_statement: string;
  full_batch: string;
}

export interface HeadBlocker {
  session_id: number;
  login_name: string;
  host_name: string;
  program_name: string;
  status: string;
  wait_type: string;
  cpu_time: number;
  reads: number;
  writes: number;
  sessions_blocked: number;
  current_sql: string;
}

export interface BlockingSnapshot {
  collected_at: string;
  blocked_session_count: number;
  head_blocker_count: number;
  max_wait_seconds: number;
  severity: Severity;
  blocked_sessions: BlockedSession[];
  head_blockers: HeadBlocker[];
  error?: string;
}

export interface WaitStat {
  wait_type: string;
  wait_seconds: number;
  resource_wait_seconds: number;
  signal_wait_seconds: number;
  waiting_tasks_count: number;
  avg_wait_seconds: number;
}

export interface WaitStats {
  collected_at: string;
  mode: "delta" | "cumulative";
  elapsed_seconds: number | null;
  top_waits: WaitStat[];
  error?: string;
}

export interface AgentJob {
  job_name: string;
  enabled: boolean | number; // SQL Server bit column comes through as 0/1, not a JSON boolean
  last_run_status: string;
  last_run_time: string | null;
  run_duration_hhmmss: number;
  last_run_message: string;
  last_run_seconds: number;
}

export interface RunningJob {
  job_name: string;
  started_at: string;
  running_seconds: number;
}

export interface AgentJobsSnapshot {
  collected_at: string;
  total_jobs: number;
  failed_count: number;
  running_count: number;
  severity: "healthy" | "critical";
  jobs: AgentJob[];
  running_jobs: RunningJob[];
  failed_jobs: AgentJob[];
  error?: string;
}

export interface DiskVolume {
  volume_mount_point: string;
  file_system_type: string;
  logical_volume_name: string;
  total_gb: number;
  available_gb: number;
  used_gb: number;
  used_pct: number;
  severity: Severity;
}

export interface DiskUsage {
  collected_at: string;
  volume_count: number;
  max_used_pct: number;
  severity: Severity;
  volumes: DiskVolume[];
  error?: string;
}

export interface DatabaseInfo {
  database_name: string;
  state: string;
  recovery_model: string;
  log_reuse_wait_desc: string;
  is_auto_shrink_on: boolean;
  is_auto_close_on: boolean;
  size_mb: number;
  last_full_backup: string | null;
  hours_since_full_backup: number | null;
  last_log_backup: string | null;
}

export interface DatabaseStatus {
  collected_at: string;
  database_count: number;
  databases_missing_backup: number;
  severity: "healthy" | "critical";
  databases: DatabaseInfo[];
  databases_missing_backup_names: string[];
  error?: string;
}

export interface LongRunningQuery {
  session_id: number;
  status: string;
  command: string;
  database_name: string;
  cpu_seconds: number;
  elapsed_seconds: number;
  reads: number;
  writes: number;
  logical_reads: number;
  blocking_session_id: number | null;
  login_name: string;
  host_name: string;
  program_name: string;
  current_statement: string;
}

export interface LongRunningQueries {
  collected_at: string;
  threshold_seconds: number;
  count: number;
  queries: LongRunningQuery[];
  error?: string;
}

export interface Snapshot {
  snapshot_time: string;
  instance: string;
  server_health: ServerHealth;
  blocking: BlockingSnapshot;
  wait_stats: WaitStats;
  long_running_queries: LongRunningQueries;
  agent_jobs: AgentJobsSnapshot;
  disk_usage: DiskUsage;
  database_status: DatabaseStatus;
  overall_severity: Severity;
}

// Verified actual shape: GET /instances/ returns {"instances": ["name1", ...]} —
// a plain list of instance name strings, not rich objects (see core/db_connection.py).
export interface InstanceListResponse {
  instances: string[];
}

export interface RegisterInstanceRequest {
  name: string;
  host: string;
  port?: number;
  user: string;
  password: string;
  database?: string;
  is_default?: boolean;
}

export interface RegisterInstanceResponse {
  status: string;
  instance: string;
}

export interface TestInstanceResponse {
  status: "connected";
  instance: string;
  server_name?: string;
  version?: string;
}

export interface AiExplainRequest {
  fresh?: boolean;
}

export interface AiTopIssue {
  issue: string;
  detail: string;
  impact: string;
  priority: "high" | "medium" | "low";
}

export interface AiExplainResponse {
  severity_label: Severity;
  headline: string;
  dba_summary: string;
  manager_summary: string;
  top_issues: AiTopIssue[];
  root_cause: string;
  generated_at: string;
  model: string;
  error?: string;
}

export interface AiSuggestRequest {
  issue_focus?: string | null;
  fresh?: boolean;
}

export interface AiRemediation {
  title: string;
  description: string;
  risk_level: "safe" | "low" | "medium" | "high";
  requires_approval: boolean;
  tsql: string;
  expected_outcome: string;
}

export interface AiSuggestResponse {
  remediations: AiRemediation[];
  immediate_actions: string[];
  monitoring_followup: string;
  generated_at: string;
  model: string;
  error?: string;
}

export interface AiAskRequest {
  question: string;
}

export interface AiAskResponse {
  question: string;
  answer: string;
  supporting_data: string;
  follow_up_suggestion: string;
  generated_at: string;
  model: string;
  error?: string;
}

// ---------------------------------------------------------------------------
// Runbook automation
// ---------------------------------------------------------------------------

export type ConditionCode =
  | "BLOCKING_CHAIN"
  | "AGENT_JOB_FAILURE"
  | "BACKUP_AGE_EXCEEDED"
  | "LOG_GROWTH"
  | "DISK_PRESSURE"
  | "WAIT_SPIKE"
  | "LONG_RUNNING_REQUEST";

export type BlastRadius =
  | "read_only"
  | "session"
  | "database"
  | "instance"
  | "host";

export interface RunbookSectionMatch {
  doc_id: string;
  doc_title: string;
  doc_filename: string;
  heading: string;
  heading_path: string[];
  anchor: string;
  citation: string;
  source_ref: string;
  body: string;
  steps: string[];
  conditions: ConditionCode[];
  mapping_reason: string;
  score: number;
  match_reason: string;
}

export interface ActionCandidate {
  action: string;
  what_it_does: string;
  expected_effect: string;
  blast_radius: BlastRadius;
  reversible: boolean;
  how_to_undo: string;
  requires_approval: boolean;
  /** "runbook" steps come from the team's own documented procedure. */
  source: "runbook" | "generic";
  tsql: string | null;
  citation: string | null;
  destructive: boolean;
}

export interface ActionPlan {
  condition: ConditionCode;
  has_team_procedure: boolean;
  guidance_source: "runbook" | "generic";
  citations: string[];
  hold_off: string[];
  actions: ActionCandidate[];
}

export interface DetectedCondition {
  code: ConditionCode;
  severity: Severity;
  title: string;
  detail: string;
  scope: string;
  impact_score: number;
  facts: Record<string, unknown>;
  evidence: string[];
  hold_off: string[];
  detected_at: string;
  runbook: {
    has_team_procedure: boolean;
    sections: RunbookSectionMatch[];
    note: string | null;
  };
  plan: ActionPlan;
}

export interface ConditionsResponse {
  instance: string;
  snapshot_time: string;
  overall_severity: Severity;
  condition_count: number;
  failed_checks: string[];
  conditions: DetectedCondition[];
}

export interface RunbookDocumentSummary {
  doc_id: string;
  title: string;
  filename: string;
  format: string;
  section_count: number;
  mapped_section_count: number;
  byte_size: number;
  ingested_at: string;
  conditions_covered: ConditionCode[];
}

export interface RunbookListResponse {
  supported_formats: string[];
  supported_extensions: string[];
  document_count: number;
  section_count: number;
  conditions_covered: ConditionCode[];
  conditions_not_covered: ConditionCode[];
  documents: RunbookDocumentSummary[];
}

export interface RunbookUploadResponse {
  doc_id: string;
  title: string;
  format: string;
  section_count: number;
  mapped_section_count: number;
  unmapped_section_count: number;
  conditions_covered: ConditionCode[];
  conditions_still_not_covered: ConditionCode[];
  note: string | null;
}

export interface GapReport {
  generated_at: string;
  window_days: number;
  total_firings: number;
  documents_in_corpus: number;
  conditions_covered_by_corpus: ConditionCode[];
  conditions_not_covered_by_corpus: ConditionCode[];
  uncovered_firings: {
    condition: ConditionCode;
    firings: number;
    last_seen: string | null;
    severity_seen: string[];
  }[];
  covered_firings: {
    condition: ConditionCode;
    firings: number;
    last_seen: string | null;
    citations: string[];
  }[];
  never_fired_gaps: ConditionCode[];
  headline: string;
}

export interface NarrationMeta {
  technical_narrative: string;
  business_summary: string;
  model: string;
  generated_at: string;
  available: boolean;
  unavailable_reason: string | null;
  verified: boolean;
  unsupported_numbers: string[];
  business_leaks: string[];
}

export interface IncidentReportResponse {
  incident_id: string;
  instance: string;
  severity: Severity;
  technical_report: string;
  business_summary: string;
  narration: NarrationMeta | null;
  evidence: Record<string, unknown>;
}
