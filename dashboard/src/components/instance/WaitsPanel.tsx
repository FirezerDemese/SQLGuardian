import { Link } from "react-router-dom";
import { Card } from "../primitives/Card";
import { ProgressBar } from "../primitives/ProgressBar";
import type { Severity, WaitStat } from "../../types/api";

const WAIT_CAP_SECONDS = 4000;

function waitSeverity(seconds: number): Severity {
  const pct = (seconds / WAIT_CAP_SECONDS) * 100;
  if (pct > 70) return "critical";
  if (pct > 40) return "warning";
  return "healthy";
}

export function WaitsPanel({ waits }: { waits: WaitStat[] }) {
  const top5 = [...waits].sort((a, b) => b.wait_seconds - a.wait_seconds).slice(0, 5);

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">Top Wait Types</h3>
        <Link to="waits" className="text-xs font-medium text-accent hover:underline">
          View all
        </Link>
      </div>
      {top5.length === 0 ? (
        <p className="text-sm text-text-tertiary">No significant waits recorded.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {top5.map((w) => (
            <ProgressBar
              key={w.wait_type}
              label={w.wait_type}
              valueLabel={`${w.wait_seconds.toFixed(1)}s · ${w.waiting_tasks_count} tasks`}
              pct={Math.min(100, (w.wait_seconds / WAIT_CAP_SECONDS) * 100)}
              severity={waitSeverity(w.wait_seconds)}
            />
          ))}
        </div>
      )}
    </Card>
  );
}
