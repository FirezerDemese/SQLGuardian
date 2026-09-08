import { useQuery, useQueries } from "@tanstack/react-query";
import { api } from "../api/endpoints";
import { queryKeys } from "../api/queryKeys";
import type { Snapshot } from "../types/api";

export function useInstances() {
  return useQuery({
    queryKey: queryKeys.instances,
    queryFn: api.getInstances,
    staleTime: 30000,
  });
}

export interface FleetEntry {
  name: string;
  snapshot: Snapshot | undefined;
  isLoading: boolean;
  isError: boolean;
}

export function useFleetSnapshots(instanceNames: string[]): FleetEntry[] {
  const results = useQueries({
    queries: instanceNames.map((name) => ({
      queryKey: queryKeys.snapshot(name),
      queryFn: () => api.getSnapshot(name),
      refetchInterval: 30000,
      retry: 1,
      staleTime: 10000,
    })),
  });

  return instanceNames.map((name, i) => ({
    name,
    snapshot: results[i].data,
    isLoading: results[i].isLoading,
    isError: results[i].isError,
  }));
}
