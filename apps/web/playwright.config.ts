import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "../../tests/e2e/playwright",
  timeout: 30_000,
  retries: 1,
  // Serial execution is required because all real-Ollama tests share a single GPU
  // instance via the Ollama server, which processes requests one at a time.
  // Parallel workers would queue up concurrent requests and cause timeout failures.
  workers: 1,
  reporter: "list",
  use: {
    baseURL: process.env.WEB_URL ?? "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
