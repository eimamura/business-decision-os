/**
 * Unit tests for ThemeToggle component.
 *
 * Requires: vitest + @testing-library/react + jsdom
 * Setup: add vitest, @vitejs/plugin-react, @testing-library/react,
 *        @testing-library/user-event, and jsdom to apps/web devDependencies,
 *        then add a vitest.config.ts at apps/web/vitest.config.ts.
 *
 * Wire-up for test-review: run `npx vitest run tests/unit/test_theme_toggle.tsx`
 * from apps/web/ once the dependencies above are installed.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ThemeToggle from "@/components/ThemeToggle";

// ---------------------------------------------------------------------------
// DOM / localStorage stubs
// ---------------------------------------------------------------------------

beforeEach(() => {
  // Reset <html> class list before each test
  document.documentElement.className = "";

  // Clear localStorage
  localStorage.clear();

  // Default: prefers-color-scheme: light
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === "(prefers-color-scheme: dark)" ? false : false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ThemeToggle", () => {
  it("renders a toggle button", () => {
    render(<ThemeToggle />);
    const btn = screen.getByRole("button");
    expect(btn).toBeTruthy();
  });

  it("clicking once adds 'dark' class to document.documentElement", async () => {
    // Start in light mode (no stored preference, prefers-color-scheme: light)
    document.documentElement.classList.remove("dark");

    render(<ThemeToggle />);
    const btn = screen.getByRole("button");

    fireEvent.click(btn);

    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("clicking twice removes 'dark' class from document.documentElement", async () => {
    document.documentElement.classList.remove("dark");

    render(<ThemeToggle />);
    const btn = screen.getByRole("button");

    fireEvent.click(btn); // light -> dark
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    fireEvent.click(btn); // dark -> light
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("persists theme choice in localStorage when toggling to dark", () => {
    document.documentElement.classList.remove("dark");

    render(<ThemeToggle />);
    const btn = screen.getByRole("button");

    fireEvent.click(btn); // -> dark
    expect(localStorage.getItem("theme")).toBe("dark");
  });

  it("persists theme choice in localStorage when toggling back to light", () => {
    document.documentElement.classList.remove("dark");

    render(<ThemeToggle />);
    const btn = screen.getByRole("button");

    fireEvent.click(btn); // -> dark
    fireEvent.click(btn); // -> light
    expect(localStorage.getItem("theme")).toBe("light");
  });

  it("respects prefers-color-scheme: dark when localStorage is empty", () => {
    // Override matchMedia to return dark preference
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query === "(prefers-color-scheme: dark)",
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });

    render(<ThemeToggle />);

    // Component useEffect runs on mount and should apply dark class
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("reads stored 'dark' preference from localStorage on mount", () => {
    localStorage.setItem("theme", "dark");

    render(<ThemeToggle />);

    // Component useEffect should apply dark class based on localStorage
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("reads stored 'light' preference and does NOT add dark class", () => {
    localStorage.setItem("theme", "light");
    // Even if OS preference is dark, stored light takes priority
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query === "(prefers-color-scheme: dark)",
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });

    render(<ThemeToggle />);

    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
