# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: tests/e2e/playwright/p102_job_dispatch_modal.spec.ts >> P102 Job Dispatch Modal >> clicking Inventory Simulation scenario injects correct prompt
- Location: tests/e2e/playwright/p102_job_dispatch_modal.spec.ts:296:7

# Error details

```
Error: apiRequestContext.post: connect ECONNREFUSED ::1:8000
Call log:
  - → POST http://localhost:8000/api/v1/sessions
    - user-agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/148.0.7778.96 Safari/537.36
    - accept: */*
    - accept-encoding: gzip,deflate,br
    - X-Dev-User: dev-user
    - content-type: application/json
    - content-length: 50

```