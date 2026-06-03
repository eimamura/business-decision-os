import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { UseQueryResult, UseMutationResult } from "@tanstack/react-query";
import { queryKeys } from "@/lib/queryKeys";
import { getApprovals, postDecision, postRevision } from "./api";
import type { Approval, ApprovalDecision, RevisionPayload } from "./api";

export function useApprovals(status: string): UseQueryResult<Approval[]> {
  return useQuery({
    queryKey: queryKeys.approvals.all(status),
    queryFn: () => getApprovals(status),
  });
}

export function useApprovalDecision(
  onSuccess?: () => void,
): UseMutationResult<void, Error, { id: string; decision: ApprovalDecision }> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: ApprovalDecision }) =>
      postDecision(id, decision),
    onSuccess: (_, { id: _id }) => {
      void qc.invalidateQueries({ queryKey: ["approvals"] });
      onSuccess?.();
    },
  });
}

export function useApprovalRevision(): UseMutationResult<
  void,
  Error,
  { id: string; payload: RevisionPayload }
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: RevisionPayload }) =>
      postRevision(id, payload),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["approvals"] }),
  });
}
