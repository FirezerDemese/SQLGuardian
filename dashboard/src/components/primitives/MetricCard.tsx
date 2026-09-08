import { Card } from "./Card";
import { SEVERITY_HEX } from "../../types/severity";
import type { Severity } from "../../types/api";

export function MetricCard({
  label,
  value,
  unit,
  severity,
  sub,
}: {
  label: string;
  value: string | number;
  unit?: string;
  severity: Severity;
  sub?: string;
}) {
  return (
    <Card severityBorder={SEVERITY_HEX[severity]}>
      <div className="text-xs font-medium uppercase tracking-wide text-text-tertiary">
        {label}
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-3xl font-semibold text-text-primary">{value}</span>
        {unit && <span className="text-sm text-text-tertiary">{unit}</span>}
      </div>
      {sub && <div className="mt-1 text-xs text-text-tertiary">{sub}</div>}
    </Card>
  );
}
