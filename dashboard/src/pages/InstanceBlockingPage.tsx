import { useQuery } from "@tanstack/react-query";
import { useInstanceContext } from "../hooks/InstanceContext";
import { api } from "../api/endpoints";
import { queryKeys } from "../api/queryKeys";
import { Badge } from "../components/primitives/Badge";
import { BlockingPanel } from "../components/instance/BlockingPanel";

export function InstanceBlockingPage() {
  const { name } = useInstanceContext();
  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.blocking(name),
    queryFn: () => api.getBlocking(name),
    refetchInterval: 15000,
    staleTime: 10000,
  });

  if (isLoading) return <p className="p-9 text-text-secondary">Loading blocking data...</p>;
  if (isError || !data) return <p className="p-9 text-severity-critical">Failed to load blocking data.</p>;

  return (
    <div className="p-9">
      <div className="mb-6 flex items-center gap-3">
        <h2 className="text-xl font-semibold text-text-primary">Blocking</h2>
        <Badge severity={data.severity} />
        <span className="text-sm text-text-tertiary">
          {data.blocked_session_count} blocked · {data.head_blocker_count} head blockers
          {data.max_wait_seconds > 0 && ` · Max wait ${Math.round(data.max_wait_seconds)}s`}
        </span>
      </div>
      <div className="max-w-6xl">
        <BlockingPanel blocking={data} />
      </div>
    </div>
  );
}
