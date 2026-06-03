import { useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";
import { queryKeys } from "@/lib/queryKeys";
import { getAgentRegistry } from "./api";
import type { RegistryData } from "./api";

export function useAgentRegistry(): UseQueryResult<RegistryData> {
  return useQuery({ queryKey: queryKeys.agents.registry, queryFn: getAgentRegistry });
}
