import { CheckCircle, XCircle, Clock, RefreshCw } from "lucide-react";
import { Badge } from "../primitives/Badge";
import { formatDateTime } from "../../lib/format";
import type { AgentJob, Severity } from "../../types/api";

function jobSeverity(status: string): Severity {
  if (status === "Failed") return "critical";
  if (status === "Succeeded") return "healthy";
  return "unknown";
}

function StatusIcon({ status }: { status: string }) {
  if (status === "Succeeded") return <CheckCircle className="h-4 w-4 text-severity-healthy" />;
  if (status === "Failed") return <XCircle className="h-4 w-4 text-severity-critical" />;
  if (status === "Running") return <RefreshCw className="h-4 w-4 animate-spin text-accent" />;
  return <Clock className="h-4 w-4 text-text-tertiary" />;
}

export function JobsList({ jobs }: { jobs: AgentJob[] }) {
  const sorted = [...jobs].sort((a, b) => {
    const prioritize = (s: string) => (s === "Failed" ? 0 : s === "Running" ? 1 : 2);
    return prioritize(a.last_run_status) - prioritize(b.last_run_status);
  });

  if (sorted.length === 0) {
    return <p className="py-4 text-sm text-text-tertiary">No agent jobs found.</p>;
  }

  return (
    <div className="flex flex-col">
      {sorted.map((job) => (
        <div
          key={job.job_name}
          className="flex items-start gap-3 border-b border-border-subtle py-4 first:pt-0 last:border-0"
        >
          <StatusIcon status={job.last_run_status} />
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-text-primary truncate">{job.job_name}</span>
              <Badge severity={jobSeverity(job.last_run_status)} className="text-[10px]">
                {job.last_run_status}
              </Badge>
              {!job.enabled && (
                <span className="text-[10px] uppercase tracking-wide text-text-tertiary">
                  disabled
                </span>
              )}
            </div>
            <div className="mt-1 text-xs text-text-tertiary">
              Last run: {formatDateTime(job.last_run_time)} · {job.last_run_seconds}s
            </div>
            {job.last_run_status === "Failed" && job.last_run_message && (
              <p className="mt-1 text-xs text-severity-critical line-clamp-2">
                {job.last_run_message}
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
