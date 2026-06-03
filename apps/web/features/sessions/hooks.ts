import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/queryKeys";
import { getSessions } from "./api";
import type { Session } from "@/types/chat";
import type { UseQueryResult } from "@tanstack/react-query";

export function useSessions(): UseQueryResult<Session[]> {
  return useQuery({ queryKey: queryKeys.sessions.all, queryFn: getSessions });
}
