import { cn } from "../../lib/cn";
import { SEVERITY_HEX } from "../../types/severity";
import type { Severity } from "../../types/api";

export function ProgressBar({
  label,
  valueLabel,
  pct,
  severity,
  max = 100,
}: {
  label: string;
  valueLabel: string;
  pct: number;
  severity: Severity;
  max?: number;
}) {
  const widthPct = Math.min(100, Math.max(0, (pct / max) * 100));
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-medium text-text-secondary">{label}</span>
        <span className="text-text-tertiary">{valueLabel}</span>
      </div>
      <div className={cn("h-2 w-full overflow-hidden rounded-full bg-surface-sunken")}>
        <div
          className="h-full rounded-full transition-[width] duration-500 ease-out"
          style={{ width: `${widthPct}%`, backgroundColor: SEVERITY_HEX[severity] }}
        />
      </div>
    </div>
  );
}
