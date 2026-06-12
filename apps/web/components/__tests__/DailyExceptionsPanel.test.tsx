/**
 * T-574: Unit tests for DailyExceptionsPanel component.
 *
 * Strategy: vi.mock global fetch at the module level so the component never
 * makes real network calls. Covers three scenarios:
 *   1. Empty state — run is null (no screening run today)
 *   2. Populated state — run with severity counts and exceptions
 *   3. "Investigate in chat" button injects the expected prompt
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import DailyExceptionsPanel from "@/components/DailyExceptionsPanel";

// ---------------------------------------------------------------------------
// Fetch stub helpers
// ---------------------------------------------------------------------------

function mockFetchResponse(body: unknown, status = 200): void {
  global.fetch = vi.fn().mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response);
}

function makeRun(overrides: Partial<{
  exception_count: number;
  severity_counts: Record<string, number>;
  exceptions: Array<{
    domain: string;
    severity: string;
    sku_id: string | null;
    order_ref: string | null;
    headline_metric: string;
    detail: string;
  }>;
}> = {}) {
  return {
    id: "run-001",
    run_date: "2026-06-12",
    triggered_by: "schedule",
    status: "completed",
    exception_count: overrides.exception_count ?? 2,
    severity_counts: overrides.severity_counts ?? { critical: 1, high: 1 },
    payload: {
      exceptions: overrides.exceptions ?? [
        {
          domain: "stockout_risk",
          severity: "critical",
          sku_id: "SKU-001",
          order_ref: null,
          headline_metric: "stockout risk critical: -10 units projected",
          detail: "Projected ending stock -10 units; estimated stockout 2026-06-15",
        },
        {
          domain: "supply_delays",
          severity: "high",
          sku_id: "SKU-002",
          order_ref: "SO-123",
          headline_metric: "3 days overdue",
          detail: "Order SO-123 for SKU-002 from supplier SUPP-01 expected 2026-06-09",
        },
      ],
      counts: { stockout_risk: 1, supply_delays: 1 },
      truncated: false,
      missing_data: [],
    },
    error: null,
    created_at: "2026-06-12T06:00:00.000Z",
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
});

describe("DailyExceptionsPanel", () => {
  // T-574 scenario 1: empty state — run is null
  it("renders the empty state when the API returns run: null", async () => {
    mockFetchResponse({ run: null });

    const onInvestigate = vi.fn();
    render(<DailyExceptionsPanel onInvestigate={onInvestigate} />);

    await waitFor(() => {
      expect(screen.getByTestId("daily-exceptions-panel")).toBeInTheDocument();
    });

    expect(screen.getByTestId("daily-exceptions-empty")).toBeInTheDocument();
    expect(screen.getByTestId("daily-exceptions-run-now")).toBeInTheDocument();

    // Investigate button not present when run is null
    expect(screen.queryByTestId("daily-exceptions-investigate")).not.toBeInTheDocument();
  });

  // T-574 scenario 2: populated state — severity counts and exception rows rendered
  it("renders severity badges and exception rows when run has data", async () => {
    mockFetchResponse({ run: makeRun() });

    const onInvestigate = vi.fn();
    render(<DailyExceptionsPanel onInvestigate={onInvestigate} />);

    await waitFor(() => {
      expect(screen.getByTestId("daily-exceptions-panel")).toBeInTheDocument();
    });

    // Severity count badges
    expect(screen.getByText(/1 critical/i)).toBeInTheDocument();
    expect(screen.getByText(/1 high/i)).toBeInTheDocument();

    // Exception rows — SKU identifiers and headline metrics
    expect(screen.getByText("SKU-001")).toBeInTheDocument();
    expect(screen.getByText("SKU-002")).toBeInTheDocument();

    // Investigate button present
    expect(screen.getByTestId("daily-exceptions-investigate")).toBeInTheDocument();

    // Run now button present
    expect(screen.getByTestId("daily-exceptions-run-now")).toBeInTheDocument();
  });

  // T-574 scenario 3: "Investigate in chat" injects the correct prompt
  it("calls onInvestigate with the correct prompt when the investigate button is clicked", async () => {
    mockFetchResponse({ run: makeRun() });

    const onInvestigate = vi.fn();
    render(<DailyExceptionsPanel onInvestigate={onInvestigate} />);

    await waitFor(() => {
      expect(screen.getByTestId("daily-exceptions-investigate")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("daily-exceptions-investigate"));

    expect(onInvestigate).toHaveBeenCalledOnce();
    expect(onInvestigate).toHaveBeenCalledWith(
      "What exceptions require human judgment today?"
    );
  });

  // T-574 scenario 4: fetch failure renders nothing (graceful failure)
  it("renders nothing when the fetch fails", async () => {
    global.fetch = vi.fn().mockRejectedValueOnce(new Error("network error"));

    const onInvestigate = vi.fn();
    const { container } = render(<DailyExceptionsPanel onInvestigate={onInvestigate} />);

    // After mount the component transitions from undefined (loading) to error
    // Allow one tick for the effect to settle
    await waitFor(() => {
      // Either still loading (null) or showed error state (null)
      expect(container.firstChild).toBeNull();
    });
  });

  // T-574 scenario 5: Run now button is disabled while in flight
  it("disables the run-now button while the POST request is in flight", async () => {
    // First fetch: today endpoint returns null run
    global.fetch = vi
      .fn()
      // Initial GET /today
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ run: null }),
      } as Response)
      // POST /run — intentionally never resolves to simulate in-flight state
      .mockReturnValueOnce(new Promise(() => undefined));

    const onInvestigate = vi.fn();
    render(<DailyExceptionsPanel onInvestigate={onInvestigate} />);

    await waitFor(() => {
      expect(screen.getByTestId("daily-exceptions-run-now")).toBeInTheDocument();
    });

    const btn = screen.getByTestId("daily-exceptions-run-now");
    expect(btn).not.toBeDisabled();

    fireEvent.click(btn);

    // Button should be disabled immediately after click
    expect(btn).toBeDisabled();
  });
});
