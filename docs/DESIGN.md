# DESIGN.md

## Purpose

This document defines the final target design of the supply chain optimization agent system.

The system spans multiple domains — demand, inventory, replenishment, procurement, production, logistics, and supplier risk — and supports human decision-making by combining operational data, business rules, and analytical results into an Agentic AI system.

This document does not define implementation steps, phases, task lists, migration procedures, source code structure, table definitions, API specifications, test case lists, or deployment procedures.
Those are managed in separate documents.

The role of this document is to declare the target state that coding agents must approach during large-scale refactoring — without being constrained by the existing implementation.

---

## Terminology

This project uses the word "agent" in two distinct, non-overlapping contexts. Confusing them is a common source of misunderstanding.

### Product Agents (runtime)

Agents that **are** the Business Decision OS system. They run in production, process user requests, call tools, and generate decision-ready answers.

| Term used in this document | Role |
|---|---|
| **SessionOrchestrator** | Session-level routing and synthesis — intent classification, planning, routing, execution control, aggregation, SessionResponse assembly |
| **Supply Chain Control Agent** | Cross-domain judgment center and user-facing responder — integrates Specialist and Cross-Domain Agent results, owns the final answer (daily – weekly cadence) |
| **S&OP Agent** | Upper-layer planning agent — scenario comparison, management decisions across demand / supply / inventory / finance. Planning horizon: monthly and beyond (the weekly S&OP review is a meeting cadence, not the planning horizon). Introduced after MVP. |
| **Specialist Domain Agent** | One-domain deep analysis — Demand Agent, Inventory Agent, Replenishment Agent, Production Agent, Procurement Agent, Logistics Agent, Finance Agent, … |
| **Cross-Domain Agent** | Functional analysis capability, not domain-bound — Anomaly Detector Agent, Simulation Optimizer Agent, Evaluator Agent, Data Engineer Agent |

When this document says "agent" without qualification, it means a product agent.

### Coding Agents (development-time)

Claude Code subagents that **build and maintain** this system. They run inside the Claude Code harness during development and never appear in the production system.

| Term used in AGENTS.md | Role |
|---|---|
| `bdos-orchestrator` | Plans phases, decomposes tasks, routes to specialists, updates TASKS.md |
| `bdos-app-builder` | Writes application code — FastAPI, Python packages, Next.js |
| `bdos-infra` | Infrastructure, Docker Compose, CI/CD, Makefile |
| `bdos-test-review` | Writes tests, reviews code, verifies phase checkpoints |

When AGENTS.md says "agent" or "subagent", it means a coding agent.

**The product agents are what the coding agents are building.** They are different things.

---

## Design Principles

This system is designed as an agent system that supports business decision-making, not as a simple chatbot.

The core of an Agentic AI is the combination of the following components:

- Agent
- Tools
- Memory
- Loop
- Guardrails
- Workflow

Agents are responsible for judgment, decomposition, and selection.
Tools are responsible for data retrieval, calculation, analysis, simulation, and external actions.
Memory retains state, assumptions, decision history, and domain knowledge.
Loop enables continuous analysis, correction, and re-evaluation.
Guardrails control permissions, safety, approvals, and auditing.
Workflow defines the collaborative process between humans and agents.

This system prioritizes clear responsibility boundaries, Tools, Memory, and Guardrails over increasing the number of agents.

### Agents Are Responsibility Boundaries, Not Organizational Departments

**Agents are not copies of business departments.**
**Agents are responsibility boundaries for reasoning, context selection, and execution control.**

A Finance Agent is not a model of the Finance department — it is a boundary for financial reasoning, financial data retrieval, and financial impact analysis. An agent that mirrors an org chart inherits its silos. An agent that mirrors a reasoning boundary composes cleanly with other agents.

This principle prevents the most common design error: mapping every department to an agent and ending up with fragmented judgment that no single agent can integrate.

### The Supply Chain Control Agent is a Business OS, Not a Single LLM

A coding agent needs a structured workspace to be effective:

```text
Coding Agent workspace
= repo / source files / tests / rules (CLAUDE.md) / skills / tools / subagents / memory / scratchpad
```

The Supply Chain Control Agent needs an equivalent business workspace:

```text
Supply Chain Agent workspace
= data / KPI definitions / business rules / past decisions / memory / tools / specialist agents / analysis scratchpad
```

The correspondence is direct:

| Coding Agent | Supply Chain Agent |
| --- | --- |
| Repository | Lakehouse / ERP / planning data |
| Source files | Orders / inventory / forecast / shipment tables |
| Tests | KPI checks / data quality checks / validation rules |
| CLAUDE.md / rules | Business rules / S&OP policy / planning assumptions |
| Skills | Standard analysis procedures (stockout analysis, excess detection, delay root cause) |
| Tools | SQL, DataFrame, forecast, optimization |
| Subagents | Demand, Inventory, Production, Finance specialists |
| Memory | Past decisions, exceptions, assumptions, user preferences |
| Worktree / scratchpad | Temporary analysis workspace for the current question |

The five elements — Memory, Skills, Tools, Specialist Agents, and Working Context — are detailed in `## Context Engineering Layer`.

The key architectural implication: **the LLM must not receive everything in every prompt.** The system must be structured so that the right rules, data, and analysis procedures are retrieved on demand — not pre-loaded into a single massive context. This is what distinguishes a context-engineered business OS from a prompt-stuffed chatbot.

### Most Important Design Principle: Integrate Judgment, Divide Processing

**Business judgment is integrated. Implementation processing may be divided.**

```text
Judgment center  = Supply Chain Control Agent
Processing units = Tools / Sub-modules / Sub-agents
```

**Bad division — judgment fragmented:**

```text
Demand Agent    judges demand alone
Inventory Agent judges inventory alone
Production Agent judges production alone
Finance Agent   judges profit alone
→ merge results at the end
```

Supply chain problems are cross-domain. Fragmented conclusions miss root causes that only appear when data is read together.

**Good division — processing delegated, judgment unified:**

```text
User
 ↓
Supply Chain Control Agent
 ↓ delegates specific processing
  - fetch demand data
  - calculate inventory KPIs
  - detect stockout risk
  - analyze shipment delays
  - calculate profit impact
  - compare scenarios
 ↓
Supply Chain Control Agent re-integrates and answers:
  - What is happening
  - Why it is happening
  - Priority order
  - Decision options
  - Next data to review
```

**Rule:** The Supply Chain Control Agent is the sole owner of operational supply chain conclusions (daily–weekly horizon). The S&OP Agent owns planning-horizon conclusions (monthly and beyond) as a peer — not a sub-agent. Sub-agents return domain-scoped analysis materials only.

Sub-agents are best understood as **analysis functions, investigation units, and calculation modules** — not as independent decision-makers. Value is preserved because judgment stays unified even as processing is distributed.

**In practice — a cross-domain example:**

Sub-agents return domain-scoped intermediate results:

```text
Demand Agent:    SKU A demand is surging.
Inventory Agent: SKU A days-on-hand is 3.
Logistics Agent: No shipping delays.
Procurement Agent: Next inbound is in 5 days.
```

The Control Agent produces the integrated final answer:

```text
SKU A has a high probability of stockout within 5 days.
Cause: demand surge combined with delayed inbound timing — not a shipping delay.
Options: reallocate existing stock by customer, emergency purchase, pull forward production.
```

**The Control Agent is:**
- The user-facing responder for **operational supply chain queries** (daily–weekly) — receives supply chain intents routed by SessionOrchestrator
- The final responder for operational judgment — the only agent that sends an operational supply chain conclusion to the user (in MVP and for daily–weekly queries in Post-MVP)
- The judgment integrator — holds cross-domain context throughout the interaction

> In Post-MVP, SessionOrchestrator routes planning-horizon queries to the S&OP Agent, which becomes the user-facing responder for those queries. Both agents are user-facing, separated by time horizon. See `§ Agent Design § S&OP Agent`.

**Sub-agents are:**
- Investigation units — gather domain-specific data
- Calculation modules — run domain-specific logic
- Specialist analysts — surface domain-scoped observations

Sub-agents do not speak directly to the user. Routing all responses through the Control Agent is the safe default even for single-domain queries. Override is permitted in Post-MVP only for: Evaluator Agent performing independent scoring — the exception is that scoring must run without seeing the producing agent's stated confidence; the Evaluator still returns scores to the Control Agent, not to the user; S&OP Agent invoking Cross-Domain Agents directly for functional sub-analysis.

**Scaling principle:** Adding agents never changes who owns the conclusion. Scaling means distributing investigation and computation — not distributing accountability for judgment.

