import { Card } from "../primitives/Card";
import { MetricCard } from "../primitives/MetricCard";
import { RadialGauge } from "../charts/RadialGauge";
import { SEVERITY_HEX } from "../../types/severity";
import type { Snapshot } from "../../types/api";

export function MetricsRow({ snapshot }: { snapshot: Snapshot }) {
  const { server_health, blocking } = snapshot;

  const blockingSeverity = blocking.blocked_session_count > 0 ? blocking.severity : "healthy";

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <Card severityBorder={SEVERITY_HEX[server_health.cpu.severity]}>
        <RadialGauge
          label="SQL CPU"
          pct={server_health.cpu.sql_cpu_pct}
          severity={server_health.cpu.severity}
        />
      </Card>
      <Card severityBorder={SEVERITY_HEX[server_health.memory.severity]}>
        <RadialGauge
          label="Memory"
          pct={server_health.memory.used_pct}
          severity={server_health.memory.severity}
          sub={`${Math.round(server_health.memory.available_mb / 1024)}GB available`}
        />
      </Card>
      <MetricCard
        label="Uptime"
        value={server_health.uptime_hours}
        unit="hrs"
        severity="healthy"
        sub={`Since ${server_health.start_time?.slice(0, 10) ?? "—"}`}
      />
      <MetricCard
        label="Blocking"
        value={blocking.blocked_session_count}
        unit="sessions"
        severity={blockingSeverity}
        sub={
          blocking.blocked_session_count > 0
            ? `Max wait ${Math.round(blocking.max_wait_seconds)}s`
            : "No blocking detected"
        }
      />
    </div>
  );
}
