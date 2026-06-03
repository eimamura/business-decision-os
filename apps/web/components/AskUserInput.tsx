"use client";

import { useState } from "react";

export interface AskUserInputProps {
  sessionId: string;
  askUserId: string;
  question: string;
  suggestions: readonly string[];
  onSubmit: (answer: string) => Promise<void>;
}

export function AskUserInput({
  sessionId: _sessionId,
  askUserId: _askUserId,
  question,
  suggestions,
  onSubmit,
}: AskUserInputProps): React.ReactElement {
  const [inputValue, setInputValue] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submittedAnswer, setSubmittedAnswer] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChipClick = (chip: string): void => {
    setInputValue(chip);
  };

  const handleSubmit = async (): Promise<void> => {
    const answer = inputValue.trim();
    if (!answer || isSubmitting) return;
    setIsSubmitting(true);
    // Show submitted state immediately (optimistic); streaming continues in context
    setSubmittedAnswer(answer);
    setSubmitted(true);
    setIsSubmitting(false);
    void onSubmit(answer);
  };

  if (submitted) {
    return (
      <div className="rounded-lg border p-4 bg-muted/30 space-y-1">
        <p data-testid="ask-user-question" className="text-sm font-medium">
          {question}
        </p>
        <p data-testid="ask-user-answered" className="text-sm text-muted-foreground">
          {submittedAnswer}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border p-4 bg-muted/30 space-y-3">
      <p data-testid="ask-user-question" className="text-sm font-medium">
        {question}
      </p>

      {suggestions.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {suggestions.map((chip, idx) => (
            <button
              key={chip}
              type="button"
              data-testid={`ask-user-suggestion-${idx}`}
              onClick={() => handleChipClick(chip)}
              className="rounded-full border px-3 py-1 text-sm hover:bg-muted cursor-pointer"
            >
              {chip}
            </button>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <input
          type="text"
          data-testid="ask-user-input"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void handleSubmit();
          }}
          placeholder="Type your answer…"
          className="flex-1 rounded-md border bg-background px-3 py-2 text-sm"
          disabled={isSubmitting}
        />
        <button
          type="button"
          data-testid="ask-user-submit"
          onClick={() => void handleSubmit()}
          disabled={isSubmitting || !inputValue.trim()}
          className="rounded-md border bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {isSubmitting ? "…" : "Submit"}
        </button>
      </div>
    </div>
  );
}
