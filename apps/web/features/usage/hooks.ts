import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { UseQueryResult, UseMutationResult } from "@tanstack/react-query";
import { queryKeys } from "@/lib/queryKeys";
import { getAgentSteps, getLlmUsage, deleteAllUsage } from "./api";
import type { AgentStep, LlmUsageRow } from "./api";

export function useAgentSteps(): UseQueryResult<AgentStep[]> {
  return useQuery({ queryKey: queryKeys.usage.steps, queryFn: getAgentSteps });
}

export function useLlmUsage(): UseQueryResult<LlmUsageRow[]> {
  return useQuery({ queryKey: queryKeys.usage.llm, queryFn: () => getLlmUsage() });
}

export function useLlmCalls(): UseQueryResult<LlmUsageRow[]> {
  return useQuery({ queryKey: queryKeys.usage.llmCalls, queryFn: () => getLlmUsage(100) });
}

export function useDeleteAllUsage(): UseMutationResult<void, Error, void> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteAllUsage,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.usage.steps });
      void qc.invalidateQueries({ queryKey: queryKeys.usage.llm });
    },
  });
}
