import { useQuery } from "@tanstack/react-query";
import { api } from "../api/endpoints";
import { queryKeys } from "../api/queryKeys";

export function useSnapshot(instanceName: string | undefined, intervalMs = 30000) {
  return useQuery({
    queryKey: queryKeys.snapshot(instanceName),
    queryFn: () => api.getSnapshot(instanceName),
    refetchInterval: intervalMs,
    enabled: !!instanceName,
    retry: 2,
    staleTime: 10000,
  });
}
