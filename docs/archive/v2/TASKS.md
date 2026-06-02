# TASKS.md

## Goal

Refactor the existing system toward the architecture defined in DESIGN.md.

Existing structure should not be preserved unless it supports the new design.

Follow the phase order in MIGRATION_PLAN.md. Do not begin Phase N+1 until Phase N checkpoint passes.

---

## Phase R — Structural Rename

| ID | Task | Owner | Status | Done when |
|---|---|---|---|---|
| R-1 | Rename `packages/state/` → `packages/persistence/`; update all Python imports; update `pyproject.toml` workspace member | bdos-app-builder | Done | `grep -r "packages/state"` returns 0 hits outside `.git` |
| R-2 | Rename `packages/domain/` → `packages/knowledge/`; update all Python imports; update `pyproject.toml` workspace member | bdos-app-builder | Done | `grep -r "packages/domain"` returns 0 hits outside `.git` |
| R-3 | Rename `packages/agent/job_runner/` → `packages/agent/runner/`; update all imports | bdos-app-builder | Done | `grep -r "job_runner"` returns 0 hits outside `.git` |
| R-4 | Rename 6 test files with phase/ticket codes to descriptive names (see MIGRATION_PLAN.md §Phase R for the mapping) | bdos-test-review | Done | All old filenames gone; pytest collects the same number of tests |
| R-5 | Update `AGENTS.md` commit scope table: `state` → `persistence`, `domain` → `knowledge` | bdos-orchestrator | Done | Scopes match renamed directories |
| R-6 | Add `§Monorepo Layout`, `§Public Interfaces`, `§Phase Progression` to `docs/DESIGN.md` | bdos-orchestrator | Done | `AGENTS.md` cross-references resolve |
| R-7 | Rewrite `docs/MIGRATION_PLAN.md` inserting Phase R before Phase 0 | bdos-orchestrator | Done | MIGRATION_PLAN reflects all 8 phases (R + 0–6) |
| R-8 | Run Phase R checkpoint; tag `phase-r-complete` | bdos-infra | Done | All grep checks return 0; pytest / mypy / ruff pass |
| R-9 | Update stale path references in docs: `docs/ARCHITECTURE_RULES.md`, `docs/CONTRACTS.md`, `docs/DEFERRED.md`, `agents/app-builder/SPEC.md`, `agents/test-review/SPEC.md` — replace `packages/state/` → `packages/persistence/`, `packages/domain/` → `packages/knowledge/` | bdos-app-builder | Done | `grep -r "packages/state\|packages/domain" docs/ agents/ --include="*.md"` returns 0 (excluding `docs/archive/`) |

---

## Phase 0 — Protect

| ID | Task | Owner | Done when |
|---|---|---|---|
| P0-1 | Audit `docs/CONTRACTS.md` — replace any placeholder items with specific, testable assertions | bdos-orchestrator | No item uses vague language ("TBD", "placeholder", "etc.") |
| P0-2 | Write contract test: `GET /healthz` returns 200 | bdos-test-review | Test passes with mock transport (no live server) |
| P0-3 | Write contract test: session create → retrieve round-trip | bdos-test-review | Test passes |
| P0-4 | Write contract test: approval state machine rejects mutations of terminal states | bdos-test-review | Test passes |
| P0-5 | Write contract test: audit log is append-only (no UPDATE/DELETE on audit rows) | bdos-test-review | Test passes |
| P0-6 | Write contract test: SSE stream terminates with `done` or `error` event | bdos-test-review | Test passes |
| P0-7 | Write contract test: missing `ANTHROPIC_API_KEY` raises `RuntimeError` at the call site | bdos-test-review | Test passes |
| P0-8 | Run full test suite; record baseline pass count in `docs/TESTING.md` | bdos-infra | Baseline count documented |
| P0-9 | Tag `phase0-complete` | bdos-infra | Tag exists in git |

---

## Phase 1 — Tool Layer Isolation

