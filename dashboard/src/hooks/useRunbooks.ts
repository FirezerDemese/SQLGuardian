import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/endpoints";
import { queryKeys } from "../api/queryKeys";

export function useConditions(instance: string | undefined) {
  return useQuery({
    queryKey: queryKeys.conditions(instance),
    queryFn: () => api.getConditions(instance),
    enabled: !!instance,
    refetchInterval: 30_000,
  });
}

export function useRunbooks() {
  return useQuery({
    queryKey: queryKeys.runbooks,
    queryFn: () => api.getRunbooks(),
  });
}

export function useRunbookGaps(days = 90) {
  return useQuery({
    queryKey: queryKeys.runbookGaps(days),
    queryFn: () => api.getRunbookGaps(days),
  });
}

export function useUploadRunbook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => api.uploadRunbook(file),
    // Coverage, gaps and every condition's retrieved procedure all change when
    // the corpus does.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runbooks });
      queryClient.invalidateQueries({ queryKey: ["runbook-gaps"] });
      queryClient.invalidateQueries({ queryKey: ["conditions"] });
    },
  });
}

export function useDeleteRunbook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (docId: string) => api.deleteRunbook(docId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runbooks });
      queryClient.invalidateQueries({ queryKey: ["runbook-gaps"] });
      queryClient.invalidateQueries({ queryKey: ["conditions"] });
    },
  });
}

export function useDraftIncidentReport() {
  return useMutation({
    mutationFn: (instance: string | undefined) => api.draftIncidentReport(instance),
  });
}
