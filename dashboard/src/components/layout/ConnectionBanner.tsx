import { AlertTriangle } from "lucide-react";

export function ConnectionBanner({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 border-b border-severity-warning-border bg-severity-warning-bg px-6 py-2 text-sm text-severity-warning">
      <AlertTriangle className="h-4 w-4 shrink-0" />
      {message}
    </div>
  );
}
