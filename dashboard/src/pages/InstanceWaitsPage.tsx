import { useQuery } from "@tanstack/react-query";
import { useInstanceContext } from "../hooks/InstanceContext";
import { api } from "../api/endpoints";
import { queryKeys } from "../api/queryKeys";
import { Card } from "../components/primitives/Card";
import { WaitBarsChart } from "../components/charts/WaitBarsChart";

export function InstanceWaitsPage() {
  const { name } = useInstanceContext();
  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.waits(name),
    queryFn: () => api.getWaits(name),
    staleTime: 30000,
  });

  if (isLoading) return <p className="p-9 text-text-secondary">Loading wait statistics...</p>;
  if (isError || !data) return <p className="p-9 text-severity-critical">Failed to load wait data.</p>;

  return (
    <div className="p-9">
      <div className="mb-6 flex items-center gap-3">
        <h2 className="text-xl font-semibold text-text-primary">Wait Statistics</h2>
        <span className="text-sm text-text-tertiary">
          Mode: {data.mode}
          {data.elapsed_seconds != null && ` · ${data.elapsed_seconds}s elapsed`}
        </span>
      </div>
      <Card className="max-w-5xl">
        <WaitBarsChart waits={data.top_waits} />
      </Card>
    </div>
  );
}
