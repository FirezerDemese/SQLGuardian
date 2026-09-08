import { cn } from "../../lib/cn";
import type { Severity } from "../../types/api";
import { SEVERITY_LABEL } from "../../types/severity";

const styles: Record<Severity, string> = {
  healthy: "bg-severity-healthy-bg text-severity-healthy border-severity-healthy-border",
  warning: "bg-severity-warning-bg text-severity-warning border-severity-warning-border",
  critical: "bg-severity-critical-bg text-severity-critical border-severity-critical-border",
  unknown: "bg-severity-unknown-bg text-severity-unknown border-severity-unknown-border",
};

export function Badge({
  severity,
  children,
  className,
}: {
  severity: Severity;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide",
        styles[severity],
        className
      )}
    >
      {children ?? SEVERITY_LABEL[severity]}
    </span>
  );
}
