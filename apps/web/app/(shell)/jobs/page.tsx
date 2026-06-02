"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types (matching packages/schemas/jobs.py)
// ---------------------------------------------------------------------------

interface JobFileResponse {
  id: string;
  job_id: string;
  file_name: string;
  file_size_bytes: number;
  mime_type: string;
  download_url: string;
  created_at: string;
}

interface JobResponse {
  id: string;
  session_id: string | null;
  status: string;
  job_type: string;
  created_at: string;
  completed_at: string | null;
  generated_files: JobFileResponse[];
}

interface JobListResponse {
  items: JobResponse[];
  next_cursor: string | null;
}

interface FileListResponse {
  items: JobFileResponse[];
  next_cursor: string | null;
}

type Tab = "jobs" | "files";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
    completed: "bg-emerald-100 text-emerald-700",
    running: "bg-blue-100 text-blue-700",
    pending: "bg-yellow-100 text-yellow-700",
    failed: "bg-red-100 text-red-700",
  };
  const cls = colors[status] ?? "bg-gray-100 text-gray-600";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function JobsPage(): React.ReactElement {
  const [tab, setTab] = useState<Tab>("jobs");

  // Jobs tab state
  const [jobs, setJobs] = useState<JobResponse[]>([]);
  const [jobsCursor, setJobsCursor] = useState<string | null>(null);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [jobsInitialized, setJobsInitialized] = useState(false);

  // Files tab state
  const [files, setFiles] = useState<JobFileResponse[]>([]);
  const [filesCursor, setFilesCursor] = useState<string | null>(null);
  const [filesLoading, setFilesLoading] = useState(false);
  const [filesInitialized, setFilesInitialized] = useState(false);

  const loadJobs = useCallback(async (cursor: string | null) => {
    setJobsLoading(true);
    try {
      const params = new URLSearchParams({ limit: "20" });
      if (cursor) params.set("cursor", cursor);
      const resp = await fetch(`${API_BASE}/api/v1/jobs?${params}`, {
        headers: { "X-Dev-User": "dev-user" },
      });
      if (!resp.ok) return;
      const data: JobListResponse = await resp.json();
      setJobs((prev) => (cursor ? [...prev, ...data.items] : data.items));
      setJobsCursor(data.next_cursor);
    } catch {
      // ignore fetch errors in client component
    } finally {
      setJobsLoading(false);
    }
  }, []);

  const loadFiles = useCallback(async (cursor: string | null) => {
    setFilesLoading(true);
    try {
      const params = new URLSearchParams({ limit: "20" });
      if (cursor) params.set("cursor", cursor);
      const resp = await fetch(`${API_BASE}/api/v1/files?${params}`, {
        headers: { "X-Dev-User": "dev-user" },
      });
      if (!resp.ok) return;
      const data: FileListResponse = await resp.json();
      setFiles((prev) => (cursor ? [...prev, ...data.items] : data.items));
      setFilesCursor(data.next_cursor);
    } catch {
      // ignore fetch errors in client component
    } finally {
      setFilesLoading(false);
    }
  }, []);

  // Initial load per tab
  useEffect(() => {
    if (tab === "jobs" && !jobsInitialized) {
      setJobsInitialized(true);
      void loadJobs(null);
    }
    if (tab === "files" && !filesInitialized) {
      setFilesInitialized(true);
      void loadFiles(null);
    }
  }, [tab, jobsInitialized, filesInitialized, loadJobs, loadFiles]);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-4">
        <Link href="/chat" className="text-sm text-blue-600 hover:underline">
          ← Chat
        </Link>
        <h1 className="text-lg font-semibold text-gray-900">Jobs</h1>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        {/* Tabs */}
        <div className="flex gap-1 mb-6 border-b border-gray-200">
          {(["jobs", "files"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
                tab === t
                  ? "bg-white border border-b-white border-gray-200 text-gray-900 -mb-px"
                  : "text-gray-500 hover:text-gray-700"
              }`}
              data-testid={`tab-${t}`}
            >
              {t === "jobs" ? "Jobs" : "Files"}
            </button>
          ))}
        </div>

        {/* Jobs tab */}
        {tab === "jobs" && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            {jobsLoading && jobs.length === 0 ? (
              <div className="p-8 text-center text-sm text-gray-400 animate-pulse">
                Loading jobs...
              </div>
            ) : jobs.length === 0 ? (
              <div className="p-8 text-center text-sm text-gray-400">No jobs yet</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      ID
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      Type
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      Status
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      Created At
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      Files
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {jobs.map((job) => (
                    <tr key={job.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 font-mono text-xs text-gray-600" title={job.id}>
                        {job.id.slice(0, 8)}…
                      </td>
                      <td className="px-4 py-3 text-gray-700">{job.job_type}</td>
                      <td className="px-4 py-3">{statusBadge(job.status)}</td>
                      <td className="px-4 py-3 text-gray-500">{formatDate(job.created_at)}</td>
                      <td className="px-4 py-3 text-gray-500">
                        {job.generated_files.length}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {jobsCursor && (
              <div className="px-4 py-3 border-t border-gray-100 text-center">
                <button
                  onClick={() => void loadJobs(jobsCursor)}
                  disabled={jobsLoading}
                  className="px-4 py-2 text-sm text-blue-600 hover:text-blue-700 disabled:opacity-50 transition-colors"
                  data-testid="jobs-load-more"
                >
                  {jobsLoading ? "Loading..." : "Load more"}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Files tab */}
        {tab === "files" && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            {filesLoading && files.length === 0 ? (
              <div className="p-8 text-center text-sm text-gray-400 animate-pulse">
                Loading files...
              </div>
            ) : files.length === 0 ? (
              <div className="p-8 text-center text-sm text-gray-400">No files yet</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      File Name
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      Size
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      MIME
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      Created At
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      Job
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {files.map((file) => (
                    <tr key={file.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 font-medium text-gray-800">
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
                      <td className="px-4 py-3 text-gray-500">
                        {formatBytes(file.file_size_bytes)}
                      </td>
                      <td className="px-4 py-3 text-gray-500 font-mono text-xs">
                        {file.mime_type}
                      </td>
                      <td className="px-4 py-3 text-gray-500">{formatDate(file.created_at)}</td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-500" title={file.job_id}>
                        {file.job_id.slice(0, 8)}…
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {filesCursor && (
              <div className="px-4 py-3 border-t border-gray-100 text-center">
                <button
                  onClick={() => void loadFiles(filesCursor)}
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
