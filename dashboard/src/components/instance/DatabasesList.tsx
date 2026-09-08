import { Badge } from "../primitives/Badge";
import { formatMb } from "../../lib/format";
import type { DatabaseInfo, Severity } from "../../types/api";

function dbSeverity(db: DatabaseInfo): Severity {
  if (!db.last_full_backup || (db.hours_since_full_backup ?? 999) > 25) return "critical";
  return "healthy";
}

export function DatabasesList({ databases }: { databases: DatabaseInfo[] }) {
  if (databases.length === 0) {
    return <p className="py-4 text-sm text-text-tertiary">No databases found.</p>;
  }

  return (
    <div className="flex flex-col">
      {databases.map((db) => {
        const sev = dbSeverity(db);
        return (
          <div
            key={db.database_name}
            className="flex items-start justify-between gap-4 border-b border-border-subtle py-4 first:pt-0 last:border-0"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-text-primary">{db.database_name}</span>
                <Badge severity={sev} className="text-[10px]" />
              </div>
              <div className="mt-1 text-xs text-text-tertiary">
                {db.recovery_model} · {db.state} · {db.log_reuse_wait_desc}
              </div>
            </div>
            <div className="flex-none text-right text-xs text-text-secondary">
              <div>{formatMb(db.size_mb)}</div>
              <div className="mt-1 text-text-tertiary">
                {db.last_full_backup
                  ? `Backup ${db.hours_since_full_backup}h ago`
                  : "No backup found"}
              </div>
              {db.last_log_backup && (
                <div className="text-text-tertiary">
                  Log: {new Date(db.last_log_backup).toLocaleDateString()}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
