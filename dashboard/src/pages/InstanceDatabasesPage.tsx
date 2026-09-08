import { useQuery } from "@tanstack/react-query";
import { useInstanceContext } from "../hooks/InstanceContext";
import { api } from "../api/endpoints";
import { queryKeys } from "../api/queryKeys";
import { Card } from "../components/primitives/Card";
import { DatabasesList } from "../components/instance/DatabasesList";

export function InstanceDatabasesPage() {
  const { name } = useInstanceContext();
  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.databases(name),
    queryFn: () => api.getDatabases(name),
    staleTime: 30000,
  });

  if (isLoading) return <p className="p-9 text-text-secondary">Loading databases...</p>;
  if (isError || !data) return <p className="p-9 text-severity-critical">Failed to load database data.</p>;

  return (
    <div className="p-9">
      <div className="mb-6 flex items-center gap-3">
        <h2 className="text-xl font-semibold text-text-primary">Databases</h2>
        <span className="text-sm text-text-tertiary">
          {data.database_count} databases · {data.databases_missing_backup} missing backup
        </span>
      </div>
      <Card className="max-w-5xl">
        <DatabasesList databases={data.databases} />
      </Card>
    </div>
  );
}
