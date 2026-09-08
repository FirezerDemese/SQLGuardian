import { RefreshCw } from "lucide-react";
import { InstanceSwitcher } from "./InstanceSwitcher";
import { cn } from "../../lib/cn";

export function TopBar({
  instanceName,
  tabLabel,
  lastUpdated,
  isFetching,
  onRefresh,
}: {
  instanceName: string;
  tabLabel: string;
  lastUpdated: Date | undefined;
  isFetching: boolean;
  onRefresh: () => void;
}) {
  return (
    <div className="flex items-center justify-between border-b border-border-subtle bg-surface-card px-6 py-3">
      <div className="flex items-center gap-3">
        <nav className="text-sm text-text-tertiary">
          Fleet <span className="mx-1">/</span>
          <span className="text-text-secondary">{instanceName}</span>
          <span className="mx-1">/</span>
          <span className="font-medium text-text-primary">{tabLabel}</span>
        </nav>
        <InstanceSwitcher current={instanceName} />
      </div>
      <div className="flex items-center gap-3 text-xs text-text-tertiary">
        {lastUpdated && <span>Updated {lastUpdated.toLocaleTimeString()}</span>}
        <button
          onClick={onRefresh}
          className="flex items-center gap-1.5 rounded-lg border border-border-subtle px-2.5 py-1.5 text-text-secondary hover:bg-surface-sunken"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} />
          Refresh
        </button>
      </div>
    </div>
  );
}
