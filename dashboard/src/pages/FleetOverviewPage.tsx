import { useState } from "react";
import { Plus } from "lucide-react";
import { useInstances } from "../hooks/useInstances";
import { FleetGrid } from "../components/fleet/FleetGrid";
import { AddInstanceDialog } from "../components/fleet/AddInstanceDialog";

export function FleetOverviewPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const { data, isLoading, isError } = useInstances();
  const instanceNames = data?.instances ?? [];

  return (
    <div className="p-9">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary">Fleet Overview</h1>
          <p className="mt-1 text-sm text-text-secondary">
            {instanceNames.length} instance{instanceNames.length === 1 ? "" : "s"} monitored
          </p>
        </div>
        <button
          onClick={() => setDialogOpen(true)}
          className="flex items-center gap-1.5 rounded-lg bg-accent px-3.5 py-2 text-sm font-medium text-white hover:bg-accent-hover"
        >
          <Plus className="h-4 w-4" />
          Add Instance
        </button>
      </div>

      <div className="mt-6">
        {isLoading && <p className="text-text-secondary">Loading instances...</p>}
        {isError && (
          <p className="text-severity-critical">Could not reach the SQLGuardian API.</p>
        )}
        {!isLoading && !isError && instanceNames.length === 0 && (
          <div className="rounded-xl border border-dashed border-border-subtle bg-surface-card p-10 text-center">
            <p className="text-text-secondary">No instances registered yet.</p>
            <button
              onClick={() => setDialogOpen(true)}
              className="mt-3 text-sm font-medium text-accent hover:underline"
            >
              Add your first instance
            </button>
          </div>
        )}
        {!isLoading && instanceNames.length > 0 && (
          <FleetGrid instanceNames={instanceNames} />
        )}
      </div>

      <AddInstanceDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  );
}
