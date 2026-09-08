import { cn } from "../../lib/cn";
import type { Severity } from "../../types/api";

const dotColor: Record<Severity, string> = {
  healthy: "bg-severity-healthy",
  warning: "bg-severity-warning",
  critical: "bg-severity-critical",
  unknown: "bg-severity-unknown",
};

export function Pulse({ severity, className }: { severity: Severity; className?: string }) {
  const animated = severity !== "healthy";
  return (
    <span className={cn("relative inline-flex h-2.5 w-2.5", className)}>
      {animated && (
        <span
          className={cn(
            "absolute inline-flex h-full w-full rounded-full opacity-75",
            dotColor[severity]
          )}
          style={{ animation: "ping 1.6s cubic-bezier(0,0,0.2,1) infinite" }}
        />
      )}
      <span className={cn("relative inline-flex h-2.5 w-2.5 rounded-full", dotColor[severity])} />
    </span>
  );
}
