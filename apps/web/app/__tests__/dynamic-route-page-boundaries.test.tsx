/**
 * Regression coverage for the Next.js 15 dynamic-route page boundary (T-750).
 *
 * Next.js 15 requires dynamic routes to be async Server Components whose
 * `params` is a Promise. These tests execute each real page boundary: they
 * call the default Page export with `Promise.resolve(params)` and assert the
 * returned React element targets the colocated Client Component with exactly
 * one primitive ID prop.
 *
 * A regression to either forbidden shape fails these tests:
 * - a direct Client Page ("use client" page.tsx) -> caught by the
 *   server-component source contract,
 * - a sync `params` object (no Promise / no await) -> caught behaviorally,
 *   because Next.js hands pages a Promise and destructuring it yields an
 *   undefined id.
 */

import { describe, it, expect, vi } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// ---------------------------------------------------------------------------
// Module mocks: replace each heavy Client Component so the boundary under
// test loads without dragging browser-only dependency trees into jsdom.
// ---------------------------------------------------------------------------

vi.mock("../chat/[sessionId]/ChatSessionClient", () => ({
  default: (_props: { sessionId: string }) => null,
}));
vi.mock("../recommendations/[id]/RecommendationDetailClient", () => ({
  default: (_props: { id: string }) => null,
}));
vi.mock("../scenarios/[sessionId]/ScenarioComparisonClient", () => ({
  default: (_props: { sessionId: string }) => null,
}));

const { default: ChatPage } = await import("../chat/[sessionId]/page");
const { default: ChatSessionClient } = await import(
  "../chat/[sessionId]/ChatSessionClient"
);
const { default: RecommendationPage } = await import(
  "../recommendations/[id]/page"
);
const { default: RecommendationDetailClient } = await import(
  "../recommendations/[id]/RecommendationDetailClient"
);
const { default: ScenarioPage } = await import("../scenarios/[sessionId]/page");
const { default: ScenarioComparisonClient } = await import(
  "../scenarios/[sessionId]/ScenarioComparisonClient"
);

// ---------------------------------------------------------------------------
// Source helpers for the server/client directive contract
// ---------------------------------------------------------------------------

function readSource(relativePath: string): string {
  return readFileSync(fileURLToPath(new URL(relativePath, import.meta.url)), "utf8");
}

function declaresUseClient(source: string): boolean {
  const trimmed = source.trimStart();
  return trimmed.startsWith('"use client"') || trimmed.startsWith("'use client'");
}

// ---------------------------------------------------------------------------
// Behavioral boundary assertions
// ---------------------------------------------------------------------------

describe("Next.js 15 dynamic page boundaries", () => {
  it("chat/[sessionId]: awaits params Promise and forwards primitive sessionId to ChatSessionClient", async () => {
    const element = await ChatPage({
      params: Promise.resolve({ sessionId: "sess-e2e-123" }),
    });

    expect(element.type).toBe(ChatSessionClient);
    expect(Object.keys(element.props)).toEqual(["sessionId"]);
    expect(element.props.sessionId).toBe("sess-e2e-123");
    expect(typeof element.props.sessionId).toBe("string");
  });

  it("recommendations/[id]: awaits params Promise and forwards primitive id to RecommendationDetailClient", async () => {
    const element = await RecommendationPage({
      params: Promise.resolve({ id: "rec-e2e-456" }),
    });

    expect(element.type).toBe(RecommendationDetailClient);
    expect(Object.keys(element.props)).toEqual(["id"]);
    expect(element.props.id).toBe("rec-e2e-456");
    expect(typeof element.props.id).toBe("string");
  });

  it("scenarios/[sessionId]: awaits params Promise and forwards primitive sessionId to ScenarioComparisonClient", async () => {
    const element = await ScenarioPage({
      params: Promise.resolve({ sessionId: "sess-cmp-789" }),
    });

    expect(element.type).toBe(ScenarioComparisonClient);
    expect(Object.keys(element.props)).toEqual(["sessionId"]);
    expect(element.props.sessionId).toBe("sess-cmp-789");
    expect(typeof element.props.sessionId).toBe("string");
  });
});

// ---------------------------------------------------------------------------
// Server/Client split contract: pages stay Server Components
// ---------------------------------------------------------------------------

describe("dynamic page server/client split contract", () => {
  it.each([
    ["chat/[sessionId]", "../chat/[sessionId]/page.tsx", "../chat/[sessionId]/ChatSessionClient.tsx"],
    [
      "recommendations/[id]",
      "../recommendations/[id]/page.tsx",
      "../recommendations/[id]/RecommendationDetailClient.tsx",
    ],
    [
      "scenarios/[sessionId]",
      "../scenarios/[sessionId]/page.tsx",
      "../scenarios/[sessionId]/ScenarioComparisonClient.tsx",
    ],
  ])("%s keeps page.tsx a Server Component and the directive on the Client Component", (route, pagePath, clientPath) => {
    const pageSource = readSource(pagePath);
    expect(pageSource, `${route}/page.tsx must not be a Client Component`).toMatch(
      /params:\s*Promise</,
    );
    expect(pageSource, `${route}/page.tsx must await params`).toMatch(/await\s+params\b/);
    expect(declaresUseClient(pageSource), `${route}/page.tsx must not declare "use client"`).toBe(
      false,
    );
    expect(
      declaresUseClient(readSource(clientPath)),
      `${route} Client Component must declare "use client"`,
    ).toBe(true);
  });
});
