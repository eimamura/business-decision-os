import { useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";
import { queryKeys } from "@/lib/queryKeys";
import { getAuditEntries } from "./api";
import type { AuditEntry } from "./api";

export function useAuditEntries(
  params?: { sessionId?: string; role?: string; limit?: number },
): UseQueryResult<AuditEntry[]> {
  return useQuery({
    queryKey: queryKeys.audit.all,
    queryFn: () => getAuditEntries(params),
  });
}
