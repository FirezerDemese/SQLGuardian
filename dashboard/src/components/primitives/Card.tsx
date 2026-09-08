import { cn } from "../../lib/cn";

export function Card({
  children,
  className,
  severityBorder,
}: {
  children: React.ReactNode;
  className?: string;
  severityBorder?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border-subtle bg-surface-card p-6 shadow-sm",
        severityBorder && "border-l-4",
        className
      )}
      style={severityBorder ? { borderLeftColor: severityBorder } : undefined}
    >
      {children}
    </div>
  );
}