```text
Integrated judgment = centralized
Investigation, calculation, analysis = distributed
```

### Screen First, Investigate Exceptions

**The agent does not process all data. The data layer screens all data.**

Supply chains with thousands of SKUs cannot be investigated exhaustively by an agent. The data layer (SQL, Python, ML, rules) monitors all items and extracts only the high-risk, high-impact exceptions that warrant investigation. The Control Agent then investigates, diagnoses, and explains those exceptions.

**Role of each layer:**

```text
Database / SQL:   reduce  — filter, aggregate, rank, extract Top N
DataFrame:        analyze — time series, anomaly detection, contribution decomposition
LLM / Agent:      interpret — investigate causes, synthesize context, explain decisions
```

An agent that processes raw bulk data is not scalable and is not the right tool. An agent that investigates pre-screened exceptions is both scalable and high-value.

The Screening Layer implementation (pipeline, scheduling, storage) is defined in `## Context Engineering Layer § Screening Layer`.

### The Agent is an Investigation Orchestrator, Not a Data Processor

The Control Agent is not an analysis engine. It is an **investigation orchestrator + meaning layer**.

```text
User question
 ↓
Plan investigation (which tools, in what order, why)
 ↓
Call tools → observe intermediate results
 ↓
Re-plan if evidence changes direction
 ↓
Call additional tools
 ↓
Synthesize: integrate facts, identify causes, explain priorities, present options
```

**Investigation loop:**

```text
Plan → Tool Use → Observe → Re-plan → Tool Use → Synthesize
```

This loop is the agent's core execution pattern. The agent's value is not in running calculations — it is in deciding which calculations to run, interpreting results, and connecting evidence into a business-meaningful answer.

The agent must also know when to stop. If required data is unavailable, rules are missing, or uncertainty is too high, the agent surfaces what is missing rather than producing an ungrounded conclusion. Stopping conditions (max tool calls per loop, confidence threshold, evidence completeness criteria) are defined in `docs/SPEC.md`.

---

## Core Capabilities

The system receives business questions from users and generates decision-ready answers by combining the necessary data, business rules, KPI definitions, historical decisions, and analytical logic.

This system does not replace human judgment entirely.
It organizes operational data and analytical results to help humans make better decisions.

### Target Questions and Agent Capabilities

The top-10 operational questions this system answers, agent capability boundaries, known limitations, and MVP priorities are defined in `docs/SPEC.md`.

### Operational Cadence

Not all monitoring and analysis runs at the same frequency. The system is designed around four operational cadences:

| Cadence | Scope | Examples |
| --- | --- | --- |
| Real-time / hourly | Urgent alerts, threshold breaches | Critical stockout, emergency shipment |
| Daily | Exception monitoring, anomaly detection | Stockout risk Top N, inventory anomalies, PO delays, demand deviations |
| Weekly | Planning review, replenishment | Demand plan review, replenishment recommendations, production schedule check |
| Monthly | S&OP, strategic planning | Demand-supply balance, scenario comparison, management decisions |

**MVP targets the daily cadence**: exception detection (stockout risk, inventory anomalies, PO delays, demand deviations) — the highest-frequency, highest-value operational use case. The screening layer runs on the daily cadence; the Control Agent investigates the top exceptions it surfaces.

---

## Architecture Overview

The system has six logical layers. The Context Engineering Layer is the key differentiator: it separates the LLM from raw data and ensures the agent receives only what it needs, when it needs it.

**Logical layers:**

1. User Interface Layer
2. Orchestration Layer
3. Agent Layer
4. Context Engineering Layer (Screening + Memory + Skill + Tool Gateway + Specialist Runtime + Working Context)
5. Guardrail Layer
6. External Systems Layer

**Request flow view** (how a user question moves through the system):

```text
User / UI
 ↓
API Gateway
 ↓
Agent Runtime (SessionOrchestrator + LangGraph)         [Orchestration Layer]
 ↓
Supply Chain Control Agent  (investigation orchestrator) [Agent Layer]
 │  Investigation loop: Plan → Tool Use → Observe → Re-plan → Synthesize
 ↓
Guardrail Layer  ──────────────────────────────────────  (cross-cutting)
 ↓
Context Engineering Layer
 ├─ Screening Layer        ← SQL/Python/ML: all items → Top N exceptions
 ├─ Memory Retriever       ← past decisions, business rules, exceptions
 ├─ Skill Loader           ← standard analysis procedures
 ├─ Tool Gateway           ← authorized, logged, rate-limited tool access
 ├─ Specialist Agent Runtime  ← domain-scoped analysis (Post-MVP)
 └─ Working Context Store  ← Context Packs, intermediate results, artifacts
 ↓
Data / Systems Layer                                    [External Systems Layer]
 ├─ Lakehouse / DWH
 ├─ ERP / Planning System
 ├─ Forecast Engine
 └─ External APIs
```

**User Interface Layer** handles user interaction, input, output, confirmations, and approvals.

**Orchestration Layer** is responsible for understanding user requests, intent classification, planning, routing, state management, result aggregation, and assembling the final `SessionResponse`. It does not own supply chain business conclusions — those belong to the Agent Layer.

**Agent Layer** is composed of the Supply Chain Control Agent, Specialist Domain Agents (one domain each), and Cross-Domain Agents (functional, not domain-bound).

**Context Engineering Layer** is the infrastructure that ensures the LLM receives relevant, scoped context on demand — not everything pre-loaded. Covers Screening Layer, Memory retrieval, Skill loading, Tool Gateway, Specialist Agent Runtime, and Working Context Store. Detailed in `## Context Engineering Layer` below.

**Guardrail Layer** is responsible for permissions, approvals, safety, auditing, and risk control. It is cross-cutting — it applies at the Tool Gateway, Action Tools, and any external-write path, not as a sequential layer below the Agent Layer.

**External Systems Layer** handles integration with databases, operational systems, documents, notification targets, and ticket systems.

Beyond routing, the system handles: conflict and risk detection when specialist results diverge; re-analysis or confirmation requests when confidence is low or information is missing; and persisting decision history and key assumptions to Decision Memory for future retrieval. Re-evaluation, condition changes, and scenario comparison are first-class operations — the system is designed for iterative analysis, not one-shot answers.

---

## Context Engineering Layer

The Context Engineering Layer is what separates a context-engineered business OS from a prompt-stuffed chatbot. The LLM does not receive everything in every call. Instead, the layer retrieves only what is relevant to the current question and injects it on demand.

```text
LLM   = judgment, language, integration
DB    = memory
Skill Registry = standard procedures
Tools = execution
Specialist Agents = domain analysis
Working Context = current session state
```

### Screening Layer

Before the Control Agent begins investigation, the Screening Layer reduces the full operational dataset to a manageable, high-signal exception set. The agent never processes raw bulk data.

**Screening pipeline:**

```text
All SKUs / orders / shipments (thousands of rows)
 ↓
SQL queries — filter by risk thresholds, date windows, status codes
 ↓
DataFrame analysis — time series deviations, anomaly scores, contribution rank
 ↓
Rule engine — apply business rules (safety stock thresholds, lead time windows)
 ↓
Top N exceptions with risk scores and key metrics
 ↓
Control Agent investigation
```

**Screening runs on the operational cadence** (daily for MVP) as a scheduled job; the Control Agent consumes its output on demand during investigation. The Screening Layer writes its results to the Working Context Store as pre-computed artifacts that the agent can reference without re-running the full scan.

**Scope: exception detection mode only.** Screening is not invoked on-demand during ad-hoc user queries (e.g., "why did sales of SKU A drop last week?"). For ad-hoc investigation, the Control Agent calls data access tools directly, following the investigation loop (Plan → Tool Use → Observe → Re-plan → Synthesize). The Screening Layer exists to surface what the human should look at *today* — not to gate all investigation.

**Monorepo placement:** Screening tools live in `packages/tools/` alongside other domain query tools and are invoked through the Tool Gateway. The scheduled daily job that runs screening is a Celery task; its trigger lives in `apps/api/` (or a dedicated worker), but its logic resides in `packages/tools/`.

### Memory Retriever

Stores and retrieves past decisions, business rules, exception history, user feedback, and planning assumptions. The LLM never holds memory in its context window — it queries on demand.

**Storage:**

```text
PostgreSQL
  - decision_log         (past decisions, outcomes, rationale, failure records — distinguished by record_type)
  - business_rule        (company-specific rules and thresholds)
  - exception_history    (SKUs / customers with special handling)
  - user_feedback        (corrections, confirmations)
  - planning_assumption  (current period assumptions)

pgvector
  - past case similarity search
  - business memo search
  - S&OP meeting note search
```

