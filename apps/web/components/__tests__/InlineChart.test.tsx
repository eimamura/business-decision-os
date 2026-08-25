/**
 * Unit tests for InlineChart component and parseChartSpec helper.
 *
 * Tests:
 * (a) valid bar ChartSpec renders without crashing and shows data-testid
 * (b) valid line ChartSpec renders without crashing and shows data-testid
 * (c) parseChartSpec returns null for invalid JSON
 * (d) parseChartSpec returns null for JSON missing required keys
 * (e) parseChartSpec returns null for unknown chart type
 * (f) parseChartSpec returns a ChartSpec for a well-formed bar spec string
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

// recharts uses ResizeObserver and SVG APIs not available in jsdom.
// Mock the entire recharts module to avoid jsdom rendering issues.
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  BarChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  LineChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="line-chart">{children}</div>
  ),
  Bar: () => <div data-testid="bar" />,
  Line: () => <div data-testid="line" />,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
}));

import InlineChart, { parseChartSpec } from "@/components/chat/InlineChart";

// ---------------------------------------------------------------------------
// Shared fixtures
// ---------------------------------------------------------------------------

const BAR_SPEC = {
  type: "bar" as const,
  title: "Stockout Risk — Days of Cover by SKU",
  xKey: "sku_code",
  series: [{ dataKey: "days_of_cover", name: "Days of Cover", color: "#ef4444" }],
  data: [{ sku_code: "SKU-001", days_of_cover: 2.1 }],
};

const LINE_SPEC = {
  type: "line" as const,
  title: "Demand Trend",
  xKey: "period",
  series: [{ dataKey: "quantity", name: "Demand (units)", color: "#3b82f6" }],
  data: [
    { period: "2026-05", quantity: 100 },
    { period: "2026-06", quantity: 110 },
  ],
};

// ---------------------------------------------------------------------------
// InlineChart render tests
// ---------------------------------------------------------------------------

describe("InlineChart", () => {
  it("renders_bar_spec_without_crashing_and_data_testid_present", () => {
    render(<InlineChart spec={BAR_SPEC} />);

    expect(screen.getByTestId("inline-chart")).toBeTruthy();
  });

  it("renders_line_spec_without_crashing_and_data_testid_present", () => {
    render(<InlineChart spec={LINE_SPEC} />);

    expect(screen.getByTestId("inline-chart")).toBeTruthy();
  });

  it("renders_bar_chart_element_for_bar_type_spec", () => {
    render(<InlineChart spec={BAR_SPEC} />);

    expect(screen.getByTestId("bar-chart")).toBeTruthy();
  });

  it("renders_line_chart_element_for_line_type_spec", () => {
    render(<InlineChart spec={LINE_SPEC} />);

    expect(screen.getByTestId("line-chart")).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// parseChartSpec helper tests
// ---------------------------------------------------------------------------

describe("parseChartSpec", () => {
  it("returns_null_for_invalid_json_string", () => {
    const result = parseChartSpec("not json at all {{{");

    expect(result).toBeNull();
  });

  it("returns_null_for_json_missing_required_keys", () => {
    const result = parseChartSpec(JSON.stringify({ type: "bar" }));

    expect(result).toBeNull();
  });

  it("returns_null_for_unknown_chart_type", () => {
    const raw = JSON.stringify({ type: "pie", xKey: "x", series: [], data: [] });

    const result = parseChartSpec(raw);

    expect(result).toBeNull();
  });

  it("returns_chart_spec_for_well_formed_bar_spec_string", () => {
    const raw = JSON.stringify(BAR_SPEC);

    const result = parseChartSpec(raw);

    expect(result).not.toBeNull();
  });

  it("returns_chart_spec_with_correct_type_for_well_formed_bar_spec_string", () => {
    const raw = JSON.stringify(BAR_SPEC);

    const result = parseChartSpec(raw);

    expect(result?.type).toBe("bar");
  });

  it("returns_chart_spec_for_well_formed_line_spec_string", () => {
    const raw = JSON.stringify(LINE_SPEC);

    const result = parseChartSpec(raw);

    expect(result?.type).toBe("line");
  });
});
