"use client";

import { useEffect, useState } from "react";

interface AppStatus {
  mock_mode: boolean;
  version: string;
  environment: string;
}

export default function MockModeBanner(): React.ReactElement | null {
  const [mockMode, setMockMode] = useState<boolean | null>(null);

  useEffect(() => {
    fetch("/api/v1/status")
      .then((r) => r.json() as Promise<AppStatus>)
      .then((data) => setMockMode(data.mock_mode))
      .catch(() => setMockMode(false));
  }, []);

  if (!mockMode) return null;

  return (
    <div
      className="sticky top-0 z-50 flex items-center justify-center gap-2 bg-amber-400 px-4 py-1.5 text-sm font-medium text-amber-900 dark:bg-amber-500 dark:text-amber-950"
      role="alert"
      aria-label="mock mode active"
      data-testid="mock-mode-banner"
    >
      <svg
        className="h-4 w-4 shrink-0"
        viewBox="0 0 20 20"
        fill="currentColor"
        aria-hidden="true"
      >
        <path
          fillRule="evenodd"
          d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
          clipRule="evenodd"
        />
      </svg>
      Mock Mode Active — LLM calls are stubbed. No API cost is incurred.
    </div>
  );
}