**Retrieval pattern:**

```text
User question
 ↓
Memory Retriever (vector similarity + filter)
 ↓
Relevant rules / past cases only (k=3–5)
 ↓
Control Agent context block
```

Memory is never pre-loaded in full. The retriever selects what is relevant to the current question.

**Persistence → Typed Store mapping:**

| Persistence location | Content | Typed Store |
|---|---|---|
| `decision_log` | Past decisions, outcomes, failure records | `DecisionMemory` |
| `business_rule`, `exception_history`, `planning_assumption` | Business rules, exceptions, assumptions | `DomainMemory` |
| `user_feedback` | User corrections and confirmations | `UserMemory` |
| `agent_session`, `task_run`, `tool_result`, `intermediate_artifact`, `approval_state` | Session and task state | `WorkingMemory` |
| pgvector: past case embeddings | Similarity search over past decisions | `DecisionMemory` |
| pgvector: business memos, S&OP notes | Semantic search over domain knowledge | `DomainMemory` |

Short-term Memory (conversation buffer) is held in LangGraph in-memory state within the session — it is not persisted to PostgreSQL.

### Skill Loader

Stores reusable standard analysis procedures so they do not need to be re-explained in every prompt. A Skill is the single source of truth for how a specific analysis should be conducted.

**Storage:**

```text
packages/knowledge/skills/  (markdown files; authoritative source)
  - skill_name
  - description
  - required_tables
  - required_kpis
  - procedure (step-by-step)
  - output_schema
```

**Example skills:**

```text
shortage_risk_analysis.md
excess_inventory_analysis.md
shipment_delay_root_cause.md
forecast_variance_decomposition.md
margin_impact_analysis.md
```

**Loading pattern:**

```text
Question: "Which products are at risk of stockout next week?"
 ↓
Skill Loader: matches → shortage_risk_analysis
 ↓
Required data: inventory + demand forecast + open orders + inbound supply
 ↓
Control Agent receives: procedure + required data list
```

Skills define **what to do**, not the LLM reasoning. This keeps analysis reproducible and auditable.

**Matching mechanism (MVP):** Keyword-based or explicit intent-to-skill mapping maintained in the Skill Loader. Vector similarity matching is Post-MVP. In MVP, the intent classification output from SessionOrchestrator determines which skill(s) to load; the mapping is declared in code, not inferred dynamically.

### Tool Gateway

All agent tool calls pass through the Tool Gateway before reaching data systems. Agents do not call data systems directly.

**Responsibilities:**

```text
Tool Gateway
  - permission check     (role × tool × data scope)
  - SQL validation       (read-only, allowlisted tables, no dangerous ops)
  - execution log        (who called what, when, with what args)
  - cost limit           (max rows, max query cost)
  - timeout enforcement
  - audit trail
```

**API surface (internal):**

```text
Domain query tools (structured, parameterized — primary interface):
  query_sales / query_inventory / query_purchase_orders / ...

Specialized analysis tools (high-value, reused):
  analyze_stockout_risk / analyze_sales_decline / detect_shipment_delay / ...

Low-level tools:
  nl_query_tool            ← text-to-SQL; schema-aware SQL generation
  dataframe_analysis_tool
  kpi_calculation_tool
  alert_detection_tool
  report_tool
  forecast_tool            (Post-MVP)
  optimization_tool        (Post-MVP)
```

The canonical tool design pattern — generic domain query tools over table-level tools, specialized analysis tools for high-value recurring analyses — is defined in `§ Tool Design § Tool Design Philosophy`. The full tool list with arguments, return schemas, and access control is in `docs/TOOLS.md`.

Without a Tool Gateway, agents can issue dangerous SQL, run expensive queries repeatedly, or bypass access controls silently. The Gateway is where those risks are contained.

### Specialist Agent Runtime

The infrastructure that makes domain-scoped specialist analysis available to the Control Agent. Its form depends on the maturity level of each domain.

**In MVP (Level 2 — Skill files):** Specialists exist only as Skill files in `packages/knowledge/skills/`. The Control Agent loads the relevant Skill via the Skill Loader and executes the analysis procedure itself. No sub-process, no separate runtime, no message passing.

**Promotion to Level 3 (Post-MVP — Independent Runtime):** A specialist is extracted to an independent subprocess only when the Control Agent's internal handling of that domain creates depth, token, or reasoning limits that measurably degrade answer quality. At Level 3:

- Each specialist receives a scoped task and returns structured analysis — not a final answer.
- Input per specialist: user question (scoped), assigned task, relevant context from Memory Retriever + Skill Loader, allowed tools (domain-scoped subset of Tool Gateway).
- Output schema: see `§ Agent Classification → Specialist Domain Agents` for the canonical output structure (observations, anomalies, root cause candidates, impact scope, confidence level, evidence, recommended next checks). Free-form prose responses from Level 3 specialists are not acceptable.

### Working Context Store

Holds intermediate state for the current analysis session. Large data objects are stored as artifacts; the LLM receives a summary and reference ID — not the raw data.

**Storage:**

```text
PostgreSQL
  - agent_session       (session state, goal, status)
  - task_run            (per-specialist task + result)
  - tool_result         (raw tool output, linked to task_run)
  - intermediate_artifact (file reference + schema + summary)
  - approval_state      (HITL approval records)

Object Storage (blob / S3 / ADLS)
  - CSV, Parquet outputs
  - Generated charts
  - Report files
```

**Artifact pattern / Context Pack:**

```text
Tool returns 50,000 row DataFrame
 ↓
Stored as artifact_id = "artifact_abc123"
 ↓
LLM receives a Context Pack:
  - summary: "8,412 SKUs with days-on-hand < 7"
  - schema: {sku_id, days_on_hand, risk_level, ...}
  - key_metrics: {at_risk_count: 8412, critical_count: 234}
  - missing_data: []
  - artifact_id: "artifact_abc123"
```

A **Context Pack** is the compressed, context-rich representation the agent actually receives — not raw rows, but summarized facts with schema, key metrics, and a `missing_data` field that surfaces data gaps explicitly. The agent reasons over Context Packs, not over raw query results.

This pattern prevents context window overflow and keeps LLM reasoning stable regardless of result set size. It also makes uncertainty explicit: a Context Pack with a non-empty `missing_data` field tells the agent to surface what is unknown rather than fabricate a conclusion.

The Working Context Store is the implementation of **Working Memory** (see `## Memory Design`). The two names refer to the same layer — "Working Context Store" describes the storage schema; "Working Memory" describes the typed store class that agents access through the Memory Layer API.

### LangGraph as the Agent Runtime

LangGraph is the execution control engine for the Agent Runtime layer. It is not the entire business OS — it manages the flow, not the storage or business logic. See `docs/DECISIONS.md` for the adoption rationale.

**What LangGraph manages in this system:**

```text
1. Control Agent state across steps
2. Specialist Agent invocation order and parallelism (Post-MVP; in MVP, Specialists exist as Skill files only)
3. Tool execution flow
4. Human Approval interrupts and resume
5. Checkpoint and session recovery
6. Intermediate result accumulation in Working Context
7. Final answer synthesis flow
```

**What requires components outside LangGraph:**

```text
Long-term Memory DB    → PostgreSQL + pgvector
Skill Registry         → packages/knowledge/skills/ (authoritative; DB-backed registry is Post-MVP)
Tool Gateway           → packages/tools/ with permission + audit layer
Artifact storage       → Object storage (S3 / ADLS / local blob)
Queue / Worker         → Celery (already in use for simulation/optimization jobs)
Frontend UI            → Next.js
Monitoring             → External
```

The accurate framing is:

> LangGraph = agent execution control engine.
> Surrounding components = the infrastructure that makes the business agent scalable.

### Constraints

- Memory MUST be retrieved on demand, not pre-loaded into every prompt.
- Skills MUST be the single source of truth for analysis procedures — not duplicated in system prompts.
- All tool calls MUST pass through the Tool Gateway; agents MUST NOT call data systems directly.
- Tools MUST return results as **Context Packs** (`summary`, `schema`, `key_metrics`, `missing_data`, `artifact_id`); raw query results MUST NOT be returned directly to the calling agent. Large underlying data is stored as blob artifacts and referenced via `artifact_id` inside the Context Pack.
- When a Context Pack's `missing_data` field is non-empty, the agent MUST surface the data gap explicitly in its response rather than fill it with assumptions or fabricate a conclusion.
- At Level 3 (independent runtime), Specialist Agent outputs MUST conform to the structured output schema defined in `§ Agent Classification → Specialist Domain Agents` — free-form prose is not acceptable.

