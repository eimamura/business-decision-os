/**
 * T-574 / T-594: Unit tests for DailyExceptionsPanel component.
 *
 * Strategy: vi.mock global fetch at the module level so the component never
 * makes real network calls. Covers the following scenarios:
 *   1. Empty state — run is null, defaultExpanded=true (empty chat)
 *   2. Populated state — run with severity counts and exceptions, defaultExpanded=true
 *   3. "Investigate in chat" button injects the expected prompt
 *   4. Fetch failure renders nothing
 *   5. Run now button disabled while in-flight
 *   6. Strip is always rendered; toggle expands/collapses the panel content
 *   7. Collapsed by default (defaultExpanded=false) — active conversation state
 *   8. Active conversation: Investigate button accessible after expanding
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
  // ---------------------------------------------------------------------------
  // Scenario 1: empty state — run is null, defaultExpanded=true (default)
  // ---------------------------------------------------------------------------
  it("renders the strip and expanded empty state when the API returns run: null", async () => {
    mockFetchResponse({ run: null });

    const onInvestigate = vi.fn();
    render(<DailyExceptionsPanel onInvestigate={onInvestigate} />);

    await waitFor(() => {
      expect(screen.getByTestId("daily-exceptions-panel")).toBeInTheDocument();
    });

    // Strip row always present
    expect(screen.getByTestId("daily-exceptions-strip")).toBeInTheDocument();
    // Toggle button always present
    expect(screen.getByTestId("daily-exceptions-toggle")).toBeInTheDocument();

    // Expanded by default — empty state content visible
    expect(screen.getByTestId("daily-exceptions-empty")).toBeInTheDocument();
    expect(screen.getByTestId("daily-exceptions-run-now")).toBeInTheDocument();

    // Investigate button not present when run is null
    expect(screen.queryByTestId("daily-exceptions-investigate")).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Scenario 2: populated state — severity counts and exception rows rendered
  // ---------------------------------------------------------------------------
  it("renders severity badges and exception rows when run has data (defaultExpanded=true)", async () => {
    mockFetchResponse({ run: makeRun() });

    const onInvestigate = vi.fn();
    render(<DailyExceptionsPanel onInvestigate={onInvestigate} />);

    await waitFor(() => {
      expect(screen.getByTestId("daily-exceptions-panel")).toBeInTheDocument();
    });

    // Strip row present
    expect(screen.getByTestId("daily-exceptions-strip")).toBeInTheDocument();
    expect(screen.getByTestId("daily-exceptions-toggle")).toBeInTheDocument();

    // Severity count badges appear in the strip
    expect(screen.getByText(/1 critical/i)).toBeInTheDocument();
    expect(screen.getByText(/1 high/i)).toBeInTheDocument();

    // Expanded content visible
    expect(screen.getByText("SKU-001")).toBeInTheDocument();
    expect(screen.getByText("SKU-002")).toBeInTheDocument();

    // Investigate button present
    expect(screen.getByTestId("daily-exceptions-investigate")).toBeInTheDocument();

    // Run now button present
    expect(screen.getByTestId("daily-exceptions-run-now")).toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Scenario 3: "Investigate in chat" injects the correct prompt
  // ---------------------------------------------------------------------------
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

  // ---------------------------------------------------------------------------
  // Scenario 4: fetch failure renders nothing (graceful failure)
  // ---------------------------------------------------------------------------
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

  // ---------------------------------------------------------------------------
  // Scenario 5: Run now button is disabled while in flight
  // ---------------------------------------------------------------------------
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

  // ---------------------------------------------------------------------------
  // Scenario 6: toggle collapses and re-expands the panel content
  // ---------------------------------------------------------------------------
  it("collapses expanded content when toggle is clicked, then re-expands", async () => {
    mockFetchResponse({ run: makeRun() });

    const onInvestigate = vi.fn();
    render(<DailyExceptionsPanel onInvestigate={onInvestigate} />);

    // Wait for panel to render in expanded state (defaultExpanded=true)
    await waitFor(() => {
      expect(screen.getByTestId("daily-exceptions-investigate")).toBeInTheDocument();
    });

    // Strip and toggle always present
    expect(screen.getByTestId("daily-exceptions-strip")).toBeInTheDocument();
    const toggle = screen.getByTestId("daily-exceptions-toggle");

    // Click toggle to collapse
    fireEvent.click(toggle);

    // Expanded content should be gone
    expect(screen.queryByTestId("daily-exceptions-investigate")).not.toBeInTheDocument();
    expect(screen.queryByTestId("daily-exceptions-run-now")).not.toBeInTheDocument();

    // Strip is still present
    expect(screen.getByTestId("daily-exceptions-strip")).toBeInTheDocument();

    // Click toggle again to re-expand
    fireEvent.click(toggle);

    expect(screen.getByTestId("daily-exceptions-investigate")).toBeInTheDocument();
    expect(screen.getByTestId("daily-exceptions-run-now")).toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Scenario 7: collapsed by default when defaultExpanded=false (active conv)
  // ---------------------------------------------------------------------------
  it("starts collapsed when defaultExpanded=false (active conversation state)", async () => {
    mockFetchResponse({ run: makeRun() });

    const onInvestigate = vi.fn();
    render(<DailyExceptionsPanel onInvestigate={onInvestigate} defaultExpanded={false} />);

    await waitFor(() => {
      expect(screen.getByTestId("daily-exceptions-panel")).toBeInTheDocument();
    });

    // Strip is present
    expect(screen.getByTestId("daily-exceptions-strip")).toBeInTheDocument();
    expect(screen.getByTestId("daily-exceptions-toggle")).toBeInTheDocument();

    // Severity badges visible in strip
    expect(screen.getByText(/1 critical/i)).toBeInTheDocument();

    // Expanded content NOT visible
    expect(screen.queryByTestId("daily-exceptions-investigate")).not.toBeInTheDocument();
    expect(screen.queryByTestId("daily-exceptions-run-now")).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Scenario 8: active conversation — Investigate accessible after manual expand
  // ---------------------------------------------------------------------------
  it("makes Investigate button accessible after user expands the collapsed strip", async () => {
    mockFetchResponse({ run: makeRun() });

    const onInvestigate = vi.fn();
    render(<DailyExceptionsPanel onInvestigate={onInvestigate} defaultExpanded={false} />);

    await waitFor(() => {
      expect(screen.getByTestId("daily-exceptions-strip")).toBeInTheDocument();
    });

    // Initially collapsed — no investigate button
    expect(screen.queryByTestId("daily-exceptions-investigate")).not.toBeInTheDocument();

    // User clicks the toggle to expand
    fireEvent.click(screen.getByTestId("daily-exceptions-toggle"));

    // Now the investigate button is visible and functional
    const investigateBtn = screen.getByTestId("daily-exceptions-investigate");
    expect(investigateBtn).toBeInTheDocument();

    fireEvent.click(investigateBtn);
    expect(onInvestigate).toHaveBeenCalledOnce();
    expect(onInvestigate).toHaveBeenCalledWith(
      "What exceptions require human judgment today?"
    );
  });

  // ---------------------------------------------------------------------------
  // Scenario 9: null run + active conversation (collapsed by default)
  // ---------------------------------------------------------------------------
  it("shows minimal strip when run=null and defaultExpanded=false", async () => {
    mockFetchResponse({ run: null });

    const onInvestigate = vi.fn();
    render(<DailyExceptionsPanel onInvestigate={onInvestigate} defaultExpanded={false} />);

    await waitFor(() => {
      expect(screen.getByTestId("daily-exceptions-panel")).toBeInTheDocument();
    });

    // Strip present
    expect(screen.getByTestId("daily-exceptions-strip")).toBeInTheDocument();
    // "No screening run today" text visible in strip
    expect(screen.getByText(/No screening run today/i)).toBeInTheDocument();

    // Expanded content NOT visible (collapsed)
    expect(screen.queryByTestId("daily-exceptions-empty")).not.toBeInTheDocument();
    expect(screen.queryByTestId("daily-exceptions-run-now")).not.toBeInTheDocument();
  });
});
