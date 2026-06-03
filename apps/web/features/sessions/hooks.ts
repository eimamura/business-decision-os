import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/queryKeys";
import { getSessions, deleteAllSessions } from "./api";
import type { Session } from "@/types/chat";
import type { UseQueryResult, UseMutationResult } from "@tanstack/react-query";

export function useSessions(): UseQueryResult<Session[]> {
  return useQuery({ queryKey: queryKeys.sessions.all, queryFn: getSessions });
}

export function useDeleteAllSessions(): UseMutationResult<void, Error, void> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteAllSessions,
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.sessions.all }),
  });
}