---

## Orchestration Design

The center of this system is the SessionOrchestrator.

The SessionOrchestrator receives `SessionUserQuery` utterances within a user session, distinguishes between chat, question answering, exploration, consultation, and explicit goal-directed tasks, and when needed generates a `SessionGoal`, creates a plan, routes work to agents, controls execution, integrates results, and synthesizes the final `SessionResponse`.

`SessionGoal` is generated only when the user's input implies a clear analytical or decision objective (e.g., "which SKUs are at stockout risk this week?", "find the root cause of shipment delays for customer X"). Conversational exchanges, simple factual lookups, and clarification requests are handled as Chat / QA without generating a `SessionGoal`.

**Draft routing criteria (to be hardened in implementation):** A `SessionGoal` is generated when the query meets any of the following: (1) spans or requires data from two or more domains, (2) requires a quantitative calculation or threshold comparison, (3) asks for a priority list or ranked recommendation, or (4) implies a decision or action to be taken. A query answerable from a single known value (e.g., "what is the current stock level for SKU A?") is handled as Chat / QA. These criteria are the authoritative boundary definition until superseded by an ADR.

In MVP and early configurations, Planner, Router, State Manager, and Aggregator are not separated into independent agents.
These are treated as internal responsibilities of the SessionOrchestrator.

The SessionOrchestrator is responsible for:

- Intent Classification
- Chat / QA Handling
- Goal Resolution
- Intent Analysis
- Routing Plan (session-level: which agent, what task, what order)
- Routing
- Execution Control
- State Management
- Result Aggregation
- Conflict Detection
- Routing Confidence Scoring
- SessionResponse Assembly

The SessionOrchestrator does not execute all specialized processing itself.
Specialized analysis and business judgment are delegated to Specialist Domain Agents or Cross-Domain Agents.

For queries outside the system's known domains (e.g., HR, legal, general knowledge), the SessionOrchestrator responds directly as Chat / QA Handling — it does not route to a specialized agent.

In the MVP phase, the Supply Chain Control Agent fulfills the Specialist Domain Agent layer — it is the single agent to which the SessionOrchestrator delegates supply chain queries. Specialist domain agents are added as distinct routing targets later.

When results from multiple agents conflict, the SessionOrchestrator detects the conflict and, if necessary, requests additional confirmation, re-analysis, or escalation to a human.

### Constraints

- Orchestrator MAY route, plan, aggregate results, detect conflicts, score routing confidence, and assemble `SessionResponse` envelopes.
- Orchestrator MUST receive user-facing work as `SessionUserQuery` and return `SessionResponse`; `SessionGoal` is internal and only used when a clear decision or analytical goal exists.
- Orchestrator MUST delegate specialized domain analysis to Specialist Domain Agents or Cross-Domain Agents.
- Orchestrator MUST NOT synthesize supply chain business conclusions; the Control Agent is the sole owner of cross-domain business judgment. (Exception: off-domain queries such as HR or legal are handled directly by the Orchestrator as Chat / QA — see `## Orchestration Design`.)
- Orchestrator MUST NOT own domain-specific calculations, supply chain thresholds, or business rules.
- Orchestrator MUST NOT call the database directly; data access goes through Tools.
- Orchestrator MUST NOT call the LLM provider SDK directly; all LLM calls go through `packages/agent/llm/`.

---

## Agent Classification

The agents in this system are classified into five types.

```text
SessionOrchestrator          ← session routing and synthesis
Supply Chain Control Agent   ← operational cross-domain judgment, user-facing responder (daily–weekly)
S&OP Agent                   ← planning-horizon judgment, user-facing responder (monthly and beyond; Post-MVP)
Specialist Domain Agents     ← one domain each, deep analysis (Level 2: Skill files; Level 3: runtime)
Cross-Domain Agents          ← functional analysis capabilities, not domain-bound
Tools                        ← calculation, query, detection
```

### SessionOrchestrator

The central session-level orchestrator. See `## Orchestration Design` for the full responsibility list and constraints.

### Supply Chain Control Agent

The **investigation orchestrator and cross-domain judgment center**. The Control Agent drives the full investigation loop (Plan → Tool Use → Observe → Re-plan → Synthesize), holds cross-domain context across steps, integrates domain-scoped results from Specialist Agents and Cross-Domain Agents, and produces the final answer for every operational supply chain query.

Its two inseparable roles:

- **Investigation orchestrator**: decides which tools to call, in what order, interprets intermediate results, re-plans when evidence shifts
- **Judgment center**: integrates all findings into a cross-domain conclusion the user can act on

See `## Design Principles § Most Important Design Principle` for the judgment-integration rule, and `## Design Principles § The Agent is an Investigation Orchestrator` for the investigation loop.

### Specialist Domain Agents

Each agent has a **primary domain** and provides analysis from that domain's perspective. To do so accurately, it also reads related domains — but it does not produce cross-domain conclusions.

```text
Specialist Agent = primary domain owner + related domain awareness (for analysis context)
```

| Agent | Primary domain | Related domains read for context |
| --- | --- | --- |
| Demand Agent | Demand | Inventory, sales, customer, pricing, stockout |
| Inventory Agent | Inventory | Demand, orders, inbound, production, shipments |
| Replenishment Agent | Replenishment | Inventory, demand, supply, lead time, location |
| Production Agent | Production | Demand, inventory, materials, capacity, lead time |
| Procurement Agent | Procurement | Inventory, demand, production, lead time |
| Logistics Agent | Shipment / delivery | Orders, inventory, customer, deadline |
| Finance Agent | Revenue / profit | Sales, inventory, cost, stockout impact |

**The primary role of a Specialist Agent is to prepare structured analysis materials that the Control Agent can use to form a business judgment.** It is a specialist analyst, not a final decision-maker.

The five responsibilities of a Specialist Agent:

1. **Read primary domain state** — inventory levels, demand trends, production capacity, etc.
2. **Reference related domains for context** — read surrounding data needed to interpret the primary domain accurately.
3. **Detect anomalies, risks, and changes** — demand surge, inventory drop, inbound delay, shipment stall, margin deterioration, forecast error widening.
4. **Surface root cause candidates** — hypotheses from the primary domain's perspective, not final conclusions.
5. **Return structured output to the Control Agent** — containing:
   - Observed facts
   - Anomalies / risks detected
   - Root cause candidates
   - Impact scope
   - Confidence level
   - Additional data worth examining
   - Candidate actions (domain-scoped)

A Specialist Agent outputs: *"From my primary domain's perspective, here is what I see."*
The Control Agent takes those outputs and produces: *"Integrating all perspectives, here is the business conclusion."*

The core principle: **route investigation to Specialists, route judgment to the Control Agent.** See `docs/DECISIONS.md` for the rationale (context window, responsibility separation, reuse, parallelism).

In MVP, Specialist Agents exist as **Skill files only (Level 2)** — no runtime units. The Control Agent exercises all specialist capabilities internally via the Skill Loader. Independent runtimes are introduced only when domain complexity demands it. See `§ Agent Design § Domain Capability Maturity Model` for the full promotion criteria.

Agents that are purely cross-domain in nature (e.g., Shortage Risk Agent, Demand-Supply Balance Agent) must not be created as Specialist Agents — cross-domain final judgment is the Control Agent's exclusive responsibility.

### Cross-Domain Agents

Functional specialists that provide reusable analytical capabilities across any domain. Unlike Specialist Domain Agents, they are not bound to one business domain; unlike the Control Agent, they do not own cross-domain judgment.

| Cross-Domain Agent | Function |
| --- | --- |
| Anomaly Detector Agent | Detect anomalies, rule violations, abnormal patterns, and surface root cause candidates |
| Simulation Optimizer Agent | Build and compare scenarios, run Monte Carlo and inventory trajectory simulations |
| Evaluator Agent | Score candidate plans against KPIs independently |
| Data Engineer Agent | Gather and normalize operational facts needed by other agents |

Cross-Domain Agents return results to the Control Agent, which integrates them into the final answer.

---

## Agent Design

### Integrated Agent First (MVP Principle)

See **Design Principles § Most Important Design Principle** for the canonical statement of the judgment-integration rule.

**MVP purpose:** Validate that the Supply Chain Control Agent can retrieve data, detect anomalies, identify root cause candidates, prioritize exceptions, and return decision-ready answers — before adding any structural complexity.

**MVP = validate integrated judgment. Post-MVP = validate that distributed processing preserves integrated judgment at scale.**

#### MVP Scope

