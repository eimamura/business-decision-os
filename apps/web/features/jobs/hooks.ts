import { useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";
import { queryKeys } from "@/lib/queryKeys";
import { getJobs, getJobFiles } from "./api";
import type { JobResponse, JobFileResponse } from "./api";

export function useJobs(
  status: string,
): UseQueryResult<{ items: JobResponse[]; next_cursor: string | null }> {
  return useQuery({
    queryKey: queryKeys.jobs.list(status),
    queryFn: () => getJobs({ status }),
  });
}

export function useJobFiles(): UseQueryResult<{
  items: JobFileResponse[];
  next_cursor: string | null;
}> {
  return useQuery({
    queryKey: queryKeys.jobs.files,
    queryFn: () => getJobFiles(),
  });
}
