import { test as base, expect } from "@playwright/test";

export { expect };

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface CleanupFixtures {
  createdSessionIds: string[];
}

/**
 * Extends Playwright's base `test` with a `createdSessionIds` fixture.
 *
 * After each test, any session IDs pushed into `createdSessionIds` are
 * deleted via `DELETE /api/v1/sessions/{id}`.  404 responses are silently
 * ignored (the session may not have been committed to the DB if the test
 * failed before the API call completed).
 */
export const testWithCleanup = base.extend<CleanupFixtures>({
  createdSessionIds: async ({}, use) => {
    const ids: string[] = [];

    await use(ids);

    for (const id of ids) {
      try {
        const response = await fetch(`${API_BASE}/api/v1/sessions/${id}`, {
          method: "DELETE",
        });
        if (!response.ok && response.status !== 404) {
          console.warn(
            `[fixtures] DELETE /api/v1/sessions/${id} returned ${response.status}`,
          );
        }
      } catch (err: unknown) {
        console.warn(
          `[fixtures] DELETE /api/v1/sessions/${id} threw:`,
          err instanceof Error ? err.message : String(err),
        );
      }
    }
  },
});