| Area | MVP treatment | Out of scope (Post-MVP) |
| --- | --- | --- |
| SessionOrchestrator | Thin router — no complex planning or synthesis | Complex multi-step planning, synthesis |
| Supply Chain Control Agent | Core — owns all operational + planning judgment and user-facing answers | — |
| Specialist Domain Agents | **Not runtime units** — Skill files only (Level 2), loaded on demand by Control Agent | Independent runtimes |
| Cross-Domain Agents | **Not runtime units** — implemented as tools or Skill files | Independent runtimes |
| S&OP Agent | **Planning mode of Control Agent** — not a separate runtime | Separate S&OP Agent runtime |
| Tools | SQL, DataFrame, KPI Calculation, Alert / Exception Detection | Forecast, optimization tools |
| Memory | Minimal: Decision Memory, Domain Memory, Working Memory | Full typed-store physical separation |
| Skills | Markdown procedure files (no registry infrastructure yet) | DB-backed skill registry |
| Guardrail | SQL read guardrail, external write blocked, minimal audit log | Full permission matrix, escalation paths |
| HITL | Designed but not wired; implement only if a high-risk action path exists in MVP | Full approval workflow |
| Scenario comparison | — | Out of scope |
| Cross-horizon queries | Control Agent handles all (no S&OP Agent runtime) | S&OP Agent peer routing |
| Automated external writes | — | Out of scope (order proposals, notifications) |

#### MVP Validation Questions

The three questions the MVP must answer to prove value:

```text
1. What exceptions does the human need to see today?
2. Which products have high stockout risk?
3. What are the root cause candidates for shipment delays and unfulfilled orders?
```

These are selected because they are used daily, easy to evaluate for correctness, and directly demonstrate the Control Agent's cross-domain judgment capability.

#### Agent Hierarchy (MVP → Target)

> **Note on naming:** "Tier" numbers below describe the agent's position in the routing hierarchy. They are separate from the "Level" numbers in the Domain Capability Maturity Model (Level 1–4), which describe a domain's implementation maturity.

```text
Tier 0: S&OP Agent                       ← planning judgment (Post-MVP peer of Control Agent)
Tier 1: Supply Chain Control Agent       ← operational judgment + planning mode in MVP
Tier 2: Specialist Domain Agents         ← Skill files in MVP; independent runtimes Post-MVP
         Cross-Domain Agents             ← tools/Skill files in MVP; independent runtimes Post-MVP
Tier 3: Tools (SQL / DataFrame / Forecast / Optimization)
```

Time horizon and focus per agent are defined in `§ Agent Design § S&OP Agent`.

Recommended MVP tool set (no sub-agents required at this stage):

```text
Supply Chain Control Agent
  + SQL Tool
  + DataFrame Analysis Tool
  + KPI Calculation Tool
  + Alert / Exception Detection Tool
```

See `docs/adr/2026-06-05-integrated-control-agent-first.md` for the full decision record.

### Post-MVP Expansion

After MVP validates integrated judgment, the system expands by progressively separating runtime boundaries — without changing the judgment ownership rules.

**Post-MVP structure:**

```text
User
 ↓
SessionOrchestrator  (intent classification, routing, session management)
 ├─ Supply Chain Control Agent  (daily–weekly operational judgment)  → User
 │       ↑ delegates operational data gathering (cross-horizon queries only)
 └─ S&OP Agent                  (monthly and beyond planning judgment) → User
      ↓                              ↓
      Specialist Domain Agents / Cross-Domain Agents
      ↓
      Tools / Simulation / Optimization
      ↓
      Memory / Skills / Guardrail / Working Context
```

The S&OP Agent → Control Agent delegation is one-directional and scoped: the S&OP Agent may request operational data gathering from the Control Agent for cross-horizon queries only. The Control Agent does not become a sub-agent of the S&OP Agent for any other purpose — it remains a peer, both reporting to SessionOrchestrator as user-facing responders for their respective horizons.

#### Phase 1 — Specialist Agent separation

Extract Specialist Domain Agents as independent runtimes in this order (most direct connection to stockout/delay/excess value):

```text
1. Inventory Agent
2. Demand Agent
3. Logistics Agent
4. Procurement Agent
5. Production Agent
6. Finance Agent
```

Each agent is extracted only when the Control Agent's internal handling of that domain creates depth, token, or reasoning limits that degrade answer quality.

#### Phase 2 — Cross-Domain Agent separation

Extract Cross-Domain Agents when reuse across Specialist Agents justifies a dedicated runtime:

```text
1. Anomaly Detector Agent
2. Evaluator Agent
3. Simulation Optimizer Agent
4. Data Engineer Agent
```

**Constraint that does not change in Post-MVP:** Cross-Domain Agents return analytical outputs (anomaly lists, scenario scores, simulation results); they do not return final recommendations. The Control Agent integrates and concludes.

#### Phase 3 — S&OP Agent

Extract S&OP Agent as an independent peer of the Control Agent after the operational layer (Phase 1 + 2) is stable. See `§ Agent Design § S&OP Agent` for the full design and extraction criteria.

### Domain Capability Maturity Model

A domain does not become a Specialist Agent immediately. Each domain progresses through four maturity levels. The trigger for promotion is **actual complexity demand**, not planned architecture.

| Level | Form | Use when |
| --- | --- | --- |
| **1 — Tool** | Deterministic function | Logic is fixed; no LLM reasoning required |
| **2 — Control Agent capability** | Domain analysis procedure defined as a **Skill file** (`packages/knowledge/skills/`), loaded on demand by the Control Agent | Analysis is needed but domain complexity is still manageable within a single context |
| **3 — Specialist Agent** | Independent domain agent | Domain-specific knowledge, procedures, and context have grown to the point where they degrade Control Agent reasoning quality |
| **4 — Multi-agent within a domain** | Multiple specialists inside one domain | The domain itself requires multiple distinct reasoning roles |

**Promotion criterion for Level 3:** Extract a Specialist Agent only when the Control Agent's internal handling of that domain creates depth, token, or reasoning limits that measurably degrade answer quality. Do not extract speculatively.

**Quantitative signals (any one triggers a promotion review):**
- That domain's share of the Control Agent context window consistently exceeds 30%
- Answer accuracy evaluated by the Evaluator Agent or human feedback falls below baseline −15% across three consecutive sessions
- The domain's Skill file requires more than 10 reasoning steps in a single analysis

**Example — Inventory domain progression:**

```text
Level 1: Inventory Tools
  - days_on_hand calculator
  - stockout risk calculator
  - excess inventory detector

Level 2: Inventory capability inside Control Agent
  - implemented as packages/knowledge/skills/inventory_analysis.md
  - Skill Loader injects the procedure into Control Agent context on demand
  - returns stockout / excess root cause candidates

Level 3: Inventory Agent (independent specialist)
  - references demand, inbound, production, shipments for context
  - returns structured inventory analysis to the Control Agent

Level 4: Inventory multi-agent workflow
  - Safety Stock Agent
  - Replenishment Agent
  - Inventory Policy Agent
  - Allocation Agent
```

**Cross-Domain Agents follow the same four levels, with a different Level 3 promotion criterion:**

| Level | Form (Cross-Domain) | Promotion criterion |
| --- | --- | --- |
| 1 | Deterministic detection / calculation tool | — |
| 2 | Cross-domain Skill file loaded by Control Agent | — |
| 3 | Independent Cross-Domain Agent runtime | The capability is needed across multiple Specialist Agent contexts, or its analytical complexity exceeds what a single Skill file can manage |
| 4 | Multi-agent within one cross-domain function | The function itself requires multiple specialized sub-agents |

The key difference: Specialist Agents are promoted when **one domain** becomes too complex for the Control Agent to handle internally. Cross-Domain Agents are promoted when **reuse across multiple domains** justifies a dedicated runtime.

**Invariant across all levels:**

```text
Final judgment         = Supply Chain Control Agent
Domain analysis        = Specialist Agents (Level 3+)
Cross-domain analysis  = Cross-Domain Agents (Level 3+)
Deterministic execution = Tools (Level 1)
```

Increasing the level of any agent never changes who owns the supply chain conclusion.

### Target Agent Design (Final State)

Full agent specifications (purpose, role, toolset, input, output, memory) are in `docs/SPEC.md § Agent Catalog`. This section summarizes responsibility boundaries only.

