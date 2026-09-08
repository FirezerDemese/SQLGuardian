import type { Snapshot } from "../types/api";

export function buildPlainSummary(snapshot: Snapshot | undefined): string[] {
  if (!snapshot) return [];
  const lines: string[] = [];
  const blocking = snapshot.blocking || ({} as Snapshot["blocking"]);
  const jobs = snapshot.agent_jobs || ({} as Snapshot["agent_jobs"]);
  const dbs = snapshot.database_status || ({} as Snapshot["database_status"]);
  const disk = snapshot.disk_usage || ({} as Snapshot["disk_usage"]);
  const server = snapshot.server_health || ({} as Snapshot["server_health"]);

  if (blocking.blocked_session_count > 0) {
    lines.push(
      `${blocking.blocked_session_count} session${
        blocking.blocked_session_count > 1 ? "s are" : " is"
      } stuck waiting on another, for up to ${Math.round(blocking.max_wait_seconds)}s.`
    );
  }

  if (jobs.failed_count > 0) {
    lines.push(
      `${jobs.failed_count} scheduled job${jobs.failed_count > 1 ? "s" : ""} failed recently.`
    );
  }

  if (dbs.databases_missing_backup > 0) {
    lines.push(
      `${dbs.databases_missing_backup} database${
        dbs.databases_missing_backup > 1 ? "s haven't" : " hasn't"
      } been backed up in over a day.`
    );
  }

  if (disk.max_used_pct >= 80) {
    lines.push(`Disk space is running low (${disk.max_used_pct}% used).`);
  }

  if (server.cpu?.severity === "critical" || server.cpu?.severity === "warning") {
    lines.push(`CPU usage is elevated at ${server.cpu.sql_cpu_pct}%.`);
  }

  if (server.memory?.severity === "critical" || server.memory?.severity === "warning") {
    lines.push(`Memory usage is elevated at ${server.memory.used_pct}%.`);
  }

  if (lines.length === 0) {
    lines.push("Everything is running smoothly — no action needed right now.");
  }

  return lines;
}
