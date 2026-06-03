import { useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";
import { queryKeys } from "@/lib/queryKeys";
import { getKpiTrends, getLlmCostEntries } from "./api";
import type { KpiTrend, LlmCostEntry } from "./api";

export function useKpiTrends(): UseQueryResult<KpiTrend[]> {
  return useQuery({ queryKey: queryKeys.kpi.trends, queryFn: getKpiTrends });
}

export function useLlmCostEntries(): UseQueryResult<LlmCostEntry[]> {
  return useQuery({ queryKey: queryKeys.kpi.llmCost, queryFn: getLlmCostEntries });
}