| Agent | Responsibility boundary | Maturity path |
| --- | --- | --- |
| SessionOrchestrator | Session routing, intent classification, SessionResponse assembly | Fixed; not domain-dependent |
| Supply Chain Control Agent | Operational cross-domain judgment (daily–weekly), user-facing responder | Core; always present |
| S&OP Agent | Planning-horizon judgment (monthly and beyond), user-facing responder | Post-MVP; extracted from Control Agent's planning mode |
| Demand Agent | Demand-scoped analysis materials | Maturity Level 2 → 3 |
| Inventory Agent | Inventory-scoped analysis materials | Maturity Level 2 → 3 |
| Replenishment Agent | Replenishment-scoped analysis materials | Maturity Level 2 → 3 |
| Procurement Agent | Procurement-scoped analysis materials | Maturity Level 2 → 3 |
| Production Agent | Production-scoped analysis materials | Maturity Level 2 → 3 |
| Logistics Agent | Logistics-scoped analysis materials | Maturity Level 2 → 3 |
| Finance Agent | Finance-scoped analysis materials | Maturity Level 2 → 3 |
| Data Engineer Agent | Operational fact retrieval across domains | Maturity Level 2 → 3 |
| Simulation Optimizer Agent | Scenario generation and comparison | Maturity Level 2 → 3 |
| Evaluator Agent | KPI-independent scoring of candidate plans | Maturity Level 2 → 3 |
| Anomaly Detector Agent | Cross-domain anomaly detection and root cause candidates | Maturity Level 2 → 3 |

### Domain Agent Constraints

- Domain Agents MAY read related-domain data through Tools to provide accurate analysis from their primary domain's perspective.
- Domain Agents MAY hold domain-specific business rules as reasoning input (not as executable code).
- Domain Agents MUST output analysis framed from their primary domain — not cross-domain conclusions.
- Domain Agents MUST NOT implement data access directly; all reads go through Tool Layer.
- Domain Agents MUST NOT produce user-facing final answers; they return domain-scoped analysis to the Control Agent.
- Domain Agents MUST NOT call the LLM provider SDK directly.

### Cross-Domain Agent Constraints

- Cross-Domain Agents MAY operate across domain boundaries by invoking Tools.
- Cross-Domain Agents MAY produce analytical outputs (anomaly lists, scenario scores, simulation results, normalized facts) but MUST NOT produce business conclusions, prioritized recommendations, or final answers — that is the Control Agent's exclusive responsibility. A Cross-Domain Agent that outputs "the recommended action is X" has overstepped its boundary.
- Cross-Domain Agents MUST NOT own domain-specific business rules; they consume domain data, not domain logic.
- Cross-Domain Agents MUST NOT route or aggregate in a way that duplicates Orchestrator or Control Agent responsibilities.
- Cross-Domain Agents MUST NOT produce user-facing responses; they return intermediate analytical results to the Control Agent.

### S&OP Agent (Post-MVP)

The S&OP Agent handles monthly and multi-cycle planning decisions that span demand, supply, inventory, and finance. The weekly S&OP review meeting is a cadence — the planning horizon starts at monthly and beyond.

**MVP treatment:** S&OP capability is a **planning mode of the Supply Chain Control Agent** — no separate runtime. The Control Agent handles both operational judgment (daily–weekly) and planning judgment (monthly and beyond) as integrated capabilities.

```text
MVP:
  Supply Chain Control Agent
    ├─ Operational mode   ← exceptions, stockout risk, shipment delays
    └─ Planning / S&OP mode ← scenario comparison, demand-supply balance
```

**Mode switching mechanism (MVP):** SessionOrchestrator detects planning-horizon intent via intent classification (monthly horizon keywords, scenario comparison, demand-supply balance) and passes `mode: "sop"` in the routed task payload. The Control Agent selects the corresponding Skill files (`packages/knowledge/skills/sop_*.md`) and a planning-mode system prompt variant based on this flag. No separate process, runtime, or API endpoint is required.

**Post-MVP:** Extract S&OP as an independent agent when planning complexity (scenario simulation, multi-period optimization, financial modeling) causes Control Agent context to degrade. At that point:

```text
Post-MVP:
  SessionOrchestrator
    ├─ Supply Chain Control Agent  ← operational judgment, daily–weekly
    └─ S&OP Agent                 ← planning judgment, monthly and beyond
```

The S&OP Agent becomes a **peer** of the Control Agent — both reporting directly to SessionOrchestrator, each owning final judgment over their respective time horizon. This follows the rule stated in `§ Design Principles § Most Important Design Principle`: the Control Agent owns operational conclusions; the S&OP Agent owns planning-horizon conclusions.

**Judgment scope by time horizon (Post-MVP target):**

| Agent | Judgment scope | Time horizon |
| --- | --- | --- |
| **Supply Chain Control Agent** | Operational cross-domain judgment — exceptions, stockout risk, shipment delays, action priorities | Daily – weekly |
| **S&OP Agent** | Planning-horizon cross-domain judgment — scenario comparison, demand-supply balance, production/purchase plan, revenue/profit impact | Monthly and beyond |

In MVP, the Control Agent handles queries spanning both horizons. In Post-MVP, the S&OP Agent owns the conclusion for cross-horizon queries; it delegates operational data gathering to the Control Agent.

**Responsibilities (target state):**
- Aggregate demand forecasts across planning horizons
- Compare supply capacity against demand plans
- Identify inventory build / drawdown implications by scenario
- Evaluate revenue and profit impact across scenarios
- Produce a ranked plan recommendation for S&OP review

**Relationship to other agents (Post-MVP):**
SessionOrchestrator routes planning-horizon queries to the S&OP Agent; operational (daily–weekly) queries go to the Control Agent. The S&OP Agent may invoke Cross-Domain Agents directly for functional sub-analysis (simulation, scenario comparison).

Full design to be defined in a dedicated ADR when Post-MVP development begins.

---

## Tool Design

Tools define the execution capabilities of agents.

Agents retrieve data, perform calculations, run analyses, and interact with external systems through Tools.
Data retrieval and calculation logic must not be embedded directly in agents.

The quality of an agent is determined by the quality of the tools it can use.

Tools are classified into the following categories:

| Category | Responsibility | Examples | MVP |
|---|---|---|---|
| Data Access Tools | Query operational tables, discover available data, inspect schemas, detect data quality issues | SQL queries, data catalog search, schema reader, data quality checker | ✓ |
| Knowledge Tools | Retrieve business documents, KPI definitions, and business rules | Business rules reader, metric definition reader, domain document search | ✓ |
| Calculation Tools | Perform numeric calculations, unit conversions, and statistical computations | Formula calculator, unit converter, statistical aggregator | ✓ |
| Analysis Tools | Trend analysis, variance analysis, root cause analysis, forecast analysis, anomaly detection | Trend analyzer, diff analyzer, root cause analyzer, forecast analyzer | ✓ |
| Optimization Tools | Constraint-based optimization, allocation optimization | LP/MIP solver, allocation optimizer | Post-MVP |
| Simulation Tools | Scenario building, Monte Carlo simulation, inventory trajectory simulation | Scenario builder, Monte Carlo runner, inventory simulator | Post-MVP |
| Communication Tools | Notifications, report generation, summarization for human consumption | Summary generator, report builder, notification dispatcher | Post-MVP |
| Action Tools | Generate order proposals, approval requests, ticket creation | Order proposal creator, approval requester, ticket creator | Post-MVP |
| Memory / Audit Tools | Decision history, assumption logging, audit trail | Audit log writer, decision history reader, assumption store | ✓ (minimal) |
| Guardrail Tools | Permission checks, approval workflows, risk assessment | Permission checker, approval gate, risk evaluator | ✓ (SQL read guardrail only) |

Tool specifications, arguments, return values, permissions, failure handling, access control, and MVP implementation priority are defined in `docs/TOOLS.md`.

In DESIGN.md, only the purpose and responsibility boundaries of tool categories are defined.

### Tool Design Philosophy

**Prefer generic domain query tools over table-level tools. Reserve specialized tools for high-value recurring analyses.**

Bad structure — one tool per data slice (causes tool explosion):

```text
get_sales_by_sku / get_sales_by_customer / get_sales_by_region / get_sales_by_month ...
```

Good structure — one generic tool per domain + named tools for important analyses:

```text
Generic domain query tools:
  query_sales(filters, group_by, metrics, time_range)
  query_inventory(filters, group_by, metrics, time_range)
  query_purchase_orders(filters, group_by, metrics, time_range)

Specialized analysis tools (high-value, reused):
  analyze_stockout_risk(sku, location, horizon)
  analyze_sales_decline(sku, period)
  detect_shipment_delay(filters, deadline_threshold)

Document / knowledge search:
  search_documents(query)
  get_business_rules(domain)
```

The `nl_query_tool` (text-to-SQL) is the primary data query interface — it accepts a natural-language question and internally generates schema-correct SQL via `get_schema_context()`. All structured bulk queries go through `nl_query` or domain-specific tools.

