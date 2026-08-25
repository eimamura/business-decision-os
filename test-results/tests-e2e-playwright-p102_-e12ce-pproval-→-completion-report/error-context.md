# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: tests/e2e/playwright/p102_job_dispatch_modal.spec.ts >> P102 Job Dispatch Modal >> live E2E: job dispatch modal → HITL approval → completion report
- Location: tests/e2e/playwright/p102_job_dispatch_modal.spec.ts:361:7

# Error details

```
Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
Call log:
  - navigating to "/chat/5229c6c7-904a-4c19-bb3e-a651bd7d7910", waiting until "load"

```

# Test source

```ts
  283 |     await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 3_000 });
  284 | 
  285 |     // The user message bubble must contain the expected prompt text.
  286 |     await expect(
  287 |       page.locator(".rounded-2xl.bg-indigo-600").filter({
  288 |         hasText: "Train the demand forecast model for SKU-001 as a background job",
  289 |       }),
  290 |     ).toBeVisible({ timeout: 10_000 });
  291 |   });
  292 | 
  293 |   /**
  294 |    * T-610-PW-3: Clicking Inventory Simulation scenario injects the correct prompt.
  295 |    */
  296 |   test("clicking Inventory Simulation scenario injects correct prompt", async ({
  297 |     page,
  298 |     createdSessionIds,
  299 |   }) => {
  300 |     test.setTimeout(30_000);
  301 | 
  302 |     const sessionId = await createSession(
  303 |       page,
  304 |       createdSessionIds,
  305 |       "P102 inventory simulation scenario test",
  306 |     );
  307 | 
  308 |     // Register mock stream BEFORE goto.
  309 |     const streamPattern = `**/api/v1/sessions/${sessionId}/stream`;
  310 |     await page.route(streamPattern, async (route) => {
  311 |       const now = new Date().toISOString();
  312 |       const events = [
  313 |         {
  314 |           type: "text_delta",
  315 |           session_id: sessionId,
  316 |           delta: "Acknowledged — simulation job queued.",
  317 |           timestamp: now,
  318 |         },
  319 |         {
  320 |           type: "done",
  321 |           session_id: sessionId,
  322 |           timestamp: now,
  323 |         },
  324 |       ];
  325 |       const body = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
  326 |       await route.fulfill({ status: 200, headers: SSE_HEADERS, body });
  327 |     });
  328 | 
  329 |     await page.goto(`/chat/${sessionId}`);
  330 |     await expect(page.locator("textarea")).toBeVisible();
  331 | 
  332 |     await openModal(page);
  333 | 
  334 |     const dialog = page.getByRole("dialog");
  335 |     await dialog.locator('[data-testid="category-job-dispatch"]').click();
  336 | 
  337 |     await dialog
  338 |       .locator('[data-testid="scenario-job-dispatch-jd-inventory-simulation"]')
  339 |       .click();
  340 | 
  341 |     await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 3_000 });
  342 | 
  343 |     await expect(
  344 |       page.locator(".rounded-2xl.bg-indigo-600").filter({
  345 |         hasText: "Run a full inventory simulation for all SKUs as a background job",
  346 |       }),
  347 |     ).toBeVisible({ timeout: 10_000 });
  348 |   });
  349 | 
  350 |   /**
  351 |    * T-610-PW-4: Live E2E — modal → HITL approval → job-status-card → completion report.
  352 |    *
  353 |    * Full flow:
  354 |    *   1. Open modal, select Job Dispatch category, click Train Forecast Model.
  355 |    *   2. Prompt is sent automatically (no separate Send click needed).
  356 |    *   3. Mocked SSE emits awaiting_approval → approval card appears.
  357 |    *   4. Click Approve → mocked decision endpoint returns 200.
  358 |    *   5. job-status-card appears and polls mocked job endpoint.
  359 |    *   6. Second SSE stream emits job_report → assistant message with "completed".
  360 |    */
  361 |   test("live E2E: job dispatch modal → HITL approval → completion report", async ({
  362 |     page,
  363 |     createdSessionIds,
  364 |   }) => {
  365 |     test.setTimeout(120_000);
  366 | 
  367 |     const sessionId = await createSession(
  368 |       page,
  369 |       createdSessionIds,
  370 |       "P102 live E2E job dispatch test",
  371 |     );
  372 | 
  373 |     const approvalId = `00000000-0000-0000-0001-${Date.now().toString().padStart(12, "0")}`;
  374 |     const jobId = `00000000-0000-0000-0002-${Date.now().toString().padStart(12, "0")}`;
  375 |     const reportContent =
  376 |       "**Job report — train_forecast completed.**\n\nModel trained successfully for SKU-001.";
  377 | 
  378 |     // Set up all mocks BEFORE navigation.
  379 |     await injectApprovalSSE(page, sessionId, approvalId, jobId);
  380 |     await mockApprovalDecision(page, approvalId);
  381 |     await mockJobPoll(page, jobId);
  382 | 
> 383 |     await page.goto(`/chat/${sessionId}`);
      |                ^ Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
  384 |     await expect(page.locator("textarea")).toBeVisible();
  385 | 
  386 |     // a. Open modal → Job Dispatch category → Train Forecast Model scenario.
  387 |     await openModal(page);
  388 |     const dialog = page.getByRole("dialog");
  389 |     await dialog.locator('[data-testid="category-job-dispatch"]').click();
  390 |     await dialog
  391 |       .locator('[data-testid="scenario-job-dispatch-jd-train-forecast"]')
  392 |       .click();
  393 | 
  394 |     // Modal closes automatically after scenario selection.
  395 |     await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 3_000 });
  396 | 
  397 |     // b. Approval card must appear from the injected SSE.
  398 |     const approvalCard = page.locator('[data-testid="job-approval-card"]').first();
  399 |     await expect(approvalCard).toBeVisible({ timeout: CARD_TIMEOUT_MS });
  400 | 
  401 |     const approveBtn = approvalCard.locator('[data-testid="approve-btn"]');
  402 |     await expect(approveBtn).toBeVisible();
  403 | 
  404 |     // c. Inject job_report SSE before clicking Approve, so the second stream is
  405 |     //    ready when the UI re-subscribes (or polls) after approval.
  406 |     await injectJobReportSSE(page, sessionId, reportContent);
  407 | 
  408 |     // d. Click Approve.
  409 |     await approveBtn.click();
  410 | 
  411 |     // e. job-status-card must appear after approval.
  412 |     await expect(
  413 |       page.locator('[data-testid="job-status-card"]').first(),
  414 |     ).toBeVisible({ timeout: STATUS_CARD_TIMEOUT_MS });
  415 | 
  416 |     // f. Assistant message containing the report text must appear (live SSE, not reload).
  417 |     await expect(
  418 |       page
  419 |         .locator("text=Job report")
  420 |         .or(page.locator("text=train_forecast completed"))
  421 |         .or(page.locator("text=completed"))
  422 |         .first(),
  423 |     ).toBeVisible({ timeout: REPORT_TIMEOUT_MS });
  424 |   });
  425 | });
  426 | 
```