import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { UseQueryResult, UseMutationResult } from "@tanstack/react-query";
import { queryKeys } from "@/lib/queryKeys";
import { getGroundTruth, saveGroundTruth, generateSampleData } from "./api";
import type { GroundTruthResponse, SampleDataTable } from "./api";

export function useGroundTruth(): UseQueryResult<GroundTruthResponse> {
  return useQuery({
    queryKey: queryKeys.settings.groundTruth,
    queryFn: getGroundTruth,
  });
}

export function useSaveGroundTruth(): UseMutationResult<void, Error, GroundTruthResponse> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: saveGroundTruth,
    onSuccess: () => void qc.invalidateQueries({ queryKey: queryKeys.settings.groundTruth }),
  });
}

export function useGenerateSampleData(): UseMutationResult<
  { tables: SampleDataTable[] },
  Error,
  {
    seed: number;
    sku_count: number;
    horizon_days: number;
    warehouse_count: number;
    missing_rate: number;
  }
> {
  return useMutation({ mutationFn: generateSampleData });
}
