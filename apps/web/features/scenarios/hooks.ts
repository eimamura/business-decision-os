import { useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";
import { queryKeys } from "@/lib/queryKeys";
import { getScenarios } from "./api";
import type { Candidate } from "./api";

export function useScenarios(sessionId: string): UseQueryResult<Candidate[]> {
  return useQuery({
    queryKey: queryKeys.scenarios.detail(sessionId),
    queryFn: () => getScenarios(sessionId),
    enabled: !!sessionId,
  });
}
