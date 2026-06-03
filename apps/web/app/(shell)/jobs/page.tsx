"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useJobs, useJobFiles } from "@/features/jobs/hooks";
import type { JobResponse, JobFileResponse, StatusFilter } from "@/features/jobs/api";

const API_BASE = "";

interface JobListResponse {
  items: JobResponse[];
  next_cursor: string | null;
}

interface FileListResponse {
  items: JobFileResponse[];
  next_cursor: string | null;
}

type Tab = "jobs" | "files";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusBadge(status: string): React.ReactElement {
  const colors: Record<string, string> = {
    completed: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
    running: "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300",
    pending: "bg-yellow-100 text-yellow-700 dark:bg-yellow-500/15 dark:text-yellow-300",
    pending_approval:
      "bg-yellow-100 text-yellow-700 dark:bg-yellow-500/15 dark:text-yellow-300",
    failed: "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300",
    cancelled: "bg-surface text-muted",
  };
  const cls = colors[status] ?? "bg-surface text-muted";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

function resultSummaryEntries(
  result: Record<string, unknown> | null,
): Array<{ key: string; value: string }> {
  if (result === null || result === undefined) return [];
  return Object.entries(result)
    .filter(([, v]) => typeof v === "string" || typeof v === "number" || typeof v === "boolean")
    .slice(0, 3)
    .map(([k, v]) => ({ key: k, value: String(v) }));
}

interface JobDetailPanelProps {
  job: JobResponse;
  detail: JobResponse | null;
  loading: boolean;
}

function JobDetailPanel({ job, detail, loading }: JobDetailPanelProps): React.ReactElement {
  const displayJob = detail ?? job;
  const summaryEntries = resultSummaryEntries(displayJob.result_json);
  const files = displayJob.generated_files;

  return (
    <tr>
      <td colSpan={6} className="px-6 py-4 bg-surface border-b border-border">
        {loading ? (
          <p className="text-xs text-muted animate-pulse">Loading details...</p>
        ) : (
          <div className="flex gap-8 text-sm">
            <div className="flex-1">
              <p className="text-xs font-semibold text-muted uppercase tracking-wide mb-2">
                Result
              </p>
              {summaryEntries.length > 0 ? (
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                  {summaryEntries.map(({ key, value }) => (
                    <React.Fragment key={key}>
                      <dt className="text-muted font-medium">{key}</dt>
                      <dd className="text-foreground font-mono truncate">{value}</dd>
                    </React.Fragment>
                  ))}
                </dl>
              ) : (
                <p className="text-muted text-xs">No result yet</p>
              )}
            </div>

            <div className="flex-1">
              <p className="text-xs font-semibold text-muted uppercase tracking-wide mb-2">
                Files
              </p>
              {files.length > 0 ? (
                <ul className="space-y-1">
                  {files.map((f) => (
                    <li key={f.id}>
                      <a
                        href={f.download_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline text-xs"
                      >
                        {f.file_name}
                      </a>
                      <span className="text-muted text-xs ml-2">
                        ({formatBytes(f.file_size_bytes)})
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted text-xs">No files</p>
              )}
            </div>
          </div>
        )}
      </td>
    </tr>
  );
}

export default function JobsPage(): React.ReactElement {
  const [tab, setTab] = useState<Tab>("jobs");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("");

  const { data: initialJobs } = useJobs(statusFilter);
  const { data: initialFiles } = useJobFiles();

  const [jobs, setJobs] = useState<JobResponse[]>([]);
  const [jobsCursor, setJobsCursor] = useState<string | null>(null);
  const [jobsLoading, setJobsLoading] = useState(false);

  const [files, setFiles] = useState<JobFileResponse[]>([]);
  const [filesCursor, setFilesCursor] = useState<string | null>(null);
  const [filesLoading, setFilesLoading] = useState(false);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detailMap, setDetailMap] = useState<
    Record<string, { detail: JobResponse | null; loading: boolean }>
  >({});

  useEffect(() => {
    if (initialJobs) {
      setJobs(initialJobs.items);
      setJobsCursor(initialJobs.next_cursor);
    }
  }, [initialJobs]);

  useEffect(() => {
    if (initialFiles) {
      setFiles(initialFiles.items);
      setFilesCursor(initialFiles.next_cursor);
    }
  }, [initialFiles]);

  const loadMoreJobs = useCallback(
    async (cursor: string, filter: StatusFilter): Promise<void> => {
      setJobsLoading(true);
      try {
        const params = new URLSearchParams({ limit: "20" });
        params.set("cursor", cursor);
        if (filter) params.set("status", filter);
        const resp = await fetch(`${API_BASE}/api/v1/jobs?${params}`, {
          headers: { "X-Dev-User": "dev-user" },
        });
        if (!resp.ok) return;
        const data: JobListResponse = await resp.json();
        setJobs((prev) => [...prev, ...data.items]);
        setJobsCursor(data.next_cursor);
      } catch {
        // ignore fetch errors
      } finally {
        setJobsLoading(false);
      }
    },
    [],
  );

  const loadMoreFiles = useCallback(async (cursor: string): Promise<void> => {
    setFilesLoading(true);
    try {
      const params = new URLSearchParams({ limit: "20" });
      params.set("cursor", cursor);
      const resp = await fetch(`${API_BASE}/api/v1/files?${params}`, {
        headers: { "X-Dev-User": "dev-user" },
      });
      if (!resp.ok) return;
      const data: FileListResponse = await resp.json();
      setFiles((prev) => [...prev, ...data.items]);
      setFilesCursor(data.next_cursor);
    } catch {
      // ignore fetch errors
    } finally {
      setFilesLoading(false);
    }
  }, []);

  const handleStatusChange = (newFilter: StatusFilter): void => {
    setStatusFilter(newFilter);
    setExpandedId(null);
  };

  const fetchJobDetail = useCallback(async (jobId: string): Promise<void> => {
    setDetailMap((prev) => ({ ...prev, [jobId]: { detail: null, loading: true } }));
    try {
      const resp = await fetch(`${API_BASE}/api/v1/jobs/${jobId}`, {
        headers: { "X-Dev-User": "dev-user" },
      });
      if (!resp.ok) {
        setDetailMap((prev) => ({ ...prev, [jobId]: { detail: null, loading: false } }));
        return;
      }
      const detail: JobResponse = await resp.json();
      setDetailMap((prev) => ({ ...prev, [jobId]: { detail, loading: false } }));
    } catch {
      setDetailMap((prev) => ({ ...prev, [jobId]: { detail: null, loading: false } }));
    }
  }, []);

  const handleRowClick = (jobId: string): void => {
    if (expandedId === jobId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(jobId);
    if (!detailMap[jobId]) {
      void fetchJobDetail(jobId);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="bg-background border-b border-border px-6 py-4 flex items-center gap-4">
        <Link href="/chat" className="text-sm text-blue-600 hover:underline">
          ← Chat
        </Link>
        <h1 className="text-lg font-semibold text-foreground">Jobs</h1>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex gap-1 mb-6 border-b border-border">
          {(["jobs", "files"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
                tab === t
                  ? "bg-background border border-b-background border-border text-foreground -mb-px"
                  : "text-muted hover:text-foreground"
              }`}
              data-testid={`tab-${t}`}
            >
              {t === "jobs" ? "Jobs" : "Files"}
            </button>
          ))}
        </div>

        {tab === "jobs" && (
          <>
            <div className="mb-4 flex items-center gap-3">
              <label
                htmlFor="status-filter"
                className="text-xs font-medium text-muted uppercase tracking-wide"
              >
                Status
              </label>
              <select
                id="status-filter"
                value={statusFilter}
                onChange={(e) => handleStatusChange(e.target.value as StatusFilter)}
                className="text-sm border border-border rounded-md px-3 py-1.5 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500"
                data-testid="status-filter"
              >
                <option value="">All</option>
                <option value="pending_approval">pending_approval</option>
                <option value="running">running</option>
                <option value="completed">completed</option>
                <option value="failed">failed</option>
                <option value="cancelled">cancelled</option>
              </select>
            </div>

            <div className="bg-background rounded-xl border border-border overflow-hidden">
              {jobsLoading && jobs.length === 0 ? (
                <div className="p-8 text-center text-sm text-muted animate-pulse">
                  Loading jobs...
                </div>
              ) : jobs.length === 0 ? (
                <div className="p-8 text-center text-sm text-muted">No jobs yet</div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-surface border-b border-border">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase tracking-wide">
                        ID
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase tracking-wide">
                        Type
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase tracking-wide">
                        Status
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase tracking-wide">
                        Session
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase tracking-wide">
                        Created At
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase tracking-wide">
                        Files
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {jobs.map((job) => (
                      <React.Fragment key={job.id}>
                        <tr
                          onClick={() => handleRowClick(job.id)}
                          className="hover:bg-surface transition-colors cursor-pointer"
                          data-testid={`job-row-${job.id}`}
                        >
                          <td
                            className="px-4 py-3 font-mono text-xs text-muted"
                            title={job.id}
                          >
                            {job.id.slice(0, 8)}…
                          </td>
                          <td className="px-4 py-3 text-foreground">{job.job_type}</td>
                          <td className="px-4 py-3">{statusBadge(job.status)}</td>
                          <td className="px-4 py-3 font-mono text-xs">
                            {job.session_id !== null ? (
                              <Link
                                href={`/chat/${job.session_id}`}
                                className="text-blue-600 hover:underline"
                                onClick={(e) => e.stopPropagation()}
                              >
                                {job.session_id.slice(0, 8)}
                              </Link>
                            ) : (
                              <span className="text-muted">—</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-muted">{formatDate(job.created_at)}</td>
                          <td className="px-4 py-3 text-muted">
                            {job.generated_files.length}
                          </td>
                        </tr>
                        {expandedId === job.id && (
                          <JobDetailPanel
                            job={job}
                            detail={detailMap[job.id]?.detail ?? null}
                            loading={detailMap[job.id]?.loading ?? true}
                          />
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              )}
              {jobsCursor && (
                <div className="px-4 py-3 border-t border-border text-center">
                  <button
                    onClick={() => void loadMoreJobs(jobsCursor, statusFilter)}
                    disabled={jobsLoading}
                    className="px-4 py-2 text-sm text-blue-600 hover:text-blue-700 disabled:opacity-50 transition-colors"
                    data-testid="jobs-load-more"
                  >
                    {jobsLoading ? "Loading..." : "Load more"}
                  </button>
                </div>
              )}
            </div>
          </>
        )}

        {tab === "files" && (
          <div className="bg-background rounded-xl border border-border overflow-hidden">
            {filesLoading && files.length === 0 ? (
              <div className="p-8 text-center text-sm text-muted animate-pulse">
                Loading files...
              </div>
            ) : files.length === 0 ? (
              <div className="p-8 text-center text-sm text-muted">No files yet</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-surface border-b border-border">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase tracking-wide">
                      File Name
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase tracking-wide">
                      Size
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase tracking-wide">
                      MIME
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase tracking-wide">
                      Created At
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase tracking-wide">
                      Job
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {files.map((file) => (
                    <tr key={file.id} className="hover:bg-surface transition-colors">
                      <td className="px-4 py-3 font-medium text-foreground">
                        {file.download_url ? (
                          <a
                            href={file.download_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:underline"
                          >
                            {file.file_name}
                          </a>
                        ) : (
                          file.file_name
                        )}
                      </td>
                      <td className="px-4 py-3 text-muted">
                        {formatBytes(file.file_size_bytes)}
                      </td>
                      <td className="px-4 py-3 text-muted font-mono text-xs">
                        {file.mime_type}
                      </td>
                      <td className="px-4 py-3 text-muted">{formatDate(file.created_at)}</td>
                      <td
                        className="px-4 py-3 font-mono text-xs text-muted"
                        title={file.job_id}
                      >
                        {file.job_id.slice(0, 8)}…
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {filesCursor && (
              <div className="px-4 py-3 border-t border-border text-center">
                <button
                  onClick={() => void loadMoreFiles(filesCursor)}
                  disabled={filesLoading}
                  className="px-4 py-2 text-sm text-blue-600 hover:text-blue-700 disabled:opacity-50 transition-colors"
                  data-testid="files-load-more"
                >
                  {filesLoading ? "Loading..." : "Load more"}
                </button>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