### Constraints

- Tools MAY execute data access, calculations, external API calls, simulations, and audit writes.
- Tools MUST expose a clear input/output schema conforming to the `Tool` base class in `packages/tools/base.py`.
- Tools MUST return a **domain-specific dict** conforming to their declared `output_schema` (see `docs/adr/2026-06-10-tool-output-contract-hybrid.md`). The former Context Pack 5-field mandate (`summary`, `schema`, `key_metrics`, `missing_data`, `artifact_id`) is superseded by this hybrid contract. Every DB-accessing tool MUST include `missing_data: list[str]` in its output: populated with short human-readable entries when required source data is absent (e.g. `"no cost_master row for SKU-123"`), and an empty list when all required data was found. Tools that return row arrays MUST cap row counts and include a `truncated: bool` flag; raw bulk rows MUST NOT be streamed unbounded into agent context.
- Tools MUST raise `RuntimeError` on missing configuration (API keys, DB connection); never silently degrade to a no-op or stub.
- Tools MUST NOT decide business strategy or routing; they are execution primitives, not decision-makers.
- Tools MUST NOT route requests between agents.
- Some tools invoke LLM reasoning internally (e.g., `NlQueryTool` for natural language → SQL conversion). These tools MUST use `LLMClient` and MUST NOT bypass it to call the provider SDK directly.
- Tools MUST NOT swallow execution errors silently. On failure (timeout, DB error, external API error) they MUST propagate a typed exception so the calling agent can decide between retry, skip, or HITL escalation.

---

## Memory Design

Memory is not simply conversation history.

In this system, Memory is the layer that retains the following:

- Conversation history
- Working state
- Intermediate results
- Decision history
- Domain knowledge
- KPI definitions
- Business rules
- User context
- Past decisions

Memory is classified as follows:

### Short-term Memory

Retains temporary information needed only during the current interaction, including conversation history. After session end, records become read-only and are retained for audit — they are not deleted.

### Working Memory

Retains intermediate state, in-progress calculations, and shared state between agents needed to complete the current task. Implemented as the **Working Context Store** in the Context Engineering Layer — see `## Context Engineering Layer § Working Context Store` for the storage schema (`agent_session`, `task_run`, `tool_result`, `intermediate_artifact`, `approval_state`).

### Long-term Memory

Retains knowledge and context to be reused in future decisions.

### Decision Memory

Retains decision rationale, alternatives, rejection reasons, preconditions, and past decisions.

### User Memory

Retains user goals, preferences, decision tendencies, and usage context.

### Domain Memory

Retains business rules, KPI definitions, domain knowledge, and historical cases.

Memory is used not only for response quality but also for accountability, reproducibility, and auditability.

### Logical Types and Physical Implementation

The six memory types above are **logical classifications** that define access semantics and agent-facing API. In MVP, they map to three physical implementation groups:

| Physical group | Logical types | Storage |
|---|---|---|
| Working storage | `ShortTermMemory`, `WorkingMemory` | LangGraph in-memory state (active session) + `agent_session`, `task_run`, `tool_result`, `intermediate_artifact`, `approval_state` tables (flushed at session end for audit retention) |
| Decision storage | `DecisionMemory`, `UserMemory` | `decision_log`, `user_feedback` tables + pgvector (past case embeddings) |
| Domain storage | `LongTermMemory`, `DomainMemory` | `business_rule`, `exception_history`, `planning_assumption` tables + pgvector (business memos, S&OP notes) |

The typed store API (`ShortTermMemory`, `WorkingMemory`, `LongTermMemory`, `DecisionMemory`, `UserMemory`, `DomainMemory`) is a public interface and does not change. The physical grouping above is an implementation detail that can evolve independently without changing the agent-facing API.

### Constraints

- Memory MUST be accessed through typed store classes: `ShortTermMemory`, `WorkingMemory`, `LongTermMemory`, `DecisionMemory`, `UserMemory`, `DomainMemory`.
- Agents MUST NOT pass raw dicts as "memory" between components; use the Memory Layer API.
- Agents MUST NOT read or write memory belonging to another agent's domain without going through the Memory Layer API.
- Memory MUST NOT be used solely as raw conversation history; it holds state, context, and decision records.

---

## Guardrail Design

The Guardrail Layer controls the scope of agent execution, safety, permissions, approvals, and auditing.

This system does not permit agents to freely execute external actions.
Important operations, high-impact proposals, writes to external systems, notifications, and approval requests all require explicit permissions and confirmations.

The Guardrail Layer is responsible for:

- Verifying user permissions
- Verifying data access permissions
- Controlling external actions
- Determining which processes require approval
- Detecting high-risk proposals
- Recording audit logs
- Retaining decision rationale
- Separating executable operations from proposal-only operations

When confidence is low or business risk is high, agents prioritize requesting human confirmation.

### Constraints

- All external actions (database writes with business impact, notifications, approval requests) MUST pass through Guardrail before execution.
- Guardrail logic MUST NOT be scattered as ad-hoc `if permission` or `if approval` checks inside Agent or Tool code.
- Guardrail MUST expose a stable API: `can_execute()`, `needs_approval()`, `audit_required()`.
- Agents MUST surface low-confidence or high-risk decisions to Guardrail; never silently degrade or self-approve.
- Approval rows in terminal states (`approved`, `rejected`, `needs_revision`, `expired`) MUST NOT be mutated by any layer.

#### SQL Read Guardrail

- `NlQueryTool` MUST validate SQL through `packages/tools/sql_guardrail.py:validate_read_sql()` before calling any persistence repository function.
- SQL read guardrail policy MUST stay in the Tool Layer. `packages/persistence/` executes validated queries and MUST NOT become the policy owner for table allowlisting or SQL safety.
- User- or LLM-provided SQL MUST be a single `SELECT` statement, reference at least one allowlisted table, and avoid non-read operations or dangerous database features.
- SQL guardrail tests MUST cover direct SQL, generated SQL, quoted identifiers, schema-qualified names, joins, comma joins, CTEs, subqueries, and `UNION` references.

### Human-in-the-Loop (HITL)

The system interrupts agent execution and requests human input when any of the following conditions are met:

- An Action Tool would write to an external system (order proposal, notification, ticket creation)
- Agent confidence falls below the threshold defined for the action type in Domain Memory
- Business risk (estimated impact) exceeds the auto-approval limit
- `Guardrail.needs_approval()` returns `true` for the proposed action

**Confidence level (MVP definition):** A float in `[0.0, 1.0]` set by the agent based on three signals: data completeness (required tables available and non-empty), rule coverage (Domain Memory contains a matching business rule), and cross-domain agreement (specialist results are consistent). The thresholds per action type are stored in Domain Memory; the calculation method is defined in `docs/GUARDRAILS.md`.

**HITL flow:**

```text
1. Agent reaches a decision point requiring approval
2. Guardrail creates an approval_state record (status: pending)
3. Agent execution pauses (LangGraph interrupt())
4. User sees: proposed action, rationale, data evidence, risk level
5. User approves / rejects / requests revision
6. Execution resumes with the recorded outcome
7. Decision is written to Decision Memory
```

**Constraints:**

- HITL interrupt points MUST be declared in the Guardrail Layer — not as ad-hoc checks inside agent or tool code.
- Agents MUST NOT self-approve high-risk actions regardless of confidence level.
- The UI MUST present enough evidence (data source, analysis step, confidence) for a human to make an informed decision.

Full approval workflow specification (thresholds, escalation paths, expiry rules) is defined in `docs/GUARDRAILS.md` (not yet authored).

---

## Response Design

Responses from this system are not simple explanatory text — they have a structure usable for decision-making.

Responses include the following as needed:

- Conclusion
- Decision rationale
- Supporting data
- Preconditions
- Risks
- Alternatives
- Priority
- Next items to review
- Points requiring human approval

However, not all elements need to be included in every response.
Response depth is adjusted based on the user's question, business risk, and required decision granularity.

---

## Quality Evaluation and Failure Learning

Product agent response quality must be evaluated continuously. The system needs mechanisms to detect poor responses, record failure patterns, and prevent recurrence — not just produce answers.

### Response Quality Dimensions

Each response can be evaluated against the following dimensions:

| Dimension | What it measures |
| --- | --- |
| Factual accuracy | Are the facts drawn from data correct? |
| Root cause validity | Does the identified cause match the evidence? |
| Completeness | Are all relevant domains considered? |
| Actionability | Are the recommended actions specific enough to act on? |
| Calibration | Does the stated confidence match the evidence strength? |
| Human judgment boundary | Are accountable decisions correctly escalated to humans? |

