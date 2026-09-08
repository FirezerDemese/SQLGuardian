import { useMutation } from "@tanstack/react-query";
import { api } from "../api/endpoints";

export function useAiExplain() {
  return useMutation({ mutationFn: api.aiExplain });
}

export function useAiSuggest() {
  return useMutation({ mutationFn: api.aiSuggest });
}

export function useAiAsk() {
  return useMutation({ mutationFn: api.aiAsk });
}