| ID | Task | Owner | Done when |
|---|---|---|---|
| P1-1 | Audit `packages/agent/specialists/base.py` and `agent_based.py` for direct SQLAlchemy usage; extract to `packages/tools/` | bdos-app-builder | `grep -rn "from sqlalchemy\|import sqlalchemy" packages/agent/` returns 0 |
| P1-2 | Audit `packages/agent/orchestrator/__init__.py` and `weights.py` for direct `anthropic` SDK calls; extract to `packages/agent/llm/` | bdos-app-builder | `grep -rn "import anthropic\|from anthropic" packages/agent/` outside `llm/` returns 0 |
| P1-3 | Verify every tool in `packages/tools/` inherits from `packages/tools/base.py:Tool` | bdos-test-review | Arch test or grep confirms |
| P1-4 | Verify all LLM calls go through `packages/agent/llm/LLMClient` | bdos-test-review | Arch test or grep confirms |
| P1-5 | Run Phase 1 checkpoint greps (grep only — pytest deferred to Phase 6) | bdos-infra | Both greps return 0 hits |
| P1-6 | Tag `phase1-complete` | bdos-infra | Tag exists in git |

---

## Phase 2 — Memory Formalization

| ID | Task | Owner | Status | Done when |
|---|---|---|---|---|
| P2-1 | Implement `ShortTermMemory` in `packages/memory/__init__.py` with typed fields | bdos-app-builder | Done | Class importable; mypy passes |
| P2-2 | Implement `WorkingMemory` | bdos-app-builder | Done | Same |
| P2-3 | Implement `LongTermMemory` | bdos-app-builder | Done | Same |
| P2-4 | Implement `DecisionMemory` | bdos-app-builder | Done | Same |
| P2-5 | Implement `UserMemory` | bdos-app-builder | Done | Same |
| P2-6 | Implement `DomainMemory` | bdos-app-builder | Done | Same |
| P2-7 | Migrate `packages/agent/history.py` usages to `ShortTermMemory` / `WorkingMemory` as appropriate | bdos-app-builder | Done | No raw `dict` passed as "memory" in agent method signatures |
| P2-8 | Run mypy on `packages/memory/` (pytest deferred to Phase 6) | bdos-infra | Done | mypy clean on packages/memory/ |
| P2-9 | Tag `phase2-complete` | bdos-infra | Done | Tag exists in git |

---

## Phase 3 — Guardrail Separation

| ID | Task | Owner | Status | Done when |
|---|---|---|---|---|
| P3-1 | Audit `packages/agent/` and `apps/api/routers/` for scattered permission / approval checks | bdos-test-review | Done | Audit findings documented in DECISIONS.md |
| P3-2 | Create Guardrail module (in `packages/tools/guardrail.py`) exposing `can_execute()`, `needs_approval()`, `audit_required()` | bdos-app-builder | Done | Module importable; all three functions exported with typed signatures |
| P3-3 | Migrate scattered checks to call the Guardrail module | bdos-app-builder | Done | Inline logic removed; 3 residual schema-field keyword-arg hits documented in DECISIONS.md |
| P3-4 | Confirm approval state enforcement stays in `packages/persistence/approvals.py`; Guardrail calls it, not the reverse | bdos-test-review | Done | `approvals.py` unchanged; guardrail does not import from persistence |
| P3-5 | Run Phase 3 checkpoint grep (pytest deferred to Phase 6) | bdos-infra | Done | 3 known-acceptable schema-field hits; inline logic gone (see DECISIONS.md) |
| P3-6 | Tag `phase3-complete` | bdos-infra | Done | Tag exists in git |

---

## Phase 4 — Agent Reclassification

| ID | Task | Owner | Status | Done when |
|---|---|---|---|---|
| P4-1 | Map pre-classification roles in `agent_based.py` to DESIGN.md Domain + Analytical agent table; document in DECISIONS.md | bdos-orchestrator | Done | Mapping complete |
| P4-2 | Create `packages/agent/domain/` with one class per Domain Agent: demand, inventory, replenishment, procurement, supplier, production, logistics | bdos-app-builder | Done | 7 classes exist; each matches a row in DESIGN.md agent table |
| P4-3 | Create `packages/agent/analytical/` with one class per Analytical Agent: exception, scenario, ranking, root_cause | bdos-app-builder | Done | 4 classes exist; each matches a row in DESIGN.md agent table |
| P4-4 | Verify each class conforms to ARCHITECTURE_RULES.md rules for its classification | bdos-test-review | Done | No sqlalchemy or direct anthropic imports in domain/ or analytical/ (mypy + grep clean) |
| P4-5 | Remove `packages/agent/specialists/` after all references are migrated | bdos-app-builder | Done | Directory absent; no imports reference `specialists` |
| P4-6 | Verify directory structure: `packages/agent/specialists/` absent; `domain/` and `analytical/` present (pytest deferred to Phase 6) | bdos-infra | Done | Directories match expected layout |
| P4-7 | Tag `phase4-complete` | bdos-infra | Done | Tag exists in git |

