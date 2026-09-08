import { useQuery } from "@tanstack/react-query";
import { useInstanceContext } from "../hooks/InstanceContext";
import { api } from "../api/endpoints";
import { queryKeys } from "../api/queryKeys";
import { Card } from "../components/primitives/Card";
import { JobsList } from "../components/instance/JobsList";

export function InstanceJobsPage() {
  const { name } = useInstanceContext();
  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.jobs(name),
    queryFn: () => api.getJobs(name),
    staleTime: 30000,
  });

  if (isLoading) return <p className="p-9 text-text-secondary">Loading agent jobs...</p>;
  if (isError || !data) return <p className="p-9 text-severity-critical">Failed to load jobs data.</p>;

  return (
    <div className="p-9">
      <div className="mb-6 flex items-center gap-3">
        <h2 className="text-xl font-semibold text-text-primary">Agent Jobs</h2>
        <span className="text-sm text-text-tertiary">
          {data.total_jobs} total · {data.failed_count} failed · {data.running_count} running
        </span>
      </div>
      <Card className="max-w-5xl">
        <JobsList jobs={data.jobs} />
      </Card>
    </div>
  );
}
