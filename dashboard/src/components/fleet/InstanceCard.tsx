import { useNavigate } from "react-router-dom";
import { Server } from "lucide-react";
import { Card } from "../primitives/Card";
import { Badge } from "../primitives/Badge";
import { Pulse } from "../primitives/Pulse";
import { SEVERITY_HEX } from "../../types/severity";
import type { Severity, Snapshot } from "../../types/api";

export function InstanceCard({
  name,
  snapshot,
  isLoading,
  isError,
}: {
  name: string;
  snapshot: Snapshot | undefined;
  isLoading: boolean;
  isError: boolean;
}) {
  const navigate = useNavigate();
  const severity: Severity = isError ? "unknown" : snapshot?.overall_severity ?? "unknown";

  return (
    <button
      onClick={() => navigate(`/instance/${encodeURIComponent(name)}`)}
      className="text-left"
    >
      <Card severityBorder={SEVERITY_HEX[severity]} className="transition-shadow hover:shadow-md">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Server className="h-4 w-4 text-text-tertiary" />
            <span className="font-semibold text-text-primary">{name}</span>
          </div>
          <Pulse severity={severity} />
        </div>

        {isLoading && <p className="mt-4 text-sm text-text-tertiary">Connecting...</p>}
        {isError && <p className="mt-4 text-sm text-severity-critical">Connection failed</p>}

        {snapshot && (
          <>
            <div className="mt-4">
              <Badge severity={snapshot.overall_severity} />
            </div>
            <div className="mt-4 grid grid-cols-3 gap-3 text-center">
              <Metric label="CPU" value={`${snapshot.server_health.cpu.sql_cpu_pct}%`} />
              <Metric label="Memory" value={`${snapshot.server_health.memory.used_pct}%`} />
              <Metric
                label="Blocking"
                value={String(snapshot.blocking.blocked_session_count)}
              />
            </div>
          </>
        )}
      </Card>
    </button>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-lg font-semibold text-text-primary">{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-text-tertiary">{label}</div>
    </div>
  );
}