---

## Phase 5 — Orchestrator Responsibility Cleanup

| ID | Task | Owner | Status | Done when |
|---|---|---|---|---|
| P5-1 | Audit `packages/agent/orchestrator/weights.py` for supply-chain domain constants | bdos-app-builder | Done | Audit complete |
| P5-2 | Move domain constants (`safety_stock`, `reorder_point`, `lead_time`, `service_level`, etc.) to `packages/knowledge/` or the appropriate domain agent | bdos-app-builder | Done | `grep -n "safety_stock\|reorder_point\|lead_time\|service_level" packages/agent/orchestrator/` returns 0 |
| P5-3 | Audit `packages/agent/orchestrator/__init__.py` for embedded domain reasoning; extract to specialists | bdos-app-builder | Done | No supply-chain domain logic in orchestrator |
| P5-4 | Run Phase 5 checkpoint grep (pytest deferred to Phase 6) | bdos-infra | Done | Grep returns 0 hits |
| P5-5 | Tag `phase5-complete` | bdos-infra | Done | Tag exists in git |

---

## Phase 6 — Final Validation

Phase 6 is the single pytest gate for the entire refactoring. Tests were not run in Phases 1–5 to avoid long feedback loops during structural work. See DECISIONS.md for rationale.

| ID | Task | Owner | Status | Done when |
|---|---|---|---|---|
| P6-1 | Run full pytest suite; compare pass count vs Phase 0 baseline (213 passed, 3 pre-existing failures) | bdos-infra | Done | No new failures vs baseline |
| P6-2 | Run mypy across all packages | bdos-infra | Done | Clean |
| P6-3 | Run ruff / lint | bdos-infra | Done | Clean |
| P6-4 | Verify code directory structure matches DESIGN.md §Monorepo Layout | bdos-test-review | Done | `find packages/agent -type d \| sort` matches expected layout |
| P6-5 | Verify ARCHITECTURE_RULES.md cross-cutting rules via grep or arch tests | bdos-test-review | Done | All pass |
| P6-6 | Verify no DEFERRED.md items have been implemented (scope check) | bdos-test-review | Done | Scope check passes |
| P6-7 | Mark all task rows in this file complete | bdos-orchestrator | Done | All rows show done |
| P6-8 | Tag `v2-complete` | bdos-infra | Done | Tag exists in git |

---

## Phase 7 — UX: Balanced Workspace

Goal: Rebuild the chat interface from a plain AI chat into a **Decision Workspace** for supply chain analysis.
Four core elements: Quick Actions, Analysis Card, Agent Activity panel, Evidence Sources.

| ID | Task | Owner | Status | Done when |
|---|---|---|---|---|
| P7-1 | Update harness docs (TASKS.md, STATE.md, DECISIONS.md) | bdos-orchestrator | Done | This row |
| P7-2 | Define `apps/web/types/workspace.ts` (AgentStep, EvidenceSource, RecommendedAction, AnalysisResult, QuickAction) | bdos-app-builder | Done | `tsc --noEmit` passes |
| P7-3 | Create `QuickActionCard` + `QuickActionGrid` components with 5 mock actions | bdos-app-builder | Done | Cards render; click fills input |
| P7-4 | Create `AnalysisCard` component; wire into `MessageBubble` via `## Summary` + `## Key Findings` detection | bdos-app-builder | Done | Structured cards render for matching AI responses |
| P7-5 | Create `AgentActivityPanel` (SSE + history; user-friendly step labels; empty state) | bdos-app-builder | Done | Right panel shows "Agent Activity" header and step list |
| P7-6 | Create `EvidenceSources` component; embed in `AgentActivityPanel` | bdos-app-builder | Done | Data sources shown from `tool_completed` events |
| P7-7 | Restructure `ChatSidebar` — Main nav section + Sessions section | bdos-app-builder | Done | Chat / KPI / Approvals / Audit Log visible as nav; sessions below |
| P7-8 | Update `page.tsx` — integrate all new components; update placeholder + Add Context button | bdos-app-builder | Done | Full page assembled |
| P7-9 | Delete old `EventLog.tsx` and `ReasoningPanel.tsx` | bdos-app-builder | Done | Files absent |
| P7-10 | Final visual + TypeScript validation | bdos-test-review | Done | `tsc --noEmit` clean; browser checklist passes |

