import { useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";
import { queryKeys } from "@/lib/queryKeys";
import { getRecommendation } from "./api";
import type { Recommendation } from "./api";

export function useRecommendation(id: string): UseQueryResult<Recommendation> {
  return useQuery({
    queryKey: queryKeys.recommendations.detail(id),
    queryFn: () => getRecommendation(id),
    enabled: !!id,
  });
}
