/**
 * Unit tests for the copy-to-clipboard button in AssistantBubble (MessageBubble.tsx).
 *
 * Run from apps/web/:
 *   npm test
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
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
const { act } = await import("@testing-library/react");

import type { ChatMessage } from "@/types/chat";

function makeAssistantMessage(content: string): ChatMessage {
  return {
    id: "msg-1",
    role: "assistant",
    content,
    isStreaming: false,
    isError: false,
  };
}

describe("AssistantBubble copy button", () => {
  beforeEach(() => {
    // Reset clipboard mock before each test.
    const mockWriteText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: mockWriteText },
      configurable: true,
      writable: true,
    });
  });

  it("renders a copy button when content is a non-empty string", () => {
    render(<MessageBubble message={makeAssistantMessage("Hello, world!")} />);
    const copyButton = screen.getByRole("button", { name: /copy response/i });
    expect(copyButton).toBeTruthy();
  });

  it("does not render a copy button when content is an empty string", () => {
    render(<MessageBubble message={makeAssistantMessage("")} />);
    const copyButton = screen.queryByRole("button", { name: /copy response/i });
    expect(copyButton).toBeNull();
  });

  it("calls navigator.clipboard.writeText with the message content on click", async () => {
    const content = "Hello, world!";
    render(<MessageBubble message={makeAssistantMessage(content)} />);

    const copyButton = screen.getByRole("button", { name: /copy response/i });
    fireEvent.click(copyButton);

    expect(navigator.clipboard.writeText).toHaveBeenCalledTimes(1);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(content);
  });

  it("shows Copied! after click and reverts to Copy after 2000ms", async () => {
    vi.useFakeTimers();
    const content = "Hello, world!";
    render(<MessageBubble message={makeAssistantMessage(content)} />);

    const copyButton = screen.getByRole("button", { name: /copy response/i });

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
    expect(screen.getByRole("button", { name: /copy response/i })).toBeTruthy();

    vi.useRealTimers();
  });
});