---

## Phase 8 — UX: Design Spec Alignment

Goal: Close the visual gap between Phase 7 implementation and the target design in `docs/archive/UX_TASKS.md`. UI-only changes; no backend work. Tests consolidated at end.

| ID | Task | Owner | Status | Done when |
|---|---|---|---|---|
| P8-1 | Update harness docs (TASKS.md, STATE.md, DECISIONS.md) | bdos-orchestrator | Done | This row |
| P8-2 | Redesign QuickActionCard + QuickActionGrid — 5-column horizontal, per-card icon + theme color | bdos-app-builder | Done | Cards render 5-across on desktop; each has icon and color accent |
| P8-3 | Add empty-state header to chat page — title, subtitle, Configure Agent button | bdos-app-builder | Done | Header visible when message list is empty |
| P8-4 | Improve AgentActivityPanel — Live badge, step connector lines, Evidence/Notes tabs | bdos-app-builder | Done | Panel shows tabs; steps connected by vertical line |
| P8-5 | Improve Chat Composer — Mic icon, disclaimer text, updated placeholder | bdos-app-builder | Done | Mic icon rendered (disabled); disclaimer visible below input |
| P8-6 | Improve ChatSidebar — bottom user area, session hover overflow button | bdos-app-builder | Done | User area fixed at bottom; `···` button appears on session hover |
| P8-7 | Unify design tokens — bg `#070B14`, radial gradient, CSS custom properties | bdos-app-builder | Done | Background matches spec; CSS vars defined in globals.css |
| P8-8 | Final TypeScript + visual validation | bdos-test-review | Done | `tsc --noEmit` clean; 0 errors |

---

## Post-Phase 8 — Ad-hoc UX Fixes & Admin Improvements

Goal: Fix UX regressions and add admin tooling discovered after Phase 8 completion.

| ID | Task | Owner | Status | Done when |
|---|---|---|---|---|
| PX-1 | `/chat` route: auto-redirect to most recent session; create new only if 0 sessions; add `useRef` guard against React 18 Strict Mode double-fire | bdos-app-builder | Done | Clicking "Decision OS" navigates to existing session, not a new one |
| PX-2 | Non-existent session ID redirect: `fetchSession()` on mount; 404 → `router.replace("/chat")` | bdos-app-builder | Done | `/chat/nonexistent-id` redirects to `/chat` |
| PX-3 | Session deletion two-step confirmation: ··· → trash icon → confirm click | bdos-app-builder | Done | Clicking ··· shows trash; clicking trash deletes; mouse-leave cancels |
| PX-4 | Fix `agent_steps_repo.py`: pass `datetime` objects to asyncpg instead of ISO strings | bdos-app-builder | Done | No more `expected datetime.datetime instance, got 'str'` warnings |
| PX-5 | Admin bulk delete: `DELETE /api/v1/admin/sessions` endpoint + "Delete All Sessions" button in `/usage` | bdos-app-builder | Done | Button deletes all sessions and reloads stats |

---

## Phase 9 — Chat UI: Analysis Result Card Redesign

Goal: Transform the AI response from a Markdown-table display into a structured Analysis Result Card UI.
Supply chain decision UI — risk/findings/actions/evidence as structured components.

### Batch 9-1 — Foundation: Types + Mock Data (Agent: App Builder)

