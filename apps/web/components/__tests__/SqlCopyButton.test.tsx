/**
 * Unit tests for the copy-to-clipboard button in SqlQueryBubble (MessageBubble.tsx).
 *
 * Run from apps/web/:
 *   npm test
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";

// Mock next/dynamic to return a simple passthrough component.
vi.mock("next/dynamic", () => ({
  default: (_loader: unknown) => {
    function MockDynamic({ children }: { children?: React.ReactNode }) {
      return <pre data-testid="syntax-highlighter">{children}</pre>;
    }
    return MockDynamic;
  },
}));

// Mock AnalysisCard to avoid complex import chains.
vi.mock("@/components/analysis/AnalysisCard", () => ({
  default: () => <div data-testid="analysis-card" />,
  isAnalysisCard: () => false,
}));

// Mock FeedbackBar to avoid complex import chains.
vi.mock("@/components/FeedbackBar", () => ({
  default: () => <div data-testid="feedback-bar" />,
}));

// Mock react-markdown to avoid ESM issues in jsdom.
vi.mock("react-markdown", () => ({
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="markdown">{children}</div>
  ),
}));

// Mock AskUserInput to avoid complex import chains.
vi.mock("@/components/AskUserInput", () => ({
  AskUserInput: () => <div data-testid="ask-user-input" />,
}));

// Mock JobApprovalCard to avoid complex import chains.
vi.mock("@/components/JobApprovalCard", () => ({
  default: () => <div data-testid="job-approval-card" />,
}));

// Dynamically import after mocks are set up.
const { default: MessageBubble } = await import(
  "@/components/chat/MessageBubble"
);

import type { ChatMessage } from "@/types/chat";

function makeSqlMessage(sql: string): ChatMessage {
  return {
    id: "msg-1",
    role: "tool",
    content: "",
    toolName: "nl_query",
    sql,
  };
}

describe("SqlQueryBubble copy button", () => {
  beforeEach(() => {
    // Reset clipboard mock before each test.
    const mockWriteText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: mockWriteText },
      configurable: true,
      writable: true,
    });
  });

  it("renders a copy button when sql is a non-empty string", () => {
    render(<MessageBubble message={makeSqlMessage("SELECT 1")} />);
    const copyButton = screen.getByRole("button", { name: /copy sql/i });
    expect(copyButton).toBeTruthy();
  });

  it("does not render a copy button when sql is empty", () => {
    render(<MessageBubble message={makeSqlMessage("")} />);
    const copyButton = screen.queryByRole("button", { name: /copy sql/i });
    expect(copyButton).toBeNull();
  });

  it("calls navigator.clipboard.writeText with the SQL string on click", async () => {
    const sql = "SELECT id, name FROM sku_master LIMIT 10";
    render(<MessageBubble message={makeSqlMessage(sql)} />);

    const copyButton = screen.getByRole("button", { name: /copy sql/i });
    fireEvent.click(copyButton);

    expect(navigator.clipboard.writeText).toHaveBeenCalledTimes(1);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(sql);
  });

  it("changes button label to Copied! after click", async () => {
    const sql = "SELECT * FROM inventory";
    render(<MessageBubble message={makeSqlMessage(sql)} />);

    const copyButton = screen.getByRole("button", { name: /copy sql/i });
    fireEvent.click(copyButton);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /copied/i })).toBeTruthy();
    });
  });

  it("reverts to idle state after 2000ms", async () => {
    vi.useFakeTimers();
    const { act } = await import("@testing-library/react");
    const sql = "SELECT * FROM demand_history";
    render(<MessageBubble message={makeSqlMessage(sql)} />);

    const copyButton = screen.getByRole("button", { name: /copy sql/i });

    await act(async () => {
      fireEvent.click(copyButton);
      // Flush the resolved clipboard promise.
      await Promise.resolve();
    });

    // Should now be in copied state.
    expect(screen.getByRole("button", { name: /copied/i })).toBeTruthy();

    // Advance past the 2000ms revert timeout.
    await act(async () => {
      vi.advanceTimersByTime(2100);
    });

    // Should have reverted to idle.
    expect(screen.getByRole("button", { name: /copy sql/i })).toBeTruthy();

    vi.useRealTimers();
  });
});
