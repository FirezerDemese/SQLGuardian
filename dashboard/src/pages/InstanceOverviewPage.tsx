import { useInstanceContext } from "../hooks/InstanceContext";
import { PlainSummaryBanner } from "../components/instance/PlainSummaryBanner";
import { MetricsRow } from "../components/instance/MetricsRow";
import { DiskPanel } from "../components/instance/DiskPanel";
import { WaitsPanel } from "../components/instance/WaitsPanel";
import { SkeletonCard } from "../components/primitives/Skeleton";

export function InstanceOverviewPage() {
  const { query } = useInstanceContext();
  const snapshot = query.data;

  if (query.isLoading) {
    return (
      <div className="flex max-w-5xl flex-col gap-6 p-9">
        <SkeletonCard className="h-16" />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => <SkeletonCard key={i} className="h-36" />)}
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <SkeletonCard className="h-48" />
          <SkeletonCard className="h-48" />
        </div>
      </div>
    );
  }

  if (!snapshot) {
    return (
      <p className="p-9 text-severity-critical">
        Could not load data for this instance.
      </p>
    );
  }

  return (
    <div className="flex max-w-5xl flex-col gap-6 p-9">
      <PlainSummaryBanner snapshot={snapshot} />
      <MetricsRow snapshot={snapshot} />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <DiskPanel disk={snapshot.disk_usage} />
        <WaitsPanel waits={snapshot.wait_stats.top_waits} />
      </div>
    </div>
  );
}
