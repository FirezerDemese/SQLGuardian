import { useFleetSnapshots } from "../../hooks/useInstances";
import { severityRank } from "../../types/severity";
import { InstanceCard } from "./InstanceCard";

export function FleetGrid({ instanceNames }: { instanceNames: string[] }) {
  const fleet = useFleetSnapshots(instanceNames);

  const sorted = [...fleet].sort((a, b) => {
    const ra = severityRank(a.snapshot?.overall_severity ?? "unknown");
    const rb = severityRank(b.snapshot?.overall_severity ?? "unknown");
    return ra - rb;
  });

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {sorted.map((entry) => (
        <InstanceCard
          key={entry.name}
          name={entry.name}
          snapshot={entry.snapshot}
          isLoading={entry.isLoading}
          isError={entry.isError}
        />
      ))}
    </div>
  );
}