Evaluation can be performed by the Evaluator Agent (scoring candidate outputs) or by human feedback after a response is acted on.

### Trace Evaluation

Evaluating only the final response misses critical signals. The investigation trace — the sequence of steps the agent took — must also be evaluated. A correct final answer reached via a wrong investigation path is a latent failure.

**Evaluation targets per investigation:**

| Target | What it measures |
| --- | --- |
| Intent understanding | Did the agent correctly classify what the user was asking? |
| Tool selection | Were the right tools called for this question? |
| Tool input parameters | Were the tools called with correct, valid parameters? |
| Intermediate result interpretation | Did the agent correctly read tool outputs and update its investigation? |
| Context Pack quality | Was the data compressed appropriately — neither over-summarized nor left as raw rows? |
| Final answer | Does the conclusion follow from the evidence? |
| Uncertainty expression | Were data gaps, missing rules, or low-confidence conclusions surfaced explicitly rather than filled with assumptions? |

Trace evaluation catches reasoning failures that a correct final answer can mask (correct answer via wrong path). It also catches systematic tool misuse before it becomes a recurring failure pattern.

**Priority tiers for evaluation (P0 → P2):**

Start evaluation with P0 questions — the ones the system must always answer correctly. Examples: "Which SKUs have stockout risk this week?", "What caused the shipment delay for customer X?" Validate tool selection, parameter correctness, and conclusion validity for these before expanding to P1 and P2.

### Failure Pattern Recording

When a response is identified as poor — through human correction, downstream error, or evaluator scoring — the failure is recorded with:

- What was asked
- What the agent answered
- What was actually correct or needed
- Which agent or reasoning step produced the error
- Root cause category (data gap, rule gap, cross-domain miss, hallucination, over-confidence, etc.)

Failure records are stored in the `decision_log` table in Decision Memory (using `record_type = 'failure'`) and surfaced to the Anomaly Detector Agent for pattern detection.

### Recurrence Prevention

A recorded failure becomes a prevention mechanism when the same pattern appears more than once.

| Failure type | Prevention mechanism |
| --- | --- |
| Missing data signal | Add data source to relevant tool's access scope |
| Implicit business rule not captured | Encode rule in Domain Memory / Knowledge Tools |
| Cross-domain miss | Strengthen Control Agent's integration prompt or add analysis step |
| Systematic over-confidence | Add calibration check to Evaluator Agent |
| Wrong domain delegation | Tighten routing logic in SessionOrchestrator |

The goal is not just to fix individual errors — it is to raise the baseline quality of future responses by encoding lessons into the system's structure.

### Constraints

- Failure records MUST be stored in Decision Memory with enough context to identify the pattern, not just the symptom.
- Evaluator Agent MUST score responses independently — it must not be influenced by the producing agent's stated confidence.
- Human corrections MUST be treated as ground truth and recorded; they are the highest-quality signal available.
- Prevention mechanisms MUST be applied to the system (memory, tools, routing) — not just documented as warnings.

---

## Scope Management

This DESIGN.md defines the target design of the entire product but does not require all agents to be instantiated simultaneously.

Agent definitions in this document are **responsibility boundaries and output contracts**, not deployment units. A capability can be exercised internally by the Supply Chain Control Agent (as a Skill file at Level 2) before it is extracted as an independent runtime (Level 3). The agent classification remains stable; only the deployment boundary changes.

The progression rules for when to extract a runtime boundary are defined in `§ Agent Design § Domain Capability Maturity Model`. The MVP and Post-MVP scope are defined in `§ Agent Design § Integrated Agent First` and `§ Agent Design § Post-MVP Expansion`.

---

## Architecture Constraints — Cross-cutting

These apply everywhere, regardless of layer. When a code review or arch test cites an architecture violation, this section and the layer-specific Constraints subsections above are the authoritative source.

| Rule | Rationale |
|------|-----------|
| Only `packages/agent/llm/` may call the LLM provider SDK | Centralizes rate limiting, cost tracking, and failover |
| Only `packages/tools/` and `packages/persistence/` may hold SQLAlchemy models or execute queries | Prevents hidden data access paths |
| `data/sample/ground_truth/` MUST NOT be read by any agent or tool | Test-data isolation |
| Public interfaces (`LLMClient`, `Tool`, `JobRunner`, `MemoryStore`, `Orchestrator`, `Specialist`) MUST NOT change without an ADR | Preserves integration contracts |
| Orchestrator interface changes are governed by `docs/adr/2026-05-21-user-query-orchestrator-flow.md` | Records the accepted `SessionUserQuery` → `SessionResponse` flow |
| No smart stubs: stubs MUST conform to schema, not approximate real behavior | Prevents false-passing tests |
| No fail-silent fallbacks: missing config raises `RuntimeError` at the call site | Prevents silent degradation in production |

---

## Relationship to Other Documents

This DESIGN.md defines the declarative design of the entire product.

Details are separated into the following documents:

| Document | Exists | What it covers |
|---|---|---|
| DESIGN.md | ✓ | What structure to achieve it with (this document) |
| AGENTS.md | ✓ | Detailed responsibilities per coding agent |
| docs/TASKS.md | ✓ | What to implement; phase definitions |
| docs/DECISIONS.md | ✓ | Why those decisions were made |
| docs/TESTING.md | ✓ | How to verify |
| docs/TOOLS.md | ✓ | Tool specifications |
| docs/FRONTEND_DESIGN.md | ✓ | Web UI component architecture and conventions |
| docs/adr/ | ✓ | Architecture decision records |
| SPEC.md | ✓ | Product requirements: top-10 questions, agent capabilities and limitations, Agent Catalog (full agent specs) |
| docs/MEMORY.md | not yet | Memory store specifications |
| docs/GUARDRAILS.md | not yet | Permission, safety, approval, and audit specifications |

DESIGN.md does not absorb too much detail.
Frequently changing concrete specifications, implementation tasks, API details, table definitions, and code structure are managed in separate documents.

---

## Monorepo Layout

The canonical directory structure that all agents must treat as authoritative.
Adding new top-level packages outside this layout requires an ADR.

```
packages/
  agent/
    orchestrator/   ← SessionOrchestrator (intent classification, chat/QA, goal
                      resolution, planning, routing, execution control, aggregation)
    control/        ← Supply Chain Control Agent (investigation orchestrator,
                      cross-domain judgment, user-facing responder)
    domain/         ← Specialist Domain Agents (demand, inventory, replenishment,
                       procurement, production, logistics, finance) — in MVP, Skill
                       files only (Level 2); runtime classes live here Post-MVP
    cross_domain/   ← Cross-Domain Agents (data_engineer, simulation_optimizer,
                       evaluator, anomaly_detector) — Post-MVP; directory does not
                       exist yet (deleted in P65; re-created when promoted to Level 3)
    llm/            ← LLM client — only entry point to LLM provider SDK
    runner/         ← Celery job runner infrastructure
    base.py         ← Specialist base protocol (public interface)
  tools/            ← Tool Layer (all execution capabilities)
  memory/           ← Memory Layer (six typed stores)
  persistence/      ← DB session management and all repository classes
  knowledge/        ← Domain knowledge: KPI definitions, business rules
    skills/         ← Standard analysis procedures (Skill Registry; loaded on demand)
  simulation/       ← Simulation compute engine (used by simulation_tool.py)
  optimization/     ← Optimization compute engine (used by optimizer_tool.py)
  prediction/       ← Prediction compute engine (used by forecast_tool.py)
  schemas/          ← Pydantic schemas shared across Python packages
  lakehouse/        ← Bronze / Silver / Gold data lake layers
apps/
  api/              ← FastAPI application (entry point)
  web/              ← Next.js frontend (entry point)
  simulation-worker/    ← Celery worker for simulation jobs
  optimization-worker/  ← Celery worker for optimization jobs
```

---

## Public Interfaces

The following interfaces may not change signature without an ADR filed in `docs/adr/`.
An interface change that is not backed by an ADR will be rejected at code review.

| Interface | Location |
|---|---|
| `LLMClient` | `packages/agent/llm/` |
| `Tool` (base class) | `packages/tools/base.py` |
| `JobRunner` | `packages/agent/runner/` |
| `MemoryStore` (the six typed classes) | `packages/memory/` |
| `Orchestrator` protocol | `packages/agent/orchestrator/` |
| `SessionOrchestrator` | `packages/agent/orchestrator/` |
| `SessionUserQuery`, `SessionIntent`, `AgentRoute`, `SessionResponse` | `packages/agent/orchestrator/` |
| `Specialist` (base protocol) | `packages/agent/base.py` |