| ID | Task | Owner | Status | Done when |
|---|---|---|---|---|
| P9-1 | Create `apps/web/types/analysis.ts` — full type definitions for `InventoryShortageAnalysis`, `RiskLevel`, `AnalysisSummaryCard`, `RecommendedAction`, `RiskItem`, `RiskGroup` | bdos-app-builder | Done | `tsc --noEmit` passes; all types exported |
| P9-2 | Create `apps/web/data/mockInventoryShortageAnalysis.ts` — full mock dataset for inventory shortage risk analysis | bdos-app-builder | Done | File importable; matches `InventoryShortageAnalysis` type |

### Batch 9-2 — P0 Analysis Result Card (Agent: App Builder)

| ID | Task | Owner | Status | Done when |
|---|---|---|---|---|
| P9-3 | Create `RiskSummaryCards.tsx` — 4-card KPI grid (Critical SKUs, High Risk SKUs, Top Driver, Action Required) with tone-based color coding | bdos-app-builder | Done | Cards render 4-across; critical=red, high=orange, warning=yellow, neutral=blue |
| P9-4 | Create `RiskBreakdownSection.tsx` — Critical/High/Medium sections with SKU rows, location, days of supply, driver, and actions text | bdos-app-builder | Done | Three visually distinct risk sections render; Critical has strongest visual weight |
| P9-5 | Create `RecommendedActionsPanel.tsx` — action list with priority badge, action text, optional metadata (owner/timing), `View action plan →` link | bdos-app-builder | Done | Actions render with Critical/High/Medium badges; at least 3 actions shown |
| P9-6 | Create `ConfidencePanel.tsx` — confidence score with progress bar and label | bdos-app-builder | Done | Progress bar renders with correct width; label shows confidence level |
| P9-7 | Create `DataUsedPanel.tsx` — data source chips with icon and name | bdos-app-builder | Done | Data sources render as styled chips |
| P9-8 | Create `AnalysisResultCard.tsx` — top-level container orchestrating all sub-panels; header with title/status/duration/confidence; summary cards; 3-column middle; risk breakdown; footer | bdos-app-builder | Done | Full card renders with mock data; no Markdown tables visible |
| P9-9 | Update `AnalysisCard.tsx` — detect `InventoryShortageAnalysis` JSON block in AI response and delegate to `AnalysisResultCard`; fall back to existing Markdown parser for other formats | bdos-app-builder | Done | Messages with JSON analysis block render as `AnalysisResultCard`; other messages unchanged |

### Batch 9-3 — P0 Side Panel + Scrollbar (Agent: App Builder)

| ID | Task | Owner | Status | Done when |
|---|---|---|---|---|
| P9-10 | Update `EvidenceSources.tsx` — show mock data sources when events are empty; add freshness column and icon per row; maintain `Used` badge | bdos-app-builder | Done | Right panel shows 4 data sources even with no SSE events |
| P9-11 | Update `AgentActivityPanel.tsx` — replace abstract step labels with business-context labels: "Understanding request", "Loading inventory data", "Checking demand forecast", "Calculating days of supply", "Identifying shortage risk", "Generating recommended actions" | bdos-app-builder | Done | Step labels are business-context; no "Analysis complete" duplicates |
| P9-12 | Add custom dark scrollbar CSS to `apps/web/app/globals.css` and apply `.custom-scrollbar` to main chat area and right panel | bdos-app-builder | Done | White scrollbar gone; dark translucent scrollbar visible on scroll |

### Batch 9-4 — P1 Layout + Polish (Agent: App Builder)

| ID | Task | Owner | Status | Done when |
|---|---|---|---|---|
| P9-13 | Update `ChatSidebar.tsx` session items — title max 2 lines (`line-clamp-2`); full title in `title` attribute; date/time visible; active session with purple left border | bdos-app-builder | Done | Session titles wrap to 2 lines; truncate after that; timestamp visible |
| P9-14 | Header state improvement — active session shows session title; empty state shows welcome header | bdos-app-builder | Done | Header displays session title when messages exist; welcome text when empty |

### Batch 9-5 — Validation (Agent: Test/Review)

| ID | Task | Owner | Status | Done when |
|---|---|---|---|---|
| P9-15 | TypeScript + lint validation for all Phase 9 changes; add `.eslintrc.json` + `"lint"` script; fix pre-existing hook-after-return error in `MessageBubble.tsx` | bdos-test-review | Done | `tsc --noEmit` exits 0; `next lint` exits 0 (3 pre-existing useEffect warnings, no errors) |
